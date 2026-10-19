import argparse
import json
import logging
import signal
import time
from aegis.calibration import load_cluster_calibration
from aegis.collector import Collector
from aegis.config import load_config
from aegis.decision import HOLD, DecisionEngine, pct
from aegis.kube import load_kubernetes_credentials
from aegis.risk import RiskCalculator
from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


# Applies the decisions by changing minReplicas of the HPA; the HPA creates or removes the pods.
class HpaActuator:
    def __init__(self, hpa_name, namespace, dry_run):
        self.hpa_name = hpa_name
        self.namespace = namespace
        self.dry_run = dry_run
        self.api = client.AutoscalingV2Api()
        self.applied = None

    @classmethod
    def from_config(cls, config, dry_run):
        kubernetes = config["kubernetes"]
        return cls(kubernetes["hpa_name"], kubernetes["namespace"], dry_run)

    # Returns (minReplicas, maxReplicas) of the HPA, or None if it cannot be read.
    def read_limits(self):
        try:
            hpa = self.api.read_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace)
        except ApiException as error:
            logger.warning("Could not read HPA %s: %s %s", self.hpa_name, error.status, error.reason)
            return None
        min_replicas = hpa.spec.min_replicas
        if min_replicas is None:
            min_replicas = 1
        self.applied = min_replicas
        return min_replicas, hpa.spec.max_replicas

    # Sets minReplicas only when it changes; on error it keeps the old value and the next cycle retries.
    def apply(self, target):
        if target == self.applied:
            return True
        if self.dry_run:
            logger.info("[dry-run] would set minReplicas %s -> %s", self.applied, target)
            self.applied = target
            return True
        try:
            self.api.patch_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace,
                                                                {"spec": {"minReplicas": target}})
        except Exception as error:
            logger.warning("Could not set minReplicas=%s on HPA %s: %s", target, self.hpa_name, error)
            return False
        logger.info("minReplicas %s -> %s on HPA %s", self.applied, target, self.hpa_name)
        self.applied = target
        return True


# Writes one JSON line per cycle (NDJSON), for the experiments and the monitor.
class DecisionLog:
    def __init__(self, path):
        self.file = None
        if path is not None:
            self.file = open(path, "a")

    def write(self, record):
        if self.file is None:
            return
        self.file.write(json.dumps(record) + "\n")
        self.file.flush()


def rounded(value, decimals):
    if value is None:
        return None
    return round(value, decimals)


def text(value):
    if value is None:
        return "-"
    return str(value)


# Everything Aegis knew and did in one cycle.
def build_record(sample, result, decision, applied, pod_capacity_rps):
    record = {
        "time": round(decision.timestamp, 3),
        "rps": None,
        "slope": None,
        "projected_rps": None,
        "sigma_rps": None,
        "p95_s": rounded(sample.p95_s, 3),
        "replicas_ready": sample.replicas_ready,
        "capacity_rps": pod_capacity_rps * decision.previous_target,
        "risk": rounded(decision.risk, 4),
        "action": decision.action,
        "previous_target": decision.previous_target,
        "target": decision.target,
        "applied": applied,
        "reason": decision.reason,
    }
    if result is not None:
        record["rps"] = round(result.rps, 2)
        record["slope"] = round(result.slope, 3)
        record["projected_rps"] = round(result.projected_rps, 2)
        record["sigma_rps"] = round(result.sigma_rps, 2)
    return record


def log_cycle(record, important):
    level = logging.INFO
    if important:
        level = logging.WARNING
    risk = "-"
    if record["risk"] is not None:
        risk = pct(record["risk"])
    logger.log(level, "demand=%s projected=%s sigma=%s risk=%s ready=%s | %s %s -> %s (%s)",
               text(rounded(record["rps"], 1)), text(rounded(record["projected_rps"], 1)), text(record["sigma_rps"]),
               risk, text(record["replicas_ready"]), record["action"].upper(), record["previous_target"],
               record["target"], record["reason"])


# Aegis main loop: collect, project, decide and apply every interval_seconds.
def run_loop(config, actuator, decision_log):
    collector = Collector.from_config(config)
    calculator = RiskCalculator.from_config(config)
    interval = config["sampling"]["interval_seconds"]
    limits = actuator.read_limits()
    if limits is None:
        logger.error("Cannot start without reading the HPA")
        return
    engine = DecisionEngine.from_config(config, limits[0])
    actuator.apply(engine.target)
    logger.info("Aegis running every %s s: C=%s req/s, T=%s s, HPA minReplicas=%s (Ctrl+C to stop)",
                interval, config["capacity_rps"], config["startup_time_seconds"], limits[0])
    next_run = time.monotonic()
    try:
        while True:
            sample = collector.collect()
            result = calculator.update(sample)
            decision = engine.decide(result, time.time())
            applied = actuator.apply(decision.target)
            record = build_record(sample, result, decision, actuator.applied, config["capacity_rps"])
            decision_log.write(record)
            log_cycle(record, decision.action != HOLD or not applied)
            next_run += interval
            time.sleep(max(0.0, next_run - time.monotonic()))
    except KeyboardInterrupt:
        logger.info("Aegis stopped")


def stop(signum, frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description="Aegis: preventive scaling through the HPA minReplicas")
    parser.add_argument("--dry-run", action="store_true", help="run the loop without changing the HPA")
    parser.add_argument("--log", help="also write every cycle as one JSON line to this file")
    parser.add_argument("--set", type=int, metavar="N", help="only set minReplicas to N and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, stop)
    config = load_config()
    load_kubernetes_credentials()
    actuator = HpaActuator.from_config(config, args.dry_run)
    if args.set is not None:
        if actuator.read_limits() is not None:
            actuator.apply(args.set)
        return
    if not load_cluster_calibration(config):
        return
    run_loop(config, actuator, DecisionLog(args.log))


if __name__ == "__main__":
    main()
