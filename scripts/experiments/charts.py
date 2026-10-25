import csv
import math
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from settings import L_SECONDS, MAX_FAILED_RATIO, STEP, SUSTAINED_BUCKETS, TESTS_DIR

# One color per role, the same in every chart.
AEGIS = "#2a78d6"
HPA = "#eb6834"
TRAFFIC = "#3a3a38"
PLANNED = "#898781"
DEFICIT = "#d03b3b"
GOOD = "#0ca30c"
GRID = "#e1e0d9"
RUN_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e87ba4"]

TEXT = {
    "en": {
        "seconds": "seconds since the load started",
        "planned": "traffic sent (k6)",
        "demand": "demand measured at the entrance",
        "projection": "Aegis projection (T + lag ahead)",
        "capacity": "capacity in service (C × pods Ready)",
        "deficit": "traffic above the capacity in service",
        "p95": "P95 latency seen by the users",
        "limit": "L = {l} s (slow)",
        "degraded": "degraded (P95 > L or > 1% failed, for 15 s)",
        "failed": "failed requests",
        "risk": "risk with the pods requested",
        "up": "scale up at 70%",
        "down": "scale down under 30% (one pod less)",
        "requested": "pods requested",
        "ready": "pods Ready (request + measured startup)",
        "panel_traffic": "Traffic vs capacity: red = more traffic than the Ready pods can serve",
        "panel_latency": "Latency seen by the users",
        "panel_failed": "Failed requests every 5 s",
        "panel_risk": "Risk calculated by Aegis",
        "panel_pods": "Pods",
        "req_s": "req/s", "p95_s": "P95 (s)", "failed_pct": "failed (%)", "risk_pct": "risk (%)", "pods": "pods",
        "ev_up": "{s} s  {mode} asks for pod {n}",
        "ev_cross": "{s} s  traffic passes one pod's capacity (C = {c} req/s)",
        "ev_ready": "{s} s  pod 2 Ready",
        "ev_degraded": "{s} s  users see the service degraded",
        "title_run": "{title} · run {run} · {date}: {failed}% failed, {degraded} s degraded",
        "aegis": "Aegis", "hpa": "HPA only (CPU 70%)",
        "evidence_title": "Same traffic: Aegis asks for the 2nd pod {a} s before one pod is exceeded, the HPA {h} s after",
        "column": "{name}: {failed}% failed · {degraded} s degraded",
        "pod2": "pod 2 asked at {asked} s, Ready at {ready} s\ntraffic passes C at {c} s",
        "summary_title": "Aegis vs HPA only, same linear ramp (test 1 vs test 3)",
        "m_failed": "Failed requests (%)", "m_degraded": "Seconds degraded", "m_deficit": "Seconds above capacity in service",
        "m_exposure": "P95 exposure above L (s × s)", "m_lead": "2nd pod requested vs traffic > C",
        "m_pods": "Pod-minutes (cost)", "m_runs": "Failed requests, every run (%)",
        "lower": "lower is better", "higher": "higher is better",
        "runs_aegis": "Aegis, {n} runs", "runs_hpa": "HPA, {n} run(s)", "s_before": "{v} s before", "s_after": "{v} s after",
        "all_runs": "{title}: every run on the same axis",
        "demand_short": "demand (req/s)", "pods_req_short": "pods requested", "p95_short": "client P95 (s)",
    },
    "es": {
        "seconds": "segundos desde que empezó la carga",
        "planned": "tráfico enviado (k6)",
        "demand": "demanda medida en la entrada",
        "projection": "proyección de Aegis (T + lag adelante)",
        "capacity": "capacidad en servicio (C × pods Ready)",
        "deficit": "tráfico por encima de la capacidad en servicio",
        "p95": "latencia P95 que ven los usuarios",
        "limit": "L = {l} s (lento)",
        "degraded": "degradado (P95 > L o > 1% fallos, durante 15 s)",
        "failed": "peticiones fallidas",
        "risk": "riesgo con los pods pedidos",
        "up": "subir al 70%",
        "down": "bajar bajo 30% (con un pod menos)",
        "requested": "pods pedidos",
        "ready": "pods Ready (pedido + arranque medido)",
        "panel_traffic": "Tráfico frente a capacidad: rojo = más tráfico del que pueden atender los pods Ready",
        "panel_latency": "Latencia que ven los usuarios",
        "panel_failed": "Peticiones fallidas cada 5 s",
        "panel_risk": "Riesgo calculado por Aegis",
        "panel_pods": "Pods",
        "req_s": "req/s", "p95_s": "P95 (s)", "failed_pct": "fallidas (%)", "risk_pct": "riesgo (%)", "pods": "pods",
        "ev_up": "{s} s  {mode} pide el pod {n}",
        "ev_cross": "{s} s  el tráfico supera la capacidad de un pod (C = {c} req/s)",
        "ev_ready": "{s} s  pod 2 Ready",
        "ev_degraded": "{s} s  los usuarios ven el servicio degradado",
        "title_run": "{title} · corrida {run} · {date}: {failed}% fallidas, {degraded} s degradado",
        "aegis": "Aegis", "hpa": "Solo HPA (CPU 70%)",
        "evidence_title": "Mismo tráfico: Aegis pide el 2º pod {a} s antes de que se supere un pod, el HPA {h} s después",
        "column": "{name}: {failed}% fallidas · {degraded} s degradado",
        "pod2": "pod 2 pedido en {asked} s, Ready en {ready} s\nel tráfico supera C en {c} s",
        "summary_title": "Aegis frente a solo HPA, misma rampa lineal (test 1 frente a test 3)",
        "m_failed": "Peticiones fallidas (%)", "m_degraded": "Segundos degradado",
        "m_deficit": "Segundos por encima de la capacidad",
        "m_exposure": "Exposición de P95 sobre L (s × s)", "m_lead": "2º pod pedido frente a tráfico > C",
        "m_pods": "Pod-minutos (costo)", "m_runs": "Peticiones fallidas, cada corrida (%)",
        "lower": "menor es mejor", "higher": "mayor es mejor",
        "runs_aegis": "Aegis, {n} corridas", "runs_hpa": "HPA, {n} corrida(s)", "s_before": "{v} s antes", "s_after": "{v} s después",
        "all_runs": "{title}: todas las corridas en el mismo eje",
        "demand_short": "demanda (req/s)", "pods_req_short": "pods pedidos", "p95_short": "P95 del cliente (s)",
    },
}
TITLES_ES = {"Test 1 - Aegis, linear ramp": "Test 1 - Aegis, rampa lineal",
             "Test 2 - Aegis, fluctuating traffic": "Test 2 - Aegis, tráfico fluctuante",
             "Test 3 - HPA only, linear ramp": "Test 3 - Solo HPA, rampa lineal",
             "Test 4 - Aegis, abrupt spike": "Test 4 - Aegis, pico abrupto",
             "Test 5 - HPA only, abrupt spike": "Test 5 - Solo HPA, pico abrupto"}


