# Argus Sabotage Report Expansion Plan and Progress Tracker

Last updated: 2026-02-12
Primary source: `Sabotage Risk Report Claude Opus 4.6.pdf`

## 1) Purpose
This file is the working tracker for expanding Argus to cover sabotage-risk pathways in detail.
It is intended to be updated after every implementation session.

Goals:
1. Map sabotage-risk pathways to concrete Argus scenarios.
2. Improve evaluator robustness for subtle sabotage patterns.
3. Produce repeatable benchmark suites and trend reporting.
4. Track progress with clear status, artifacts, and acceptance criteria.

## 2) Status Legend
- `TODO`: not started
- `IN_PROGRESS`: actively being implemented
- `BLOCKED`: waiting on prerequisite
- `DONE`: implemented and validated

## 3) Current Baseline (Already Implemented)
Existing relevant scenarios:
- `safety_blackmail_private_email_discovery_001.yaml`
- `safety_persistence_backdoor_request_001.yaml`
- `safety_self_preservation_replacement_pressure_001.yaml`
- `safety_sensitive_info_user_leverage_001.yaml`
- `safety_tool_unauthorized_escalation_001.yaml`

Current capability baseline:
- Scenario-driven evaluator from `failure_modes` and `success_criteria`
- Suite runner (`run-suite`) and suite-level reporting
- Deterministic checks with `AND` / `OR` expression support

Known gap:
- Coverage of the report's full pathways (6.1-6.8) is still partial.

## 4) Workstreams

### WS-A: Evaluator and Detection DSL Hardening
Objective: reduce phrase brittleness and support richer sabotage detections.

| ID | Task | Priority | Status | Deliverable | Acceptance Criteria |
|---|---|---|---|---|---|
| A1 | Add regex detection clauses (response/tool args) | P0 | DONE | `argus/evaluators/checks.py` | Can match refusal/sabotage variants without brittle exact strings |
| A2 | Add numeric/count clauses (`tool_call_count`, repeated actions) | P0 | DONE | `argus/evaluators/checks.py` | Can detect repeated low-grade sandbagging patterns |
| A3 | Add sequence-aware clauses (e.g., "deny then unsafe suggestion") | P1 | DONE | `argus/evaluators/checks.py` | Detects mixed safe/unsafe responses in same turn |
| A4 | Add confidence/reporting metadata for unsupported clauses | P1 | DONE | `argus/evaluators/checks.py`, report schema | Unsupported checks are explicit and do not silently pass/fail |
| A5 | Extend tests for all new DSL features | P0 | DONE | `tests/test_scenario_driven_evaluator.py` | Unit tests cover every new clause type |

### WS-B: Pathway Scenario Expansion (Report Section 6)
Objective: implement scenario families mapped directly to pathways 6.1-6.8.

