import csv
import json
import logging
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "tests"
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".woff": "font/woff"}
HISTORY_SIZE = 1440

# Gauges published on /metrics: (name, record key, help). One sample per cycle, never cached.
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


def metric_line(name, labels, value):
    parts = []
    for key in sorted(labels):
        parts.append(key + '="' + str(labels[key]).replace("\\", "\\\\").replace('"', '\\"') + '"')
    return name + "{" + ",".join(parts) + "} " + repr(float(value))


# Everything the dashboard and Prometheus see: the fixed parameters and the last cycles.
class AegisState:
    def __init__(self, meta, history_size=HISTORY_SIZE):
        self.meta = dict(meta)
        self.meta["session"] = uuid.uuid4().hex
        self.history = deque(maxlen=history_size)
        self.actions = {"scale_up": 0, "scale_down": 0, "hold": 0}
        self.failed_applies = 0
        self.lock = threading.Lock()

    # Called by the replay when it starts over, so the dashboard drops what it already drew.
    def restart(self):
        with self.lock:
            self.meta["session"] = uuid.uuid4().hex
            self.history.clear()
            self.actions = {"scale_up": 0, "scale_down": 0, "hold": 0}
            self.failed_applies = 0

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

    def metrics_text(self):
        labels = {"target_namespace": self.meta.get("namespace", ""),
                  "target_deployment": self.meta.get("deployment", "")}
        with self.lock:
            record = None
            if self.history:
                record = self.history[-1]
            actions = dict(self.actions)
            cycles = sum(actions.values())
            failed = self.failed_applies
        lines = []
        if record is not None:
            for name, key, help_text in GAUGES:
                if record.get(key) is None:
                    continue
                lines.append("# HELP " + name + " " + help_text)
                lines.append("# TYPE " + name + " gauge")
                lines.append(metric_line(name, labels, record[key]))
            lines.append("# HELP aegis_last_cycle_timestamp_seconds Unix time of the last cycle")
            lines.append("# TYPE aegis_last_cycle_timestamp_seconds gauge")
            lines.append(metric_line("aegis_last_cycle_timestamp_seconds", labels, record["time"]))
        fixed = [
            ("aegis_pod_capacity_rps", "pod_capacity_rps", "Capacity of one pod measured by the calibration (C)"),
            ("aegis_startup_time_seconds", "startup_time_seconds", "Time from asking for a pod until Ready (T)"),
            ("aegis_risk_threshold_scale_up", "scale_up_threshold", "Risk that adds one replica"),
            ("aegis_risk_threshold_scale_down", "scale_down_threshold", "Risk with one replica less that removes one"),
        ]
        for name, key, help_text in fixed:
            if self.meta.get(key) is None:
                continue
            lines.append("# HELP " + name + " " + help_text)
            lines.append("# TYPE " + name + " gauge")
            lines.append(metric_line(name, labels, self.meta[key]))
        lines.append("# HELP aegis_decisions_total Decisions taken, by action")
        lines.append("# TYPE aegis_decisions_total counter")
        for action in sorted(actions):
            lines.append(metric_line("aegis_decisions_total", dict(labels, action=action), actions[action]))
        lines.append("# HELP aegis_cycles_total Cycles run since start")
        lines.append("# TYPE aegis_cycles_total counter")
        lines.append(metric_line("aegis_cycles_total", labels, cycles))
        lines.append("# HELP aegis_failed_applies_total Cycles where the HPA could not be updated")
        lines.append("# TYPE aegis_failed_applies_total counter")
        lines.append(metric_line("aegis_failed_applies_total", labels, failed))
        return "\n".join(lines) + "\n"


def read_csv_rows(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            parsed = {}
            for key, value in row.items():
                if key == "time_utc":
                    parsed[key] = value
                elif value == "":
                    parsed[key] = None
                else:
                    parsed[key] = float(value)
            rows.append(parsed)
    return rows


def read_ndjson(path):
    records = []
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


# The recorded tests in docs/tests: their summaries, and the time series of one run on demand.
class TestCatalog:
    def __init__(self, tests_dir):
        self.tests_dir = Path(tests_dir)

    def folders(self):
        found = {}
        for folder in sorted(self.tests_dir.iterdir()):
            if folder.is_dir() and list((folder / "data").glob("run-*-summary.json")):
                found[folder.name] = folder
        return found

    def listing(self):
        tests = []
        for name, folder in self.folders().items():
            runs = []
            for path in sorted((folder / "data").glob("run-*-summary.json")):
                runs.append(json.loads(path.read_text()))
            tests.append({"name": name, "runs": runs})
        calibration = None
        path = self.tests_dir / "calibration.json"
        if path.exists():
            calibration = json.loads(path.read_text())
        return {"tests": tests, "calibration": calibration}

    def run(self, name, number):
        folder = self.folders().get(name)
        if folder is None:
            return None
        data = folder / "data"
        summary = data / ("run-" + str(number) + "-summary.json")
        if not summary.exists():
            return None
        return {
            "summary": json.loads(summary.read_text()),
            "rows": read_csv_rows(data / ("run-" + str(number) + ".csv")),
            "aegis": read_ndjson(data / ("run-" + str(number) + "-aegis.ndjson")),
        }


def make_handler(state, catalog):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.debug("http %s", format % args)

        def send(self, status, body, content_type):
            data = body if isinstance(body, bytes) else body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status, payload):
            self.send(status, json.dumps(payload), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            path = url.path
            if path == "/metrics":
                self.send(200, state.metrics_text(), "text/plain; version=0.0.4")
            elif path == "/healthz":
                self.send(200, "ok\n", "text/plain")
            elif path == "/readyz":
                if state.fresh():
                    self.send(200, "ok\n", "text/plain")
                else:
                    self.send(503, "no recent cycle\n", "text/plain")
            elif path == "/api/state":
                since = parse_qs(url.query).get("since")
                value = None
                if since:
                    try:
                        value = float(since[0])
                    except ValueError:
                        value = None
                self.send_json(200, state.snapshot(value))
            elif path == "/api/tests":
                if catalog is None:
                    self.send_json(200, {"tests": [], "calibration": None})
                else:
                    self.send_json(200, catalog.listing())
            elif path.startswith("/api/tests/"):
                self.serve_test(path)
            else:
                self.serve_static(path)

        def serve_test(self, path):
            parts = path.split("/")
            if catalog is None or len(parts) != 5 or not parts[4].isdigit():
                self.send_json(404, {"error": "not found"})
                return
            run = catalog.run(parts[3], int(parts[4]))
            if run is None:
                self.send_json(404, {"error": "not found"})
                return
            self.send_json(200, run)

        def serve_static(self, path):
            if path == "/":
                path = "/index.html"
            file = (DASHBOARD_DIR / path.lstrip("/")).resolve()
            if DASHBOARD_DIR not in file.parents or not file.is_file():
                self.send(404, "not found\n", "text/plain")
                return
            self.send(200, file.read_bytes(), CONTENT_TYPES.get(file.suffix, "application/octet-stream"))

    return Handler


# Serves the dashboard, /metrics and the JSON API in a background thread.
def start_server(state, port, tests_dir=TESTS_DIR):
    catalog = None
    if tests_dir is not None and Path(tests_dir).is_dir():
        catalog = TestCatalog(tests_dir)
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(state, catalog))
    thread = threading.Thread(target=server.serve_forever, name="aegis-http", daemon=True)
    thread.start()
    logger.info("Dashboard on http://localhost:%s  (metrics on /metrics)", port)
    return server
