import logging
import math
import statistics
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from scipy.stats import norm

from aegis.calibration import load_cluster_calibration
from aegis.collector import PrometheusCollector, format_value
from aegis.config import load_config
from aegis.kube import load_kubernetes_credentials

logger = logging.getLogger(__name__)

MIN_REPLICAS_FOR_CAPACITY = 1


# Phi((projection - capacity) / sigma): probability that traffic exceeds capacity.
def risk_probability(projected_rps, capacity_rps, sigma_rps):
    return float(norm.cdf((projected_rps - capacity_rps) / sigma_rps))


@dataclass(frozen=True)
class RiskResult:
    timestamp: float
    rps: float                 # r: current traffic
    slope: float               # m: req/s gained (or lost) per second
    projected_rps: float       # expected traffic T seconds from now
    replicas: int              # N used for the capacity
    capacity_rps: float        # C * N
    risk: float                # probability of degradation, between 0 and 1
    pod_capacity_rps: float    # C
    sigma_rps: float           # sigma used for this risk
    sigma_errors: int          # projection errors sigma was calculated from (0 = initial value)

    # Risk the same projected traffic would have with a different number of replicas.
    def risk_at(self, replicas):
        return risk_probability(self.projected_rps, self.pod_capacity_rps * max(1, replicas), self.sigma_rps)


# sigma = how much the traffic has come in ABOVE the projections lately.
# Each projection ("T seconds from now there will be X req/s") is kept until that moment
# arrives, then compared with the real traffic. Only errors where the real traffic was higher
# count: the risk is about exceeding capacity, so traffic lower than projected is a safe
# error (for example when traffic stops suddenly) and must not make Aegis react later.
# sigma = sqrt(2 * mean(max(0, error)^2)) over the last window_seconds. The factor 2 makes it
# equal to the usual sigma when the noise is symmetric, and a projection that is always late
# during a ramp (a bias) counts fully: that is exactly the error the risk must allow for.
class SigmaEstimator:
    def __init__(self, initial_rps, min_rps, window_seconds, min_errors, match_tolerance_seconds):
        self.initial_rps = initial_rps            # used until there are min_errors errors
        self.min_rps = min_rps                    # floor: very steady traffic must not make Aegis overconfident
        self.window_seconds = window_seconds
        self.min_errors = min_errors
        self.match_tolerance_seconds = match_tolerance_seconds   # samples do not land exactly at t + T
        self.pending = deque()   # (target_time, projected_rps) waiting for the real traffic
        self.errors = deque()    # (timestamp, real - projected)

    @classmethod
    def from_config(cls, config):
        sigma = config["sigma"]
        return cls(
            initial_rps=sigma["initial_rps"],
            min_rps=sigma["min_rps"],
            window_seconds=sigma["window_seconds"],
            min_errors=sigma["min_errors"],
            match_tolerance_seconds=config["sampling"]["interval_seconds"] / 2,
        )

    # A new real value: closes the projections that were made for this moment.
    def observe(self, timestamp, rps):
        while self.pending and self.pending[0][0] - self.match_tolerance_seconds <= timestamp:
            target_time, projected_rps = self.pending.popleft()
            # After a data gap the sample is too late to judge that projection: drop it
            if timestamp - target_time <= 3 * self.match_tolerance_seconds:
                self.errors.append((timestamp, rps - projected_rps))
        while self.errors and self.errors[0][0] < timestamp - self.window_seconds:
            self.errors.popleft()

    def add_projection(self, target_time, projected_rps):
        # Traffic cannot be negative: do not count that part of a falling projection as an error
        self.pending.append((target_time, max(0.0, projected_rps)))

    def count(self):
        return len(self.errors)

    def value(self):
        if len(self.errors) < self.min_errors:
            return self.initial_rps
        total = 0.0
        for timestamp, error in self.errors:
            if error > 0:
                total += error * error
        return max(self.min_rps, math.sqrt(2 * total / len(self.errors)))


