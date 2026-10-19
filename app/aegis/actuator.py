import argparse
import logging
import time

from kubernetes import client
from kubernetes.client.rest import ApiException

from aegis.calibration import load_cluster_calibration
from aegis.collector import PrometheusCollector, format_value
from aegis.config import load_config
from aegis.decision import HOLD, DecisionEngine, pct
from aegis.kube import load_kubernetes_credentials
from aegis.risk import RiskCalculator

logger = logging.getLogger(__name__)


# Applies the target replicas by changing minReplicas of the HPA.
# The HPA then creates (or allows removing) the pods: Aegis never touches the Deployment.
class HpaActuator:
    def __init__(self, hpa_name, namespace, api=None, dry_run=False):
        self.hpa_name = hpa_name
        self.namespace = namespace
        self.dry_run = dry_run
        self.api = api
        if self.api is None:
            self.api = client.AutoscalingV2Api()
        self.applied = None    # last minReplicas confirmed in the cluster

    @classmethod
    def from_config(cls, config, dry_run=False):
        kubernetes = config["kubernetes"]
        return cls(
            hpa_name=kubernetes["hpa_name"],
            namespace=kubernetes["namespace"],
            dry_run=dry_run,
        )

    # Returns (minReplicas, maxReplicas) of the HPA, or None if it cannot be read.
    def read_limits(self):
        try:
            hpa = self.api.read_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace)
        except ApiException as error:
            logger.warning("Could not read HPA %s/%s: %s %s", self.namespace, self.hpa_name,
                           error.status, error.reason)
            return None
        min_replicas = hpa.spec.min_replicas
        if min_replicas is None:
            min_replicas = 1    # Kubernetes default when minReplicas is not set
        self.applied = min_replicas
        return min_replicas, hpa.spec.max_replicas

    # Makes minReplicas equal to target. Only calls the API when the value changes.
    # On error it returns False and keeps the old value, so the next cycle tries again.
    def apply(self, target):
        if target == self.applied:
            return True

        if self.dry_run:
            logger.info("[dry-run] would set minReplicas %s -> %s", self.applied, target)
            self.applied = target
            return True

        body = {"spec": {"minReplicas": target}}
        try:
            self.api.patch_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace, body)
        except ApiException as error:
            logger.warning("Could not set minReplicas=%s on HPA %s/%s: %s %s", target, self.namespace,
                           self.hpa_name, error.status, error.reason)
            return False
        except Exception as error:
            # Network errors (API server down) arrive as urllib3 exceptions
            logger.warning("Could not reach the Kubernetes API: %s", error)
            return False

        logger.info("minReplicas %s -> %s on HPA %s/%s", self.applied, target, self.namespace, self.hpa_name)
        self.applied = target
        return True


def run_loop(config, actuator):
    collector = PrometheusCollector.from_config(config)
    calculator = RiskCalculator.from_config(config)
    interval = config["sampling"]["interval_seconds"]

    # Start from the current minReplicas so a restart of Aegis does not undo a scale-up
    limits = actuator.read_limits()
    if limits is None:
        logger.error("Cannot start without reading the HPA")
        return
    current_min, hpa_max = limits
    if config["kubernetes"]["max_replicas"] > hpa_max:
        logger.warning("config max_replicas=%s is higher than HPA maxReplicas=%s: the API will reject it",
                       config["kubernetes"]["max_replicas"], hpa_max)
    engine = DecisionEngine.from_config(config, initial_target=current_min)
    if engine.target != current_min:
        # The HPA had a value outside the configured range: bring it back
        actuator.apply(engine.target)

    logger.info("Aegis running every %s s, HPA minReplicas=%s (Ctrl+C to stop)", interval, current_min)
    next_run = time.monotonic()
    try:
        while True:
            result = calculator.update(collector.collect())
            decision = engine.decide(result)
            applied = actuator.apply(decision.target)

            level = logging.INFO
            if decision.action != HOLD or not applied:
                level = logging.WARNING

            rps_text = "-"
            risk_text = "-"
            if result is not None:
                rps_text = format_value(result.rps)
                risk_text = pct(result.risk)

            logger.log(
                level,
                "rps=%s risk=%s %s target %s -> %s, applied=%s (%s)",
                rps_text,
                risk_text,
                decision.action.upper(),
                decision.previous_target,
                decision.target,
                actuator.applied,
                decision.reason,
            )
            next_run += interval
            time.sleep(max(0.0, next_run - time.monotonic()))
    except KeyboardInterrupt:
        logger.info("Aegis stopped")


def main():
    parser = argparse.ArgumentParser(description="Aegis actuator: applies decisions to the HPA minReplicas")
    parser.add_argument("--set", type=int, metavar="N", help="set minReplicas to N once and exit (manual test)")
    parser.add_argument("--dry-run", action="store_true", help="run the full loop without changing the HPA")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    source = load_kubernetes_credentials()
    actuator = HpaActuator.from_config(config, dry_run=args.dry_run)
    logger.info("Kubernetes credentials from %s, HPA %s/%s", source, actuator.namespace, actuator.hpa_name)

    if args.set is None:
        if not load_cluster_calibration(config):
            return
        run_loop(config, actuator)
        return

    low = config["kubernetes"]["min_replicas"]
    high = config["kubernetes"]["max_replicas"]
    if args.set < low or args.set > high:
        logger.error("--set must be between %s and %s (kubernetes.min_replicas / max_replicas)", low, high)
        return
    if actuator.read_limits() is None:
        return
    actuator.apply(args.set)


if __name__ == "__main__":
    main()
