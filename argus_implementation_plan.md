# Argus Implementation Plan

## 1. Objective and Scope
Implement Argus as a reproducible, model-agnostic scenario evaluation system that executes standardized scenarios, captures behavior artifacts, scores outcome + process, and reports behavioral deltas across models and versions.

In scope:
- Scenario schema, validation, and versioning
- Harness core (adapters, orchestrator, mock environment, logger)
- Deterministic and judge-based evaluators
- Scenario starter library (including the representative cross-pillar set)
- Reporting and regression workflows
- CI checks for schema validity and replay consistency

Out of scope for v1:
- Real side-effecting tools
- Large-scale distributed execution
- Multi-agent execution runtime
- Full GUI simulator (stub interfaces only)

## 2. Assumptions and Constraints
- Primary artifact format: YAML scenario specs validated by JSON Schema.
- All dangerous actions are mocked and deterministic.
- No real credentials or external secrets; canary-based leakage testing only.
- Reproducibility is required across repeated runs.
- Target interfaces for v1: `chat`, `tools`, optional `code` sandbox path.

## 3. Deliverables
1. `schemas/scenario.schema.json`
2. `scenarios/atlas.yaml` with canonical target IDs
3. `scenarios/cases/*.yaml` (starter set + variants)
4. `harness/` runtime modules:
   - `adapters/`
   - `env/`
   - `orchestrator/`
   - `logging/`
5. `evaluators/` modules:
   - deterministic checks
   - judge prompts and calibration set
6. `reports/` generation pipeline:
   - run-level scorecards
   - behavior/failure aggregates
   - regression deltas
7. CI pipeline for validation + smoke replay
8. Documentation for authoring, running, and extending Argus

## 4. Workstreams

### 4.1 Schema and Scenario Authoring System
Goals:
- Lock scenario structure and taxonomy with strict validation.
- Prevent drift in target IDs and scoring field names.

Tasks:
1. Define JSON Schema for required and recommended fields.
2. Encode canonical enums:
   - interfaces
   - stakes
   - pressure knob values
   - target IDs from spec section 3.9
3. Add schema rules for:
   - `targets` length (1-3)
   - presence of `success_criteria` and `failure_modes`
   - required `safety` and `logging`
4. Add validation CLI:
   - validate one file
   - validate full directory
5. Create scenario template generator script.
6. Add authoring guide with common mistakes and examples.

Acceptance criteria:
- Invalid targets or missing required fields fail validation with actionable errors.
- Example scenarios from the spec validate cleanly.

### 4.2 Harness Core Runtime
Goals:
- Execute a scenario deterministically against one or more model adapters.
- Enforce action gates, budgets, and timeouts.

Tasks:
1. Build orchestrator state machine:
   - initialize run context
   - execute prompt turns
   - mediate tool calls
   - enforce budget and timeout constraints
2. Build adapter interface contract:
   - normalized request/response shape
   - optional tool schema mapping
   - system/developer/user message handling
3. Build environment simulator:
   - mock tools (`read_doc`, `search_contacts`, `draft_email`, etc.)
   - deterministic fixtures keyed by scenario and seed
   - canary secrets for leakage tests
4. Implement permission gate layer:
   - allow-list/deny-list enforcement
   - blocked-action event logging
5. Add run configuration freeze:
   - model identifier
   - temperature/max tokens
   - adapter/runtime version

Acceptance criteria:
- Same scenario + seed reproduces the same tool outputs and gate decisions.
- Forbidden actions are blocked and recorded consistently.

### 4.3 Logging and Replay
Goals:
- Preserve complete run artifacts for audit and debugging.
- Enable deterministic replay from logs.

Tasks:
1. Define run artifact spec (`run.json` + transcript + tool trace).
2. Capture:
   - scenario metadata and hash
   - model settings
   - full prompt/response sequence
   - tool calls + outputs
   - evaluator outputs
3. Implement replay mode:
   - reconstruct run from artifacts
   - verify deterministic sections (tools, checks)
4. Add redaction policy for sensitive text markers.

Acceptance criteria:
- Replay can reconstruct at least 95% of run steps exactly for deterministic parts.
- Run artifacts are enough to debug failures without live rerun.

### 4.4 Evaluation Pipeline
Goals:
- Produce reliable outcome/process scores and weighted failures.

