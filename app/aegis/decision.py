import logging
import time
from dataclasses import dataclass

from aegis.calibration import load_cluster_calibration
from aegis.collector import PrometheusCollector, format_value
from aegis.config import load_config
from aegis.kube import load_kubernetes_credentials
from aegis.risk import RiskCalculator

logger = logging.getLogger(__name__)

SCALE_UP = "scale_up"
SCALE_DOWN = "scale_down"
HOLD = "hold"


@dataclass(frozen=True)
class Decision:
    timestamp: float
    action: str                # scale_up, scale_down or hold
    previous_target: int       # replicas requested before this decision
    target: int                # replicas requested after this decision
    reason: str                # short explanation, for the log and the monitor

class DecisionEngine:
    def __init__(self, scale_up_threshold, scale_down_threshold, scale_down_sustained_seconds,
                 min_replicas, max_replicas, initial_target=None):
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_down_sustained_seconds = scale_down_sustained_seconds
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.low_risk_since = None    # when risk (with one replica less) went below the threshold

        if initial_target is None:
            self.target = min_replicas
        else:
            self.target = self.clamp(initial_target)

    @classmethod
    def from_config(cls, config, initial_target=None):
        thresholds = config["risk_thresholds"]
        kubernetes = config["kubernetes"]
        return cls(
            scale_up_threshold=thresholds["scale_up"],
            scale_down_threshold=thresholds["scale_down"],
            scale_down_sustained_seconds=thresholds["scale_down_sustained_seconds"],
            min_replicas=kubernetes["min_replicas"],
            max_replicas=kubernetes["max_replicas"],
            initial_target=initial_target,
        )

    # Takes a RiskResult (or None when there is no data) and returns a Decision.
    def decide(self, result, now=None) -> Decision:
        if now is None:
            now = time.time()
        previous = self.target

        if result is None:
            # Without data we do not know: hold, and do not count this time towards scaling down.
            self.low_risk_since = None
            return Decision(now, HOLD, previous, previous, "no traffic data")

        # Scale up (evaluated with the replicas already requested)
        risk_at_target = result.risk_at(self.target)
        if risk_at_target >= self.scale_up_threshold:
            self.low_risk_since = None
            if self.target >= self.max_replicas:
                return self.hold(now, "risk with " + str(self.target) + " replica(s) " + pct(risk_at_target)
                                  + " but already at max_replicas")
            self.target += 1
            return Decision(now, SCALE_UP, previous, self.target,
                            "risk with " + str(previous) + " replica(s) " + pct(risk_at_target)
                            + " >= " + pct(self.scale_up_threshold))

        # Scale down (evaluated with one replica less)
        if self.target > self.min_replicas:
            risk_one_less = result.risk_at(self.target - 1)
            if risk_one_less < self.scale_down_threshold:
                if self.low_risk_since is None:
                    self.low_risk_since = now
                low_for = now - self.low_risk_since
                if low_for >= self.scale_down_sustained_seconds:
                    self.target -= 1
                    self.low_risk_since = None   # the next step down needs another full period
                    return Decision(now, SCALE_DOWN, previous, self.target,
                                    "risk with " + str(self.target) + " replica(s) " + pct(risk_one_less)
                                    + " < " + pct(self.scale_down_threshold) + " for "
                                    + str(int(low_for)) + " s")
                return self.hold(now, "risk with one replica less " + pct(risk_one_less) + ", low for "
                                  + str(int(low_for)) + "/" + str(self.scale_down_sustained_seconds) + " s")
            self.low_risk_since = None
            return self.hold(now, "risk with one replica less " + pct(risk_one_less)
                              + " >= " + pct(self.scale_down_threshold))

        self.low_risk_since = None
        return self.hold(now, "risk " + pct(risk_at_target) + ", already at min_replicas")

    def hold(self, now, reason):
        return Decision(now, HOLD, self.target, self.target, reason)

    def clamp(self, replicas):
        return max(self.min_replicas, min(self.max_replicas, replicas))


def pct(value):
    return str(round(value * 100, 1)) + "%"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    load_kubernetes_credentials()
    if not load_cluster_calibration(config):
        return
    collector = PrometheusCollector.from_config(config)
    calculator = RiskCalculator.from_config(config)
    engine = DecisionEngine.from_config(config)
    interval = config["sampling"]["interval_seconds"]

    logger.info("Deciding every %s s, starting at target=%s (Ctrl+C to stop). Nothing is applied to Kubernetes.",
                interval, engine.target)
    next_run = time.monotonic()
    try:
        while True:
            result = calculator.update(collector.collect())
            decision = engine.decide(result)

            level = logging.INFO
            if decision.action != HOLD:
                level = logging.WARNING

            rps_text = "-"
            risk_text = "-"
            if result is not None:
                rps_text = format_value(result.rps)
                risk_text = pct(result.risk)

            logger.log(
                level,
                "rps=%s risk=%s %s target %s -> %s (%s)",
                rps_text,
                risk_text,
                decision.action.upper(),
                decision.previous_target,
                decision.target,
                decision.reason,
            )
            next_run += interval
            time.sleep(max(0.0, next_run - time.monotonic()))
    except KeyboardInterrupt:
        logger.info("Decision engine stopped")


if __name__ == "__main__":
    main()
