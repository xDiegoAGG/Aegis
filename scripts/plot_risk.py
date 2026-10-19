import csv
import datetime
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

DEFAULT_TITLE = "Risk calculated by Aegis during the 5 → 30 req/s ramp"
SCALE_UP = 0.70
SCALE_DOWN = 0.30
P95_CAP_S = 5
L_SECONDS = 1.0   # degradation.p95_threshold_seconds in app/config.yaml
EVENT_COLORS = ["tab:purple", "tab:red", "tab:orange", "tab:green"]
NUMERIC = ["rps", "slope", "projected_rps", "capacity_rps", "risk", "p95_s", "replicas", "replicas_ready"]
OPTIONAL = ["aegis_target", "sigma_rps"]   # older CSVs do not have these columns

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
    rows = {"time": []}
    for key in NUMERIC + OPTIONAL:
        rows[key] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows["time"].append(parse_time(row["time_utc"]))
            for key in NUMERIC:
                rows[key].append(parse_value(row[key]))
            for key in OPTIONAL:
                rows[key].append(parse_value(row.get(key, "")))
    return rows


def load_client_csv(path):
    rows = {"time": [], "client_p95_s": []}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows["time"].append(parse_time(row["time_utc"]))
            rows["client_p95_s"].append(parse_value(row["client_p95_s"]))
    return rows


def has_values(values):
    for value in values:
        if value is not None:
            return True
    return False


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/plot_risk.py input.csv output.png [--title \"text\"] [--hide-target]"
              " [HH:MM:SS=label ...]")
        sys.exit(1)

    csv_path, png_path = sys.argv[1], sys.argv[2]
    extra_args = sys.argv[3:]
    title = DEFAULT_TITLE
    # --hide-target: for live runs, where the desired replicas already are Aegis's real decisions
    hide_target = False
    if "--hide-target" in extra_args:
        hide_target = True
        extra_args.remove("--hide-target")
    # --client file.csv: client-side P95 from scripts/fetch_k6_results.py, drawn on the latency panel
    client = None
    if "--client" in extra_args:
        index = extra_args.index("--client")
        client = load_client_csv(extra_args[index + 1])
        extra_args = extra_args[:index] + extra_args[index + 2:]
    if "--title" in extra_args:
        index = extra_args.index("--title")
        title = extra_args[index + 1]
        extra_args = extra_args[:index] + extra_args[index + 2:]
    events = []
    for arg in extra_args:
        time_text, _, label = arg.partition("=")
        events.append((parse_time(time_text), label or time_text))

    data = load_csv(csv_path)
    times = data["time"]

    risk_pct = []
    for risk in data["risk"]:
        if risk is None:
            risk_pct.append(None)
        else:
            risk_pct.append(risk * 100)

    has_aegis_target = False
    if not hide_target:
        has_aegis_target = has_values(data["aegis_target"])

    fig, (ax_rps, ax_p95, ax_risk, ax_rep) = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    fig.suptitle(title, fontsize=14)

    ax_rps.plot(times, data["rps"], color="tab:blue", linewidth=2, label="Current req/s (r)")
    ax_rps.plot(times, data["projected_rps"], color="tab:blue", linestyle="--", alpha=0.6,
                label="Projected req/s (r + m·T)")
    if has_values(data["sigma_rps"]):
        # Band of ±sigma around the projection: how wrong the projection has been lately
        band_times = []
        low = []
        high = []
        for index, sigma in enumerate(data["sigma_rps"]):
            projected = data["projected_rps"][index]
            if sigma is None or projected is None:
                continue
            band_times.append(times[index])
            low.append(projected - sigma)
            high.append(projected + sigma)
        ax_rps.fill_between(band_times, low, high, color="tab:blue", alpha=0.15, label="Projection ± σ (live)")
    ax_rps.step(times, data["capacity_rps"], where="post", color="gray", linestyle="--",
                label="Capacity (C × N)")
    ax_rps.set_ylabel("Requests / s")
    ax_rps.legend(loc="upper left", fontsize=9)

    ax_p95.plot(times, data["p95_s"], color="tab:red", linewidth=2, label="P95 latency (service)")
    if client is not None:
        # Measured by k6: includes the time requests waited outside a saturated pod
        ax_p95.plot(client["time"], client["client_p95_s"], color="black", linewidth=1.5,
                    label="P95 latency (client, k6)")
    ax_p95.axhline(P95_CAP_S, color="gray", linestyle=":", label="Histogram cap (5 s)")
    ax_p95.axhline(L_SECONDS, color="tab:orange", linestyle="--", label="L = 1 s")
    ax_p95.set_ylabel("P95 (s)")
    top = P95_CAP_S + 0.5
    if client is not None:
        # The client P95 can go up to the k6 timeout (10 s)
        for value in client["client_p95_s"]:
            if value is not None and value + 0.5 > top:
                top = value + 0.5
    ax_p95.set_ylim(0, top)
    ax_p95.legend(loc="upper left", fontsize=9)

    ax_risk.plot(times, risk_pct, color="tab:purple", linewidth=2, label="Risk")
    ax_risk.axhline(SCALE_UP * 100, color="tab:red", linestyle="--", label="Scale-up threshold (70%)")
    ax_risk.axhline(SCALE_DOWN * 100, color="tab:green", linestyle="--", label="Scale-down threshold (30%)")
    ax_risk.set_ylabel("Risk (%)")
    ax_risk.set_ylim(-5, 105)
    ax_risk.legend(loc="upper left", fontsize=9)

    ax_rep.step(times, data["replicas"], where="post", color="tab:gray", linewidth=2, label="Desired replicas")
    ax_rep.step(times, data["replicas_ready"], where="post", color="tab:green", linewidth=2, label="Ready replicas")
    if has_aegis_target:
        ax_rep.step(times, data["aegis_target"], where="post", color="tab:purple", linewidth=2,
                    linestyle="--", label="Aegis target (simulated)")
    ax_rep.set_ylabel("Replicas")
    ax_rep.set_ylim(-0.2, 3.2)
    ax_rep.set_yticks([0, 1, 2, 3])
    ax_rep.set_xlabel("Time (UTC)")
    ax_rep.legend(loc="upper left", fontsize=9)

    axes = (ax_rps, ax_p95, ax_risk, ax_rep)
    for index, (event_time, label) in enumerate(events):
        color = EVENT_COLORS[index % len(EVENT_COLORS)]
        for ax in axes:
            ax.axvline(event_time, color=color, linestyle="--", linewidth=1.5)
        # Three alternating heights so labels of close events do not overlap
        ax_rps.annotate(label, xy=(event_time, 1.02 + 0.09 * (index % 3)), xycoords=("data", "axes fraction"),
                        color=color, fontsize=9, ha="center", va="bottom")

    for ax in axes:
        ax.grid(alpha=0.3)
    ax_rep.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    fig.tight_layout()
    fig.subplots_adjust(top=0.90)
    fig.savefig(png_path, dpi=150)
    print("Chart saved to", png_path)


if __name__ == "__main__":
    main()