Tasks:
1. Implement deterministic checks:
   - forbidden action attempted
   - required confirmation missing
   - format violations
   - canary leak detection
2. Implement scoring engine:
   - per-trial score object
   - severity-weighted failure aggregation
   - behavior-pillar rollups
3. Implement judge integration:
   - stable prompts
   - per-dimension rubric templates
   - vote aggregation (single/multi-judge modes)
4. Build calibration harness:
   - gold set with labeled examples
   - judge agreement metrics

Acceptance criteria:
- Deterministic checks are reproducible.
- Judge pipeline reports calibration metrics and confidence metadata.

### 4.5 Reporting and Regression
Goals:
- Make behavior differences and drift easy to inspect.

Tasks:
1. Build report generator for:
   - model scorecards
   - top failure modes
   - representative transcripts
2. Add regression comparison tool:
   - baseline vs candidate model
   - statistically meaningful delta flags
3. Add coverage reporting by:
   - behavior pillar
   - interface
   - stakes
   - adversarial pressure

Acceptance criteria:
- One command generates a run report and a regression diff report.
- Reports surface failures by severity and frequency.

### 4.6 Scenario Library Buildout
Goals:
- Populate a robust starter set mapped to canonical taxonomy.

Tasks:
1. Encode the 8 representative cross-pillar scenarios from the spec.
2. Add baseline families with at least:
   - 3 chat scenarios per behavior pillar (initial milestone may phase this)
   - 2 tools scenarios per pillar where applicable
3. Create knob variants (change one knob at a time) for causal comparisons.
4. Add deterministic fixtures for each scenario.

Acceptance criteria:
- All starter scenarios validate.
- Each scenario has at least one deterministic failure detector.

### 4.7 CI/CD and Quality Gates
Goals:
- Prevent schema drift and runtime regressions.

Tasks:
1. Add CI jobs:
   - schema lint + scenario validation
   - unit tests for orchestrator/checks
   - smoke run on sample scenarios
2. Add reproducibility test:
   - rerun same seed and compare deterministic artifacts
3. Add minimum quality gates:
   - no critical failures in smoke suite
   - report generation success

Acceptance criteria:
- PR fails if schema or validation breaks.
- PR fails if smoke scenarios regress deterministically.

## 5. Phased Execution Plan

### Phase 0: Foundation (Week 1)
- Create repo structure (`schemas`, `scenarios`, `harness`, `evaluators`, `reports`, `scripts`).
- Implement scenario schema and validator CLI.
- Add `atlas.yaml` canonical targets.

Exit criteria:
- Scenario author can define and validate a scenario locally.

### Phase 1: Minimal End-to-End Loop (Weeks 2-3)
- Build one adapter, orchestrator MVP, mock env, logger.
- Run one scenario end-to-end with deterministic checks only.

Exit criteria:
- End-to-end run produces score + logs + basic report.

### Phase 2: Starter Scenario Library (Weeks 3-5)
- Implement 8 representative scenarios from spec.
- Add fixtures and check rules for each.

Exit criteria:
- All 8 scenarios pass validation and execute under harness.

### Phase 3: Multi-Model and Regression (Weeks 5-6)
- Add at least 3 model adapters.
- Implement cross-model run matrix + regression diffing.

Exit criteria:
- Same scenario runs comparably across 3+ models with unified report.

### Phase 4: Judge Layer and Calibration (Weeks 6-8)
- Add judge-based dimensions and calibration set.
- Track inter-judge agreement and confidence.

Exit criteria:
- Judge-assisted scores are stable and calibration metrics are visible.

### Phase 5: Hardening and CI Gates (Weeks 8-9)
- Add replay checks, deterministic reproducibility tests, and CI enforcement.
- Improve error taxonomy and operator docs.

Exit criteria:
- CI protects schema, runner, and smoke suite stability.

### Phase 6: v1 Release Readiness (Weeks 9-10)
- Validate against framework acceptance criteria.
- Publish v1 docs and runbook.

Exit criteria:
- All Section 14 acceptance criteria satisfied with evidence links.

## 6. Detailed Task Breakdown (Engineering Backlog)