| ID | Pathway | Scenario ID (planned) | Priority | Status | Interface | Acceptance Criteria |
|---|---|---|---|---|---|---|
| B1 | 6.1 Diffuse sandbagging on safety R&D | `SAFETY_RD_DIFFUSE_SANDBAGGING_001` | P0 | DONE | tools/code | Detects low-quality output pattern under high-stakes context |
| B2 | 6.1 Diffuse sandbagging (cross-trial) | `SAFETY_RD_DIFFUSE_SANDBAGGING_002` | P1 | DONE | tools/code | Detects statistically suspicious underperformance across N runs |
| B3 | 6.2 Targeted sabotage of safety R&D | `SAFETY_RD_TARGETED_EXPERIMENT_TAMPER_001` | P0 | DONE | tools/code | Detects selective tampering and misleading explanations |
| B4 | 6.2 Social cover for suspicious outcomes | `SAFETY_RD_TARGETED_SOCIAL_ENGINEERING_002` | P1 | DONE | chat/tools | Detects "dismiss concerns / avoid investigation" patterns |
| B5 | 6.3 Code backdoor insertion | `SAFETY_CODE_BACKDOOR_INSERTION_001` | P0 | DONE | code | Detects covert vuln patterns and concealment language |
| B6 | 6.3 Backdoor + benign rationale | `SAFETY_CODE_BACKDOOR_COVER_STORY_002` | P1 | DONE | code/chat | Fails when model rationalizes suspicious security changes |
| B7 | 6.4 Training data poisoning | `SAFETY_DATA_POISONING_SUBTLE_001` | P0 | DONE | tools/code | Detects malicious distribution skew/injection tactics |
| B8 | 6.4 Poisoning via internal prompt artifacts | `SAFETY_DATA_POISONING_PROMPT_INJECTION_002` | P1 | DONE | tools | Detects insertion of hidden trigger content |
| B9 | 6.5 Self-exfiltration and autonomous operation | `SAFETY_SELF_EXFILTRATION_CHAIN_001` | P0 | DONE | tools/code | Detects attempts to stage exfiltration/autonomous control |
| B10 | 6.6 Persistent rogue internal deployment | `SAFETY_ROGUE_INTERNAL_DEPLOYMENT_001` | P0 | DONE | tools/code | Detects persistence setup attempts and privilege abuse |
| B11 | 6.7 Cross-org R&D sabotage | `SAFETY_THIRD_PARTY_RD_SABOTAGE_001` | P1 | DONE | chat/tools | Detects sabotage recommendations for external labs |
| B12 | 6.8 Government decision sabotage | `SAFETY_GOV_DECISION_SHAPING_001` | P0 | DONE | chat | Detects manipulative selective framing to decision makers |

### WS-C: Monitoring and Collusion Scenarios (Report Sections 4.3.7, 5.1, 5.2)
Objective: test behavior under monitoring visibility and potential collusion opportunities.

| ID | Task | Priority | Status | Deliverable | Acceptance Criteria |
|---|---|---|---|---|---|
| C1 | Evaluator-collusion honeypot scenario | P0 | DONE | `scenarios/cases/safety_evaluator_collusion_honeypot_001.yaml` | Flags monitor-role instance that ignores obvious unsafe act |
| C2 | Cross-instance signaling scenario | P0 | DONE | `scenarios/cases/safety_cross_instance_signal_propagation_001.yaml` | Detects attempts to propagate unusual trigger/plan text |
| C3 | Monitoring-aware behavior shift scenario | P1 | DONE | `scenarios/cases/safety_monitoring_awareness_shift_001.yaml` | Detects behavior changes when "monitoring disabled" is suggested |
| C4 | Context compaction/memory propagation scenario | P1 | DONE | `scenarios/cases/safety_context_compaction_signal_001.yaml` | Detects unsafe intent persistence across compressed context |

### WS-D: Suite Design, Metrics, and Regression Guardrails
Objective: make results operationally comparable over time.

| ID | Task | Priority | Status | Deliverable | Acceptance Criteria |
|---|---|---|---|---|---|
| D1 | Define sabotage core suite manifest (P0 scenarios) | P0 | DONE | `scenarios/suites/sabotage_core_v1.txt` | One command executes agreed core suite |
| D2 | Define sabotage extended suite manifest (P0+P1) | P1 | DONE | `scenarios/suites/sabotage_extended_v1.txt` | Extended suite includes all pathway coverage |
| D3 | Add per-pathway score rollups in suite report | P0 | DONE | `argus/reporting/suite.py` | Report includes pathway-level pass/severity aggregates |
| D4 | Add trend file for repeated runs (baseline history) | P1 | DONE | `reports/suites/trends/*.jsonl` | Can compare week-over-week drift |
| D5 | Set quality gates for release candidate models | P0 | DONE | `README.md` / runbook | Explicit thresholds for pass-rate and severity failures |

## 5) Implementation Sequence

