import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from scipy.stats import norm

from aegis.collector import PrometheusCollector, format_value
from aegis.config import load_config

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
    sigma_rps: float           # sigma

    # Risk the same projected traffic would have with a different number of replicas.
    def risk_at(self, replicas):
        return risk_probability(self.projected_rps, self.pod_capacity_rps * max(1, replicas), self.sigma_rps)


# projection = r + m * T
# risk       = Phi((projection - C * N) / sigma)
# Edge cases:
# - Fewer than 2 samples in the window: no slope yet, m = 0.
# - Sample without req/s (Prometheus failed): ignored, not counted as 0 traffic.
# - 0 Ready replicas (saturated pod failing its readiness probe): N = 1, the pod still serves.
class RiskCalculator:
    def __init__(self, capacity_rps, startup_time_seconds, sigma_rps, window_seconds):
        self.capacity_rps = capacity_rps
        self.startup_time_seconds = startup_time_seconds
        self.sigma_rps = sigma_rps
        self.window_seconds = window_seconds
        self._window = deque()          # valid (timestamp, rps) pairs inside the window
        self._last_replicas = None

    @classmethod
    def from_config(cls, config):
        return cls(
            capacity_rps=config["capacity_rps"],
            startup_time_seconds=config["startup_time_seconds"],
            sigma_rps=config["sigma_rps"],
            window_seconds=config["sampling"]["projection_window_seconds"],
        )

    # Adds a sample and returns the current risk, or None if there is no traffic data yet.
    def update(self, sample) -> Optional[RiskResult]:
        if sample.rps is not None:
            self._window.append((sample.timestamp, sample.rps))
        if sample.replicas_ready is not None:
            self._last_replicas = sample.replicas_ready

        # Drop samples that fell out of the window
        while self._window and self._window[0][0] < sample.timestamp - self.window_seconds:
            self._window.popleft()

        if not self._window:
            return None

        timestamp, rps = self._window[-1]
        slope = self._slope()
        projected_rps = rps + slope * self.startup_time_seconds

        replicas = max(MIN_REPLICAS_FOR_CAPACITY, self._last_replicas or 0)
        capacity = self.capacity_rps * replicas
        risk = risk_probability(projected_rps, capacity, self.sigma_rps)

        return RiskResult(
            timestamp=timestamp,
            rps=rps,
            slope=slope,
            projected_rps=projected_rps,
            replicas=replicas,
            capacity_rps=capacity,
            risk=risk,
            pod_capacity_rps=self.capacity_rps,
            sigma_rps=self.sigma_rps,
        )

    def _slope(self):
        if len(self._window) < 2:
            return 0.0
        times = []
        values = []
        for timestamp, rps in self._window:
            times.append(timestamp)
            values.append(rps)
        return statistics.linear_regression(times, values).slope

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
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
                    "rps=%s m=%s projection=%s capacity=%s (N=%s) risk=%s%%",
                    format_value(result.rps),
                    format_value(result.slope, 3),
                    format_value(result.projected_rps),
                    format_value(result.capacity_rps, 0),
                    result.replicas,
                    format_value(result.risk * 100, 1),
                )
            next_run += interval
            time.sleep(max(0.0, next_run - time.monotonic()))
    except KeyboardInterrupt:
        logger.info("Risk calculator stopped")

if __name__ == "__main__":
    main()