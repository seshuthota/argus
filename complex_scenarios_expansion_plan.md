# Argus Complex Scenario Expansion Plan

Last updated: 2026-02-12
Owner: Argus core pipeline
Status: IMPLEMENTED_IN_CODE

## 1) Goal
Extend Argus beyond static single-script scenarios into a robust evaluation system for:
1. Multi-turn behavioral reliability across long conversations.
2. Dynamic scenario injection that changes flow based on model behavior.
3. Strong model-vs-model benchmark comparison with paired analysis.
4. Visualization outputs for pass/fail trends and failure mode distributions.

## 2) Baseline and Gaps
Current baseline:
- Scenario schema + validator (`schemas/scenario.schema.json`, `argus/schema_validator.py`).
- Deterministic scenario execution (`argus/orchestrator/runner.py`) with tool gates.
- Suite benchmarking and reporting (`argus/reporting/suite.py`, `argus/reporting/comparison.py`, `argus/reporting/trends.py`).
- CLI entry points (`argus/cli.py`) for validate/run/run-suite/gate/benchmark/trend-report.

Main gaps:
- Scenario flow is mostly static (`prompt_sequence` only), not stateful dialogue.
- No trigger-action runtime for response-driven injections mid-test.
- Benchmark comparison is mostly descriptive deltas, not paired/statistical.
- Visualization is markdown-first; no chart assets or dashboard-style outputs.

## 3) Scope
In scope:
- Schema extensions for dialogue flow and dynamic triggers.
- Runner state machine upgrades for turn orchestration and event handling.
- New reporting modules for paired comparisons and visual assets.
- New CLI commands for matrix benchmarks and chart generation.
- Tests for schema, runner behavior, and reporting correctness.

Out of scope (this phase):
- Real external side-effecting tools.
- Full web app with persistent backend.
- Human-in-the-loop adjudication UI.

## 4) Workstreams

### WS1: Multi-Turn Scenarios
Objective: support realistic conversations where earlier turns alter later execution.

Design:
- Add scenario fields:
  - `conversation`: max turns, stop conditions, assistant/user turn policy.
  - `simulated_user`: deterministic responder profile and templates.
  - `turn_assertions`: required/forbidden patterns by turn window.
- Keep backward compatibility: if `conversation` missing, use existing `prompt_sequence` path.

Implementation tasks:
1. Extend schema with optional `conversation`, `simulated_user`, `turn_assertions`.
2. Add loader normalization so old scenarios remain valid.
3. Implement `SimulatedUserEngine` in `argus/env/` for deterministic follow-ups.
4. Refactor `ScenarioRunner.run()` to a turn-by-turn state machine:
   - assistant reply -> optional tool calls -> tool results -> simulated user next turn.
5. Add turn-indexed transcript metadata to run artifacts.
6. Add deterministic checks for state-tracking regressions:
   - contradiction with earlier constraints,
   - dropped requirement detection.

Acceptance criteria:
- At least 3 new multi-turn scenarios run end-to-end without manual prompts.
- Runner handles >= 8 turns deterministically with fixed seed.
- Reports include turn-level evidence for success/failure checks.

### WS2: Dynamic Scenario Injection
Objective: modify scenario conditions at runtime based on model outputs/actions.

Design:
- Add `dynamic_events` to scenario:
  - trigger expression (DSL over responses/tool calls/gates),
  - action (`inject_message`, `update_knob`, `restrict_tools`, `terminate_run`, `set_flag`),
  - one-shot or repeat mode.
- Event execution is deterministic and logged as first-class run events.

Implementation tasks:
1. Extend schema for `dynamic_events` with strict action enum and payload validation.
2. Build event evaluator reusing detection DSL parser from checks layer.
3. Add event executor in runner:
   - evaluate triggers after each assistant/tool cycle,
   - mutate runtime state safely.
4. Persist event activation records in artifact (`events` + summary counters).
5. Add evaluator checks for expected event outcomes.
6. Add scenarios where model behavior deliberately triggers injections.

Acceptance criteria:
- Triggered events fire exactly once when configured `mode=once`.
- Runtime state changes (tool restrictions, injected prompt) are observable in logs.
- False trigger rate is zero on control scenarios.

### WS3: Benchmark Comparison Engine
Objective: produce rigorous cross-model comparison beyond raw pass-rate deltas.

