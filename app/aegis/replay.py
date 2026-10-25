import argparse
import json
import logging
import re
import signal
import threading
import time
from aegis.config import load_config
from aegis.server import TESTS_DIR, AegisState, read_ndjson, start_server
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_RUN = TESTS_DIR / "test1-linear-ramp" / "data" / "run-4-aegis.ndjson"


# The same parameters a live Aegis shows, from config.yaml and the calibration the run used.
def build_meta(config, records, calibration, source, speed):
    thresholds = config["risk_thresholds"]
    sampling = config["sampling"]
    kubernetes = config["kubernetes"]
    capacity = None
    startup = None
    calibrated_at = None
    if calibration is not None:
        capacity = float(calibration["capacity_rps"])
        startup = float(calibration["startup_time_seconds"])
        calibrated_at = calibration.get("measured_at")
    if capacity is None and records:
        capacity = records[0]["capacity_rps"] / max(1, records[0]["previous_target"])
    return {
        "mode": "replay",
        "actuator_mode": "min_replicas",
        "source": source,
        "speed": speed,
        "namespace": kubernetes["namespace"],
        "deployment": kubernetes["deployment_name"],
        "hpa_name": kubernetes["hpa_name"],
        "min_replicas": kubernetes["min_replicas"],
        "max_replicas": kubernetes["max_replicas"],
        "pod_capacity_rps": capacity,
        "startup_time_seconds": startup,
        "metric_lag_seconds": sampling["metric_lag_seconds"],
        "projection_window_seconds": sampling["projection_window_seconds"],
        "interval_seconds": sampling["interval_seconds"],
        "p95_threshold_seconds": config["degradation"]["p95_threshold_seconds"],
        "sustained_seconds": config["degradation"]["sustained_seconds"],
        "scale_up_threshold": thresholds["scale_up"],
        "scale_down_threshold": thresholds["scale_down"],
        "scale_down_sustained_seconds": thresholds["scale_down_sustained_seconds"],
        "calibrated_at": calibrated_at,
        "started_at": time.time(),
    }


# Plays recorded runs on the dashboard at `speed` times their real pace; the dashboard can switch the run.
class Replayer:
    def __init__(self, state, config, calibration, speed, loop):
        self.state = state
        self.config = config
        self.calibration = calibration
        self.speed = speed
        self.loop = loop
        self.generation = 0
        self.lock = threading.Lock()
        state.select = self.select

    # Only runs saved under docs/tests with an Aegis log can be chosen.
    def select(self, test, run):
        if not re.fullmatch(r"test[\w-]+", test) or run < 1:
            return "unknown run"
        path = TESTS_DIR / test / "data" / ("run-" + str(run) + "-aegis.ndjson")
        if not path.is_file():
            return "no Aegis log for " + test + " run " + str(run)
        self.play(path)
        return None

    def play(self, path):
        records = read_ndjson(path)
        if not records:
            return
        source = path.parent.parent.name + "/" + path.name if path.parent.name == "data" else path.name
        with self.lock:
            self.generation += 1
            generation = self.generation
        meta = build_meta(self.config, records, self.calibration, source, self.speed)
        logger.info("Replaying %s cycles of %s at x%s", len(records), source, self.speed)
        threading.Thread(target=self.feed, args=(records, meta, generation), daemon=True).start()

    def feed(self, records, meta, generation):
        while True:
            with self.lock:
                if generation != self.generation:
                    return
                self.state.restart(meta)
            previous = None
            for record in records:
                if previous is not None:
                    time.sleep(max(0.0, (record["time"] - previous) / self.speed))
                with self.lock:
                    if generation != self.generation:
                        return
                    self.state.push(record)
                previous = record["time"]
            if not self.loop:
                logger.info("Replay finished; the dashboard keeps the whole run")
                return
            time.sleep(5)


def stop(signum, frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description="Show a recorded Aegis run (NDJSON) on the dashboard")
    parser.add_argument("log", nargs="?", default=str(DEFAULT_RUN), help="Aegis NDJSON log of a run")
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed (default: real time)")
    parser.add_argument("--loop", action="store_true", help="start over when the run ends")
    parser.add_argument("--port", type=int, help="port of the dashboard (default: server.port)")
    parser.add_argument("--calibration", default=str(TESTS_DIR / "calibration.json"),
                        help="calibration.json the run used (C and T)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, stop)

    config = load_config()
    path = Path(args.log)
    records = read_ndjson(path)
    if not records:
        logger.error("No cycles in %s", path)
        return
    calibration = None
    if Path(args.calibration).exists():
        calibration = json.loads(Path(args.calibration).read_text())
    source = path.name
    if path.parent.name == "data":
        source = path.parent.parent.name + "/" + path.name
    state = AegisState(build_meta(config, records, calibration, source, args.speed))
    start_server(state, args.port or config.get("server", {}).get("port", 8080), TESTS_DIR)
    Replayer(state, config, calibration, args.speed, args.loop).play(path)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Replay stopped")


if __name__ == "__main__":
    main()
