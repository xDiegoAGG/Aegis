import csv
import datetime
import json
import sys
import urllib.parse
import urllib.request

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"
STEP = "5s"
QUERIES = {
    "rps": 'sum(rate(http_request_duration_seconds_count{route="/"}[10s]))',
    "p95_s": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{route="/"}[10s])) by (le))',
    "replicas": 'sum(kube_deployment_status_replicas{deployment="catalog-service"})',
    "replicas_ready": 'sum(kube_deployment_status_replicas_ready{deployment="catalog-service"})',
}


def query_range(query, start, end, step):
    params = urllib.parse.urlencode({
        "query": query,
        "start": start,
        "end": end,
        "step": step,
    })
    url = PROMETHEUS_URL + "?" + params
    with urllib.request.urlopen(url) as response:
        return json.load(response)["data"]["result"]


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 scripts/export_run.py START END output_path")
        sys.exit(1)

    start, end, out = sys.argv[1], sys.argv[2], sys.argv[3]
    csv_path = out + ".csv"

    series = {}
    for name, query in QUERIES.items():
        result = query_range(query, start, end, STEP)
        values = {}
        if result:
            for t, v in result[0]["values"]:
                values[float(t)] = float(v)
        series[name] = values

    all_times = set()
    for values in series.values():
        for t in values:
            all_times.add(t)
    times = sorted(all_times)

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_utc"] + list(QUERIES))
        for t in times:
            time_utc = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%H:%M:%S")
            row = [time_utc]
            for name in QUERIES:
                row.append(series[name].get(t, ""))
            writer.writerow(row)

    print(len(times), "rows saved to", csv_path)


if __name__ == "__main__":
    main()
