import argparse
from load import read_profile
from metrics import false_alarms, needed_pod_minutes
from report import load_test
from settings import BOUNDARY_TESTS, COMPARISONS, L_SECONDS, STEP, TESTS, TESTS_DIR

# (key, label, decimals, better): better is "lower" or "higher" for the verdict column.
ROWS = [
    ("failed_percent", "Failed requests (%)", 2, "lower"),
    ("degraded_seconds", "Seconds degraded (P95 > L or > 1% failed, for T_d)", 0, "lower"),
    ("p95_excess_s2", "P95 exposure above L (s x s)", 1, "lower"),
    ("client_p95_s", "Client P95 over the whole run (s)", 2, "lower"),
    ("first_scale_up_s", "First pod requested (s from k6 start)", 1, "lower"),
    ("second_pod_ready_s", "Second pod Ready (s)", 1, "lower"),
    ("lead_s", "Lead: traffic passes C minus 2nd pod Ready (s)", 1, "higher"),
    ("degraded_to_ready_s", "Degradation onset to 2nd pod Ready (s; negative: Ready before)", 1, "lower"),
    ("pod_minutes", "Pod-minutes", 2, "lower"),
    ("extra_pod_minutes", "Pod-minutes above what the planned traffic needed", 2, "lower"),
    ("false_scale_ups", "False alarm scale-ups", 0, "lower"),
]


# Fills the metrics added after a run was recorded, from its saved CSV and the load profile.
def complete(summary, rows):
    profile = read_profile(summary["profile"], summary["capacity_rps"])
    if summary.get("p95_excess_s2") is None:
        area = 0.0
        for row in rows:
            if row["client_p95_s"] is not None and 0 <= row["seconds"]:
                area += max(0.0, row["client_p95_s"] - L_SECONDS) * STEP
        summary["p95_excess_s2"] = round(area, 1)
    if summary.get("degraded_to_ready_s") is None and summary["first_degraded_s"] is not None \
            and summary["second_pod_ready_s"] is not None:
        summary["degraded_to_ready_s"] = round(summary["second_pod_ready_s"] - summary["first_degraded_s"], 1)
    if summary.get("false_scale_ups") is None:
        summary["false_scale_ups"] = false_alarms(summary["scale_ups"], profile, summary["capacity_rps"])
    if summary.get("needed_pod_minutes") is None:
        summary["needed_pod_minutes"] = needed_pod_minutes(profile, summary["capacity_rps"])
        summary["extra_pod_minutes"] = round(summary["pod_minutes"] - summary["needed_pod_minutes"], 2)
    return summary


def collect(name):
    summaries, runs = load_test(TESTS_DIR / name)
    return [complete(summary, rows) for summary, rows in zip(summaries, runs)]


def cell(summaries, key, decimals):
    values = [s[key] for s in summaries if s.get(key) is not None]
    if not values:
        return None, "–"
    mean = sum(values) / len(values)
    text = str(round(mean, decimals)) if decimals else str(int(round(mean)))
    if len(values) > 1:
        text += " (" + str(round(min(values), decimals)) + " – " + str(round(max(values), decimals)) + ")"
    return mean, text


def verdict(aegis, hpa, better):
    if aegis is None or hpa is None or aegis == hpa:
        return "="
    if (aegis < hpa) == (better == "lower"):
        return "Aegis"
    return "HPA"


def table(aegis_name, hpa_name, title):
    aegis = collect(aegis_name)
    hpa = collect(hpa_name)
    lines = ["## " + title, ""]
    if not aegis or not hpa:
        missing = [name for name, runs in ((aegis_name, aegis), (hpa_name, hpa)) if not runs]
        lines.append("Not run yet: `python3 run.py " + "` and `python3 run.py ".join(missing) + "`.")
        return lines + [""]
    lines.append("Mean over the runs (min – max). Aegis: " + str(len(aegis)) + " run(s) of [" + aegis_name + "]("
                 + aegis_name + "/); HPA only: " + str(len(hpa)) + " run(s) of [" + hpa_name + "](" + hpa_name + "/).")
    lines += ["", "| | Aegis | HPA only | Better |", "|---|---|---|---|"]
    for key, label, decimals, better in ROWS:
        aegis_mean, aegis_text = cell(aegis, key, decimals)
        hpa_mean, hpa_text = cell(hpa, key, decimals)
        lines.append("| " + label + " | " + aegis_text + " | " + hpa_text + " | " + verdict(aegis_mean, hpa_mean, better)
                     + " |")
    return lines + [""]


