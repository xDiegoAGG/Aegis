import csv
import datetime
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import logging  # noqa: E402

from aegis.calibration import load_cluster_calibration  # noqa: E402
from aegis.collector import Sample  # noqa: E402
from aegis.config import load_config  # noqa: E402
from aegis.decision import DecisionEngine  # noqa: E402
from aegis.kube import load_kubernetes_credentials  # noqa: E402
from aegis.risk import RiskCalculator  # noqa: E402

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"
# Latency for the chart: short window (10s) to see the jump when it actually happens
QUERY_P95_10S = 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{route="/"}[10s])) by (le))'
QUERY_REPLICAS = 'sum(kube_deployment_status_replicas{deployment="catalog-service"})'
COLUMNS = ["time_utc", "rps", "slope", "projected_rps", "capacity_rps", "risk",
           "p95_s", "replicas", "replicas_ready", "action", "aegis_target"]


def query_range(query, start, end, step):
    params = urllib.parse.urlencode({"query": query, "start": start, "end": end, "step": step})
    with urllib.request.urlopen(PROMETHEUS_URL + "?" + params) as response:
        result = json.load(response)["data"]["result"]
    values = {}
    if result:
        for t, v in result[0]["values"]:
            values[float(t)] = float(v)
    return values


# Returns None for missing values and NaN
def clean(value):
    if value is None:
        return None
    if value != value:
        return None
    return value


# Removes "--name value" from args and returns the value, or None if it is not there
def take_option(args, name):
    if name not in args:
        return None
    index = args.index(name)
    value = args[index + 1]
    del args[index:index + 2]
    return value


def main():
    args = sys.argv[1:]
    capacity = take_option(args, "--capacity")
    startup = take_option(args, "--startup")
    if len(args) != 3:
        print("Usage: python3 scripts/replay_risk.py START END output_path [--capacity C] [--startup T]")
        print("Without --capacity and --startup, C and T come from the cluster calibration (aegis.calibrate).")
        print("Runs before the calibration existed used C = 18 and T = 13.")
        sys.exit(1)

    start, end, out = args[0], args[1], args[2]
    csv_path = out + ".csv"
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config()
    if capacity is None or startup is None:
        load_kubernetes_credentials()
        if not load_cluster_calibration(config):
            sys.exit(1)
    if capacity is not None:
        config["capacity_rps"] = float(capacity)
    if startup is not None:
        config["startup_time_seconds"] = float(startup)
    prometheus = config["prometheus"]
    step = str(config["sampling"]["interval_seconds"]) + "s"

    rps = query_range(prometheus["query_rps"], start, end, step)
    ready = query_range(prometheus["query_replicas_ready"], start, end, step)
    p95 = query_range(QUERY_P95_10S, start, end, step)
    replicas = query_range(QUERY_REPLICAS, start, end, step)

    calculator = RiskCalculator.from_config(config)
    engine = DecisionEngine.from_config(config)
    times = sorted(set(rps) | set(ready))
    decisions = []

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for t in times:
            ready_value = clean(ready.get(t))
            replicas_ready = None
            if ready_value is not None:
                replicas_ready = int(ready_value)

            sample = Sample(
                timestamp=t,
                rps=clean(rps.get(t)),
                p95_s=None,
                replicas_ready=replicas_ready,
            )
            result = calculator.update(sample)
            decision = engine.decide(result, now=t)
            time_utc = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%H:%M:%S")

            if result is None:
                risk_fields = ["", "", "", "", ""]
            else:
                risk_fields = [result.rps, result.slope, result.projected_rps, result.capacity_rps, result.risk]
            writer.writerow([time_utc] + risk_fields + [
                p95.get(t, ""), replicas.get(t, ""), ready.get(t, ""),
                decision.action, decision.target,
            ])

            if decision.action != "hold":
                decisions.append(time_utc + " " + decision.action + " " + str(decision.previous_target)
                                 + " -> " + str(decision.target) + " (" + decision.reason + ")")

    print(len(times), "rows saved to", csv_path)
    for line in decisions:
        print("  simulated decision:", line)


if __name__ == "__main__":
    main()