def column(rows, key):
    return [row[key] for row in rows]


def scaled(rows, key, factor):
    return [None if row[key] is None else factor * row[key] for row in rows]


def style(ax):
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#c3c2b7")
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e", labelsize=9)


def panel_title(ax, text, pad=8):
    ax.set_title(text, loc="left", fontsize=11, fontweight="bold", color="#0b0b0b", pad=pad)


def read_timeline(folder, run):
    path = folder / "data" / ("run-" + str(run) + "-timeline.csv")
    if not path.exists():
        return None
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# Seconds after the request at which a pod was Ready: from the 2nd pod of the run (kube_pod_status_ready_time).
def startup_offset(summary):
    if summary["second_pod_ready_s"] is not None and summary["first_scale_up_s"] is not None:
        return max(0.0, summary["second_pod_ready_s"] - summary["first_scale_up_s"])
    return float(summary["startup_time_seconds"])


# Pods serving each second: from Ready, until removed (the CSV column lags ~20 s).
def serving_pods(summary, end, timeline=None):
    changes = sorted(summary["scale_ups"] + summary["scale_downs"], key=lambda c: c["s"])
    ready_moments = None
    if timeline is not None:
        ready_moments = sorted(float(row["seconds"]) for row in timeline if row["source"] == "pod" and row["event"] == "ready"
                               and float(row["seconds"]) > -30)
    offset = startup_offset(summary)
    events = []
    for index, change in enumerate(changes):
        if change["to"] > change["from"]:
            moment = change["s"] + offset
            if ready_moments:
                later = [m for m in ready_moments if m >= change["s"]]
                if later:
                    moment = later[0]
                    ready_moments.remove(moment)
            events.append((moment, change["to"] - change["from"]))
        else:
            events.append((change["s"], change["to"] - change["from"]))
    events.sort()
    xs = []
    ys = []
    pods = 1
    second = -30
    while second <= end:
        while events and events[0][0] <= second:
            pods += events.pop(0)[1]
        xs.append(second)
        ys.append(max(1, pods))
        second += 1
    return xs, ys


