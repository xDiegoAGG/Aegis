import csv
from load import total_duration
from metrics import utc

TIMELINE_COLUMNS = ["seconds", "time_utc", "source", "event", "detail"]


# Every step of a run on one clock: load, Aegis decisions, Kubernetes events, pods and the client's view.
def write_timeline(path, profile, k6_start, records, events, pods, summary):
    rows = [(k6_start, "k6", "load started", profile["name"]),
            (k6_start + total_duration(profile), "k6", "load finished", "")]
    for record in records:
        if record["action"] == "hold":
            continue
        rows.append((record["time"], "aegis", record["action"] + " " + str(record["previous_target"]) + "->"
                     + str(record["target"]), "risk " + str(record["risk"]) + ": " + record["reason"]))
    for event in events:
        rows.append((event["time"], "kubernetes", event["reason"], event["kind"] + "/" + event["name"] + ": "
                     + event["message"]))
    for name, times in pods.items():
        rows.append((times["created"], "pod", "created", name))
        if times["ready"] is not None:
            rows.append((times["ready"], "pod", "ready", name))
    if summary["first_degraded_s"] is not None:
        rows.append((k6_start + summary["first_degraded_s"], "client", "degraded",
                     "P95 above L or over 1% failed for T_d"))
    if summary["crosses_c_s"] is not None:
        rows.append((k6_start + summary["crosses_c_s"], "k6", "planned traffic passes C",
                     str(summary["capacity_rps"]) + " req/s"))
    rows.sort(key=lambda row: row[0])
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(TIMELINE_COLUMNS)
        for moment, source, event, detail in rows:
            writer.writerow([round(moment - k6_start, 1), utc(moment), source, event, detail])
