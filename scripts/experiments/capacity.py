import json
from matplotlib.figure import Figure
from settings import TESTS_DIR

COLORS = ["tab:blue", "tab:orange", "tab:green"]


# Capacity curve of one pod from the saved calibration: served vs sent and highest P95 per load step.
def main():
    calibration = json.loads((TESTS_DIR / "calibration.json").read_text())
    limit = calibration["degradation"]["p95_threshold_seconds"]
    capacity = calibration["capacity_rps"]
    fig = Figure(figsize=(12, 4.2))
    served, latency = fig.subplots(1, 2)
    top = 0
    for index, run in enumerate(calibration["capacity_runs"]):
        steps = [step for step in run["steps"]]
        sent = [step["target_rps"] for step in steps]
        top = max(top, max(sent))
        label = "run " + str(index + 1) + " (C = " + str(run["capacity_rps"]) + ")"
        points = [(s["target_rps"], s["measured_rps"]) for s in steps if s["measured_rps"] is not None]
        served.plot([p[0] for p in points], [p[1] for p in points], marker="o", color=COLORS[index], label=label)
        latency.plot(sent, [s["p95_max_s"] for s in steps], marker="o", color=COLORS[index], label=label)
    served.plot([0, top], [0, top], color="gray", linestyle="--", linewidth=1, label="served = sent")
    for ax in (served, latency):
        ax.axvline(capacity, color="tab:red", linestyle=":", linewidth=1.2)
        ax.set_xlabel("req/s sent to 1 pod (30 s per step)")
        ax.grid(alpha=0.3)
    served.annotate("C = " + str(capacity), xy=(capacity, 0.02), xycoords=("data", "axes fraction"), color="tab:red")
    latency.axhline(limit, color="black", linestyle="--", linewidth=1)
    latency.annotate("L = " + str(limit) + " s", xy=(0.02, limit), xycoords=("axes fraction", "data"), va="bottom")
    served.set_ylabel("req/s served")
    latency.set_ylabel("highest P95 in the step (s)")
    served.set_title("Served vs sent")
    latency.set_title("Latency per step")
    served.legend(fontsize=8)
    latency.legend(fontsize=8)
    cpu = calibration.get("environment", {}).get("cpu_limit") or "?"
    fig.suptitle("Capacity of one catalog-service pod (" + cpu + " CPU), calibration of " + calibration["measured_at"])
    fig.tight_layout()
    path = TESTS_DIR / "capacity-curve.png"
    fig.savefig(path, dpi=110)
    print("saved", path)


if __name__ == "__main__":
    main()