# Rise of the stage where the planned traffic first passes C, in req/s per second, and seconds from base to C.
def climb(profile, capacity):
    rate = profile["start_rate"]
    for target, duration in profile["stages"]:
        if target >= capacity > rate or (target >= capacity and rate >= capacity):
            if target == rate:
                return None, None
            slope = (target - rate) / duration
            return round(slope, 3), round((capacity - rate) / slope, 1)
        rate = target
    return None, None


def mean_text(values, decimals):
    values = [v for v in values if v is not None]
    if not values:
        return "–"
    mean = round(sum(values) / len(values), decimals) if decimals else int(round(sum(values) / len(values)))
    if len(values) == 1:
        return str(mean)
    return str(mean) + " (" + str(round(min(values), decimals)) + " – " + str(round(max(values), decimals)) + ")"


# How fast the traffic can rise before Aegis stops anticipating (hypothesis H2).
def boundary_table():
    lines = ["## Boundary: how fast the traffic can rise", "",
             "Aegis runs. Ahead = seconds from requesting the 2nd pod to the traffic passing C.", "",
             "| Test | Climb (req/s per s) | Base → C (s) | Runs | Failed (%) | Requested ahead (s) | Seconds degraded |",
             "|---|---|---|---|---|---|---|"]
    found = False
    for name in BOUNDARY_TESTS:
        runs = collect(name)
        if not runs:
            lines.append("| " + name + " | | | 0 (not run yet) | | | |")
            continue
        found = True
        slope, to_c = climb(read_profile(runs[0]["profile"], runs[0]["capacity_rps"]), runs[0]["capacity_rps"])
        ahead = [r["crosses_c_s"] - r["first_scale_up_s"] for r in runs
                 if r["crosses_c_s"] is not None and r["first_scale_up_s"] is not None]
        lines.append("| [" + name + "](" + name + "/) | " + str(slope if slope is not None else "step") + " | "
                     + str(to_c if to_c is not None else "≈ 0") + " | " + str(len(runs)) + " | "
                     + mean_text([r["failed_percent"] for r in runs], 2) + " | " + mean_text(ahead, 1) + " | "
                     + mean_text([r["degraded_seconds"] for r in runs], 0) + " |")
    steep = TESTS_DIR / "test2-fluctuating" / "data" / "steep-waves-summary.json"
    if steep.exists():
        import json
        data = json.loads(steep.read_text())
        lines.append("| steep waves (earlier version of test 2) | 0.58 | 33 | 1 | " + str(data["failed_percent"]) + " | "
                     + str(round(data["crosses_c_s"] - data["first_scale_up_s"], 1)) + " | "
                     + str(data["degraded_seconds"]) + " |")
    return lines + [""] if found else lines + ["", "Run the boundary tests: `python3 run.py test6-ramp-045 --runs 3`.", ""]


# Aegis deciding through the Custom Metrics API (test 8) vs writing minReplicas (test 1), same ramp.
def metric_table():
    metric = collect("test8-metric-mode")
    direct = collect("test1-linear-ramp")
    lines = ["## Metric mode: the HPA reads the Aegis decision through the Custom Metrics API", ""]
    if not metric:
        return lines + ["Not run yet: `python3 run.py test8-metric-mode --runs 3` (needs `scripts/setup.sh --aegis`).", ""]
    delays = [d for r in metric for d in r.get("metric_path_delays_s", [])]
    lines += ["| | minReplicas mode (test 1) | metric mode (test 8) |", "|---|---|---|"]
    for key, label, decimals in [("failed_percent", "Failed requests (%)", 2), ("degraded_seconds", "Seconds degraded", 0),
                                 ("first_scale_up_s", "First pod requested by the HPA (s)", 1),
                                 ("second_pod_ready_s", "Second pod Ready (s)", 1), ("pod_minutes", "Pod-minutes", 2)]:
        lines.append("| " + label + " | " + mean_text([r.get(key) for r in direct], decimals) + " | "
                     + mean_text([r.get(key) for r in metric], decimals) + " |")
    lines += ["", "Aegis decision → HPA rescale: " + mean_text(delays, 1)
              + " s over " + str(len(delays)) + " scale-ups.", ""]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="Aegis vs HPA only, same load: docs/tests/comparison.md")
    parser.parse_args(argv)
    lines = ["# Aegis vs HPA only", "",
             "Generated by `compare.py`. Degraded = client P95 > " + str(L_SECONDS) + " s or > 1% failed, for T_d. "
             "False alarm = a scale-up the planned traffic did not need within 60 s.", ""]
    for aegis_name, hpa_name, title in COMPARISONS:
        if aegis_name in TESTS and hpa_name in TESTS:
            lines += table(aegis_name, hpa_name, title)
    lines += boundary_table()
    lines += metric_table()
    (TESTS_DIR / "comparison.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
