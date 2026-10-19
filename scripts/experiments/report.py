import argparse
import csv
import json
from charts import plot_all_runs, plot_comparison, plot_run
from settings import TESTS, TESTS_DIR

RESULT_KEYS = ["failed_percent", "client_p95_s", "degraded_seconds", "crosses_c_s", "first_scale_up_s",
               "second_pod_ready_s", "lead_s", "max_pods", "pod_minutes", "dropped_iterations"]


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
        if summary[key] is not None:
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
                row.append(summary[key])
            writer.writerow(row)
    print()
    print(title)
    for summary in summaries:
        line = ["  run", summary["run"], summary["k6_start_utc"]]
        for key in RESULT_KEYS:
            line.append(key + "=" + str(summary[key]))
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
        for index, summary in enumerate(summaries):
            plot_run(folder / ("run-" + str(summary["run"]) + ".png"), title, summary, runs[index])
        plot_all_runs(folder / "all-runs.png", title, summaries, runs)
        write_results(folder, title, summaries)
        tests.append((title, summaries))
    if len(tests) > 1:
        plot_comparison(tests, stats)
    print("charts saved")


def main():
    parser = argparse.ArgumentParser(description="Draw the charts and tables of the tests that ran")
    parser.add_argument("tests", nargs="*", default=list(TESTS), choices=list(TESTS))
    args = parser.parse_args()
    report(args.tests)


if __name__ == "__main__":
    main()
