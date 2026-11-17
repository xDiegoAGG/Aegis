import threading
import time
import uuid
from collections import deque

HISTORY_SIZE = 1440
GAUGES = [
    ("aegis_demand_rps", "rps", "Demand at the entrance in req/s (r)"),
    ("aegis_slope_rps_per_second", "slope", "Trend of the demand over the projection window (m)"),
    ("aegis_projected_rps", "projected_rps", "Demand projected T + lag seconds ahead (p)"),
    ("aegis_sigma_rps", "sigma_rps", "Projection error learned live (sigma)"),
    ("aegis_risk", "risk", "Probability of going over the capacity of the replicas already requested"),
    ("aegis_risk_one_less", "risk_one_less", "Risk with one replica less (scale-down condition)"),
    ("aegis_target_replicas", "target", "Replicas Aegis wants after this cycle"),
    ("aegis_applied_min_replicas", "applied", "minReplicas Aegis last wrote on the HPA"),
    ("aegis_replicas_ready", "replicas_ready", "Ready replicas of the workload"),
    ("aegis_capacity_rps", "capacity_rps", "Capacity of the replicas requested before the decision (C * N)"),
    ("aegis_p95_seconds", "p95_s", "P95 latency at the entrance"),
    ("aegis_hpa_desired_replicas", "hpa_desired", "desiredReplicas reported by the HPA"),
    ("aegis_hpa_current_replicas", "hpa_current", "currentReplicas reported by the HPA"),
]
FIXED_GAUGES = [
    ("aegis_pod_capacity_rps", "pod_capacity_rps", "Capacity of one pod measured by the calibration (C)"),
    ("aegis_startup_time_seconds", "startup_time_seconds", "Time from asking for a pod until Ready (T)"),
    ("aegis_risk_threshold_scale_up", "scale_up_threshold", "Risk that adds one replica"),
    ("aegis_risk_threshold_scale_down", "scale_down_threshold", "Risk with one replica less that removes one"),
]


def metric_line(name, labels, value):
    parts = []
    for key in sorted(labels):
        parts.append(key + '="' + str(labels[key]).replace("\\", "\\\\").replace('"', '\\"') + '"')
    return name + "{" + ",".join(parts) + "} " + repr(float(value))


def add_metric(lines, name, help_text, kind, labels, value):
    lines.append("# HELP " + name + " " + help_text)
    lines.append("# TYPE " + name + " " + kind)
    lines.append(metric_line(name, labels, value))


# Everything the monitor and Prometheus see: the fixed parameters and the last cycles.
class AegisState:
    def __init__(self, meta, history_size=HISTORY_SIZE):
        self.meta = dict(meta)
        self.meta["session"] = uuid.uuid4().hex
        self.history = deque(maxlen=history_size)
        self.actions = {"scale_up": 0, "scale_down": 0, "hold": 0}
        self.failed_applies = 0
        self.lock = threading.Lock()

    def push(self, record):
        with self.lock:
            self.history.append(record)
            action = record.get("action", "hold")
            self.actions[action] = self.actions.get(action, 0) + 1
            if record.get("applied") is not None and record.get("target") != record.get("applied"):
                self.failed_applies += 1

    def latest(self):
        with self.lock:
            if not self.history:
                return None
            return self.history[-1]

    def snapshot(self, since):
        with self.lock:
            records = []
            for record in self.history:
                if since is None or record["time"] > since:
                    records.append(record)
            return {"meta": self.meta, "records": records, "actions": dict(self.actions)}

    # True while cycles keep arriving (used by the readiness probe).
    def fresh(self):
        record = self.latest()
        if record is None:
            return False
        return time.time() - record["time"] < 4 * self.meta.get("interval_seconds", 5)

    # The Prometheus text format of the last cycle, the fixed parameters and the counters.
    def metrics_text(self):
        labels = {"target_namespace": self.meta.get("namespace", ""),
                  "target_deployment": self.meta.get("deployment", "")}
        with self.lock:
            record = None
            if self.history:
                record = self.history[-1]
            actions = dict(self.actions)
            failed = self.failed_applies
        cycles = 0
        for count in actions.values():
            cycles += count
        lines = []
        if record is not None:
            for name, key, help_text in GAUGES:
                if record.get(key) is not None:
                    add_metric(lines, name, help_text, "gauge", labels, record[key])
            add_metric(lines, "aegis_last_cycle_timestamp_seconds", "Unix time of the last cycle", "gauge", labels,
                       record["time"])
        for name, key, help_text in FIXED_GAUGES:
            if self.meta.get(key) is not None:
                add_metric(lines, name, help_text, "gauge", labels, self.meta[key])
        lines.append("# HELP aegis_decisions_total Decisions taken, by action")
        lines.append("# TYPE aegis_decisions_total counter")
        for action in sorted(actions):
            lines.append(metric_line("aegis_decisions_total", dict(labels, action=action), actions[action]))
        add_metric(lines, "aegis_cycles_total", "Cycles run since start", "counter", labels, cycles)
        add_metric(lines, "aegis_failed_applies_total", "Cycles where the HPA could not be updated", "counter", labels,
                   failed)
        return "\n".join(lines) + "\n"
