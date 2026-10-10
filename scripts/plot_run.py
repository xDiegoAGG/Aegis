import csv
import datetime
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

DEFAULT_TITLE = "catalog-service with HPA (CPU 70%), without Aegis: 5 → 30 req/s ramp"
CAPACITY_RPS = 18      # measured C (app/config.yaml)
P95_CAP_S = 5          # highest histogram bucket: Prometheus cannot see beyond it
EVENT_COLORS = ["tab:red", "tab:orange", "tab:green", "tab:purple"]


def parse_time(text):
    return datetime.datetime.strptime(text, "%H:%M:%S")


def parse_value(text):
    try:
        value = float(text)
    except ValueError:
        return None
    if value != value:  # drop NaN
        return None
    return value


def load_csv(path):
    rows = {"time": [], "rps": [], "p95_s": [], "replicas": [], "replicas_ready": []}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows["time"].append(parse_time(row["time_utc"]))
            for key in ("rps", "p95_s", "replicas", "replicas_ready"):
                rows[key].append(parse_value(row[key]))
    return rows


def parse_events(args):
    events = []
    for arg in args:
        time_text, _, label = arg.partition("=")
        events.append((parse_time(time_text), label or time_text))
    return events


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/plot_run.py input.csv output.png [--title \"text\"] [HH:MM:SS=label ...]")
        sys.exit(1)

    csv_path, png_path = sys.argv[1], sys.argv[2]
    extra_args = sys.argv[3:]
    title = DEFAULT_TITLE
    if "--title" in extra_args:
        index = extra_args.index("--title")
        title = extra_args[index + 1]
        extra_args = extra_args[:index] + extra_args[index + 2:]

    data = load_csv(csv_path)
    events = parse_events(extra_args)
    times = data["time"]

    fig, (ax_rps, ax_p95, ax_rep) = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(title, fontsize=14)

    ax_rps.plot(times, data["rps"], color="tab:blue", linewidth=2, label="Measured req/s")
    ax_rps.axhline(CAPACITY_RPS, color="gray", linestyle="--", label="Capacity of 1 pod (C = 18 req/s)")
    ax_rps.set_ylabel("Requests / s")
    ax_rps.legend(loc="upper left")

    ax_p95.plot(times, data["p95_s"], color="tab:red", linewidth=2, label="P95 latency")
    ax_p95.axhline(P95_CAP_S, color="gray", linestyle=":", label="Histogram cap (5 s)")
    ax_p95.set_ylabel("P95 (s)")
    ax_p95.set_ylim(0, P95_CAP_S + 0.5)
    ax_p95.legend(loc="upper left")

    ax_rep.step(times, data["replicas"], where="post", color="tab:gray", linewidth=2, label="Desired replicas")
    ax_rep.step(times, data["replicas_ready"], where="post", color="tab:green", linewidth=2, label="Ready replicas")
    ax_rep.set_ylabel("Replicas")
    ax_rep.set_ylim(-0.2, 3.2)
    ax_rep.set_yticks([0, 1, 2, 3])
    ax_rep.set_xlabel("Time (UTC)")
    ax_rep.legend(loc="upper left")

    for index, (event_time, label) in enumerate(events):
        color = EVENT_COLORS[index % len(EVENT_COLORS)]
        for ax in (ax_rps, ax_p95, ax_rep):
            ax.axvline(event_time, color=color, linestyle="--", linewidth=1.5)
        ax_rps.annotate(label, xy=(event_time, 1.02), xycoords=("data", "axes fraction"),
                        color=color, fontsize=9, ha="center", va="bottom", rotation=0)

    for ax in (ax_rps, ax_p95, ax_rep):
        ax.grid(alpha=0.3)
    ax_rep.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    print("Chart saved to", png_path)


if __name__ == "__main__":
    main()
