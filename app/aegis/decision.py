SCALE_UP = "scale_up"
SCALE_DOWN = "scale_down"
HOLD = "hold"


def pct(value):
    return str(round(value * 100, 1)) + "%"


# One decision: the action, the replicas before and after, and the risk it was based on.
class Decision:
    def __init__(self, timestamp, action, previous_target, target, risk, reason):
        self.timestamp = timestamp
        self.action = action
        self.previous_target = previous_target
        self.target = target
        self.risk = risk
        self.reason = reason


# Turns the risk into replicas. Up: one more pod when the risk with the requested pods reaches 70%.
# Down: for every smaller count k, how long the risk with k pods has stayed under 30%, and the highest
# risk seen meanwhile. k is allowed after a wait between min_wait (risk ~0%) and max_wait (risk near
# 30%): the surer the projection, the sooner the pod is given back (ski-rental style break-even).
# Aegis then goes straight to the smallest allowed k, so 3 -> 1 does not take two full waits.
class DecisionEngine:
    def __init__(self, scale_up_threshold, scale_down_threshold, scale_down_max_wait_seconds,
                 min_replicas, max_replicas, initial_target, scale_down_min_wait_seconds=None):
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_down_max_wait_seconds = scale_down_max_wait_seconds
        self.scale_down_min_wait_seconds = (scale_down_max_wait_seconds if scale_down_min_wait_seconds is None
                                            else scale_down_min_wait_seconds)
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target = max(min_replicas, min(max_replicas, initial_target))
        self.low = {}  # pods -> [since, highest risk while low]

    @classmethod
    def from_config(cls, config, initial_target):
        thresholds = config["risk_thresholds"]
        kubernetes = config["kubernetes"]
        return cls(
            thresholds["scale_up"],
            thresholds["scale_down"],
            thresholds["scale_down_sustained_seconds"],
            kubernetes["min_replicas"],
            kubernetes["max_replicas"],
            initial_target,
            thresholds.get("scale_down_min_wait_seconds"),
        )

    # Seconds the risk with fewer pods must stay low: min_wait at 0%, max_wait at the threshold.
    def wait_for(self, highest_risk):
        share = min(1.0, max(0.0, highest_risk / self.scale_down_threshold))
        return self.scale_down_min_wait_seconds + (self.scale_down_max_wait_seconds - self.scale_down_min_wait_seconds) * share

    # Scale up uses the risk with the replicas already requested; scale down, the risk with fewer.
    def decide(self, result, now):
        previous = self.target
        if result is None:
            self.low.clear()
            return Decision(now, HOLD, previous, previous, None, "no traffic data")
        risk = result.risk_at(self.target)
        if risk >= self.scale_up_threshold:
            self.low.clear()
            if self.target >= self.max_replicas:
                return Decision(now, HOLD, previous, previous, risk, "risk " + pct(risk) + " but already at max_replicas")
            self.target += 1
            return Decision(now, SCALE_UP, previous, self.target, risk,
                            "risk with " + str(previous) + " pod(s) " + pct(risk) + " >= " + pct(self.scale_up_threshold))
        if self.target <= self.min_replicas:
            self.low.clear()
            return Decision(now, HOLD, previous, previous, risk, "already at min_replicas")
        for pods in range(self.min_replicas, self.target):
            pods_risk = result.risk_at(pods)
            if pods_risk >= self.scale_down_threshold:
                self.low.pop(pods, None)
            elif pods in self.low:
                self.low[pods][1] = max(self.low[pods][1], pods_risk)
            else:
                self.low[pods] = [now, pods_risk]
        allowed = [pods for pods, (since, highest) in self.low.items()
                   if pods < self.target and now - since >= self.wait_for(highest)]
        risk_one_less = result.risk_at(self.target - 1)
        if not allowed:
            reason = "risk with one pod less " + pct(risk_one_less)
            if self.target - 1 in self.low:
                since, highest = self.low[self.target - 1]
                reason += ", low for " + str(int(now - since)) + "/" + str(int(round(self.wait_for(highest)))) + " s"
            return Decision(now, HOLD, previous, previous, risk, reason)
        self.target = min(allowed)
        since, highest = self.low[self.target]
        self.low.clear()
        return Decision(now, SCALE_DOWN, previous, self.target, risk,
                        "risk with " + str(self.target) + " pod(s) " + pct(result.risk_at(self.target)) + " < "
                        + pct(self.scale_down_threshold) + " for " + str(int(now - since)) + " s (wait "
                        + str(int(round(self.wait_for(highest)))) + " s)")
