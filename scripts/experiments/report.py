import argparse
import csv
import json
from charts import plot_all_runs, plot_run, read_timeline
from settings import TESTS, TESTS_DIR

RESULT_KEYS = ["failed_percent", "client_p95_s", "degraded_seconds", "p95_excess_s2", "crosses_c_s",
               "first_scale_up_s", "second_pod_ready_s", "lead_s", "degraded_to_ready_s", "max_pods", "pod_minutes",
               "extra_pod_minutes", "false_scale_ups", "dropped_iterations"]


def load_rows(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            parsed = {}
            for key, value in row.items():
                if key == "time_utc":
                    parsed[key] = value
                elif value == "":
                    parsed[key] = None
                else:
                    parsed[key] = float(value)
            rows.append(parsed)
    return rows


def run_number(path):
    return int(path.name.split("-")[1])


# The summaries and time series of every saved run of a test.
def load_test(folder):
    summaries = []
    runs = []
    for path in sorted((folder / "data").glob("run-*-summary.json"), key=run_number):
        summary = json.loads(path.read_text())
        summaries.append(summary)
        runs.append(load_rows(folder / "data" / ("run-" + str(summary["run"]) + ".csv")))
    return summaries, runs


def stats(summaries, key):
    values = []
    for summary in summaries:
        if summary.get(key) is not None:
            values.append(summary[key])
    if not values:
        return None
    return {"mean": round(sum(values) / len(values), 2), "min": min(values), "max": max(values), "n": len(values)}


def changes_text(summary):
    changes = []
    for change in summary["scale_ups"] + summary["scale_downs"]:
        changes.append((change["s"], str(change["from"]) + "->" + str(change["to"]) + " at " + str(int(change["s"])) + " s"))
    changes.sort()
    labels = []
    for seconds, label in changes:
        labels.append(label)
    return ", ".join(labels)


# Writes results.csv of a test and prints its numbers.
def write_results(folder, title, summaries):
    with open(folder / "results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run", "k6_start_utc", "scale_changes"] + RESULT_KEYS)
        for summary in summaries:
            row = [summary["run"], summary["date_utc"] + " " + summary["k6_start_utc"], changes_text(summary)]
            for key in RESULT_KEYS:
                row.append(summary.get(key))
            writer.writerow(row)
    print()
    print(title)
    for summary in summaries:
        line = ["  run", summary["run"], summary["k6_start_utc"]]
        for key in RESULT_KEYS:
            line.append(key + "=" + str(summary.get(key)))
        print(*line)
        print("     ", changes_text(summary))
    for key in RESULT_KEYS:
        print("  ", key, stats(summaries, key))


def report(names):
    tests = []
    for name in names:
        folder = TESTS_DIR / name
        title = TESTS[name][2]
        summaries, runs = load_test(folder)
        if not summaries:
            print(name, "has no runs yet")
            continue
        # chart.png (English) and chart.es.png (Spanish); with several runs one chart per run plus all-runs.
        for lang, suffix in (("en", ".png"), ("es", ".es.png")):
            if len(summaries) == 1:
                plot_run(folder / ("chart" + suffix), title, summaries[0], runs[0], lang,
                         read_timeline(folder, summaries[0]["run"]))
                continue
            for index, summary in enumerate(summaries):
                plot_run(folder / ("run-" + str(summary["run"]) + suffix), title, summary, runs[index], lang,
                         read_timeline(folder, summary["run"]))
            plot_all_runs(folder / ("all-runs" + suffix), title, summaries, runs, lang)
        write_results(folder, title, summaries)
        tests.append((title, summaries))
    import evidence  # here, not at the top: evidence imports this module
    evidence.main()
    print("charts saved")


def main():
    parser = argparse.ArgumentParser(description="Draw the charts and tables of the tests that ran")
    parser.add_argument("tests", nargs="*", default=list(TESTS), choices=list(TESTS))
    args = parser.parse_args()
    report(args.tests)


if __name__ == "__main__":
    main()
