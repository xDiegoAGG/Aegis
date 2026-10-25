#!/usr/bin/env bash
# The whole campaign (~3 h, resumable). Options go to campaign.py (--archive, a list of tests).
set -euo pipefail
cd "$(dirname "$0")"
python3 campaign.py "$@"
