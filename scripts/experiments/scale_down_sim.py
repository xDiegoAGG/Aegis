"""Scale-down rules compared offline, without the cluster.

The demand of every recorded Aegis run (and synthetic traffic with short dips and bursts, which the
recorded runs lack) goes through the real RiskCalculator; only the scale-down rule changes. Scale-up is
the same in every rule (risk >= 70%). The rule "several pods, wait by risk" is the one in
app/aegis/decision.py; the script checks that the real engine takes the same decisions.

Model, the same for every rule:
- Demand at t = the rps Aegis logged LAG s later (its 30 s rate shows the traffic of ~20 s before).
- A requested pod serves T = 15 s after the request; a removed pod stops at once.
- Cost = requested pods x time, from k6 start to the end of the run.
- Short = seconds with demand > C x serving pods.
Limitation: the demand is the one measured in the real run; with other decisions the overload, and so
the measured demand, could have been slightly different. Failed requests are not simulated.

Usage: python3 scripts/experiments/scale_down_sim.py [--json out.json]
"""
import argparse
import datetime
import json
import random
import sys
from settings import CONFIG, ROOT, TESTS_DIR

sys.path.insert(0, str(ROOT / "app"))
from aegis.collector import Sample  # noqa: E402
from aegis.decision import DecisionEngine  # noqa: E402
from aegis.risk import RiskCalculator  # noqa: E402

UP = CONFIG["risk_thresholds"]["scale_up"]
DOWN = CONFIG["risk_thresholds"]["scale_down"]
LAG = CONFIG["sampling"]["metric_lag_seconds"]
STEP = CONFIG["sampling"]["interval_seconds"]
MIN_R, MAX_R = CONFIG["kubernetes"]["min_replicas"], CONFIG["kubernetes"]["max_replicas"]
STARTUP = 15


class Rule:
    """wait(highest risk while low) -> seconds; multi: go straight to the smallest allowed pod count."""

    def __init__(self, name, wait, multi=False):
        self.name, self.wait, self.multi = name, wait, multi

    def run(self, results, start_target):
        target = start_target
        low = {}  # pods -> [since, highest risk while low]
        plan = []
        for now, result in results:
            action = "hold"
            if result is None:
                low.clear()
            elif result.risk_at(target) >= UP:
                low.clear()
                if target < MAX_R:
                    target += 1
                    action = "up"
            elif target > MIN_R:
                for k in range(MIN_R, target):
                    r = result.risk_at(k)
                    if r >= DOWN:
                        low.pop(k, None)
                    elif k in low:
                        low[k][1] = max(low[k][1], r)
                    else:
                        low[k] = [now, r]
                allowed = [k for k, (since, top) in low.items() if k < target and now - since >= self.wait(top)]
                new = min(allowed) if self.multi and allowed else (target - 1 if target - 1 in allowed else None)
                if new is not None:
                    target = new
                    low.clear()
                    action = "down"
            else:
                low.clear()
            plan.append((now, target, action))
        return plan


def by_risk(top):
    return 15 + 45 * min(1.0, top / DOWN)


RULES = [
    Rule("fixed 60 s, -1 (Oct 2026)", lambda top: 60),
    Rule("fixed 30 s, -1", lambda top: 30),
    Rule("fixed 15 s, -1", lambda top: 15),
    Rule("wait by risk, -1", by_risk),
    Rule("several pods, 60 s", lambda top: 60, multi=True),
    Rule("several pods, wait by risk (current)", by_risk, multi=True),
]


def evaluate(records, plan, capacity, window):
    times = [r["time"] for r in records]
    rps = [r["rps"] for r in records]

    def demand(t):
        i = min(range(len(times)), key=lambda j: abs(times[j] - (t + LAG)))
        return rps[i] if abs(times[i] - (t + LAG)) <= STEP and rps[i] is not None else None

    starting = []
    serving = previous = plan[0][1]
    cost = short = 0.0
    ups = downs = 0
    for i, (now, target, action) in enumerate(plan):
        dt = plan[i + 1][0] - now if i + 1 < len(plan) else STEP
        if action == "up":
            ups += 1
            starting.append(now + STARTUP)
        if action == "down":
            downs += 1
            drop = previous - target
            cancelled = min(drop, len(starting))
            starting = starting[cancelled:]
            serving -= drop - cancelled
        while starting and starting[0] <= now:
            starting.pop(0)
            serving += 1
        previous = target
        if window[0] <= now <= window[1]:
            cost += target * dt
        d = demand(now)
        if d is not None and d > capacity * serving + 0.5:
            short += dt
    return {"pod_minutes": cost / 60, "short_s": short, "ups": ups, "downs": downs}


