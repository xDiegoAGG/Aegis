import argparse
import csv
import json
import time
from aegis_process import aegis_scale_changes, read_ndjson, start_aegis, stop_aegis
from cluster import hpa_scale_changes, kubectl, pod_times, range_values, read_calibration, reset, say
from load import client_buckets, percentile, planned_rate, read_profile, start_load, total_duration, wait_k6
from metrics import requested_at, summarize, utc
from pathlib import Path
from settings import AFTER_SECONDS, BEFORE_SECONDS, CONFIG, COOLDOWN_SECONDS, RUNS_PER_TEST, STEP, TESTS, TESTS_DIR

QUERY_SERVED_PODS = 'sum(rate(http_request_duration_seconds_count{route="/"}[30s]))'
CSV_COLUMNS = ["seconds", "time_utc", "planned_rps", "client_rps", "client_p95_s", "client_failed_ratio",
               "demand_rps", "served_rps", "requested", "ready", "aegis_projected_rps", "aegis_sigma_rps",
               "aegis_risk", "aegis_target"]


def blank(value, decimals):
    if value is None:
        return ""
    if decimals is None:
        return value
    return round(value, decimals)


# One row every STEP seconds with what k6, Prometheus and Aegis saw.
def write_run_csv(path, profile, k6_start, buckets, records, changes, window_start, window_end):
    demand = range_values(CONFIG["prometheus"]["query_rps"], window_start, window_end)
    served = range_values(QUERY_SERVED_PODS, window_start, window_end)
    ready = range_values(CONFIG["prometheus"]["query_replicas_ready"], window_start, window_end)
    aegis = {}
    for record in records:
        aegis[int(record["time"] // STEP * STEP)] = record
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for timestamp in range(window_start, window_end + 1, STEP):
            seconds = timestamp - k6_start
            planned = ""
            if 0 <= seconds <= total_duration(profile):
                planned = round(planned_rate(profile, seconds), 2)
            client = ["", "", ""]
            bucket = buckets.get(timestamp)
            if bucket is not None and bucket["durations"]:
                failed = 0.0
                if bucket["requests"]:
                    failed = bucket["failed"] / bucket["requests"]
                client = [round(len(bucket["durations"]) / STEP, 2), round(percentile(bucket["durations"], 0.95), 3),
                          round(failed, 4)]
            record = aegis.get(timestamp, {})
            writer.writerow([seconds, utc(timestamp), planned] + client + [
                blank(demand.get(timestamp), 2), blank(served.get(timestamp), 2),
                requested_at(changes, timestamp + STEP / 2), blank(ready.get(timestamp), 0),
                blank(record.get("projected_rps"), None), blank(record.get("sigma_rps"), None),
                blank(record.get("risk"), None), blank(record.get("target"), None)])


# One full run: reset, Aegis on or off, load, then the data from k6, Prometheus and Aegis.
def run_once(folder, profile, mode, run_number, calibration):
    data_dir = folder / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    prefix = str(data_dir / ("run-" + str(run_number)))
    reset(mode)
    time.sleep(COOLDOWN_SECONDS)
    ndjson = Path(prefix + "-aegis.ndjson")
    if ndjson.exists():
        ndjson.unlink()
    process = None
    console = None
    if mode == "aegis":
        process, console = start_aegis(ndjson, Path(prefix + "-aegis.log"))
        time.sleep(10)
    try:
        start_load(profile)
        say("run", run_number, "started:", profile["name"], "load,", mode)
        pod, logs = wait_k6(profile)
        k6_start, buckets = client_buckets(pod)
        say("k6 finished, watching", AFTER_SECONDS[mode], "s more")
        time.sleep(AFTER_SECONDS[mode])
    finally:
        if process is not None:
            stop_aegis(process, console)
    window_start = int((k6_start - BEFORE_SECONDS) // STEP * STEP)
    window_end = int(time.time() // STEP * STEP)
    Path(prefix + "-k6.log").write_text(logs)
    kubectl(["delete", "job", profile["job"], "--ignore-not-found"])
    records = read_ndjson(ndjson)
    if mode == "aegis":
        changes = aegis_scale_changes(records)
    else:
        changes = hpa_scale_changes(window_start)
    write_run_csv(prefix + ".csv", profile, k6_start, buckets, records, changes, window_start, window_end)
    summary = summarize(run_number, profile, mode, k6_start, buckets, logs, changes, calibration,
                        pod_times(window_start, window_end), window_end)
    Path(prefix + "-summary.json").write_text(json.dumps(summary, indent=2))
    say("run", run_number, "done: failed", summary["failed_percent"], "%, degraded", summary["degraded_seconds"],
        "s, 2nd pod Ready at", summary["second_pod_ready_s"], "s, traffic over C at", summary["crosses_c_s"], "s")


# Runs the missing runs of a test; a run that fails is tried once more.
def run_test(name, runs, first_run):
    profile_name, mode, title = TESTS[name]
    folder = TESTS_DIR / name
    profile = read_profile(profile_name)
    calibration = read_calibration()
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    (TESTS_DIR / "calibration.json").write_text(json.dumps(calibration, indent=2))
    for run_number in range(first_run, runs + 1):
        if (folder / "data" / ("run-" + str(run_number) + "-summary.json")).exists():
            say(name, "run", run_number, "already done, skipped")
            continue
        for attempt in (1, 2):
            try:
                run_once(folder, profile, mode, run_number, calibration)
                break
            except Exception as error:
                say(name, "run", run_number, "attempt", attempt, "failed:", error)
                if attempt == 2:
                    raise
    reset("aegis")


def main():
    parser = argparse.ArgumentParser(description="Run one Aegis test: N runs with the same load")
    parser.add_argument("test", choices=list(TESTS))
    parser.add_argument("--runs", type=int, default=RUNS_PER_TEST)
    parser.add_argument("--start", type=int, default=1, help="first run number, to resume")
    args = parser.parse_args()
    run_test(args.test, args.runs, args.start)


if __name__ == "__main__":
    main()
