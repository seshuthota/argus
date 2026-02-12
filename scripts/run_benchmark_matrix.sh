#!/usr/bin/env bash
set -euo pipefail

# Wrapper around Argus benchmark-matrix command.
# Usage:
#   scripts/run_benchmark_matrix.sh [extra benchmark-matrix args...]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="./.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

"$PY" -m argus.cli benchmark-matrix "$@"