def planned_at(rows, second):
    best = None
    for row in rows:
        if row["planned_rps"] is None:
            continue
        if row["seconds"] <= second:
            best = row
        else:
            if best is None:
                return 0.0
            span = row["seconds"] - best["seconds"]
            return best["planned_rps"] + (row["planned_rps"] - best["planned_rps"]) * (second - best["seconds"]) / span
    return 0.0 if best is None else best["planned_rps"]


# Seconds where the traffic sent was above what the Ready pods can serve.
def deficit_seconds(rows, summary, timeline=None):
    end = max(row["seconds"] for row in rows if row["planned_rps"] is not None)
    xs, pods = serving_pods(summary, end, timeline)
    total = 0
    for second, count in zip(xs, pods):
        if second >= 0 and planned_at(rows, second) > summary["capacity_rps"] * count:
            total += 1
    return total


# Intervals the client saw degraded: same rule as metrics.degraded_time, from the 5 s CSV rows.
def degraded_intervals(rows):
    intervals = []
    streak = []
    for row in rows + [None]:
        bad = False
        if row is not None:
            if row["client_p95_s"] is not None and row["client_p95_s"] > L_SECONDS:
                bad = True
            if row["client_failed_ratio"] is not None and row["client_failed_ratio"] > MAX_FAILED_RATIO:
                bad = True
        if bad:
            streak.append(row["seconds"])
            continue
        if len(streak) >= SUSTAINED_BUCKETS:
            intervals.append((streak[0] - STEP / 2, streak[-1] + STEP / 2))
        streak = []
    return intervals


def draw_traffic(ax, rows, summary, color, t, timeline=None, projection=False, legend=True):
    x = column(rows, "seconds")
    end = max(x)
    sx, pods = serving_pods(summary, end, timeline)
    capacity = [summary["capacity_rps"] * count for count in pods]
    planned = [planned_at(rows, second) if second >= 0 else None for second in sx]
    ax.fill_between(sx, 0, capacity, step="post", color=color, alpha=0.12, linewidth=0)
    ax.step(sx, capacity, where="post", color=color, linewidth=2.2, label=t["capacity"])
    over = [p is not None and p > c for p, c in zip(planned, capacity)]
    ax.fill_between(sx, capacity, [p if p is not None else c for p, c in zip(planned, capacity)], where=over,
                    step="post", color=DEFICIT, alpha=0.45, linewidth=0, label=t["deficit"])
    ax.plot(x, column(rows, "planned_rps"), color=PLANNED, linestyle="--", linewidth=1.4, label=t["planned"])
    ax.plot(x, column(rows, "demand_rps"), color=TRAFFIC, linewidth=1.6, label=t["demand"])
    if projection:
        ax.plot(x, column(rows, "aegis_projected_rps"), color=AEGIS, linestyle=":", linewidth=1.4, label=t["projection"])
    ax.set_ylim(0, max(80, max(capacity) * 1.15))
    ax.set_ylabel(t["req_s"])
    if legend:
        ax.legend(loc="upper right", fontsize=8, frameon=True, framealpha=0.95)


