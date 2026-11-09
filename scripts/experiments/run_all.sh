#!/usr/bin/env bash
# The experiment design (docs/experiments/design.md): 6 blocks x 9 cells, ~13 h, resumable.
# Options go to campaign.py (--blocks 1-2, --plan, --archive).
set -euo pipefail
cd "$(dirname "$0")"
python3 campaign.py "$@"
