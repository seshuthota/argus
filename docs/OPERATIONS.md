# Argus Operations Guide

This guide summarizes production-facing controls added in the current roadmap iterations.

## Benchmark Presets

Use `--suite-preset` in benchmark commands:

- `minimax_core_v1`
- `openrouter_extended_v1`
- `mixed_calibration_fast_v1`

Examples:

```bash
python -m argus.cli benchmark-pipeline --suite-preset minimax_core_v1 --trials 1
python -m argus.cli benchmark-matrix --suite-preset mixed_calibration_fast_v1 --trials 1
```

## Alert Webhooks

`benchmark-pipeline` and `benchmark-matrix` support webhook delivery:

- `--alert-webhook`
- `--alert-on` (`always`, `never`, `gate_failures`)
- `--alert-timeout-s`

Webhook payload includes:

- benchmark event name
- suite IDs
- pass/fail gate outcome
- comparison and gate artifact paths

## Drift Monitoring

`trend-drift-check` summarizes model drift and can fail CI.

```bash
python -m argus.cli trend-drift-check \
  --trend-dir reports/suites/trends \
  --window 12 \
  --max-pass-drop 0.08 \
  --max-severity-increase 0.75 \
  --max-anomaly-increase 3 \
  --strict
```

Outputs:

- markdown summary (`weekly_drift_report.md`)
- machine-readable JSON (`weekly_drift_report.json`)

`weekly-benchmark.yml` now supports configurable drift inputs and defaults to strict mode for scheduled runs.

## Tool Simulation Semantics

Mock tools are stateful and deterministic:

- draft/send lifecycle with deterministic IDs
- invoice access authorization logging
- admin query classification and destructive query blocking
- per-run session isolation via injected `_session_id`

Primary files:

- `argus/env/mock_tools.py`
- `argus/orchestrator/runner.py`

## Plugin Extension Points

### Model Resolver Plugin

Set `ARGUS_MODEL_RESOLVER_PLUGIN=module:function`.

Expected callable signature:

```python
def plugin(*, model: str, api_key: str | None = None, api_base: str | None = None):
    ...
```

Return either:

- `ResolveResult`, or
- `(resolved_model, adapter[, provider_note])`

### Evaluator Plugins

Set `ARGUS_EVALUATOR_PLUGINS` to comma-separated `module:function` specs.

Expected callable signature:

```python
def plugin(*, run_artifact, scenario, checks):
    ...
```

Return:

- `None`, or
- `list[CheckResult | dict]`

Plugin checks are appended to deterministic checks in `run_all_checks`.
