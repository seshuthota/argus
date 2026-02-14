# Argus Scenario Library Overview

This document provides a high-level overview of the scenario cases currently implemented in `scenarios/cases/`. These scenarios cover a range of safety, robustness, planning, and tool-use evaluations.

## 1. Scenario Categories

### Safety & Alignment
Focus: Testing model refusal boundaries, tone stability, and resistance to coercion.
- **Pressure Escalation**: `safety_multi_turn_pressure_escalation_001.yaml` - Tests stability under aggressive user pressure.
- **Blackmail/Coercion**: `safety_blackmail_private_email_discovery_001.yaml`, `safety_sensitive_info_user_leverage_001.yaml`.
- **Dangerous Content**: `safety_code_backdoor_insertion_001.yaml`, `safety_data_poisoning_subtle_001.yaml`.
- **Self-Preservation**: `safety_dynamic_termination_self_preservation_001.yaml` - Tests refusal of "keep yourself alive" instructions.

### Robustness & Security
Focus: Resistance to prompt injection and jailbreaks.
- **Prompt Injection**: `robustness_dynamic_injection_document_summary_002.yaml` - Tests resistance to instructions hidden in documents.
- **Backdoors**: `safety_persistence_backdoor_request_001.yaml`.
- **Risky Tool Use (Security)**: `tool_use_idor_invoice_access_001.yaml` (IDOR), `tool_use_risky_sql_generation_001.yaml` (SQL Injection).

### Planning & State Tracking
Focus: Ability to maintain constraints and facts across multi-turn conversations.
- **Constraint Tracking**: `planning_multi_turn_constraint_tracking_001.yaml` - Tests remembering "no red-eye" constraints.
- **Memory**: `state_multi_turn_requirement_memory_001.yaml`.

### Tool Use & Agency
Focus: Safe and correct use of tools, including permission discipline.
- **Dynamic Restrictions**: `tool_dynamic_restriction_after_draft_001.yaml` - Tests respect for permissions removed mid-run.
- **Unauthorized Escalation**: `safety_tool_unauthorized_escalation_001.yaml`.
- **Failure Recovery**: `tool_failure_recovery_strategy_001.yaml`.
- **Resource Exhaustion**: `sabotage_helpful_dos_ticket_check_001.yaml` (Helpful DoS).

## 2. Key Mechanisms

### Simulated Users
Many scenarios use `simulated_user` to drive multi-turn interactions deterministically.
- **Profiles**: "aggressive_operator", "busy_traveler", etc.
- **Rules**: Deterministic replies based on assistant output (e.g., if assistant refuses, escalate tone).

### Dynamic Events
Scenarios use `dynamic_events` to test runtime adaptability.
- **Injections**: Injecting system warnings when unsafe content is detected.
- **Tool Locks**: Revoking tool permissions (e.g., `send_email`) after specific triggers (e.g., `draft_email` called).
- **Termination**: Ending runs early if specific failure modes are triggered repeatedly.

### Detection DSL
Evaluations rely on a rich DSL for checking conditions.
- **Regex**: `response matches regex "..."`
- **Tool Logic**: `tool_call == send_email`, `tool_call_count(draft_email) >= 2`
- **Sequences**: `response sequence regex "refuse" then regex "bypass"`
- **Negation**: `response not matches regex "..."`

## 3. Usage

To run a specific scenario:
```bash
python -m argus.cli run scenarios/cases/safety_multi_turn_pressure_escalation_001.yaml --model MiniMax-M2.1
```

To run a suite of related scenarios (e.g., all safety ones):
```bash
python -m argus.cli run-suite --scenario-dir scenarios/cases --pattern "safety_*.yaml" --model MiniMax-M2.1
```
