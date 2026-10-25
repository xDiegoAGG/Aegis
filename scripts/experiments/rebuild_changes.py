import csv
import json
from cluster import replica_changes
from load import read_profile, total_duration
from metrics import false_alarms, needed_pod_minutes, requested_at
from run import metric_path_delays
from settings import TESTS, TESTS_DIR


# Pods and events of a saved run, read back from its timeline (times in seconds since k6 started).
def timeline_inputs(path):
    pods = {}
    events = []
    aegis = []
    for row in csv.DictReader(open(path)):
        moment = float(row["seconds"])
        if row["source"] == "pod" and row["event"] == "created":
            pods[row["detail"]] = {"created": moment}
        elif row["source"] == "kubernetes":
            kind, _, name = row["detail"].split(":", 1)[0].partition("/")
            events.append({"time": moment, "reason": row["event"], "kind": kind, "name": name})
        elif row["source"] == "aegis" and row["event"].startswith("scale_up"):
            target = int(row["event"].split("->")[1])
            aegis.append({"time": moment, "action": "scale_up", "target": target})
    return pods, events, aegis


# Rebuilds the HPA replica changes of the saved HPA-only and metric-mode runs from their timelines.
def rebuild(name):
    profile_name, mode, _ = TESTS[name]
    if mode == "aegis":
        return
    for path in sorted((TESTS_DIR / name / "data").glob("run-*-summary.json")):
        summary = json.loads(path.read_text())
        prefix = str(path).replace("-summary.json", "")
        rows = list(csv.DictReader(open(prefix + ".csv")))
        since = float(rows[0]["seconds"])
        pods, events, aegis = timeline_inputs(prefix + "-timeline.csv")
        changes = replica_changes(pods, events, since)
        profile = read_profile(profile_name, summary["capacity_rps"])
        ups = [{"s": round(c["time"], 1), "from": c["from"], "to": c["to"]} for c in changes if c["to"] > c["from"]]
        downs = [{"s": round(c["time"], 1), "from": c["from"], "to": c["to"]} for c in changes if c["to"] < c["from"]]
        replicas = [requested_at(changes, second) for second in range(int(total_duration(profile)))]
        summary.update({
            "first_scale_up_s": ups[0]["s"] if ups else None, "scale_ups": ups, "scale_downs": downs,
            "max_pods": max([1] + replicas), "pod_minutes": round(sum(replicas) / 60, 2),
            "false_scale_ups": false_alarms(ups, profile, summary["capacity_rps"]),
        })
        summary["extra_pod_minutes"] = round(summary["pod_minutes"] - needed_pod_minutes(profile, summary["capacity_rps"]), 2)
        if mode == "metric":
            summary["metric_path_delays_s"] = metric_path_delays(aegis, changes)
        path.write_text(json.dumps(summary, indent=2))
        for row in rows:
            row["requested"] = requested_at(changes, float(row["seconds"]) + 2.5)
        with open(prefix + ".csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(name, "run", summary["run"], [(u["s"], u["from"], u["to"]) for u in ups + downs])


if __name__ == "__main__":
    for test in TESTS:
        rebuild(test)
