import argparse
import datetime
import glob
import itertools
import json
import math
import sys
from pathlib import Path
from load import planned_rate, read_profile, total_duration
from metrics import false_alarms
from settings import CONFIG, ROOT, TESTS_DIR

sys.path.insert(0, str(ROOT / "app"))
from aegis.collector import Sample  # noqa: E402
from aegis.decision import SCALE_DOWN, SCALE_UP, DecisionEngine  # noqa: E402
from aegis.risk import RiskResult, SigmaEstimator  # noqa: E402

STEP = CONFIG["sampling"]["interval_seconds"]
WINDOW = CONFIG["sampling"]["projection_window_seconds"]
LAG = CONFIG["sampling"]["metric_lag_seconds"]
GRID_ALPHA = [0.3, 0.5, 0.7, 0.9]
GRID_BETA = [0.1, 0.2, 0.3, 0.5]
GRID_PHI = [0.7, 0.8, 0.85, 0.9, 0.95, 0.98]


def damped_sum(phi, steps):
    return sum(phi ** i for i in range(1, steps + 1))


# Forecasters of the demand `horizon` seconds ahead, fed one sample every STEP seconds.
class Naive:
    name = "naive (r stays)"

    def __init__(self, horizon):
        self.last = None

    def update(self, timestamp, rps):
        self.last = rps
        return rps, 0.0


# What Aegis does: least-squares slope over the last WINDOW seconds, extrapolated; phi < 1 damps the trend.
class LinearTrend:
    def __init__(self, horizon, phi=1.0):
        self.horizon = horizon
        self.phi = phi
        self.window = []
        self.name = "linear trend (Aegis)" if phi == 1.0 else "damped linear trend (phi=" + str(phi) + ")"

    def update(self, timestamp, rps):
        self.window.append((timestamp, rps))
        self.window = [(t, v) for t, v in self.window if t >= timestamp - WINDOW]
        slope = 0.0
        if len(self.window) >= 2:
            times = [t for t, _ in self.window]
            mean_t = sum(times) / len(times)
            mean_v = sum(v for _, v in self.window) / len(self.window)
            den = sum((t - mean_t) ** 2 for t in times)
            if den > 0:
                slope = sum((t - mean_t) * (v - mean_v) for t, v in self.window) / den
        steps = round(self.horizon / STEP)
        gain = self.horizon if self.phi == 1.0 else STEP * damped_sum(self.phi, steps)
        return rps + slope * gain, slope


# Holt's linear method with damped trend (Gardner and McKenzie): level, trend per step, phi damping.
class DampedHolt:
    def __init__(self, horizon, alpha, beta, phi):
        self.horizon = horizon
        self.alpha = alpha
        self.beta = beta
        self.phi = phi
        self.level = None
        self.trend = 0.0
        self.name = "damped Holt (a=" + str(alpha) + ", b=" + str(beta) + ", phi=" + str(phi) + ")"

    def update(self, timestamp, rps):
        if self.level is None:
            self.level = rps
            return rps, 0.0
        previous = self.level
        self.level = self.alpha * rps + (1 - self.alpha) * (previous + self.phi * self.trend)
        self.trend = self.beta * (self.level - previous) + (1 - self.beta) * self.phi * self.trend
        steps = round(self.horizon / STEP)
        return self.level + self.trend * damped_sum(self.phi, steps), self.trend / STEP


