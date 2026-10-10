import datetime
import json
import statistics
import sys
import urllib.parse
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"
STEP = "15s"
POD_FILTER = 'namespace="default",pod=~"catalog-service.*"'
CONFIG_T_SECONDS = 13  # T in app/config.yaml


def query_range(query, start, end):
    params = urllib.parse.urlencode({"query": query, "start": start, "end": end, "step": STEP})
    with urllib.request.urlopen(PROMETHEUS_URL + "?" + params) as response:
        return json.load(response)["data"]["result"]


# Returns {pod: [distinct timestamps the metric took]} (sorted).
def values_by_pod(metric, start, end):
    query = "max by (pod) (" + metric + "{" + POD_FILTER + "})"
    result = {}
    for series in query_range(query, start, end):
        distinct = set()
        for _, v in series["values"]:
            distinct.add(float(v))
        result[series["metric"]["pod"]] = sorted(distinct)
    return result


def to_utc(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)


def parse_utc(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 scripts/plot_startup.py START END output.png")
        sys.exit(1)

    start, end, png_path = sys.argv[1], sys.argv[2], sys.argv[3]
    start_ts = parse_utc(start)
    end_ts = parse_utc(end)

    created = values_by_pod("kube_pod_created", start, end)
    ready = values_by_pod("kube_pod_status_ready_time", start, end)

    pods = []
    for pod, created_values in created.items():
        created_at = created_values[0]
        if not start_ts <= created_at <= end_ts:
            continue
        # First time the pod became Ready after being created
        for ready_at in ready.get(pod, []):
            if ready_at >= created_at:
                pods.append((created_at, pod, ready_at - created_at))
                break

    if not pods:
        print("No pods created in that range.")
        sys.exit(1)

    pods.sort()
    labels = []
    seconds = []
    bar_texts = []
    for created_at, pod, startup_seconds in pods:
        labels.append(to_utc(created_at).strftime("%H:%M:%S") + "\n" + pod[-5:])
        seconds.append(startup_seconds)
        bar_texts.append(str(int(startup_seconds)) + " s")
        print(pod, "created", to_utc(created_at).strftime("%H:%M:%S"), "->", int(startup_seconds), "s until Ready")

    mean = statistics.mean(seconds)
    print("mean:", round(mean, 1), "s | min:", int(min(seconds)), "s | max:", int(max(seconds)), "s")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(labels, seconds, color="tab:blue", width=0.55)
    ax.bar_label(bars, labels=bar_texts, padding=3)
    ax.axhline(mean, color="tab:orange", linestyle="--", label="Measured mean: " + str(round(mean, 1)) + " s")
    ax.axhline(CONFIG_T_SECONDS, color="gray", linestyle=":", label="T in config.yaml: " + str(CONFIG_T_SECONDS) + " s")
    ax.set_ylabel("Seconds from creation until Ready")
    ax.set_xlabel("New pod (creation time, UTC)")
    ax.set_ylim(0, max(seconds) * 1.3)
    ax.set_title("Startup time of a catalog-service pod (T)", fontsize=14)
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    print("Chart saved to", png_path)


if __name__ == "__main__":
    main()
