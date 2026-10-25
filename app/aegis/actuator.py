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
from aegis.server import AegisState, start_server
from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


MODE_MIN_REPLICAS = "min_replicas"
MODE_METRIC = "metric"


# Applies decisions through minReplicas; in metric mode it writes nothing (the HPA reads /metrics).
class HpaActuator:
    def __init__(self, hpa_name, namespace, dry_run, mode=MODE_MIN_REPLICAS):
        self.hpa_name = hpa_name
        self.namespace = namespace
        self.dry_run = dry_run
        self.mode = mode
        self.api = client.AutoscalingV2Api()
        self.applied = None

    @classmethod
    def from_config(cls, config, dry_run):
        kubernetes = config["kubernetes"]
        mode = config.get("actuator", {}).get("mode", MODE_MIN_REPLICAS)
        if mode not in (MODE_MIN_REPLICAS, MODE_METRIC):
            raise ValueError("actuator.mode must be min_replicas or metric, not " + str(mode))
        return cls(kubernetes["hpa_name"], kubernetes["namespace"], dry_run, mode)

    def read_hpa(self):
        try:
            return self.api.read_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace)
        except ApiException as error:
            logger.warning("Could not read HPA %s: %s %s", self.hpa_name, error.status, error.reason)
            return None

    # Returns (starting replicas, maxReplicas) of the HPA, or None if it cannot be read.
    # min_replicas mode starts from minReplicas; metric mode from the replicas running now.
    def read_limits(self):
        hpa = self.read_hpa()
        if hpa is None:
            return None
        min_replicas = hpa.spec.min_replicas
        if min_replicas is None:
            min_replicas = 1
        start = min_replicas
        if self.mode == MODE_METRIC and hpa.status is not None and hpa.status.current_replicas:
            start = hpa.status.current_replicas
        self.applied = start
        return start, hpa.spec.max_replicas

    # What the HPA reports this cycle, for the log and the dashboard.
    def observe(self):
        hpa = self.read_hpa()
        if hpa is None:
            return {"hpa_min": None, "hpa_current": None, "hpa_desired": None}
        observed = {"hpa_min": hpa.spec.min_replicas or 1, "hpa_current": None, "hpa_desired": None}
        if hpa.status is not None:
            observed["hpa_current"] = hpa.status.current_replicas
            observed["hpa_desired"] = hpa.status.desired_replicas
        return observed

    # Sets minReplicas only when it changes; on error it keeps the old value and the next cycle retries.
    def apply(self, target):
        if target == self.applied:
            return True
        if self.mode == MODE_METRIC:
            logger.info("aegis_target_replicas %s -> %s (the HPA reads it)", self.applied, target)
            self.applied = target
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
def build_record(sample, result, decision, applied, pod_capacity_rps, observed=None):
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
        "risk_one_less": None,
    }
    if result is not None:
        record["rps"] = round(result.rps, 2)
        record["slope"] = round(result.slope, 3)
        record["projected_rps"] = round(result.projected_rps, 2)
        record["sigma_rps"] = round(result.sigma_rps, 2)
        if decision.previous_target > 1:
            record["risk_one_less"] = round(result.risk_at(decision.previous_target - 1), 4)
    if observed is not None:
        record.update(observed)
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


# The fixed parameters the dashboard shows next to the cycles.
def build_meta(config, actuator):
    kubernetes = config["kubernetes"]
    thresholds = config["risk_thresholds"]
    sampling = config["sampling"]
    mode = "live"
    if actuator.dry_run:
        mode = "dry-run"
    return {
        "mode": mode,
        "actuator_mode": actuator.mode,
        "namespace": kubernetes["namespace"],
        "deployment": kubernetes["deployment_name"],
        "hpa_name": kubernetes["hpa_name"],
        "min_replicas": kubernetes["min_replicas"],
        "max_replicas": kubernetes["max_replicas"],
        "pod_capacity_rps": config["capacity_rps"],
        "startup_time_seconds": config["startup_time_seconds"],
        "metric_lag_seconds": sampling["metric_lag_seconds"],
        "projection_window_seconds": sampling["projection_window_seconds"],
        "interval_seconds": sampling["interval_seconds"],
        "p95_threshold_seconds": config["degradation"]["p95_threshold_seconds"],
        "sustained_seconds": config["degradation"]["sustained_seconds"],
        "scale_up_threshold": thresholds["scale_up"],
        "scale_down_threshold": thresholds["scale_down"],
        "scale_down_sustained_seconds": thresholds["scale_down_sustained_seconds"],
        "calibrated_at": config.get("calibrated_at"),
        "started_at": time.time(),
    }


# Aegis main loop: collect, project, decide and apply every interval_seconds.
def run_loop(config, actuator, decision_log, state=None):
    collector = Collector.from_config(config)
    calculator = RiskCalculator.from_config(config)
    interval = config["sampling"]["interval_seconds"]
    limits = actuator.read_limits()
    if limits is None:
        logger.error("Cannot start without reading the HPA")
        return
    engine = DecisionEngine.from_config(config, limits[0])
    actuator.apply(engine.target)
    logger.info("Aegis running every %s s (%s mode): C=%s req/s, T=%s s, start at %s replica(s) (Ctrl+C to stop)",
                interval, actuator.mode, config["capacity_rps"], config["startup_time_seconds"], limits[0])
    next_run = time.monotonic()
    try:
        while True:
            sample = collector.collect()
            result = calculator.update(sample)
            decision = engine.decide(result, time.time())
            applied = actuator.apply(decision.target)
            observed = actuator.observe()
            record = build_record(sample, result, decision, actuator.applied, config["capacity_rps"], observed)
            decision_log.write(record)
            if state is not None:
                state.push(record)
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
    parser.add_argument("--port", type=int, help="port of the dashboard and /metrics (default: server.port)")
    parser.add_argument("--no-server", action="store_true", help="do not serve the dashboard and /metrics")
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
    state = None
    if not args.no_server:
        port = args.port or config.get("server", {}).get("port", 8080)
        state = AegisState(build_meta(config, actuator))
        try:
            start_server(state, port)
        except OSError as error:
            logger.warning("Dashboard and /metrics not served (port %s: %s); Aegis keeps running", port, error)
    run_loop(config, actuator, DecisionLog(args.log), state)


if __name__ == "__main__":
    main()
