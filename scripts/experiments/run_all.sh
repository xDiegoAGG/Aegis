#!/usr/bin/env bash
# Runs the three tests (5 runs each, about 2 hours) and draws every chart. Runs already done are skipped.
set -euo pipefail
cd "$(dirname "$0")"

python3 run.py test1-linear-ramp
python3 report.py test1-linear-ramp
python3 run.py test3-hpa-baseline
python3 report.py test3-hpa-baseline
python3 run.py test2-fluctuating
python3 report.py
