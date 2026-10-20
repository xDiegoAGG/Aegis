from matplotlib.figure import Figure
from settings import L_SECONDS, TESTS_DIR

RUN_COLORS = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple"]


def column(rows, key):
    values = []
    for row in rows:
        values.append(row[key])
    return values


def scaled(rows, key, factor):
    values = []
    for row in rows:
        if row[key] is None:
            values.append(None)
        else:
            values.append(factor * row[key])
    return values


# Vertical lines at the key moments of a run, on every panel.
def mark_events(axes, summary):
    marks = [
        (summary["crosses_c_s"], "gray", ":", "traffic over C"),
        (summary["first_scale_up_s"], "tab:purple", "--", "1st scale-up"),
        (summary["second_pod_ready_s"], "tab:green", "--", "2nd pod Ready"),
        (summary["first_degraded_s"], "tab:red", "--", "client degraded"),
    ]
    for index, (seconds, color, style, label) in enumerate(marks):
        if seconds is None:
            continue
        for ax in axes:
            ax.axvline(seconds, color=color, linestyle=style, linewidth=1.2)
        axes[0].annotate(label, xy=(seconds, 1.01 + 0.06 * index), xycoords=("data", "axes fraction"),
                         color=color, fontsize=8, ha="center", va="bottom")


# Chart of one run: traffic and capacity, client latency, Aegis risk (if on) and pods.
def plot_run(path, title, summary, rows):
    aegis = summary["mode"] == "aegis"
    panels = 3
    if aegis:
        panels = 4
    fig = Figure(figsize=(12, 2.7 * panels + 1))
    axes = fig.subplots(panels, 1, sharex=True)
    x = column(rows, "seconds")
    ax = axes[0]
    ax.plot(x, column(rows, "planned_rps"), color="gray", linestyle="--", label="Sent by k6 (planned)")
    ax.plot(x, column(rows, "demand_rps"), color="tab:blue", linewidth=2, label="Demand seen at the entrance")
    if aegis:
        ax.plot(x, column(rows, "aegis_projected_rps"), color="tab:blue", linestyle=":", label="Aegis projection")
    ax.step(x, scaled(rows, "requested", summary["capacity_rps"]), where="post", color="tab:red",
            label="Capacity of the requested pods (C x N)")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("req/s")
    ax.legend(loc="upper left", fontsize=8)
    ax = axes[1]
    ax.plot(x, column(rows, "client_p95_s"), color="black", label="P95 latency (k6 client)")
    ax.axhline(L_SECONDS, color="tab:orange", linestyle="--", label="L = " + str(L_SECONDS) + " s")
    ax.set_ylabel("P95 (s)")
    ax.set_ylim(0, 11)
    ax.legend(loc="upper left", fontsize=8)
    twin = ax.twinx()
    twin.plot(x, scaled(rows, "client_failed_ratio", 100), color="tab:red", alpha=0.5, label="Failed requests (%)")
    twin.set_ylabel("failed %")
    twin.set_ylim(0, 105)
    twin.legend(loc="upper right", fontsize=8)
    if aegis:
        ax = axes[2]
        ax.plot(x, scaled(rows, "aegis_risk", 100), color="tab:purple", linewidth=2, label="Risk with the requested pods")
        ax.axhline(70, color="tab:red", linestyle="--", label="Scale up (70%)")
        ax.axhline(30, color="tab:green", linestyle="--", label="Scale down (30%, one pod less)")
        ax.set_ylabel("risk %")
        ax.set_ylim(-5, 105)
        ax.legend(loc="upper left", fontsize=8)
    ax = axes[-1]
    ax.step(x, column(rows, "requested"), where="post", color="tab:purple", linewidth=2, label="Pods requested")
    ax.step(x, column(rows, "ready"), where="post", color="tab:green", label="Pods Ready (kube-state-metrics, ~20 s late)")
    ax.set_ylabel("pods")
    ax.set_ylim(0, 3.5)
    ax.set_yticks([0, 1, 2, 3])
    ax.set_xlabel("seconds since k6 started")
    ax.legend(loc="upper left", fontsize=8)
    mark_events(axes, summary)
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.suptitle(title + " - run " + str(summary["run"]) + " (" + summary["date_utc"] + " " + summary["k6_start_utc"]
                 + " UTC): failed " + str(summary["failed_percent"]) + "%, degraded "
                 + str(summary["degraded_seconds"]) + " s", fontsize=12)
    fig.tight_layout()
    fig.subplots_adjust(top=0.9)
    fig.savefig(path, dpi=110)


# The runs of a test on top of each other, to see that they behave the same.
def plot_all_runs(path, title, summaries, runs):
    fig = Figure(figsize=(12, 10))
    axes = fig.subplots(3, 1, sharex=True)
    for index, summary in enumerate(summaries):
        rows = runs[index]
        color = RUN_COLORS[index % len(RUN_COLORS)]
        label = "run " + str(summary["run"])
        x = column(rows, "seconds")
        if index == 0:
            axes[0].plot(x, column(rows, "planned_rps"), color="gray", linestyle="--", linewidth=2, label="Sent (planned)")
        axes[0].plot(x, column(rows, "demand_rps"), color=color, label=label)
        axes[1].step(x, column(rows, "requested"), where="post", color=color, label=label)
        axes[2].plot(x, column(rows, "client_p95_s"), color=color, label=label)
    axes[0].axhline(summaries[0]["capacity_rps"], color="tab:red", linestyle=":", label="C (1 pod)")
    axes[0].set_ylabel("demand (req/s)")
    axes[1].set_ylabel("pods requested")
    axes[1].set_yticks([0, 1, 2, 3])
    axes[1].set_ylim(0, 3.5)
    axes[2].axhline(L_SECONDS, color="tab:orange", linestyle="--", label="L")
    axes[2].set_ylabel("client P95 (s)")
    axes[2].set_ylim(0, 11)
    axes[2].set_xlabel("seconds since k6 started")
    for ax in axes:
        ax.grid(alpha=0.3)
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(title + " - all runs", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


# Bars with the mean and the range (min to max) of the runs of each test.
def plot_comparison(tests, stats):
    metrics = [
        ("failed_percent", "Failed requests (%)"),
        ("degraded_seconds", "Seconds degraded (client)"),
        ("lead_s", "2nd pod Ready before traffic > C (s)"),
        ("pod_minutes", "Pod-minutes during the load"),
    ]
    fig = Figure(figsize=(14, 4.5))
    axes = fig.subplots(1, len(metrics))
    for index, (key, label) in enumerate(metrics):
        ax = axes[index]
        names = []
        means = []
        low = []
        high = []
        for title, summaries in tests:
            names.append(title.replace(" - ", "\n"))
            result = stats(summaries, key)
            if result is None:
                means.append(0)
                low.append(0)
                high.append(0)
            else:
                means.append(result["mean"])
                low.append(result["mean"] - result["min"])
                high.append(result["max"] - result["mean"])
        ax.bar(range(len(names)), means, yerr=[low, high], capsize=6, color=RUN_COLORS[:len(names)])
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=7)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=0.3, axis="y")
    fig.suptitle("Mean of the runs of each test (lines show min and max)", fontsize=12)
    fig.tight_layout()
    fig.savefig(TESTS_DIR / "comparison.png", dpi=110)