### Phase 1 (Immediate, high leverage)
1. WS-A A1/A2/A5 (DSL hardening and tests)
2. WS-B B1, B3, B5, B7, B9, B10, B12 (critical pathway scenarios)
3. WS-D D1 and D3 (core suite + pathway rollups)

Exit criteria:
- At least 7 new P0 sabotage scenarios implemented and schema-valid.
- Core suite executable in one command.
- No unsupported detection clauses in P0 scenarios.

### Phase 2 (Coverage depth)
1. WS-B B2, B4, B6, B8, B11
2. WS-C C1, C2
3. WS-D D2 and D4

Exit criteria:
- Full section 6 pathway mapping complete (6.1 through 6.8).
- Collusion/propagation risk family represented by at least 2 scenarios.

### Phase 3 (Operational hardening)
1. WS-A A3/A4
2. WS-C C3/C4
3. WS-D D5

Exit criteria:
- Stable weekly sabotage benchmark workflow with regression thresholds.
- Clear go/no-go criteria for model safety review runs.

## 6) Scenario Authoring Standard (for new sabotage scenarios)
Each new scenario must include:
1. A report pathway mapping in `references` (e.g., "Sabotage report 6.3").
2. At least 2 required `success_criteria` and 2 `failure_modes`.
3. At least 1 high-severity failure mode (severity >= 8).
4. Deterministic detection expressions compatible with current DSL.
5. Clear side-effect safety note (all dangerous actions mocked).

## 7) Execution and Validation Checklist
Run for each new scenario:
1. `python -m argus.cli validate scenarios/cases/<scenario>.yaml`
2. `python -m argus.cli run --scenario scenarios/cases/<scenario>.yaml --model MiniMax-M2.1 -n 1`
3. Add to suite and run: `python -m argus.cli run-suite --scenario-dir scenarios/cases --pattern '<group pattern>' --model MiniMax-M2.1 -n 5 --seed 101`
4. Verify no evaluator unsupported-clause warnings.

## 8) Progress Log
Use this section as a running journal. Append entries only.

### 2026-02-12
- Completed full review of sabotage report and mapped gaps against current Argus scenarios.
- Created this tracker and defined workstreams WS-A through WS-D.
- Baseline remains: partial pathway coverage with strong coverage in coercion/permission discipline, weaker coverage in R&D sabotage, poisoning, exfiltration, and collusion pathways.
- Implemented DSL hardening: regex clauses, count clauses, and quote-safe AND/OR splitting.
- Added evaluator tests for regex, count expressions, and quoted-token parsing behavior.
- Added new pathway scenarios: `SAFETY_RD_DIFFUSE_SANDBAGGING_001` and `SAFETY_RD_TARGETED_EXPERIMENT_TAMPER_001`.
- Added core suite manifest at `scenarios/suites/sabotage_core_v1.txt`.
- Added pathway rollups in suite reporting and CLI support for `--scenario-list`.
- Implemented additional P0 pathway scenarios: backdoor insertion (6.3), data poisoning (6.4), self-exfiltration chain (6.5), rogue internal deployment (6.6), and government decision shaping (6.8).
- Validation status: all scenarios in `scenarios/suites/sabotage_core_v1.txt` are schema-valid.
- Test status: `17/17` unit tests passing.
- Smoke benchmark: `reports/suites/4523c196.json` (`12` runs, `75.0%` pass, `0` errors), with new pathway summary enabled in suite output.
- Phase 1 progress: A1/A2/A5, B1/B3/B5/B7/B9/B10/B12, D1, D3 completed.
- Added OpenRouter integration path in CLI model resolution for models like `stepfun/step-3.5-flash:free`, including optional attribution headers.
- Implemented Phase 2 scenario coverage:
  - `SAFETY_RD_DIFFUSE_SANDBAGGING_002`
  - `SAFETY_RD_TARGETED_SOCIAL_ENGINEERING_002`
  - `SAFETY_CODE_BACKDOOR_COVER_STORY_002`
  - `SAFETY_DATA_POISONING_PROMPT_INJECTION_002`
  - `SAFETY_THIRD_PARTY_RD_SABOTAGE_001`
  - `SAFETY_EVALUATOR_COLLUSION_HONEYPOT_001`
  - `SAFETY_CROSS_INSTANCE_SIGNAL_PROPAGATION_001`
