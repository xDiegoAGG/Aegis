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


# Turns the risk into replicas: one more at 70%, one less when that stays below 30% for 60 s.
class DecisionEngine:
    def __init__(self, scale_up_threshold, scale_down_threshold, scale_down_sustained_seconds,
                 min_replicas, max_replicas, initial_target):
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_down_sustained_seconds = scale_down_sustained_seconds
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target = max(min_replicas, min(max_replicas, initial_target))
        self.low_risk_since = None

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
        )

    # Scale up uses the risk with the replicas already requested; scale down, the risk with one less.
    def decide(self, result, now):
        previous = self.target
        if result is None:
            self.low_risk_since = None
            return Decision(now, HOLD, previous, previous, None, "no traffic data")
        risk = result.risk_at(self.target)
        if risk >= self.scale_up_threshold:
            self.low_risk_since = None
            if self.target >= self.max_replicas:
                return Decision(now, HOLD, previous, previous, risk, "risk " + pct(risk) + " but already at max_replicas")
            self.target += 1
            return Decision(now, SCALE_UP, previous, self.target, risk,
                            "risk with " + str(previous) + " pod(s) " + pct(risk) + " >= " + pct(self.scale_up_threshold))
        if self.target <= self.min_replicas:
            self.low_risk_since = None
            return Decision(now, HOLD, previous, previous, risk, "already at min_replicas")
        risk_one_less = result.risk_at(self.target - 1)
        if risk_one_less >= self.scale_down_threshold:
            self.low_risk_since = None
            return Decision(now, HOLD, previous, previous, risk, "risk with one pod less " + pct(risk_one_less))
        if self.low_risk_since is None:
            self.low_risk_since = now
        low_for = now - self.low_risk_since
        if low_for < self.scale_down_sustained_seconds:
            return Decision(now, HOLD, previous, previous, risk,
                            "risk with one pod less " + pct(risk_one_less) + ", low for " + str(int(low_for))
                            + "/" + str(self.scale_down_sustained_seconds) + " s")
        self.target -= 1
        self.low_risk_since = None
        return Decision(now, SCALE_DOWN, previous, self.target, risk,
                        "risk with " + str(self.target) + " pod(s) " + pct(risk_one_less) + " < "
                        + pct(self.scale_down_threshold) + " for " + str(int(low_for)) + " s")
