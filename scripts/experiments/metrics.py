import datetime
from load import first_crossing, percentile, summary_value, total_duration
from settings import BEFORE_SECONDS, L_SECONDS, MAX_FAILED_RATIO, STEP, SUSTAINED_BUCKETS


def utc(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%H:%M:%S")


def utc_date(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y-%m-%d")


def requested_at(changes, timestamp):
    replicas = 1
    for change in changes:
        if change["time"] <= timestamp:
            replicas = change["to"]
    return replicas


# Seconds the client saw the service degraded (P95 above L or over 1% failed, for at least T_d).
def degraded_time(buckets, k6_start):
    degraded = 0
    first = None
    streak = 0
    for timestamp in sorted(buckets):
        bucket = buckets[timestamp]
        bad = False
        if bucket["durations"] and percentile(bucket["durations"], 0.95) > L_SECONDS:
            bad = True
        if bucket["requests"] and bucket["failed"] / bucket["requests"] > MAX_FAILED_RATIO:
            bad = True
        if not bad:
            streak = 0
            continue
        streak += 1
        if streak == SUSTAINED_BUCKETS:
            degraded += SUSTAINED_BUCKETS * STEP
            if first is None:
                first = timestamp - (SUSTAINED_BUCKETS - 1) * STEP - k6_start
        elif streak > SUSTAINED_BUCKETS:
            degraded += STEP
    return degraded, first


def second_pod_ready(pods, k6_start):
    first = None
    for name, times in pods.items():
        if times["created"] >= k6_start - BEFORE_SECONDS and times["ready"] is not None:
            moment = times["ready"] - k6_start
            if first is None or moment < first:
                first = round(moment, 1)
    return first


# The numbers of one run that go into the tables.
def summarize(run_number, profile, mode, k6_start, buckets, logs, changes, calibration, pods, window_end):
    capacity = float(calibration["capacity_rps"])
    durations = []
    requests = 0
    failed = 0
    for bucket in buckets.values():
        durations.extend(bucket["durations"])
        requests += bucket["requests"]
        failed += bucket["failed"]
    degraded, first_degraded = degraded_time(buckets, k6_start)
    ups = []
    downs = []
    for change in changes:
        entry = {"s": round(change["time"] - k6_start, 1), "from": change["from"], "to": change["to"]}
        if change["to"] > change["from"]:
            ups.append(entry)
        else:
            downs.append(entry)
    first_up = None
    if ups:
        first_up = ups[0]["s"]
    ready = second_pod_ready(pods, k6_start)
    crosses = first_crossing(profile, capacity)
    lead = None
    if crosses is not None and ready is not None:
        lead = round(crosses - ready, 1)
    pod_seconds = 0
    max_pods = 1
    second = 0
    while second < total_duration(profile):
        replicas = requested_at(changes, k6_start + second)
        max_pods = max(max_pods, replicas)
        pod_seconds += replicas
        second += 1
    return {
        "run": run_number,
        "profile": profile["name"],
        "mode": mode,
        "date_utc": utc_date(k6_start),
        "k6_start_utc": utc(k6_start),
        "end_utc": utc(window_end),
        "capacity_rps": capacity,
        "startup_time_seconds": calibration["startup_time_seconds"],
        "requests": requests,
        "failed_percent": round(100 * failed / max(1, requests), 2),
        "client_p95_s": round(percentile(durations, 0.95), 3),
        "client_max_s": round(max(durations), 3),
        "dropped_iterations": int(float(summary_value(logs, "dropped_iterations"))),
        "degraded_seconds": degraded,
        "first_degraded_s": first_degraded,
        "crosses_c_s": crosses,
        "first_scale_up_s": first_up,
        "second_pod_ready_s": ready,
        "lead_s": lead,
        "scale_ups": ups,
        "scale_downs": downs,
        "max_pods": max_pods,
        "pod_minutes": round(pod_seconds / 60, 2),
    }
