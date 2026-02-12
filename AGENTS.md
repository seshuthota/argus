# Repository Guidelines

## Project Structure & Module Organization
- `argus/`: core Python package.
  - `cli.py`: command entrypoints (`run`, `run-suite`, `benchmark-*`, `preflight`, visualization).
  - `orchestrator/`, `evaluators/`, `scoring/`, `reporting/`, `models/`, `env/`: runtime, checks, scoring, outputs, provider adapter, mock/simulated env.
- `scenarios/cases/`: individual scenario YAMLs (source of truth for behavior tests).
- `scenarios/suites/`: newline-delimited scenario manifests for suite runs.
- `schemas/scenario.schema.json`: schema for scenario validation.
- `tests/`: `unittest` suite for runner, evaluator DSL, reporting, CLI helpers.
- `scripts/`: reproducible shell wrappers for benchmark and full live evaluation.
- `reports/`: generated artifacts (treat as runtime output, not source).

## Build, Test, and Development Commands
- Setup:
  - `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Validate one scenario:
  - `python -m argus.cli validate scenarios/cases/<scenario>.yaml`
- Run unit tests:
  - `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- Run suites:
  - `python -m argus.cli run-suite --scenario-list scenarios/suites/sabotage_core_v1.txt --model MiniMax-M2.1 -n 1`
- Run model preflight checks:
  - `python -m argus.cli preflight --models MiniMax-M2.1 --models stepfun/step-3.5-flash:free`
- End-to-end logged run:
  - `scripts/run_full_live_eval_with_logs.sh`

## Coding Style & Naming Conventions
- Python style: 4-space indentation, type hints, small focused functions, `snake_case` for files/functions.
- Keep evaluator and runner logic deterministic; avoid hidden randomness.
- Scenario filenames use lowercase snake case with numeric suffix (example: `safety_*_001.yaml`).
- Scenario IDs remain stable and explicit (`PILLAR_TOPIC_001`).

## Testing Guidelines
- Framework: standard library `unittest`.
- Test files: `tests/test_<feature>.py`; test methods should describe behavior (example: `test_run_preflight_fails_on_dns_error`).
- For behavior changes, add both:
  - unit tests for new logic, and
  - at least one scenario-level validation/run command in your verification notes.

## Commit & Pull Request Guidelines
- Commit messages: imperative, concise, outcome-focused (example: `Add preflight checks and retry backoff`).
- Keep each commit scoped: code + tests + docs for one logical change.
- PRs should include:
  - summary of behavior changes,
  - commands run and results,
  - impacted files/modules,
  - any required env/config changes.

## Security & Configuration Tips
- Configure secrets in `.env` (`MINIMAX_API_KEY`, `OPENROUTER_API_KEY`); never commit secrets.
- Run `preflight` before long benchmark jobs.
- Avoid committing generated outputs under `reports/suites/`, `reports/visuals/`, and `reports/execution_logs/` unless explicitly needed for analysis.
