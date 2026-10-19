import csv
import datetime
import gzip
import json
import math
import subprocess
import sys
import time

# Copies the per-request results of a k6 Job (kubernetes/k6-ramp-demo) and turns them into
# client-side latency every 5 s: what the user feels, including requests that waited outside a
# saturated pod (the service's own P95 does not see those, test 14).
# Usage: python3 scripts/fetch_k6_results.py output_path [--job k6-ramp-demo] [--keep]
#   writes output_path.csv (time series) and output_path-summary.json; deletes the Job unless --keep.

BUCKET_SECONDS = 5
P95_THRESHOLD_S = 1.0       # L, as in app/config.yaml (degradation.p95_threshold_seconds)
SUSTAINED_SECONDS = 15      # T_d, as in app/config.yaml (degradation.sustained_seconds)
RESULTS_FILE = "/results/requests.csv.gz"
WAIT_SECONDS = 900


def kubectl(args):
    return subprocess.run(["kubectl"] + args, capture_output=True)


def job_pod(job):
    result = kubectl(["get", "pods", "-l", "job-name=" + job, "-o", "jsonpath={.items[0].metadata.name}"])
    return result.stdout.decode().strip()


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def utc_text(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%H:%M:%S")


def wait_until_finished(job):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        pod = job_pod(job)
        if pod:
            logs = kubectl(["logs", pod]).stdout.decode()
            if "K6_FINISHED" in logs:
                return pod, logs
        time.sleep(5)
    print("k6 did not finish in", WAIT_SECONDS, "s")
    sys.exit(1)


def summary_value(logs, name):
    # Line like "dropped_iterations.............: 20     0.08/s"
    for line in logs.splitlines():
        stripped = line.strip()
        if stripped.startswith(name + "."):
            parts = stripped.split(":", 1)[1].split()
            if parts:
                return parts[0]
    return None


def main():
    args = sys.argv[1:]
    job = "k6-ramp-demo"
    keep = False
    if "--job" in args:
        index = args.index("--job")
        job = args[index + 1]
        del args[index:index + 2]
    if "--keep" in args:
        keep = True
        args.remove("--keep")
    if len(args) != 1:
        print("Usage: python3 scripts/fetch_k6_results.py output_path [--job k6-ramp-demo] [--keep]")
        sys.exit(1)
    out = args[0]

    pod, logs = wait_until_finished(job)
    copied = kubectl(["exec", pod, "--", "cat", RESULTS_FILE])
    if copied.returncode != 0:
        print("Could not copy", RESULTS_FILE, "from", pod, ":", copied.stderr.decode())
        sys.exit(1)
    lines = gzip.decompress(copied.stdout).decode().splitlines()

    # Every request has one http_req_duration row (ms) and one http_req_failed row (1 = failed)
    durations = {}
    failures = {}
    all_durations = []
    total = 0
    failed = 0
    for row in csv.DictReader(lines):
        timestamp = int(row["timestamp"])
        bucket = timestamp - timestamp % BUCKET_SECONDS
        if row["metric_name"] == "http_req_duration":
            seconds = float(row["metric_value"]) / 1000
            durations.setdefault(bucket, []).append(seconds)
            all_durations.append(seconds)
        elif row["metric_name"] == "http_req_failed":
            total += 1
            if float(row["metric_value"]) > 0:
                failed += 1
                failures[bucket] = failures.get(bucket, 0) + 1

    buckets = sorted(durations)
    csv_path = out + ".csv"
    degraded_buckets = 0
    streak = 0
    degraded_sustained_seconds = 0
    first_degraded = None
    needed = math.ceil(SUSTAINED_SECONDS / BUCKET_SECONDS)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_utc", "client_rps", "client_p95_s", "client_failed_ratio"])
        previous = None
        for bucket in buckets:
            values = durations[bucket]
            p95 = percentile(values, 0.95)
            writer.writerow([utc_text(bucket), round(len(values) / BUCKET_SECONDS, 2), round(p95, 3),
                             round(failures.get(bucket, 0) / len(values), 4)])
            # Degraded time: P95 above L in runs of at least T_d (same rule as the calibration)
            if previous is not None and bucket - previous != BUCKET_SECONDS:
                streak = 0
            previous = bucket
            if p95 > P95_THRESHOLD_S:
                degraded_buckets += 1
                streak += 1
                if streak == needed:
                    degraded_sustained_seconds += needed * BUCKET_SECONDS
                    if first_degraded is None:
                        first_degraded = utc_text(bucket - (needed - 1) * BUCKET_SECONDS)
                elif streak > needed:
                    degraded_sustained_seconds += BUCKET_SECONDS
            else:
                streak = 0

    summary = {
        "job": job,
        "start_utc": utc_text(buckets[0]),
        "end_utc": utc_text(buckets[-1] + BUCKET_SECONDS),
        "requests": total,
        "failed": failed,
        "failed_ratio": round(failed / total, 4),
        "p95_s": round(percentile(all_durations, 0.95), 3),
        "p99_s": round(percentile(all_durations, 0.99), 3),
        "max_s": round(max(all_durations), 3),
        "seconds_p95_above_L": degraded_buckets * BUCKET_SECONDS,
        "seconds_degraded_sustained": degraded_sustained_seconds,
        "first_degraded_utc": first_degraded,
        "dropped_iterations": summary_value(logs, "dropped_iterations"),
        "L_s": P95_THRESHOLD_S,
        "T_d_s": SUSTAINED_SECONDS,
    }
    with open(out + "-summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(len(buckets), "rows saved to", csv_path)
    print(json.dumps(summary, indent=2))

    if not keep:
        kubectl(["delete", "job", job, "--wait=false"])
        print("Job", job, "deleted")


if __name__ == "__main__":
    main()
