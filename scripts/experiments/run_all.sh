#!/usr/bin/env bash
# Runs the three tests once each (about 25 minutes) and draws their charts. Runs already done are skipped.
set -euo pipefail
cd "$(dirname "$0")"

python3 run.py test1-linear-ramp
python3 run.py test3-hpa-baseline
python3 run.py test2-fluctuating
python3 report.py