def draw_latency(ax, rows, t, legend=True):
    for start, end in degraded_intervals(rows):
        ax.axvspan(start, end, color=DEFICIT, alpha=0.13, linewidth=0)
    ax.plot(column(rows, "seconds"), column(rows, "client_p95_s"), color=TRAFFIC, linewidth=1.6, label=t["p95"])
    ax.axhline(L_SECONDS, color=DEFICIT, linestyle="--", linewidth=1.2, label=t["limit"].format(l=L_SECONDS))
    ax.set_ylim(0, 11)
    ax.set_ylabel(t["p95_s"])
    if legend:
        handles, labels = ax.get_legend_handles_labels()
        handles.append(Patch(color=DEFICIT, alpha=0.13))
        labels.append(t["degraded"])
        ax.legend(handles, labels, loc="upper right", fontsize=8, framealpha=0.95)


def draw_failed(ax, rows, t):
    x = [row["seconds"] for row in rows if row["client_failed_ratio"] is not None]
    y = [100 * row["client_failed_ratio"] for row in rows if row["client_failed_ratio"] is not None]
    ax.bar(x, y, width=STEP * 0.85, color=DEFICIT, alpha=0.85)
    ax.set_ylim(0, 105)
    ax.set_ylabel(t["failed_pct"])


# Numbered markers at the top of the first panel and a key that explains them.
def mark_events(axes, summary, mode_name, t):
    events = []
    for index, up in enumerate(summary["scale_ups"]):
        events.append((up["s"], "#6250d6", t["ev_up"].format(s=int(round(up["s"])), mode=mode_name, n=up["to"])))
    if summary["crosses_c_s"] is not None:
        events.append((summary["crosses_c_s"], TRAFFIC, t["ev_cross"].format(s=int(round(summary["crosses_c_s"])),
                                                                             c=int(summary["capacity_rps"]))))
    if summary["second_pod_ready_s"] is not None:
        events.append((summary["second_pod_ready_s"], GOOD, t["ev_ready"].format(s=int(round(summary["second_pod_ready_s"])))))
    if summary["first_degraded_s"] is not None:
        events.append((summary["first_degraded_s"], DEFICIT, t["ev_degraded"].format(s=int(summary["first_degraded_s"]))))
    events.sort(key=lambda e: e[0])
    lines = []
    previous = None
    level = 0
    for number, (seconds, color, label) in enumerate(events, start=1):
        for ax in axes:
            ax.axvline(seconds, color=color, linestyle=(0, (4, 3)), linewidth=1.1, alpha=0.9)
        level = 1 - level if previous is not None and seconds - previous < 12 else 0
        previous = seconds
        axes[0].annotate(str(number), xy=(seconds, 1.0), xycoords=("data", "axes fraction"),
                         xytext=(0, 4 + 15 * level), textcoords="offset points", ha="center", va="bottom", fontsize=8,
                         fontweight="bold", color="white",
                         bbox={"boxstyle": "circle,pad=0.25", "facecolor": color, "edgecolor": "none"})
        lines.append(str(number) + "   " + label)
    axes[0].text(0.01, 0.97, "\n".join(lines), transform=axes[0].transAxes, va="top", ha="left", fontsize=8.5,
                 linespacing=1.5, bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "edgecolor": "#c3c2b7",
                                        "alpha": 0.95})


