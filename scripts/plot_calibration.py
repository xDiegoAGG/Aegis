import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Chart of a calibration saved with `python3 -m aegis.calibrate --output file.json`:
# for every capacity run, the req/s sent vs served per step and the highest P95 of each step.
# Usage: python3 scripts/plot_calibration.py calibration.json output.png

RUN_COLORS = ["tab:blue", "tab:orange", "tab:green", "tab:purple"]


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/plot_calibration.py calibration.json output.png")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        calibration = json.load(f)
    threshold = calibration["degradation"]["p95_threshold_seconds"]
    capacity = calibration["capacity_rps"]

    fig, (ax_rps, ax_p95) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    fig.suptitle("Automatic calibration: C = " + str(capacity) + " req/s, T = "
                 + str(calibration["startup_time_seconds"]) + " s (" + calibration["measured_at"] + ")",
                 fontsize=13)

    highest_target = 0
    for index, run in enumerate(calibration["capacity_runs"]):
        color = RUN_COLORS[index % len(RUN_COLORS)]
        targets = []
        served = []
        p95_targets = []
        p95_values = []
        for step in run["steps"]:
            if step["target_rps"] > highest_target:
                highest_target = step["target_rps"]
            if step["measured_rps"] is not None:
                targets.append(step["target_rps"])
                served.append(step["measured_rps"])
            if step["p95_max_s"] is not None:
                p95_targets.append(step["target_rps"])
                p95_values.append(step["p95_max_s"])
        label = "Run " + str(index + 1) + " (C = " + str(run["capacity_rps"]) + ")"
        ax_rps.plot(targets, served, marker="o", color=color, linewidth=2, label=label)
        ax_p95.plot(p95_targets, p95_values, marker="o", color=color, linewidth=2, label=label)
        if "degraded_step_rps" in run:
            for ax in (ax_rps, ax_p95):
                ax.axvline(run["degraded_step_rps"], color=color, linestyle=":", linewidth=1.5)

    ax_rps.plot([0, highest_target], [0, highest_target], color="gray", linestyle="--", label="Served = sent")
    ax_rps.axvline(capacity, color="tab:red", linestyle="--", linewidth=2, label="Calibrated C")
    ax_rps.set_ylabel("Served req/s (mean of the step)")
    ax_rps.legend(loc="upper left", fontsize=9)

    ax_p95.axhline(threshold, color="tab:red", linestyle="--", label="L = " + str(threshold) + " s")
    ax_p95.axvline(capacity, color="tab:red", linestyle="--", linewidth=2)
    ax_p95.set_ylabel("Highest P95 of the step (s)")
    ax_p95.set_xlabel("Sent req/s (step)")
    ax_p95.legend(loc="upper left", fontsize=9)

    for ax in (ax_rps, ax_p95):
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(sys.argv[2], dpi=150)
    print("Chart saved to", sys.argv[2])


if __name__ == "__main__":
    main()