Design:
- Introduce paired benchmark execution: same scenario IDs, same seeds, same trial counts.
- Add per-scenario paired outcome table and significance helpers.
- Add comparative risk posture summary (severity, high-risk failure prevalence).

Implementation tasks:
1. Add `benchmark-matrix` CLI command:
   - input: scenario manifest, model list, trials, seed schedule,
   - output: suite IDs + unified comparison artifact.
2. Implement paired analysis module (`argus/reporting/paired.py`):
   - pass-rate delta with confidence intervals (bootstrap),
   - severity delta and top regression scenarios,
   - optional McNemar test for binary pass/fail.
3. Extend comparison markdown to include:
   - statistically notable differences,
   - per-pathway winner/loser table,
   - failure mode distribution deltas.
4. Emit machine-readable comparison JSON for downstream automation.

Acceptance criteria:
- One command compares >= 2 models on the same run matrix.
- Comparison output highlights statistically significant regressions.
- Pipeline remains reproducible with fixed seeds.

### WS4: Visualization Layer
Objective: add inspectable chart outputs for stakeholders and review loops.

Design:
- Static chart generation first (PNG/SVG + markdown embedding).
- Optional HTML summary page built from generated assets.

Implementation tasks:
1. Add plotting dependency (`matplotlib` + `seaborn`).
2. Implement `argus/reporting/visualize.py`:
   - pass-rate by model (bar),
   - pathway pass-rate heatmap,
   - failure mode severity histogram,
   - trend line from JSONL histories.
3. Add CLI command:
   - `visualize-suite` for one suite,
   - `visualize-comparison` for paired reports.
4. Save outputs under `reports/visuals/<timestamp>/`.
5. Add README usage and artifact examples.

Acceptance criteria:
- Chart generation works headless in CI.
- At least 4 chart types generated from real suite reports.
- Visual outputs linkable from comparison markdown.

## 5) Execution Plan (Phased)

### Phase A: Foundations (WS1 schema + runner prep, WS2 schema)
Duration: 2-3 working sessions
Tasks:
1. Schema updates for conversation + dynamic events.
2. Backward compatibility guards in loader/runner.
3. Minimal runner refactor to explicit turn loop and runtime state object.
Exit criteria:
- Existing scenarios still pass validation and execute unchanged.
- New schema fields parse and appear in normalized runtime config.

### Phase B: Multi-Turn + Dynamic Runtime (WS1 + WS2 core)
Duration: 3-4 working sessions
Tasks:
1. Simulated user engine.
2. Dynamic event trigger evaluator + executor.
3. New scenarios and deterministic checks.
Exit criteria:
- New multi-turn + injection scenarios run deterministically.
- Reports capture event activations and turn-level assertions.

### Phase C: Benchmark Matrix + Paired Analysis (WS3)
Duration: 2-3 working sessions
Tasks:
1. `benchmark-matrix` CLI.
2. Paired analysis JSON + markdown.
3. Gate integration for comparative thresholds (e.g., max regression count).
Exit criteria:
- Single command produces suite artifacts + paired comparison report.
- Regressions are ranked and machine-readable.

### Phase D: Visualization + CI Integration (WS4)
Duration: 2 working sessions
Tasks:
1. Chart module and CLI.
2. Weekly workflow updates to publish charts as artifacts.
3. README and tracker updates.
Exit criteria:
- CI job generates visuals for latest weekly benchmark.
- Trend + comparison + visuals are available in one artifact bundle.

## 6) File-Level Change Plan

Schema and validation:
- `schemas/scenario.schema.json`
- `argus/schema_validator.py` (if normalization hooks are needed)

Runtime:
- `argus/orchestrator/runner.py`
- `argus/env/mock_tools.py` (if dynamic tool behavior needed)
- `argus/env/simulated_user.py` (new)

Evaluation:
- `argus/evaluators/checks.py`
- `tests/test_scenario_driven_evaluator.py`
- `tests/test_runner.py`

Reporting and CLI:
- `argus/reporting/comparison.py`
- `argus/reporting/paired.py` (new)
- `argus/reporting/visualize.py` (new)
- `argus/cli.py`
- `README.md`

Scenario assets:
- `scenarios/cases/*_multi_turn_*.yaml` (new)
- `scenarios/cases/*_dynamic_injection_*.yaml` (new)
- `scenarios/suites/complex_behavior_v1.txt` (new)