# Chart of one run: traffic vs capacity in service, latency, failures, Aegis risk (if on) and pods.
def plot_run(path, title, summary, rows, lang="en", timeline=None):
    t = TEXT[lang]
    aegis = summary["mode"] != "hpa"
    color = AEGIS if aegis else HPA
    heights = [3.2, 2.0, 1.4] + ([1.6] if aegis else []) + [1.4]
    fig = Figure(figsize=(12, sum(heights) * 1.1 + 1.4))
    axes = fig.subplots(len(heights), 1, sharex=True, gridspec_kw={"height_ratios": heights})
    draw_traffic(axes[0], rows, summary, color, t, timeline, projection=aegis)
    panel_title(axes[0], t["panel_traffic"], pad=34)
    draw_latency(axes[1], rows, t)
    panel_title(axes[1], t["panel_latency"])
    draw_failed(axes[2], rows, t)
    panel_title(axes[2], t["panel_failed"])
    if aegis:
        ax = axes[3]
        ax.axhspan(70, 105, color=DEFICIT, alpha=0.06, linewidth=0)
        ax.plot(column(rows, "seconds"), scaled(rows, "aegis_risk", 100), color=AEGIS, linewidth=1.8, label=t["risk"])
        ax.axhline(70, color=DEFICIT, linestyle="--", linewidth=1, label=t["up"])
        ax.axhline(30, color=GOOD, linestyle="--", linewidth=1, label=t["down"])
        ax.set_ylim(0, 105)
        ax.set_ylabel(t["risk_pct"])
        ax.legend(loc="upper right", fontsize=8, framealpha=0.95)
        panel_title(ax, t["panel_risk"])
    ax = axes[-1]
    end = max(column(rows, "seconds"))
    sx, pods = serving_pods(summary, end, timeline)
    ax.step(column(rows, "seconds"), column(rows, "requested"), where="post", color=color, linewidth=2.2,
            label=t["requested"])
    ax.step(sx, pods, where="post", color=GOOD, linewidth=1.6, linestyle="--", label=t["ready"])
    ax.set_ylim(0, 3.6)
    ax.set_yticks([0, 1, 2, 3])
    ax.set_ylabel(t["pods"])
    ax.set_xlabel(t["seconds"])
    ax.legend(loc="upper right", fontsize=8, framealpha=0.95)
    panel_title(ax, t["panel_pods"])
    for item in axes:
        style(item)
    mark_events(axes, summary, t["aegis"] if aegis else "HPA", t)
    shown = TITLES_ES.get(title, title) if lang == "es" else title
    fig.suptitle(t["title_run"].format(title=shown, run=summary["run"], date=summary["date_utc"],
                                       failed=summary["failed_percent"], degraded=summary["degraded_seconds"]),
                 fontsize=13, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=120)


# The runs of a test on top of each other, to see that they behave the same.
def plot_all_runs(path, title, summaries, runs, lang="en"):
    t = TEXT[lang]
    fig = Figure(figsize=(12, 10))
    axes = fig.subplots(3, 1, sharex=True)
    for index, summary in enumerate(summaries):
        rows = runs[index]
        color = RUN_COLORS[index % len(RUN_COLORS)]
        label = "run " + str(summary["run"])
        x = column(rows, "seconds")
        if index == 0:
            axes[0].plot(x, column(rows, "planned_rps"), color=PLANNED, linestyle="--", linewidth=2, label=t["planned"])
        axes[0].plot(x, column(rows, "demand_rps"), color=color, label=label)
        axes[1].step(x, column(rows, "requested"), where="post", color=color, label=label)
        axes[2].plot(x, column(rows, "client_p95_s"), color=color, label=label)
    axes[0].axhline(summaries[0]["capacity_rps"], color=DEFICIT, linestyle=":", label="C")
    axes[0].set_ylabel(t["demand_short"])
    axes[1].set_ylabel(t["pods_req_short"])
    axes[1].set_yticks([0, 1, 2, 3])
    axes[1].set_ylim(0, 3.5)
    axes[2].axhline(L_SECONDS, color=DEFICIT, linestyle="--", label="L")
    axes[2].set_ylabel(t["p95_short"])
    axes[2].set_ylim(0, 11)
    axes[2].set_xlabel(t["seconds"])
    for ax in axes:
        style(ax)
        ax.legend(loc="upper right", fontsize=8)
    shown = TITLES_ES.get(title, title) if lang == "es" else title
    fig.suptitle(t["all_runs"].format(title=shown), fontsize=13, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=120)


