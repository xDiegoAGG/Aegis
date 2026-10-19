import json
import signal
import subprocess
import sys
import time
from settings import ROOT


# Starts Aegis as a separate process that writes its NDJSON log, and waits for its first cycle.
def start_aegis(log_path, console_path):
    console = open(console_path, "w")
    process = subprocess.Popen([sys.executable, "-m", "aegis.actuator", "--log", str(log_path)],
                               cwd=ROOT / "app", stdout=console, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Aegis stopped at start, see " + str(console_path))
        if log_path.exists() and log_path.stat().st_size > 0:
            return process, console
        time.sleep(1)
    raise RuntimeError("Aegis did not start in time")


def stop_aegis(process, console):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(20)
        except subprocess.TimeoutExpired:
            process.kill()
    console.close()


def read_ndjson(path):
    records = []
    if not path.exists():
        return records
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


# Replica changes Aegis decided, from its log.
def aegis_scale_changes(records):
    changes = []
    for record in records:
        if record["action"] != "hold":
            changes.append({"time": record["time"], "from": record["previous_target"], "to": record["target"]})
    return changes
