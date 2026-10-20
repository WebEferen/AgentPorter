#!/usr/bin/env bash
set -euo pipefail
python3 "$(dirname "$0")/../_lib/stage.py" surveyed --license GPL-3.0-only