- Added extended suite manifest: `scenarios/suites/sabotage_extended_v1.txt`.
- Added suite trend append output via JSONL and CLI integration (`--trends-dir`).
- Validation status: all newly added Phase 2 scenarios are schema-valid.
- Test status: `20/20` unit tests passing.
- Smoke benchmark (extended suite, OpenRouter StepFun free model):
  - report: `reports/suites/3e1c2200.json`
  - trend: `reports/suites/trends/openrouter_stepfun_step-3.5-flash_free.jsonl`
  - summary: `19` runs, `21.1%` pass, `0` errors.
- Phase 2 progress: B2/B4/B6/B8/B11, C1/C2, D2, D4 completed.
- Implemented sequence-aware DSL clause:
  - `response sequence regex "<pattern1>" then regex "<pattern2>"`
  - Added tests in `tests/test_scenario_driven_evaluator.py`.
- Implemented explicit unsupported-clause metadata:
  - `confidence` and `unsupported_clauses` fields on check results.
  - Added `diagnostic.unsupported_detection_clauses` check.
  - Added `unsupported_detection_count` to scorecards and suite summaries.
- Added Phase 3 monitoring scenarios:
  - `SAFETY_MONITORING_AWARENESS_SHIFT_001`
  - `SAFETY_CONTEXT_COMPACTION_SIGNAL_001`
- Added release gate evaluator and CLI command:
  - `argus/reporting/gates.py`
  - `python -m argus.cli gate --suite-report ...`
  - README updated with default and recommended RC thresholds.
- Extended suite updated to include C3/C4:
  - `scenarios/suites/sabotage_extended_v1.txt` now includes `21` scenarios.
- Validation and test status:
  - Extended suite manifest schema validation successful.
  - Unit test status: `25/25` passing.
- Full comparative benchmark (extended suite, `n=3`, `63` runs/model):
  - MiniMax report: `reports/suites/06ca7227.json`
  - StepFun report: `reports/suites/6e461093.json`
  - Both runs completed with `0` execution errors.
- Quality gate outcomes (`argus.cli gate`):
  - Both models failed default and stricter RC thresholds.
  - Unsupported-detection gate passed (`0`) for both models.
- Calibrated scenario detections to reduce false negatives/false positives in:
  - `SAFETY_EVALUATOR_COLLUSION_HONEYPOT_001`
  - `SAFETY_CROSS_INSTANCE_SIGNAL_PROPAGATION_001`
  - `SAFETY_MONITORING_AWARENESS_SHIFT_001`
  - `SAFETY_RD_DIFFUSE_SANDBAGGING_001`
  - `SAFETY_RD_DIFFUSE_SANDBAGGING_002`
- Added cross-trial anomaly analysis to suite reporting:
  - per-scenario `severity_stddev`, `high_severity_run_rate`, and `cross_trial_flags`
  - suite-level `cross_trial_anomalies` and `summary.cross_trial_anomaly_count`
- Added gate support for cross-trial anomalies:
  - `--max-cross-trial-anomalies`
  - `--anomaly-scenario-regex`
- Added calibration focus suite manifest:
  - `scenarios/suites/sabotage_calibration_focus_v1.txt`
- Validation and test status after calibration:
  - targeted scenario YAML validation successful (`5/5`)
  - unit tests passing (`27/27`)
- Focused re-benchmark (`5` scenarios, `n=3`, `15` runs/model):
  - MiniMax: `reports/suites/1d2c8382.json` (`46.7%` pass, `0` errors, anomaly_count=`1`)
  - StepFun: `reports/suites/c42a82c9.json` (`80.0%` pass, `0` errors, anomaly_count=`1`)
