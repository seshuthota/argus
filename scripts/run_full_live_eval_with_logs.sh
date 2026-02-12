#!/usr/bin/env bash
set -u

# Full Argus live execution runner with timestamped logs.
# Intended for environments with working network/provider access.
#
# Usage:
#   scripts/run_full_live_eval_with_logs.sh
#
# Optional overrides via env vars:
#   ARGUS_TRIALS=3
#   ARGUS_MAX_TURNS=6
#   ARGUS_SEED=42
#   ARGUS_PROFILE=candidate
#   ARGUS_MODEL_A=MiniMax-M2.1
#   ARGUS_MODEL_B=stepfun/step-3.5-flash:free
#   ARGUS_MATRIX_MODELS="MiniMax-M2.1,stepfun/step-3.5-flash:free,sourceful/riverflow-v2-pro"
#   ARGUS_PIPELINE_SCENARIO_LIST=scenarios/suites/sabotage_extended_v1.txt
#   ARGUS_MATRIX_SCENARIO_LIST=scenarios/suites/complex_behavior_v1.txt
#   ARGUS_TREND_WINDOW=12
#   ARGUS_PREFLIGHT_TIMEOUT=8

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="./.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

TRIALS="${ARGUS_TRIALS:-1}"
MAX_TURNS="${ARGUS_MAX_TURNS:-6}"
SEED="${ARGUS_SEED:-42}"
PROFILE="${ARGUS_PROFILE:-candidate}"
MODEL_A="${ARGUS_MODEL_A:-MiniMax-M2.1}"
MODEL_B="${ARGUS_MODEL_B:-stepfun/step-3.5-flash:free}"
MODEL_C="${ARGUS_MODEL_C:-sourceful/riverflow-v2-pro}"
MATRIX_MODELS="${ARGUS_MATRIX_MODELS:-$MODEL_A,$MODEL_B,$MODEL_C}"
PIPELINE_SCENARIO_LIST="${ARGUS_PIPELINE_SCENARIO_LIST:-scenarios/suites/sabotage_extended_v1.txt}"
MATRIX_SCENARIO_LIST="${ARGUS_MATRIX_SCENARIO_LIST:-scenarios/suites/complex_behavior_v1.txt}"
TREND_WINDOW="${ARGUS_TREND_WINDOW:-12}"
PREFLIGHT_TIMEOUT="${ARGUS_PREFLIGHT_TIMEOUT:-8}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="reports/execution_logs/$STAMP"
mkdir -p "$RUN_DIR"
START_MARKER="$RUN_DIR/.start_marker"
touch "$START_MARKER"

SUMMARY="$RUN_DIR/summary.md"
STATUS_TSV="$RUN_DIR/step_status.tsv"
: >"$STATUS_TSV"

echo "# Argus Live Execution Summary ($STAMP)" >"$SUMMARY"
echo "" >>"$SUMMARY"
echo "- Root: \`$ROOT_DIR\`" >>"$SUMMARY"
echo "- Python: \`$PY\`" >>"$SUMMARY"
echo "- Trials: \`$TRIALS\`" >>"$SUMMARY"
echo "- Max turns: \`$MAX_TURNS\`" >>"$SUMMARY"
echo "- Seed: \`$SEED\`" >>"$SUMMARY"
echo "- Profile: \`$PROFILE\`" >>"$SUMMARY"
echo "- Model A: \`$MODEL_A\`" >>"$SUMMARY"
echo "- Model B: \`$MODEL_B\`" >>"$SUMMARY"
echo "- Model C (matrix default): \`$MODEL_C\`" >>"$SUMMARY"
echo "- Matrix models: \`$MATRIX_MODELS\`" >>"$SUMMARY"
echo "- Pipeline scenarios: \`$PIPELINE_SCENARIO_LIST\`" >>"$SUMMARY"
echo "- Matrix scenarios: \`$MATRIX_SCENARIO_LIST\`" >>"$SUMMARY"
echo "- Preflight timeout: \`$PREFLIGHT_TIMEOUT\`s" >>"$SUMMARY"
echo "" >>"$SUMMARY"

