"""The experiment campaign: a randomized complete block design (docs/experiments/design.md).

Every block runs the 9 cells (3 autoscalers x 3 loads) once, in a random order fixed by DESIGN_SEED and
the block number. Run number = block number, so `ramp-aegis/data/run-3-*` is the ramp with Aegis of
block 3. Blocks can be split across sessions (--blocks 1-2, then --blocks 3-4, ...): a block is the unit
that absorbs drift between sessions. Saved runs are skipped, so an interrupted session resumes.

Usage:
  python3 campaign.py --plan              # print the order of every block, run nothing
  python3 campaign.py --blocks 1-2        # run blocks 1 and 2
  python3 campaign.py                     # run every missing block, then the analysis
"""
import argparse
import json
import random
import sys
import time
from cluster import say
from preflight import power_profile, preflight
from run import run_test
from settings import BLOCKS, DESIGN_SEED, DESIGN_TESTS, TESTS_DIR

SCHEDULE_FILE = TESTS_DIR / "design-schedule.json"


# The order of the 9 cells in every block: a fresh random permutation per block, reproducible from the seed.
def schedule(blocks=BLOCKS, seed=DESIGN_SEED):
    cells = sorted(DESIGN_TESTS)
    plan = []
    for block in range(1, blocks + 1):
        order = random.Random(seed * 1000 + block).sample(cells, len(cells))
        plan.append({"block": block, "order": order})
    return plan


def parse_blocks(text):
    if not text:
        return list(range(1, BLOCKS + 1))
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def done(test, block):
    return (TESTS_DIR / test / "data" / ("run-" + str(block) + "-summary.json")).exists()


def main():
    parser = argparse.ArgumentParser(description="Run the experiment design: 9 cells per block, random order")
    parser.add_argument("--blocks", help="blocks to run, e.g. 1-2 (default: all)")
    parser.add_argument("--plan", action="store_true", help="print the order and exit")
    parser.add_argument("--archive", action="store_true", help="move runs made with another calibration to archive/")
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()
    plan = schedule()
    SCHEDULE_FILE.write_text(json.dumps({"seed": DESIGN_SEED, "blocks": plan}, indent=1))
    blocks = parse_blocks(args.blocks)
    if args.plan:
        for entry in plan:
            if entry["block"] in blocks:
                marks = [test + (" (done)" if done(test, entry["block"]) else "") for test in entry["order"]]
                print("block", entry["block"], ":", ", ".join(marks))
        return
    runs = {test: max(blocks) for test in DESIGN_TESTS}
    if not args.skip_preflight and not preflight(sorted(DESIGN_TESTS), runs, args.archive):
        sys.exit(1)
    started = time.monotonic()
    for entry in plan:
        if entry["block"] not in blocks:
            continue
        say("=== block", entry["block"], "of", BLOCKS)
        for position, test in enumerate(entry["order"], start=1):
            if done(test, entry["block"]):
                continue
            say("--- block", entry["block"], "cell", position, "of 9:", test)
            run_test(test, entry["block"], entry["block"], args.archive,
                     extra={"block": entry["block"], "order_in_block": position, "design_seed": DESIGN_SEED,
                            "power_profile": "/".join(str(p) for p in power_profile())})
    import design_analysis
    import report
    report.report(sorted(DESIGN_TESTS))
    design_analysis.main([])
    say("blocks", blocks, "finished in", round((time.monotonic() - started) / 60), "min: docs/tests/design-results.md")


if __name__ == "__main__":
    main()
