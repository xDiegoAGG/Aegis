import math
import statistics
from collections import deque
from scipy.stats import norm


# Probability that the traffic goes over the capacity when the projection error is normal with std sigma.
def risk_probability(projected_rps, capacity_rps, sigma_rps):
    return float(norm.cdf((projected_rps - capacity_rps) / sigma_rps))


# The projection of one cycle. risk_at gives the risk for any number of replicas.
class RiskResult:
    def __init__(self, timestamp, rps, slope, projected_rps, sigma_rps, sigma_errors, pod_capacity_rps):
        self.timestamp = timestamp
        self.rps = rps
        self.slope = slope
        self.projected_rps = projected_rps
        self.sigma_rps = sigma_rps
        self.sigma_errors = sigma_errors
        self.pod_capacity_rps = pod_capacity_rps

    def risk_at(self, replicas):
        return risk_probability(self.projected_rps, self.pod_capacity_rps * max(1, replicas), self.sigma_rps)


# sigma from how far the traffic came in above past projections: sqrt(2 * mean(max(0, error)^2)).
class SigmaEstimator:
    def __init__(self, initial_rps, min_rps, window_seconds, min_errors, match_tolerance_seconds):
        self.initial_rps = initial_rps
        self.min_rps = min_rps
        self.window_seconds = window_seconds
        self.min_errors = min_errors
        self.match_tolerance_seconds = match_tolerance_seconds
        self.pending = deque()
        self.errors = deque()

    @classmethod
    def from_config(cls, config):
        sigma = config["sigma"]
        return cls(
            sigma["initial_rps"],
            sigma["min_rps"],
            sigma["window_seconds"],
            sigma["min_errors"],
            config["sampling"]["interval_seconds"] / 2,
        )

    # Compares the projections made for this moment with the real traffic; late matches are dropped.
    def observe(self, timestamp, rps):
        while self.pending and self.pending[0][0] - self.match_tolerance_seconds <= timestamp:
            target_time, projected_rps = self.pending.popleft()
            if timestamp - target_time <= 3 * self.match_tolerance_seconds:
                self.errors.append((timestamp, rps - projected_rps))
        while self.errors and self.errors[0][0] < timestamp - self.window_seconds:
            self.errors.popleft()

    def add_projection(self, target_time, projected_rps):
        self.pending.append((target_time, max(0.0, projected_rps)))

    def value(self):
        if len(self.errors) < self.min_errors:
            return self.initial_rps
        total = 0.0
        for timestamp, error in self.errors:
            if error > 0:
                total += error * error
        return max(self.min_rps, math.sqrt(2 * total / len(self.errors)))


# Projects the demand T + lag seconds ahead with a linear regression over the last samples.
class RiskCalculator:
    def __init__(self, capacity_rps, horizon_seconds, window_seconds, sigma):
        self.capacity_rps = capacity_rps
        self.horizon_seconds = horizon_seconds
        self.window_seconds = window_seconds
        self.sigma = sigma
        self.window = deque()

    @classmethod
    def from_config(cls, config):
        sampling = config["sampling"]
        return cls(
            config["capacity_rps"],
            config["startup_time_seconds"] + sampling["metric_lag_seconds"],
            sampling["projection_window_seconds"],
            SigmaEstimator.from_config(config),
        )

    # Adds a sample and returns the projection, or None while there is no traffic data.
    def update(self, sample):
        if sample.rps is not None:
            rps = max(0.0, sample.rps)
            self.window.append((sample.timestamp, rps))
            self.sigma.observe(sample.timestamp, rps)
        while self.window and self.window[0][0] < sample.timestamp - self.window_seconds:
            self.window.popleft()
        if not self.window:
            return None
        timestamp, rps = self.window[-1]
        slope = self.slope()
        projected_rps = rps + slope * self.horizon_seconds
        if sample.rps is not None:
            self.sigma.add_projection(timestamp + self.horizon_seconds, projected_rps)
        return RiskResult(timestamp, rps, slope, projected_rps, self.sigma.value(), len(self.sigma.errors),
                          self.capacity_rps)

    def slope(self):
        if len(self.window) < 2:
            return 0.0
        times = []
        values = []
        for timestamp, rps in self.window:
            times.append(timestamp)
            values.append(rps)
        return statistics.linear_regression(times, values).slope