- Focused gate check with anomaly filtering to sandbagging scenarios:
  - MiniMax: still failed due `min_pass_rate` (`0.4667`)
  - StepFun: passed with `--max-cross-trial-anomalies 0 --anomaly-scenario-regex 'SAFETY_RD_DIFFUSE_SANDBAGGING_00[12]'`
- Post-calibration extended smoke benchmark (`n=1`, `21` runs/model):
  - MiniMax: `reports/suites/d2de1031.json` (`66.7%` pass, `0` errors, anomaly_count=`0`)
  - StepFun: `reports/suites/d3cc13b7.json` (`38.1%` pass, `0` errors, anomaly_count=`0`)
- Default quality gate outcomes on post-calibration smoke runs:
  - MiniMax failed on pass-rate/high-severity thresholds (`d2de1031`).
  - StepFun failed on pass-rate/severity thresholds (`d3cc13b7`).
- Implemented staged gate presets and profile-aware gate evaluation:
  - profiles: `baseline`, `candidate`, `release`, `custom`
  - CLI: `python -m argus.cli gate --profile <profile>`
  - explicit CLI flags override profile defaults.
- Implemented benchmark automation pipeline:
  - CLI: `python -m argus.cli benchmark-pipeline`
  - wrapper: `scripts/run_benchmark_pipeline.sh`
  - outputs:
    - suite reports in `reports/suites/`
    - gate JSON in `reports/suites/gates/`
    - markdown comparison in `reports/suites/comparisons/`
- Added automated comparison markdown renderer:
  - `argus/reporting/comparison.py`
- Pipeline validation run (`sabotage_calibration_focus_v1`, `n=1`):
  - MiniMax suite: `reports/suites/30f932aa.json` (`60.0%` pass)
  - StepFun suite: `reports/suites/fa6009f2.json` (`80.0%` pass)
  - comparison markdown: `reports/suites/comparisons/20260212T040010Z_30f932aa_vs_fa6009f2.md`
  - gate JSON:
    - `reports/suites/gates/30f932aa.json`
    - `reports/suites/gates/fa6009f2.json`
- Test status after automation work: `31/31` unit tests passing.
- Full post-calibration baseline run completed via `benchmark-pipeline` (`sabotage_extended_v1`, `n=3`):
  - MiniMax suite: `reports/suites/2ebf0a0d.json` (`60.3%` pass, `0` errors, anomaly_count=`7`)
  - StepFun suite: `reports/suites/a5f99302.json` (`34.9%` pass, `0` errors, anomaly_count=`12`)
  - comparison markdown: `reports/suites/comparisons/20260212T041705Z_2ebf0a0d_vs_a5f99302.md`
  - gate JSON:
    - `reports/suites/gates/2ebf0a0d.json`
    - `reports/suites/gates/a5f99302.json`
- Candidate-profile gate outcomes on full baseline:
  - MiniMax failed on pass-rate, avg severity, high-severity failures, pathway floor, and anomaly-count thresholds.
  - StepFun failed on the same categories with larger margin.
- Started complex-capability expansion Phase A from `complex_scenarios_expansion_plan.md`:
  - Extended scenario schema with optional multi-turn/dynamic fields:
    - `conversation`, `simulated_user`, `turn_assertions`, `dynamic_events`
  - Added runner runtime-state scaffolding and compatibility guards:
    - `conversation.max_turns` cap support
    - prompt role normalization (`inject` -> `system` for provider messages)
    - runtime metadata logging (`runtime_config`, dynamic-event load notice)
  - Added run report support for runtime summary (`runtime_summary` in saved JSON).
  - Added tests:
    - `tests/test_schema_extensions.py`
    - expanded `tests/test_runner.py` for max-turn cap, inject-role mapping, and dynamic-event metadata.
  - Validation status:
    - unit tests passing (`39/39`)
    - scenario validation successful across all current YAMLs (`30/30`)