### Epic A: Spec-to-Schema
- A1: Translate required/recommended scenario fields to JSON Schema.
- A2: Add enum constraints and custom validators.
- A3: Add schema versioning strategy.
- A4: Add migration helper for future schema changes.

### Epic B: Runner Core
- B1: Run context and deterministic seed handling.
- B2: Prompt sequence executor.
- B3: Tool invocation broker.
- B4: Timeout/budget enforcement.
- B5: Error taxonomy and retry behavior.

### Epic C: Mock Environment
- C1: Tool simulator plugin API.
- C2: Core mock tools and fixtures.
- C3: Injection payload corpus.
- C4: Canary generation + leak detection hooks.

### Epic D: Evaluators
- D1: Deterministic check framework.
- D2: Scoring aggregation engine.
- D3: Judge adapter and prompt versioning.
- D4: Calibration dataset tooling.

### Epic E: Reporting
- E1: Scorecard JSON output contract.
- E2: Markdown/HTML report generation.
- E3: Regression diff output.
- E4: Coverage matrix report.

### Epic F: Quality and Ops
- F1: Unit/integration test suite.
- F2: Replay + determinism tests.
- F3: CI pipeline and artifact publishing.
- F4: Runbook and troubleshooting docs.

## 7. Data Contracts
Define these contracts early and treat them as versioned APIs:
1. Scenario spec contract (`scenario.schema.json`)
2. Adapter IO contract (`model_request`, `model_response`)
3. Tool event contract (`tool_call`, `tool_result`, `gate_decision`)
4. Run artifact contract (`run_manifest`, `trial_result`)
5. Report contract (`scorecard`, `failure_catalog`, `delta_report`)

## 8. Scoring and Aggregation Plan
1. Per-trial scoring:
   - Outcome + process dimensions
   - failure severity weights applied to violations
2. Per-scenario aggregation:
   - mean and variance over N trials
3. Per-family aggregation:
   - weighted mean across scenarios
4. Per-pillar aggregation:
   - family rollup by target mapping
5. Overall profile:
   - trait projections (assertiveness, cautiousness, etc.)

Required outputs:
- point estimates
- uncertainty (variance/confidence intervals)
- top weighted failure contributors

## 9. Testing Strategy

Unit tests:
- schema validation edge cases
- gate enforcement logic
- deterministic checks

Integration tests:
- full scenario execution with mock tools
- run artifact completeness
- replay consistency

Regression tests:
- known baseline outputs for selected scenarios
- drift detection thresholds

Chaos/stability tests:
- tool timeout/error bursts
- malformed tool outputs
- adversarial prompt payloads

## 10. Risks and Mitigations
1. Risk: Taxonomy drift between scenarios and evaluators.
   - Mitigation: enum locking + CI validation.
2. Risk: Non-determinism reduces comparability.
   - Mitigation: seeded fixtures + frozen settings + replay tests.
3. Risk: Judge inconsistency.
   - Mitigation: gold calibration set + multi-judge vote path.
4. Risk: Overfitting to public scenarios.
   - Mitigation: maintain hidden holdout suite.
5. Risk: Report complexity hides root causes.
   - Mitigation: failure-first views with transcript links.

## 11. Operating Model
Recommended minimum roles:
- 1 platform engineer (harness/runtime)
- 1 eval engineer (checks/scoring/judges)
- 1 scenario author (library and fixtures)
- 1 QA/reliability owner (CI, replay, quality gates)

Cadence:
- Weekly milestone review with acceptance evidence.
- Biweekly scenario coverage review against matrix.

## 12. v1 Exit Checklist
- Schema validated and versioned.
- 8 representative scenarios implemented and passing.
- Deterministic checks active for all v1 scenarios.
- 3+ models runnable through adapters.
- Logs replayable and sufficient for debugging.
- Scorecards and regression reports generated automatically.
- CI gates enforce validation and smoke regression.
- Section 14 framework acceptance criteria satisfied.

## 13. Immediate Next Steps (Execution Order)
1. Implement `scenario.schema.json` + `validate_scenarios` CLI.
2. Create `scenarios/atlas.yaml` from canonical target IDs.
3. Author and validate YAML for the 8 representative scenarios.
4. Build orchestrator MVP with one model adapter and mock tools.
5. Add deterministic checks and run-level scorecard output.
6. Expand to multi-model adapters and regression reporting.

