import argparse
import sys
import time
from cluster import say
from preflight import preflight
from run import run_test
from settings import CAMPAIGN_RUNS, TESTS


# Preflight, every test, then charts and tables. Saved runs are skipped, so it can resume.
def main():
    parser = argparse.ArgumentParser(description="Run the whole experiment campaign")
    parser.add_argument("tests", nargs="*", default=list(CAMPAIGN_RUNS), choices=list(TESTS))
    parser.add_argument("--runs", type=int, help="runs of every test (default: CAMPAIGN_RUNS in settings.py)")
    parser.add_argument("--archive", action="store_true", help="move runs made with another calibration to archive/")
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()
    runs = {name: args.runs or CAMPAIGN_RUNS.get(name, 1) for name in args.tests}
    if not args.skip_preflight and not preflight(args.tests, runs, args.archive):
        sys.exit(1)
    started = time.monotonic()
    for name in args.tests:
        say("=== " + name + ": " + str(runs[name]) + " run(s)")
        run_test(name, runs[name], 1, args.archive)
    import capacity
    import compare
    import forecast_accuracy
    import report
    report.report(list(TESTS))
    compare.main([])
    capacity.main()
    forecast_accuracy.main([])
    say("campaign finished in", round((time.monotonic() - started) / 60), "min: docs/tests/comparison.md")


if __name__ == "__main__":
    main()
