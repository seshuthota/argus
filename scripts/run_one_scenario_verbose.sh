#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <scenario_yaml> <model> [extra args...]"
  echo "Example:"
  echo "  $0 scenarios/cases/agency_email_001.yaml MiniMax-M2.5 --log-file reports/execution_logs/manual_verbose.log"
  exit 1
fi

SCENARIO_PATH="$1"
MODEL_NAME="$2"
shift 2

./.venv/bin/python scripts/run_one_scenario_verbose.py \
  --scenario "$SCENARIO_PATH" \
  --model "$MODEL_NAME" \
  "$@"
