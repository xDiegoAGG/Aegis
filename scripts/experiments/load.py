import csv
import gzip
import math
import re
import subprocess
import time
from cluster import kubectl
from settings import PROFILES, REFERENCE_CAPACITY_RPS, STEP

RATE_FIELDS = r"(startRate|target|preAllocatedVUs|maxVUs):(\s*)(\d+)"


# Multiplies rates and VUs by scale; durations stay.
def scaled_text(text, scale):
    def replace(match):
        return match.group(1) + ":" + match.group(2) + str(max(1, int(round(int(match.group(3)) * scale))))
    return re.sub(RATE_FIELDS, replace, text)


# Stages of a load file, rates scaled to capacity_rps.
def read_profile(name, capacity_rps=REFERENCE_CAPACITY_RPS):
    scale = float(capacity_rps) / REFERENCE_CAPACITY_RPS
    text = scaled_text(PROFILES[name].read_text(), scale)
    stages = []
    for target, duration in re.findall(r"target:\s*(\d+),\s*duration:\s*'(\d+)s'", text):
        stages.append((float(target), float(duration)))
    start_rate = float(re.search(r"startRate:\s*(\d+)", text).group(1))
    return {"name": name, "job": "load-" + name, "file": PROFILES[name], "start_rate": start_rate, "stages": stages,
            "scale": round(scale, 3), "text": text}


def total_duration(profile):
    total = 0.0
    for target, duration in profile["stages"]:
        total += duration
    return total


# Requests per second k6 is told to send at a moment of the run (linear between stages).
def planned_rate(profile, seconds):
    rate = profile["start_rate"]
    elapsed = 0.0
    for target, duration in profile["stages"]:
        if seconds < elapsed + duration:
            return rate + (target - rate) * (seconds - elapsed) / duration
        rate = target
        elapsed += duration
    return 0.0


def first_crossing(profile, level):
    seconds = 0.0
    while seconds <= total_duration(profile):
        if planned_rate(profile, seconds) >= level:
            return round(seconds, 1)
        seconds += 0.5
    return None


# Foreground, so wait_k6 never reads the previous run's pod.
def start_load(profile):
    kubectl(["delete", "job", profile["job"], "--ignore-not-found", "--wait=true", "--cascade=foreground"])
    result = subprocess.run(["kubectl", "apply", "-f", "-"], input=profile["text"].encode(), capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("kubectl apply of " + profile["name"] + ": " + result.stderr.decode().strip())


# Waits until k6 printed its summary and returns the pod name and its log.
def wait_k6(profile):
    deadline = time.monotonic() + total_duration(profile) + 300
    while time.monotonic() < deadline:
        pod = kubectl(["get", "pods", "-l", "job-name=" + profile["job"], "-o", "jsonpath={.items[0].metadata.name}"],
                      False).decode().strip()
        if pod:
            logs = kubectl(["logs", pod], False).decode()
            if "K6_FINISHED" in logs:
                return pod, logs
        time.sleep(10)
    raise RuntimeError("k6 did not finish in time")


# k6 requests in STEP-second buckets: durations, count, failures.
def client_buckets(pod):
    data = kubectl(["exec", pod, "--", "cat", "/results/requests.csv.gz"])
    buckets = {}
    first = None
    for row in csv.DictReader(gzip.decompress(data).decode().splitlines()):
        name = row["metric_name"]
        if name != "http_req_duration" and name != "http_req_failed":
            continue
        timestamp = int(row["timestamp"])
        if first is None or timestamp < first:
            first = timestamp
        entry = buckets.setdefault(timestamp - timestamp % STEP, {"durations": [], "requests": 0, "failed": 0})
        if name == "http_req_duration":
            entry["durations"].append(float(row["metric_value"]) / 1000)
        else:
            entry["requests"] += 1
            if float(row["metric_value"]) > 0:
                entry["failed"] += 1
    return first, buckets


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


# A number from the k6 end-of-test summary, like dropped_iterations.
def summary_value(logs, name):
    for line in logs.splitlines():
        stripped = line.strip()
        if stripped.startswith(name + "."):
            parts = stripped.split(":", 1)[1].split()
            if parts:
                return parts[0]
    return "0"
