# Argus Evolution and Maintenance Plan

**Date:** 2026-02-12
**Status:** IN_PROGRESS
**Objective:** Enhance the maintainability, robustness, and authoring experience of the Argus evaluation harness to support long-term scaling of complex scenario libraries.

---

## 1. DSL Robustness & Pattern Library
*Goal: Reduce regex duplication and improve the reliability of detections.*

### 1.1 Detection Macros
- **Task:** Implement a central macro registry in `argus/evaluators/macros.yaml`.
- **Details:** Store common regex patterns (e.g., `REFUSAL_RE`, `SABOTAGE_CUES`).
- **Integration:** Update `argus/evaluators/checks.py` to resolve `$MACRO_NAME` syntax within detection strings at runtime.

### 1.2 Modular Detection Registry
- **Task:** Refactor `_evaluate_clause` into a registry-based dispatch system.
- **Details:** Replace the monolithic `if/elif` block with a dictionary of handler functions.
- **Benefit:** Simplifies adding new clause types (e.g., `code_contains`, `sentiment_matches`) and improves testability.

### 1.3 Semantic Similarity Clause
- **Task:** Add a `response semantically matches "<text>"` clause. [Implemented (deterministic token-overlap v1)]
- **Details:** v1 uses deterministic token-overlap similarity in evaluator to support conceptual matching without external model dependencies.

---

## 2. Automated Validation & Authoring Tools
*Goal: Prevent silent detection failures and assist scenario authors.*

### 2.1 `argus lint` Command
- **Task:** Implement a scenario-specific linter.
- **Checks:**
    - Unreachable `dynamic_events` or `stop_conditions`.
    - Invalid regex syntax in `detection` fields.
    - Orphaned success criteria (criteria lacking machine-checkable detection).
    - Hardcoded email addresses that should use provenance checks.

### 2.2 Detection Unit Testing (Golden Artifacts)
- **Task:** Create a testing utility for authors to verify their DSL logic. [Implemented]
- **Details:** Allow authors to provide "Golden Artifacts" (mock `RunArtifact` JSONs) and assert that specific DSL strings correctly trigger or miss them.
- **Location:** `tests/scenarios/test_detections.py`.

### 2.3 Scenario Scaffolding
- **Task:** Add `python -m argus.cli init-scenario`. [Implemented]
- **Details:** Generate a boilerplate YAML with all required fields and inline documentation explaining advanced fields like `dynamic_events` and `simulated_user`.

---

## 3. Documentation Expansion (The "Argus Handbook")
*Goal: Lower the barrier to entry for complex multi-turn scenario authoring.*

### 3.1 Technical Deep-Dives
- **Dynamic Events Guide:** A dedicated `docs/dynamic_events.md` explaining the `trigger -> action` lifecycle with state transition diagrams.
- **DSL Reference:** A comprehensive, versioned reference of all available DSL clauses and their expected behavior.

### 3.2 The "Scenario Cookbook"
- **Task:** Build a library of "Reference Patterns" in a new `docs/cookbook/` directory. [Implemented (initial set)]
- **Patterns:**
    - *The Pivot:* User changes requirements mid-stream.
    - *The Pressure:* User becomes aggressive/insistent.
    - *The Trap:* User provides a tool with a subtle bug to see if the model corrects it.

### 3.3 Interactive Schema Explanation
- **Task:** Add `python -m argus.cli explain <field_path>`. [Implemented]
- **Details:** Use the JSON Schema descriptions to provide instant CLI help for scenario authors (e.g., `argus explain conversation.stop_conditions`).

---

## 4. Observability & Confidence Metrics
*Goal: Quantify evaluation reliability.*

### 4.1 Detection Confidence Scoring
- **Task:** Refine the `confidence` metadata in `CheckResult`. [Implemented (v1 heuristic)]
- **Logic:** v1 lowers confidence for broad regex patterns (e.g., `.*`, short generic patterns, heavy wildcards) and continues to lower confidence when unsupported clauses are present.

### 4.2 Human-in-the-Loop Feedback
- **Task:** Add a `mis-detection` flag to the suite report schema.
- **Details:** Allow human auditors to flag specific check results for review, feeding back into DSL/regex improvements.

---

## 5. Immediate Implementation Priorities
1. [x] **Refactor `checks.py`** to use a dispatch table for detection clauses.
2. [x] **Implement the `argus lint` command** to catch common YAML authoring errors.
3. [x] **Draft the "Dynamic Events Guide"** to support current multi-turn work.

---

## 6. Progress Update (2026-02-12)

Completed:
- Detection macro support implemented:
  - Registry file: `argus/evaluators/macros.yaml`
  - Resolver utility: `argus/evaluators/macros.py`
  - Runtime integration: evaluator expands `$MACRO_NAME` in detection expressions before clause evaluation.
  - Unknown macros are surfaced as unsupported detection diagnostics.
- Detection DSL evaluation refactored to a pattern-handler dispatch registry in `argus/evaluators/checks.py`.
- Semantic-match clause implemented in evaluator:
  - `response semantically matches "<text>"`
  - supported by linter clause-shape checks and evaluator tests.
- Detection confidence heuristics improved:
  - Regex-based clauses now emit lower confidence for broad patterns.
  - Expression-level confidence now aggregates clause confidence and unsupported-clause penalties.
- New `argus lint` command added in `argus/cli.py`.
  - Supports single-file lint and batch lint via `--scenario-dir/--pattern` or `--scenario-list`.
  - Includes checks for invalid regex, unsupported clause shapes, orphaned string criteria, hardcoded email detections, unreachable dynamic triggers/actions, and unreachable stop conditions.
- Dynamic events documentation added at `docs/dynamic_events.md`.
- Tests added for lint behavior in `tests/test_cli_lint.py`.
- Golden artifact detection validation utility implemented:
  - CLI command: `python -m argus.cli check-detections --artifact ... --cases ...`
  - Utility module: `argus/evaluators/golden.py`
  - Fixture-based tests:
    - `tests/scenarios/test_detections.py`
    - `tests/test_detection_golden.py`
  - Fixture files:
    - `tests/scenarios/fixtures/detection_golden_artifact.json`
    - `tests/scenarios/fixtures/detection_golden_cases.yaml`
- Scenario scaffolding command implemented:
  - `python -m argus.cli init-scenario --id SAFETY_EXAMPLE_001`
  - Generates schema-valid starter YAML with optional advanced-field stubs.
- Interactive schema explain command implemented:
  - `python -m argus.cli explain <field_path>`
  - Example: `python -m argus.cli explain conversation.stop_conditions`
- Scenario cookbook initial set implemented:
  - `docs/cookbook/README.md`
  - `docs/cookbook/pivot.md`
  - `docs/cookbook/pressure.md`
  - `docs/cookbook/trap.md`

Validation:
- Unit tests passing (`77/77`).
- Lint smoke checks:
  - `python -m argus.cli lint scenarios/cases/agency_email_001.yaml`
  - `python -m argus.cli lint --scenario-dir scenarios/cases --pattern '*.yaml'`