# projection = r + m * T
# risk       = Phi((projection - C * N) / sigma)
# Edge cases:
# - Fewer than 2 samples in the window: no slope yet, m = 0.
# - Sample without req/s (Prometheus failed): ignored, not counted as 0 traffic.
# - 0 Ready replicas (saturated pod failing its readiness probe): N = 1, the pod still serves.
class RiskCalculator:
    def __init__(self, capacity_rps, startup_time_seconds, window_seconds, sigma):
        self.capacity_rps = capacity_rps
        self.startup_time_seconds = startup_time_seconds
        self.window_seconds = window_seconds
        self.sigma = sigma                 # SigmaEstimator
        self.window = deque()              # valid (timestamp, rps) pairs inside the window
        self.last_replicas = None

    @classmethod
    def from_config(cls, config):
        return cls(
            capacity_rps=config["capacity_rps"],
            startup_time_seconds=config["startup_time_seconds"],
            window_seconds=config["sampling"]["projection_window_seconds"],
            sigma=SigmaEstimator.from_config(config),
        )

    # Adds a sample and returns the current risk, or None if there is no traffic data yet.
    def update(self, sample) -> Optional[RiskResult]:
        if sample.rps is not None:
            self.window.append((sample.timestamp, sample.rps))
            self.sigma.observe(sample.timestamp, sample.rps)
        if sample.replicas_ready is not None:
            self.last_replicas = sample.replicas_ready

        # Drop samples that fell out of the window
        while self.window and self.window[0][0] < sample.timestamp - self.window_seconds:
            self.window.popleft()

        if not self.window:
            return None

        timestamp, rps = self.window[-1]
        slope = self.slope()
        projected_rps = rps + slope * self.startup_time_seconds

        # Only a new real value makes a new projection (not a repeat of the last one)
        if sample.rps is not None:
            self.sigma.add_projection(timestamp + self.startup_time_seconds, projected_rps)

        replicas = max(MIN_REPLICAS_FOR_CAPACITY, self.last_replicas or 0)
        capacity = self.capacity_rps * replicas
        sigma_rps = self.sigma.value()
        risk = risk_probability(projected_rps, capacity, sigma_rps)

        return RiskResult(
            timestamp=timestamp,
            rps=rps,
            slope=slope,
            projected_rps=projected_rps,
            replicas=replicas,
            capacity_rps=capacity,
            risk=risk,
            pod_capacity_rps=self.capacity_rps,
            sigma_rps=sigma_rps,
            sigma_errors=self.sigma.count(),
        )

    def slope(self):
        if len(self.window) < 2:
            return 0.0
        times = []
        values = []
        for timestamp, rps in self.window:
            times.append(timestamp)
            values.append(rps)
        return statistics.linear_regression(times, values).slope

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    load_kubernetes_credentials()
    if not load_cluster_calibration(config):
        return
    collector = PrometheusCollector.from_config(config)
    calculator = RiskCalculator.from_config(config)
    interval = config["sampling"]["interval_seconds"]

    logger.info("Calculating risk every %s s (Ctrl+C to stop)", interval)
    next_run = time.monotonic()
    try:
        while True:
            result = calculator.update(collector.collect())
            if result is None:
                logger.info("No traffic data yet")
            else:
                logger.info(
                    "rps=%s m=%s projection=%s capacity=%s (N=%s) sigma=%s (%s errors) risk=%s%%",
                    format_value(result.rps),
                    format_value(result.slope, 3),
                    format_value(result.projected_rps),
                    format_value(result.capacity_rps, 0),
                    result.replicas,
                    format_value(result.sigma_rps),
                    result.sigma_errors,
                    format_value(result.risk * 100, 1),
                )
            next_run += interval
            time.sleep(max(0.0, next_run - time.monotonic()))
    except KeyboardInterrupt:
        logger.info("Risk calculator stopped")

if __name__ == "__main__":
    main()