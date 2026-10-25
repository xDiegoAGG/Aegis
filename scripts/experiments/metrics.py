import datetime
import math
from load import first_crossing, percentile, planned_rate, summary_value, total_duration
from settings import (BEFORE_SECONDS, CONFIG, FALSE_ALARM_SECONDS, L_SECONDS, MAX_FAILED_RATIO, STEP,
                      SUSTAINED_BUCKETS)


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


# Area of the client P95 above L, in s x s: how far and for how long the service was slow.
def p95_excess_area(buckets):
    area = 0.0
    for bucket in buckets.values():
        if bucket["durations"]:
            area += max(0.0, percentile(bucket["durations"], 0.95) - L_SECONDS) * STEP
    return round(area, 1)


# Pod-minutes the planned traffic needed: ceil(planned / C) pods every second, between 1 and max_replicas.
def needed_pod_minutes(profile, capacity):
    pod_seconds = 0
    second = 0
    while second < total_duration(profile):
        pods = math.ceil(planned_rate(profile, second) / capacity)
        pod_seconds += max(1, min(CONFIG["kubernetes"]["max_replicas"], pods))
        second += 1
    return round(pod_seconds / 60, 2)


# Scale-ups the planned traffic did not need: it never went over the pods before them in FALSE_ALARM_SECONDS.
def false_alarms(ups, profile, capacity):
    count = 0
    for up in ups:
        needed = False
        second = max(0.0, up["s"])
        while second <= up["s"] + FALSE_ALARM_SECONDS:
            if planned_rate(profile, second) > capacity * up["from"]:
                needed = True
                break
            second += 1
        if not needed:
            count += 1
    return count


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
    degraded_to_ready = None
    if first_degraded is not None and ready is not None:
        degraded_to_ready = round(ready - first_degraded, 1)
    pod_seconds = 0
    max_pods = 1
    second = 0
    while second < total_duration(profile):
        replicas = requested_at(changes, k6_start + second)
        max_pods = max(max_pods, replicas)
        pod_seconds += replicas
        second += 1
    needed = needed_pod_minutes(profile, capacity)
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
        "p95_excess_s2": p95_excess_area(buckets),
        "degraded_to_ready_s": degraded_to_ready,
        "false_scale_ups": false_alarms(ups, profile, capacity),
        "needed_pod_minutes": needed,
        "extra_pod_minutes": round(pod_seconds / 60 - needed, 2),
    }