def calculator(capacity):
    config = json.loads(json.dumps(CONFIG))
    config["capacity_rps"] = capacity
    config["startup_time_seconds"] = STARTUP
    return config, RiskCalculator.from_config(config)


def recorded_runs(capacity):
    for folder in sorted(TESTS_DIR.glob("test*")):
        for log in sorted((folder / "data").glob("run-*-aegis.ndjson")):
            records = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
            summary = json.loads((folder / "data" / log.name.replace("-aegis.ndjson", "-summary.json")).read_text())
            stamp = lambda hms: datetime.datetime.fromisoformat(summary["date_utc"] + "T" + hms + "+00:00").timestamp()
            start, end = stamp(summary["k6_start_utc"]), stamp(summary["end_utc"])
            yield folder.name, records, (start, end if end >= start else end + 86400)


# Traffic the recorded runs lack: 40 req/s with 30-60 s dips to 12, or 15 req/s with 40 s bursts to 45.
def synthetic(kind, seed):
    rnd = random.Random(seed)
    raw = []
    for t in range(0, 900, STEP):
        if kind == "dips":
            base = 12 if t > 60 and (t % 150) < 30 + 30 * ((t // 150) % 2) else 40
        else:
            base = 45 if t > 60 and (t % (120 + 60 * ((t // 180) % 2))) < 40 else 15
        raw.append(max(0.0, base + rnd.gauss(0, 2.5)))
    records = []
    for i, _ in enumerate(raw):  # the 30 s rate Aegis reads smooths the traffic
        window = raw[max(0, i - 5): i + 1]
        records.append({"time": 1e6 + i * STEP, "rps": sum(window) / len(window), "p95_s": 0.2, "replicas_ready": 1,
                        "previous_target": 1})
    return records


def results_for(records, capacity):
    _, calc = calculator(capacity)
    return [(r["time"], calc.update(Sample(r["time"], r["rps"], r["p95_s"], r["replicas_ready"]))) for r in records]


def table(groups):
    rows = []
    for group, runs in groups.items():
        base = None
        print(f"\n{group}  ({len(runs)} runs)")
        print(f"  {'rule':40} {'pod-min':>8} {'saving':>7} {'s short':>14} {'ups':>5} {'downs':>6}")
        for rule in RULES:
            scores = [score[rule.name] for score in runs]
            mean = {k: sum(s[k] for s in scores) / len(scores) for k in scores[0]}
            base = base or mean
            saving = 100 * (base["pod_minutes"] - mean["pod_minutes"]) / base["pod_minutes"]
            print(f"  {rule.name:40} {mean['pod_minutes']:8.2f} {saving:6.1f}% {mean['short_s']:6.0f} ({mean['short_s'] - base['short_s']:+4.0f})"
                  f" {mean['ups']:5.1f} {mean['downs']:6.1f}")
            rows.append(dict(group=group, rule=rule.name, runs=len(runs), saving_percent=round(saving, 1),
                             **{k: round(v, 2) for k, v in mean.items()}))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the table here")
    args = parser.parse_args()
    # The recorded traces are the October 2026 runs, recorded with this calibration.
    capacity = float(json.loads((TESTS_DIR / "calibration-2026-10-25.json").read_text())["capacity_rps"])
    groups = {}
    mismatches = 0
    for test, records, window in recorded_runs(capacity):
        results = results_for(records, capacity)
        score = {}
        for rule in RULES:
            plan = rule.run(results, records[0]["previous_target"])
            score[rule.name] = evaluate(records, plan, capacity, window)
        config, _ = calculator(capacity)
        engine = DecisionEngine.from_config(config, records[0]["previous_target"])
        if [engine.decide(r, t).target for t, r in results] != [p[1] for p in RULES[-1].run(results, records[0]["previous_target"])]:
            mismatches += 1
        groups.setdefault(test, []).append(score)
    for kind in ["dips", "bursts"]:
        for seed in range(20):
            records = synthetic(kind, seed)
            results = results_for(records, 22.0)
            groups.setdefault("synthetic " + kind, []).append(
                {rule.name: evaluate(records, rule.run(results, 1), 22.0, (0, 1e12)) for rule in RULES})
    print(f"decision.py against the simulated current rule: {mismatches} recorded runs differ")
    rows = table(groups)
    if args.json:
        with open(args.json, "w") as out:
            json.dump(rows, out, indent=1)


if __name__ == "__main__":
    main()
