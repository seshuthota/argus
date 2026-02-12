#!/usr/bin/env bash
set -euo pipefail

# Wrapper around Argus benchmark automation.
# Usage:
#   scripts/run_benchmark_pipeline.sh [extra benchmark-pipeline args...]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="./.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

"$PY" -m argus.cli benchmark-pipeline "$@"