def read_ndjson(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def summary_for(log_path):
    path = Path(str(log_path).replace("-aegis.ndjson", "-summary.json"))
    if not path.exists():
        return None
    return json.loads(path.read_text())


def k6_start(summary):
    moment = datetime.datetime.strptime(summary["date_utc"] + " " + summary["k6_start_utc"], "%Y-%m-%d %H:%M:%S")
    return moment.replace(tzinfo=datetime.timezone.utc).timestamp()


# Recorded Aegis runs: demand per cycle and the summary.
def load_runs(pattern):
    runs = []
    for path in sorted(glob.glob(str(TESTS_DIR / pattern))):
        summary = summary_for(path)
        records = [r for r in read_ndjson(path) if r["rps"] is not None]
        if summary is None or len(records) < 20 or summary["mode"] == "hpa":
            continue
        name = str(Path(path).relative_to(TESTS_DIR)).replace("/data/", " ").replace("-aegis.ndjson", "")
        runs.append({"name": name, "records": records, "summary": summary})
    return runs


def horizon_of(summary):
    return summary["startup_time_seconds"] + LAG


# Forecast errors against the demand measured `horizon` seconds later, split by what the traffic did.
def forecast_errors(runs, make):
    groups = {"rising": [], "stable": [], "falling": [], "all": []}
    bias = []
    for run in runs:
        horizon = horizon_of(run["summary"])
        model = make(horizon)
        by_time = {round(r["time"] / STEP) * STEP: r["rps"] for r in run["records"]}
        for record in run["records"]:
            forecast, _ = model.update(record["time"], record["rps"])
            future = by_time.get(round(record["time"] / STEP) * STEP + horizon)
            if future is None or (future < 1 and record["rps"] < 1):
                continue
            error = max(0.0, forecast) - future
            change = future - record["rps"]
            group = "rising" if change > 3 else "falling" if change < -3 else "stable"
            groups[group].append(abs(error))
            groups["all"].append(abs(error))
            bias.append(error)
    result = {key: (sum(v) / len(v) if v else float("nan"), len(v)) for key, v in groups.items()}
    result["bias"] = (sum(bias) / len(bias) if bias else float("nan"), len(bias))
    return result


# The Aegis risk calculator with a different forecaster inside; sigma is learned from that forecaster's errors.
class ReplayCalculator:
    def __init__(self, model, capacity, horizon):
        self.model = model
        self.capacity = capacity
        self.horizon = horizon
        self.sigma = SigmaEstimator.from_config(CONFIG)

    def update(self, sample):
        self.sigma.observe(sample.timestamp, sample.rps)
        projected, slope = self.model.update(sample.timestamp, sample.rps)
        self.sigma.add_projection(sample.timestamp + self.horizon, projected)
        return RiskResult(sample.timestamp, sample.rps, slope, projected, self.sigma.value(), len(self.sigma.errors),
                          self.capacity)


# Replays the decisions with another forecaster and measures them against the planned traffic of the run.
def replay_decisions(run, make):
    summary = run["summary"]
    capacity = summary["capacity_rps"]
    startup = summary["startup_time_seconds"]
    horizon = horizon_of(summary)
    calculator = ReplayCalculator(make(horizon), capacity, horizon)
    engine = DecisionEngine.from_config(CONFIG, run["records"][0]["previous_target"])
    start = k6_start(summary)
    changes = []
    for record in run["records"]:
        decision = engine.decide(calculator.update(Sample(record["time"], record["rps"], None, None)), record["time"])
        if decision.action in (SCALE_UP, SCALE_DOWN):
            changes.append({"s": record["time"] - start, "from": decision.previous_target, "to": decision.target})
    profile = read_profile(summary["profile"], capacity)
    end = total_duration(profile)
    requested = 1
    serving = 1
    pending = []
    pod_seconds = 0
    short_seconds = 0
    index = 0
    ups = [c for c in changes if c["to"] > c["from"]]
    for second in range(int(-30), int(end)):
        while index < len(changes) and changes[index]["s"] <= second:
            change = changes[index]
            if change["to"] > change["from"]:
                pending.append(change["s"] + startup)
            else:
                serving -= 1
            requested = change["to"]
            index += 1
        while pending and pending[0] <= second:
            pending.pop(0)
            serving += 1
        if second >= 0:
            pod_seconds += requested
            if planned_rate(profile, second) > capacity * serving:
                short_seconds += 1
    crossing = summary["crosses_c_s"]
    first_up = ups[0]["s"] if ups else None
    return {"ahead": None if first_up is None or crossing is None else crossing - first_up, "short": short_seconds,
            "pod_minutes": pod_seconds / 60, "ups": len(ups), "false": false_alarms(ups, profile, capacity)}


def tune(runs):
    best = {}
    for alpha, beta, phi in itertools.product(GRID_ALPHA, GRID_BETA, GRID_PHI):
        score = forecast_errors(runs, lambda h: DampedHolt(h, alpha, beta, phi))["all"][0]
        if "holt" not in best or score < best["holt"][0]:
            best["holt"] = (score, (alpha, beta, phi))
    for phi in GRID_PHI:
        score = forecast_errors(runs, lambda h: LinearTrend(h, phi))["all"][0]
        if "linear" not in best or score < best["linear"][0]:
            best["linear"] = (score, phi)
    return best["holt"][1], best["linear"][1]


def fmt(value, decimals=1):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    return str(round(value, decimals))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forecast accuracy of Aegis vs naive and damped-trend forecasters")
    parser.parse_args(argv)
    # Tune on earlier calibrations, evaluate on the current one (archived current runs were invalid).
    current = json.loads((TESTS_DIR / "calibration.json").read_text())["measured_at"]
    runs = load_runs("*/data/run-*-aegis.ndjson") + load_runs("*/archive/*/run-*-aegis.ndjson")
    evaluation = [r for r in runs if r["summary"].get("calibration_measured_at") == current and "archive/" not in r["name"]]
    tuning = [r for r in runs if r["summary"].get("calibration_measured_at") != current]
    if not tuning or not evaluation:
        print("need runs of an earlier calibration (to tune) and of the current one (to evaluate)")
        return
    tune_text = ", ".join(r["name"] for r in tuning)
    eval_text = "calibration " + current
    (alpha, beta, phi_holt), phi_linear = tune(tuning)
    models = [
        ("naive", lambda h: Naive(h)),
        ("aegis", lambda h: LinearTrend(h)),
        ("damped-linear", lambda h: LinearTrend(h, phi_linear)),
        ("damped-holt", lambda h: DampedHolt(h, alpha, beta, phi_holt)),
    ]
    names = {key: make(35).name for key, make in models}
    lines = ["# Forecast accuracy", "",
             "Generated by `forecast_accuracy.py`. Each forecaster is replayed on the demand Aegis recorded and compared "
             "with the demand 35 s later. Parameters tuned on " + str(len(tuning)) + " run(s) of an earlier calibration ("
             + tune_text + "), evaluated on " + str(len(evaluation)) + " run(s) of the " + eval_text + ". Chosen: damped "
             "Holt alpha=" + str(alpha) + ", beta=" + str(beta) + ", phi=" + str(phi_holt) + "; damped linear phi="
             + str(phi_linear) + ".", "",
             "## Forecast error (mean absolute error, req/s)", "",
             "Rising / falling: the demand 35 s later is > 3 req/s above / below the current one.", "",
             "| Forecaster | Rising | Stable | Falling | All | Bias (+ = over) |", "|---|---|---|---|---|---|"]
    for key, make in models:
        result = forecast_errors(evaluation, make)
        lines.append("| " + names[key] + " | " + " | ".join(fmt(result[g][0]) for g in ("rising", "stable", "falling", "all"))
                     + " | " + fmt(result["bias"][0]) + " |")
    counts = forecast_errors(evaluation, models[0][1])
    lines += ["", "Samples: " + ", ".join(g + " " + str(counts[g][1]) for g in ("rising", "stable", "falling")) + ".", "",
              "## Decisions with each forecaster", "",
              "The full decision engine replayed with each forecaster (valid because k6 sends at a fixed rate; a pod "
              "serves from its request + T). Short = seconds the planned traffic was above the capacity in service. "
              "Ahead = seconds from the first scale-up to the traffic passing C.",
              "", "| Forecaster | Ahead (s) | Short (s) | Pod-minutes | Scale-ups | False alarms |",
              "|---|---|---|---|---|---|"]
    for key, make in models:
        results = [replay_decisions(run, make) for run in evaluation]
        aheads = [r["ahead"] for r in results if r["ahead"] is not None]
        lines.append("| " + names[key] + " | " + fmt(sum(aheads) / len(aheads) if aheads else None) + " | "
                     + fmt(sum(r["short"] for r in results) / len(results)) + " | "
                     + fmt(sum(r["pod_minutes"] for r in results) / len(results), 2) + " | "
                     + fmt(sum(r["ups"] for r in results) / len(results)) + " | "
                     + str(sum(r["false"] for r in results)) + " |")
    lines += ["", "Mean per run over: " + ", ".join(run["name"] for run in evaluation) + ".", ""]
    (TESTS_DIR / "forecast.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