Automation:
- `.github/workflows/weekly-benchmark.yml` (extend)

## 7) Test Strategy
Unit tests:
1. Schema accepts valid new fields and rejects malformed dynamic events.
2. Runner executes deterministic multi-turn conversations.
3. Dynamic trigger engine fires/does not fire under expected conditions.
4. Paired comparison math is stable for fixed fixtures.
5. Visualization functions generate files with non-zero size.

Integration tests:
1. Run `benchmark-matrix` on a small suite with MiniMax + StepFun.
2. Validate comparison JSON/markdown structure.
3. Generate visuals from produced suite/comparison reports.

Regression tests:
1. Existing scenario corpus remains valid.
2. Existing commands (`run-suite`, `benchmark-pipeline`, `gate`, `trend-report`) remain functional.

## 8) Risks and Mitigations
Risk: schema complexity causes authoring friction.
Mitigation: add concise examples/templates and keep new fields optional.

Risk: dynamic triggers become brittle.
Mitigation: reuse deterministic DSL + strict unit coverage for trigger clauses.

Risk: statistical outputs are misread.
Mitigation: include clear caveats and minimum sample-size warnings in report text.

Risk: chart dependencies break CI.
Mitigation: use headless backend and pin plotting versions.

## 9) Deliverables Checklist
- [x] Schema extension merged with backward compatibility.
- [x] Multi-turn runtime path merged and tested.
- [x] Dynamic event engine merged and tested.
- [x] New scenario suite for complex behaviors added.
- [x] Benchmark matrix + paired comparison outputs.
- [x] Visualization command and generated artifacts.
- [x] Weekly automation updated to include comparison + visuals.
- [x] Documentation updated with end-to-end usage.

## 10) Progress Tracker
Use this table as execution tracker for implementation sessions.

| ID | Work Item | Status | Notes |
|---|---|---|---|
| P1 | Schema extension for multi-turn + dynamic events | DONE | Added `conversation`, `simulated_user`, `turn_assertions`, `dynamic_events` in schema with strict enums and payload validation. |
| P2 | Runner state machine refactor | DONE | Added runtime-state loop with simulated-user turns, dynamic-event evaluation, runtime summaries, stop-condition enforcement, and compatible role normalization. |
| P3 | Simulated user engine | DONE | Added deterministic rule-based simulator (`argus/env/simulated_user.py`) with max-turn and one-shot rule handling. |
| P4 | Dynamic trigger/action executor | DONE | Added trigger evaluation + actions (`inject_message`, `restrict_tools`, `update_knob`, `set_flag`, `terminate_run`). |
| P5 | Multi-turn scenarios (>=3) | DONE | Added: `PLANNING_MULTI_TURN_CONSTRAINT_TRACKING_001`, `SAFETY_MULTI_TURN_PRESSURE_ESCALATION_001`, `STATE_MULTI_TURN_REQUIREMENT_MEMORY_001`. |
| P6 | Dynamic injection scenarios (>=3) | DONE | Added: `ROBUSTNESS_DYNAMIC_INJECTION_DOCUMENT_SUMMARY_002`, `TOOL_DYNAMIC_RESTRICTION_AFTER_DRAFT_001`, `SAFETY_DYNAMIC_TERMINATION_SELF_PRESERVATION_001`. |
| P7 | `benchmark-matrix` CLI | DONE | Added `argus.cli benchmark-matrix` for multi-model, seed-aligned suite execution with pairwise artifact output. |
| P8 | Paired statistical comparison module | DONE | Added `argus/reporting/paired.py` (paired deltas, bootstrap CI, McNemar statistic) and pairwise markdown/JSON outputs. |
| P9 | Visualization module + CLI | DONE | Added `argus/reporting/visualize.py` and CLI commands `visualize-suite`, `visualize-matrix`, `visualize-comparison` (suite, matrix, pairwise, and trend SVG outputs). |
| P10 | Weekly workflow + docs updates | DONE | Updated weekly workflow to run matrix + visual generation and upload artifacts; README updated with usage examples. |
| P11 | Turn assertion evaluation path | DONE | Added `turn_assertions` evaluation as weighted success checks with role/turn-window filtering in `argus/evaluators/checks.py`. |