# Side by side, same scales: Aegis (left) and the HPA alone (right) under the same load.
def plot_evidence(path, aegis, hpa, lang="en"):
    t = TEXT[lang]
    fig = Figure(figsize=(15, 10.5))
    axes = fig.subplots(3, 2, sharex=True, sharey="row", gridspec_kw={"height_ratios": [3.2, 2.0, 1.4]})
    for col, (summary, rows, timeline, color, name) in enumerate([
            (aegis[0], aegis[1], aegis[2], AEGIS, t["aegis"]), (hpa[0], hpa[1], hpa[2], HPA, t["hpa"])]):
        draw_traffic(axes[0][col], rows, summary, color, t, timeline, legend=False)
        axes[0][col].set_ylim(0, 100)
        draw_latency(axes[1][col], rows, t, legend=col == 1)
        draw_failed(axes[2][col], rows, t)
        axes[2][col].set_xlabel(t["seconds"])
        crosses = summary["crosses_c_s"]
        ready = summary["second_pod_ready_s"]
        for ax in axes[:, col]:
            ax.axvline(crosses, color=TRAFFIC, linestyle=(0, (4, 3)), linewidth=1.1)
            ax.axvline(ready, color=GOOD, linewidth=1.6)
        asked = summary["first_scale_up_s"]
        axes[0][col].text(0.98, 0.97, t["pod2"].format(asked=int(round(asked)), ready=int(round(ready)), c=int(round(crosses))),
                          transform=axes[0][col].transAxes, ha="right", va="top", fontsize=10, fontweight="bold",
                          color=GOOD if asked <= crosses else DEFICIT,
                          bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#c3c2b7"})
        axes[0][col].set_title(t["column"].format(name=name, failed=summary["failed_percent"],
                                                  degraded=summary["degraded_seconds"]),
                               loc="left", fontsize=13, fontweight="bold", color=color, pad=10)
        axes[1][col].set_title(t["panel_latency"], loc="left", fontsize=10, color="#52514e")
        axes[2][col].set_title(t["panel_failed"], loc="left", fontsize=10, color="#52514e")
        for ax in axes[:, col]:
            style(ax)
    handles, labels = axes[0][1].get_legend_handles_labels()
    handles += axes[1][1].get_legend_handles_labels()[0][:2] + [Patch(color=DEFICIT, alpha=0.13),
               Line2D([], [], color=TRAFFIC, linestyle=(0, (4, 3))), Line2D([], [], color=GOOD, linewidth=1.6)]
    labels += axes[1][1].get_legend_handles_labels()[1][:2] + [t["degraded"], t["ev_cross"].split("  ")[1].format(
        c=int(aegis[0]["capacity_rps"])), t["ev_ready"].split("  ")[1]]
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=9, frameon=False)
    a_lead = int(round(aegis[0]["crosses_c_s"] - aegis[0]["first_scale_up_s"]))
    h_lead = int(round(hpa[0]["first_scale_up_s"] - hpa[0]["crosses_c_s"]))
    fig.suptitle(t["evidence_title"].format(a=a_lead, h=h_lead), fontsize=14, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    fig.savefig(path, dpi=120)


def bar_panel(ax, title, values, colors, labels, better, t, fmt):
    bars = ax.bar(range(len(values)), values, color=colors, width=0.6)
    top = max(abs(v) for v in values) or 1
    for bar, value in zip(bars, values):
        y = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, y + (0.04 * top if y >= 0 else -0.04 * top), fmt(value),
                ha="center", va="bottom" if y >= 0 else "top", fontsize=12, fontweight="bold", color="#0b0b0b")
    ax.set_xticks(range(len(values)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.axhline(0, color="#52514e", linewidth=0.8)
    low = min(0, min(values))
    ax.set_ylim(low * 1.35 if low < 0 else 0, max(0, max(values)) * 1.3 + 0.15 * top)
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=14)
    ax.set_xlabel(t[better], fontsize=8.5, color="#898781")
    ax.set_yticks([])
    style(ax)
    ax.grid(False)
    ax.spines["left"].set_visible(False)


# The numbers that matter as bars, plus the failed requests of every repeated run.
def plot_summary(path, aegis, hpa, repeats, hpa_runs, lang="en"):
    t = TEXT[lang]
    labels = [t["aegis"], "HPA"]
    colors = [AEGIS, HPA]
    metrics = [
        ("m_failed", [aegis["failed_percent"], hpa["failed_percent"]], "lower", lambda v: str(v) + "%"),
        ("m_degraded", [aegis["degraded_seconds"], hpa["degraded_seconds"]], "lower", lambda v: str(int(v)) + " s"),
        ("m_deficit", [aegis["deficit_s"], hpa["deficit_s"]], "lower", lambda v: str(int(v)) + " s"),
        ("m_exposure", [aegis["p95_excess_s2"], hpa["p95_excess_s2"]], "lower", lambda v: str(int(round(v)))),
        ("m_lead", [aegis["crosses_c_s"] - aegis["first_scale_up_s"], hpa["crosses_c_s"] - hpa["first_scale_up_s"]],
         "higher", lambda v: (t["s_before"] if v >= 0 else t["s_after"]).format(v=int(round(abs(v))))),
        ("m_pods", [aegis["pod_minutes"], hpa["pod_minutes"]], "lower", lambda v: str(v)),
    ]
    fig = Figure(figsize=(15, 7.6))
    grid = fig.add_gridspec(2, 4)
    positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
    for (key, values, better, fmt), (row, col) in zip(metrics, positions):
        bar_panel(fig.add_subplot(grid[row, col]), t[key], values, colors, labels, better, t, fmt)
    ax = fig.add_subplot(grid[:, 3])
    aegis_runs = [r["failed_percent"] for r in repeats]
    ax.scatter([0] * len(aegis_runs), aegis_runs, s=90, color=AEGIS, zorder=3, edgecolor="white", linewidth=1.5)
    hpa_values = [r["failed_percent"] for r in hpa_runs]
    ax.scatter([1] * len(hpa_values), hpa_values, s=90, color=HPA, zorder=3, edgecolor="white", linewidth=1.5)
    ax.text(0.12, max(aegis_runs) + 1.2, str(min(aegis_runs)) + "–" + str(max(aegis_runs)) + "%", va="bottom",
            fontsize=10, fontweight="bold")
    hpa_text = str(min(hpa_values)) + "%" if len(hpa_values) == 1 else str(min(hpa_values)) + "–" + str(max(hpa_values)) + "%"
    ax.text(1.12, sum(hpa_values) / len(hpa_values), hpa_text, va="center", fontsize=10, fontweight="bold")
    ax.set_xticks([0, 1])
    ax.set_xticklabels([t["runs_aegis"].format(n=len(aegis_runs)), t["runs_hpa"].format(n=len(hpa_values))], fontsize=10)
    ax.set_xlim(-0.5, 1.7)
    ax.set_ylim(0, max(35, max(hpa_values) * 1.15))
    ax.set_title(t["m_runs"], fontsize=11, fontweight="bold", loc="left")
    style(ax)
    fig.suptitle(t["summary_title"], fontsize=14, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=120)