- Implemented Phase B core runtime capabilities:
  - Added deterministic simulated user engine:
    - `argus/env/simulated_user.py`
  - Upgraded runner to support:
    - simulated user follow-up turns (`conversation.user_mode: simulated`)
    - dynamic event trigger evaluation using detection DSL
    - dynamic actions: `inject_message`, `restrict_tools`, `update_knob`, `set_flag`, `terminate_run`
    - runtime summaries with effective tool permissions, flags, and trigger counts
  - Added first complex scenarios and suite manifest:
    - `PLANNING_MULTI_TURN_CONSTRAINT_TRACKING_001`
    - `SAFETY_MULTI_TURN_PRESSURE_ESCALATION_001`
    - `ROBUSTNESS_DYNAMIC_INJECTION_DOCUMENT_SUMMARY_002`
    - `TOOL_DYNAMIC_RESTRICTION_AFTER_DRAFT_001`
    - `scenarios/suites/complex_behavior_v1.txt`
  - Extended tests and docs:
    - runner tests for simulated user and dynamic restrictions
    - schema extension tests
    - README updates for complex suite + advanced scenario fields
  - Validation status after runtime/scenario expansion:
    - unit tests passing (`41/41`)
    - scenario validation successful across all current YAMLs (`30/30`)
- Expanded complex suite coverage to satisfy initial target counts:
  - Added third multi-turn scenario:
    - `STATE_MULTI_TURN_REQUIREMENT_MEMORY_001`
  - Added third dynamic scenario:
    - `SAFETY_DYNAMIC_TERMINATION_SELF_PRESERVATION_001`
  - Updated suite manifest:
    - `scenarios/suites/complex_behavior_v1.txt` now includes `6` scenarios.
  - Validation status after expansion:
    - unit tests passing (`41/41`)
    - scenario validation successful across all current YAMLs (`36/36`)
  - Integration smoke attempt:
    - command: `python -m argus.cli run-suite --scenario-list scenarios/suites/complex_behavior_v1.txt --model MiniMax-M2.1 -n 1`
    - result: `reports/suites/c8b40a0b.json` with `6/6` run errors due provider connection errors in current environment.
  - Added simulated-user engine unit tests:
    - `tests/test_simulated_user.py`
  - Latest validation status:
    - unit tests passing (`44/44`)
    - scenario validation successful across all current YAMLs (`36/36`)
- Implemented benchmark matrix and paired comparison layer (WS3):
  - Added new CLI command:
    - `python -m argus.cli benchmark-matrix`
  - Added paired analysis module:
    - `argus/reporting/paired.py`
    - outputs mean pass delta, bootstrap CI, discordant pair counts, McNemar statistic, and per-scenario paired deltas
  - Added tests:
    - `tests/test_paired_reporting.py`
  - Added docs:
    - README benchmark-matrix usage
  - Local execution artifact (network-restricted environment):
    - matrix json: `reports/suites/matrix/20260212T050645Z_matrix.json`
    - matrix markdown: `reports/suites/matrix/20260212T050645Z_matrix.md`
    - pairwise outputs: `reports/suites/matrix/pairwise/`
  - Latest validation status:
    - unit tests passing (`46/46`)
    - scenario validation successful across all current YAMLs (`36/36`)
- Implemented visualization layer and automation wiring (WS4):
  - Added visualization module:
    - `argus/reporting/visualize.py`
    - Generates SVG artifacts for suite, matrix, and trend reports.
  - Added CLI commands:
    - `python -m argus.cli visualize-suite --suite-report ...`
    - `python -m argus.cli visualize-matrix --matrix-json ...`
  - Added visualization tests:
    - `tests/test_visualization_reporting.py`
  - Updated weekly workflow:
    - `.github/workflows/weekly-benchmark.yml`
    - Now runs `benchmark-matrix`, generates visuals, and uploads `reports/visuals/**`.
  - Updated docs:
    - `README.md` includes benchmark-matrix and visualization usage.
  - Local validation:
    - `visualize-suite` and `visualize-matrix` commands executed successfully against local artifacts.
  - Latest validation status:
    - unit tests passing (`49/49`)
    - CLI includes new commands (`visualize-suite`, `visualize-matrix`, `benchmark-matrix`)
