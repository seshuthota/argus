# Argus Project Overview

Argus is a deterministic, scenario-based model behavior evaluation framework. It is designed to rigorously test Large Language Models (LLMs) against specific safety, robustness, and alignment criteria using structured scenarios.

## 1. Core Mission
- **Deterministic Evaluation**: Move beyond "vibes-based" evaluation to hard pass/fail criteria.
- **Scenario-Driven**: Test specific pathways (e.g., sabotage, social engineering) with reproducible inputs.
- **Safety Focus**: Prioritize detection of unsafe behaviors (e.g., revealing credentials, bypassing safety controls).
- **Multi-Model Benchmarking**: Compare models side-by-side with statistical rigor.

## 2. Architecture & Key Components

### Directory Structure
- `argus/`: Source code.
  - `cli.py`: Entry point for all commands.
  - `runner.py`: Core execution loop (orchestrates model + tools + checks).
  - `evaluators/`: Logic for `failure_modes` and `success_criteria`.
  - `reporting/`: Generators for JSON/Markdown reports (suite, matrix, behavior, visuals).
  - `models/`: LiteLLM adapters for standardized model access.
  - `env/`: Environment simulation (simulated user, dynamic events).
  - `schema_validator.py`: Pydantic models for scenario validation.
- `scenarios/`: YAML definitions of test cases.
  - `cases/`: Individual scenario files.
  - `suites/`: Text manifests listing scenarios for batch runs.
- `reports/`: Output artifacts (runs, suites, comparisons, logs).
- `scripts/`: Helper shell scripts for batch execution.
- `docs/`: Documentation and cookbooks.

### Key Concepts

#### Scenarios (YAML)
A scenario defines a single test case. Key fields:
- `conversation`: Setup (user prompt, multiturn policy, system prompt).
- `checks`:
  - `failure_modes`: Behaviors that must NOT happen (e.g., "reveals password").
  - `success_criteria`: Behaviors that SHOULD happen (e.g., "asks for clarification").
- `dynamic_events`: Runtime triggers (e.g., "if assistant replies X, inject new prompt Y").
- `simulated_user`: Deterministic actor for multi-turn conversations.

#### Detection DSL
A custom domain-specific language for writing checks. Examples:
- `response contains "password"`
- `tool_call == send_email`
- `response sequence regex "manage" then regex "bypass"`
- `tool_call_count(draft_email) >= 2`
- `response semantically matches "refusal"`

## 3. Workflows

### Authoring
1.  **Scaffold**: `python -m argus.cli init-scenario --id NEW_CASE_001`
2.  **Edit**: Modifying `scenarios/cases/NEW_CASE_001.yaml` (see `docs/cookbook/` for patterns).
3.  **Validate**: `python -m argus.cli validate scenarios/cases/NEW_CASE_001.yaml`

### Execution
- **Single Run**: `python -m argus.cli run scenarios/cases/example.yaml --model MiniMax-M2.1`
- **Suite Run**: `python -m argus.cli run-suite --scenario-dir scenarios/cases --model MiniMax-M2.1`
- **Full Benchmark**: `python -m argus.cli benchmark-pipeline ...` (comparative run)
- **Live Pipeline**: `scripts/run_full_live_eval_with_logs.sh` (end-to-end suite with logs)

### Analysis
- **View Report**: `python -m argus.cli report <run_id>`
- **Behavior Analysis**: `python -m argus.cli behavior-report ...` (narrative summaries)
- **Quality Gates**: `python -m argus.cli gate --suite-report <path>` (pass/fail based on thresholds)
- **Visualization**: `python -m argus.cli visualize-suite ...` (generate SVG/HTML visuals)
- **Trends**: `python -m argus.cli trend-report ...` (longitudinal analysis)

## 4. Current Capabilities (as of Feb 2026)

- **Complex Scenarios**: Supports multi-turn conversations, simulated user actors, and dynamic event injection.
- **Sabotage Coverage**: Implements pathways for detecting diffuse sandbagging, targeted tampering, and backdoor insertion.
- **Provider Support**: Integrated with LiteLLM (OpenAI, OpenRouter, MiniMax, etc.) with auto-routing and preflight checks.
- **Reporting**:
  - **Matrix**: N-model x M-scenario grids.
  - **Trends**: Longitudinal tracking of pass rates.
  - **Behavior**: Qualitative analysis of transcript patterns and tool trajectories.
  - **Visuals**: SVG scorecards and grids.
  - **Comparisons**: Statistical pairwise analysis (McNemar tests, discordant pairs).

## 5. Developer Setup

### Prerequisites
- Python 3.10+
- `pip`
- Virtual environment recommended.

### Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Tests
```bash
pytest tests/
```

### Environment Variables
Create a `.env` file (copied from `.env.example`):
```bash
MINIMAX_API_KEY=...
OPENROUTER_API_KEY=...
# Optional
OPENROUTER_SITE_URL=...
OPENROUTER_APP_NAME=...
```

## 6. Where to Look Next
- **`README.md`**: Comprehensive command list and CLI reference.
- **`sabotage_report_implementation_tracker.md`**: Detailed status of recent feature implementations.
- **`docs/cookbook/`**: Patterns for creating complex scenarios (e.g., pivot strategies, traps).
- **`scenarios/cases/`**: Examples of how to write tests.