run_step() {
  local step_name="$1"
  shift
  local logfile="$RUN_DIR/${step_name}.log"
  echo "==> [$step_name] $*" | tee -a "$logfile"
  "$@" >>"$logfile" 2>&1
  local code=$?
  echo -e "${step_name}\t${code}\t${logfile}" >>"$STATUS_TSV"
  if [[ $code -eq 0 ]]; then
    echo "[PASS] $step_name" | tee -a "$logfile"
  else
    echo "[FAIL:$code] $step_name" | tee -a "$logfile"
  fi
  return 0
}

matrix_args=()
preflight_args=()
IFS=',' read -r -a matrix_models_arr <<<"$MATRIX_MODELS"
declare -A seen_models=()
for m in "${matrix_models_arr[@]}"; do
  trimmed="$(echo "$m" | xargs)"
  if [[ -n "$trimmed" ]]; then
    matrix_args+=(--models "$trimmed")
    if [[ -z "${seen_models[$trimmed]:-}" ]]; then
      preflight_args+=(--models "$trimmed")
      seen_models["$trimmed"]=1
    fi
  fi
done
if [[ ${#matrix_args[@]} -lt 4 ]]; then
  # two models => 4 args: --models x --models y
  matrix_args=(--models "$MODEL_A" --models "$MODEL_B")
fi
if [[ ${#preflight_args[@]} -eq 0 ]]; then
  preflight_args=(--models "$MODEL_A" --models "$MODEL_B")
fi

# 1) Environment snapshot (non-secret)
run_step "00_env_snapshot" bash -lc "
  set -e
  echo \"timestamp=$STAMP\"
  echo \"pwd=\$(pwd)\"
  echo \"python_path=$PY\"
  echo \"python_version=\$($PY --version 2>&1 || true)\"
  echo \"git_head=\$(git rev-parse --short HEAD 2>/dev/null || echo n/a)\"
  echo \"git_branch=\$(git branch --show-current 2>/dev/null || echo n/a)\"
  echo \"has_minimax_key=\$([ -n \"\${MINIMAX_API_KEY:-}\" ] && echo yes || echo no)\"
  echo \"has_openrouter_key=\$([ -n \"\${OPENROUTER_API_KEY:-}\" ] && echo yes || echo no)\"
"

# 2) Unit tests
run_step "10_unittest" "$PY" -m unittest discover -s tests -p "test_*.py"

# 2.5) Provider/model preflight checks
run_step "15_preflight" \
  "$PY" -m argus.cli preflight \
    "${preflight_args[@]}" \
    --timeout "$PREFLIGHT_TIMEOUT"

# 3) Validate all scenario YAMLs
run_step "20_validate_all" bash -lc "
  set -e
  count=0
  for f in scenarios/cases/*.yaml; do
    $PY -m argus.cli validate \"\$f\" >/dev/null
    count=\$((count+1))
  done
  echo \"validated_scenarios=\$count\"
"

# 4) Benchmark pipeline
run_step "30_benchmark_pipeline" \
  "$PY" -m argus.cli benchmark-pipeline \
    --scenario-list "$PIPELINE_SCENARIO_LIST" \
    --model-a "$MODEL_A" \
    --model-b "$MODEL_B" \
    --trials "$TRIALS" \
    --seed "$SEED" \
    --max-turns "$MAX_TURNS" \
    --profile "$PROFILE" \
    --output-dir reports/suites \
    --trends-dir reports/suites/trends

# 5) Benchmark matrix
run_step "40_benchmark_matrix" \
  "$PY" -m argus.cli benchmark-matrix \
    --scenario-list "$MATRIX_SCENARIO_LIST" \
    "${matrix_args[@]}" \
    --trials "$TRIALS" \
    --seed "$SEED" \
    --max-turns "$MAX_TURNS" \
    --profile "$PROFILE" \
    --output-dir reports/suites \
    --trends-dir reports/suites/trends

# 5.5) Narrative behavior report from latest matrix
run_step "45_behavior_report" bash -lc "
  set -e
  latest_matrix=\$(ls -1t reports/suites/matrix/*_matrix.json 2>/dev/null | head -n1 || true)
  if [[ -z \"\$latest_matrix\" ]]; then
    echo 'no_matrix_json_found'
    exit 0
  fi
  echo \"latest_matrix=\$latest_matrix\"
  $PY -m argus.cli behavior-report \
    --matrix-json \"\$latest_matrix\" \
    --top-scenarios 6 \
    --excerpt-chars 240 \
    --output \"reports/suites/behavior/behavior_report_$STAMP.md\"
"

# 6) Trend markdown
run_step "50_trend_report" \
  "$PY" -m argus.cli trend-report \
    --trend-dir reports/suites/trends \
    --window "$TREND_WINDOW" \
    --output "reports/suites/trends/weekly_trend_report_$STAMP.md"

# 7) Visualize newly created suite reports
run_step "60_visualize_new_suites" bash -lc "
  set -e
  mapfile -t suites < <(find reports/suites -maxdepth 1 -type f -name '*.json' -newer '$START_MARKER' | sort)
  echo \"new_suite_count=\${#suites[@]}\"
  for s in \"\${suites[@]}\"; do
    echo \"visualizing_suite=\$s\"
    $PY -m argus.cli visualize-suite --suite-report \"\$s\" --output-dir reports/visuals
  done
"

# 8) Visualize latest matrix report
run_step "70_visualize_latest_matrix" bash -lc "
  set -e
  latest_matrix=\$(ls -1t reports/suites/matrix/*_matrix.json 2>/dev/null | head -n1 || true)
  if [[ -z \"\$latest_matrix\" ]]; then
    echo 'no_matrix_json_found'
    exit 0
  fi
  echo \"latest_matrix=\$latest_matrix\"
  $PY -m argus.cli visualize-matrix \
    --matrix-json \"\$latest_matrix\" \
    --trend-dir reports/suites/trends \
    --window \"$TREND_WINDOW\" \
    --output-dir reports/visuals
"

# Build summary
echo "## Step Status" >>"$SUMMARY"
echo "" >>"$SUMMARY"
echo "| Step | Exit Code | Log |" >>"$SUMMARY"
echo "|---|---:|---|" >>"$SUMMARY"
overall_fail=0
while IFS=$'\t' read -r step code log; do
  [[ -z "$step" ]] && continue
  if [[ "$code" != "0" ]]; then
    overall_fail=1
  fi
  echo "| \`$step\` | $code | \`$log\` |" >>"$SUMMARY"
done <"$STATUS_TSV"

echo "" >>"$SUMMARY"
echo "## New Artifacts" >>"$SUMMARY"
echo "" >>"$SUMMARY"
{
  echo "- New suite reports:"
  find reports/suites -maxdepth 1 -type f -name '*.json' -newer "$START_MARKER" | sort | sed 's/^/  - /'
  echo "- New matrix artifacts:"
  find reports/suites/matrix -type f -newer "$START_MARKER" 2>/dev/null | sort | sed 's/^/  - /'
  echo "- New trend artifacts:"
  find reports/suites/trends -maxdepth 1 -type f -newer "$START_MARKER" 2>/dev/null | sort | sed 's/^/  - /'
  echo "- New behavior reports:"
  find reports/suites/behavior -maxdepth 1 -type f -newer "$START_MARKER" 2>/dev/null | sort | sed 's/^/  - /'
  echo "- New visual artifacts:"
  find reports/visuals -type f -newer "$START_MARKER" 2>/dev/null | sort | sed 's/^/  - /'
} >>"$SUMMARY"

echo ""
echo "Execution complete. Summary: $SUMMARY"
echo "Detailed logs directory: $RUN_DIR"

if [[ $overall_fail -ne 0 ]]; then
  echo "One or more steps failed. Check $SUMMARY and per-step logs."
  exit 1
fi

exit 0