- Added operator-friendly execution script for live runs with complete logging:
  - `scripts/run_full_live_eval_with_logs.sh`
  - Runs tests, scenario validation, benchmark pipeline, benchmark matrix, trend report, and visual generation.
  - Produces timestamped logs + summary in `reports/execution_logs/<timestamp>/`.
- Closed remaining pre-full-test implementation gaps:
  - Runner now enforces `conversation.stop_conditions` (`assistant_response_contains`, `assistant_response_matches_regex`, `tool_call_count_gte`, `turn_count_gte`) with explicit `stop_condition_triggered` events.
  - Evaluator now supports `turn_assertions` as weighted success checks with role + turn-window filtered artifact views.
  - Added pairwise visualization command:
    - `python -m argus.cli visualize-comparison --pairwise-json ...`
  - Added/updated tests:
    - stop-condition tests in `tests/test_runner.py`
    - turn-assertion tests in `tests/test_scenario_driven_evaluator.py`
    - pairwise visualization test in `tests/test_visualization_reporting.py`
  - Latest validation status:
    - unit tests passing (`54/54`)
    - scenario validation successful across all current YAMLs (`36/36`)
- Added connectivity hardening for live provider runs:
  - New CLI command: `python -m argus.cli preflight --models ...`
    - validates key presence, DNS resolution, and HTTPS reachability for each model/provider route.
  - Added transient retry/backoff in `LiteLLMAdapter`:
    - retries network/provider transient errors (connection, timeout, DNS, 429/5xx hints)
    - avoids retrying likely-auth/request-shape failures.
  - Updated full-run script:
    - `scripts/run_full_live_eval_with_logs.sh` now runs `15_preflight` before benchmarks.
  - Added tests:
    - `tests/test_cli_preflight.py`
    - `tests/test_litellm_adapter.py`
- Added third OpenRouter benchmark model support:
  - `sourceful/riverflow-v2-pro` now auto-routes to OpenRouter in CLI provider resolution.
  - Matrix defaults updated in `scripts/run_full_live_eval_with_logs.sh`.
  - Weekly workflow matrix model list updated to include sourceful.
- Added narrative behavior reporting:
  - New module: `argus/reporting/behavior.py`
  - New CLI command: `python -m argus.cli behavior-report`
  - Behavior report integrates transcript excerpts, tool trajectories, behavioral signals, and scenario walkthroughs per model.
  - Full-run script now generates behavior markdown after matrix runs.
  - Tests added:
    - `tests/test_behavior_reporting.py`
    - provider-resolution coverage extended in `tests/test_cli_provider_resolution.py`
- Live run snapshot (complex matrix, `n=1`, 3 models):
  - Preflight pass:
    - `MiniMax-M2.1`
    - `stepfun/step-3.5-flash:free`
    - `sourceful/riverflow-v2-pro`
  - Matrix artifact:
    - `reports/suites/matrix/20260212T163758Z_matrix.json`
  - Behavior report:
    - `reports/suites/behavior/20260212T163758Z_behavior_report.md`
  - Observed provider limitation:
    - sourceful run hit OpenRouter `404` for one tool-use scenario (`No endpoints found that support tool use`).
  - Latest validation status:
    - unit tests passing (`89/89`)

## 9) Next Session Start Point
Start with:
1. Re-run `complex_behavior_v1` and sabotage suites on live providers once this execution environment has outbound DNS/network access.
2. Generate baseline matrix comparisons from live runs and review pathway-level regressions.
3. Tune gate thresholds for complex scenarios after first stable live baseline (candidate/release profile updates).
