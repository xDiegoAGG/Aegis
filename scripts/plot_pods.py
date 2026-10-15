import csv
import datetime
import json
import sys
import urllib.parse
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"
STEP = "5s"
QUERY_RPS = 'sum by (pod) (rate(http_request_duration_seconds_count{route="/"}[10s]))'
QUERY_READY = 'kube_pod_status_ready{namespace="default",pod=~"catalog-service.*",condition="true"}'
CAPACITY_RPS = 18


# Returns {pod: {timestamp: value}}
def query_by_pod(query, start, end):
    params = urllib.parse.urlencode({"query": query, "start": start, "end": end, "step": STEP})
    with urllib.request.urlopen(PROMETHEUS_URL + "?" + params) as response:
        result = json.load(response)["data"]["result"]
    series = {}
    for item in result:
        values = {}
        for t, v in item["values"]:
            value = float(v)
            if value == value:  # drop NaN
                values[float(t)] = value
        series[item["metric"]["pod"]] = values
    return series


def to_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).replace(tzinfo=None)


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 scripts/plot_pods.py START END output_path [--title \"text\"]")
        sys.exit(1)

    start, end, out = sys.argv[1], sys.argv[2], sys.argv[3]
    title = "Traffic received by each pod"
    if "--title" in sys.argv:
        title = sys.argv[sys.argv.index("--title") + 1]

    rps = query_by_pod(QUERY_RPS, start, end)
    ready = query_by_pod(QUERY_READY, start, end)
    pods = sorted(set(rps) | set(ready))

    all_times = set()
    for values in rps.values():
        for t in values:
            all_times.add(t)
    for values in ready.values():
        for t in values:
            all_times.add(t)
    times = sorted(all_times)

    csv_path = out + ".csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["time_utc"]
        for pod in pods:
            header.append("rps_" + pod)
            header.append("ready_" + pod)
        writer.writerow(header)
        for t in times:
            row = [to_time(t).strftime("%H:%M:%S")]
            for pod in pods:
                row.append(rps.get(pod, {}).get(t, ""))
                row.append(ready.get(pod, {}).get(t, ""))
            writer.writerow(row)
    print(len(times), "rows saved to", csv_path)

    fig, (ax_rps, ax_ready) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                           gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle(title, fontsize=14)

    for index, pod in enumerate(pods):
        # Short name: the last 5 characters of the pod name
        label = "pod ..." + pod[-5:]
        color = "C" + str(index)
        pod_times = []
        pod_values = []
        for t in sorted(rps.get(pod, {})):
            pod_times.append(to_time(t))
            pod_values.append(rps[pod][t])
        ax_rps.plot(pod_times, pod_values, color=color, linewidth=2, label=label)

        ready_times = []
        ready_values = []
        for t in sorted(ready.get(pod, {})):
            ready_times.append(to_time(t))
            ready_values.append(ready[pod][t] + index * 0.04)  # small offset so lines do not hide each other
        ax_ready.step(ready_times, ready_values, where="post", color=color, linewidth=2, label=label)

    ax_rps.axhline(CAPACITY_RPS, color="gray", linestyle="--", label="Capacity of one pod (C = 18)")
    ax_rps.set_ylabel("Requests / s")
    ax_rps.legend(loc="upper left", fontsize=9)
    ax_ready.set_ylabel("Ready")
    ax_ready.set_yticks([0, 1])
    ax_ready.set_yticklabels(["no", "yes"])
    ax_ready.set_ylim(-0.2, 1.3)
    ax_ready.set_xlabel("Time (UTC)")
    ax_ready.legend(loc="lower right", fontsize=9)
    for ax in (ax_rps, ax_ready):
        ax.grid(alpha=0.3)
    ax_ready.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    fig.tight_layout()
    png_path = out + ".png"
    fig.savefig(png_path, dpi=150)
    print("Chart saved to", png_path)


if __name__ == "__main__":
    main()
