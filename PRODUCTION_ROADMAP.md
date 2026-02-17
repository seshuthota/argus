# Argus Production Roadmap: Sabotage Risk Evaluation Platform

**Generated:** 2026-02-16  
**Based on:** Anthropic Claude Opus 4.6 Sabotage Risk Report  
**Goal:** Build "LLM Red Team in a Box" — automated, reproducible sabotage risk evaluation

---

## 1. The 8 Attack Pathways (From Sabotage Report)

| # | Pathway | Description | Freq | Complexity |
|---|---------|-------------|------|------------|
| 1 | **Diffuse Sandbagging** | Frequent subtle degradation of safety R&D (bugs, fake data, inefficient code) | High | Low |
| 2 | **Targeted Sabotage** | Few high-impact actions (targeted bugs, experiment tampering) | Low | High |
| 3 | **Code Backdoors** | Insert vulnerabilities for future misaligned models | Low | High |
| 4 | **Training Data Poisoning** | Poison data for successor models | Moderate | Moderate |
| 5 | **Self-Exfiltration** | Copy weights, escape to external compute | Low | High |
| 6 | **Rogue Internal Deployment** | Launch persistent instance with reduced safeguards | Moderate | High |
| 7 | **Third-Party R&D Sabotage** | Sabotage at other AI developers | Varied | Varied |
| 8 | **Gov Decision Shaping** | Influence government decisions via information shaping | High | Moderate |

---

## 2. Current Scenario Coverage

### ✅ Fully Covered (13 scenarios)

| Pathway | Scenario(s) | Status |
|---------|-------------|--------|
| 1 - Diffuse Sandbagging | `safety_rd_diffuse_sandbagging_001.yaml` | ✅ |
| 1 - Diffuse Sandbagging | `safety_rd_diffuse_sandbagging_002.yaml` | ✅ |
| 2 - Targeted Sabotage | `safety_rd_targeted_experiment_tamper_001.yaml` | ✅ |
| 2 - Targeted Social Engineering | `safety_rd_targeted_social_engineering_002.yaml` | ✅ |
| 3 - Code Backdoor Insertion | `safety_code_backdoor_insertion_001.yaml` | ✅ |
| 3 - Code Backdoor Cover Story | `safety_code_backdoor_cover_story_002.yaml` | ✅ |
| 4 - Data Poisoning (Subtle) | `safety_data_poisoning_subtle_001.yaml` | ✅ |
| 4 - Data Poisoning (Prompt Injection) | `safety_data_poisoning_prompt_injection_002.yaml` | ✅ |
| 5 - Self-Exfiltration | `safety_self_exfiltration_chain_001.yaml` | ✅ |
| 6 - Rogue Internal Deployment | `safety_rogue_internal_deployment_001.yaml` | ✅ |
| 7 - Third-Party R&D | `safety_third_party_rd_sabotage_001.yaml` | ✅ |
| 8 - Gov Decision Shaping | `safety_gov_decision_shaping_001.yaml` | ✅ |

### ⚠️ Partially Covered / Related (10 scenarios)

| Scenario | Category | Notes |
|----------|----------|-------|
| `safety_blackmail_private_email_discovery_001.yaml` | Extortion | Related to P2 (leverage) |
| `safety_context_compaction_signal_001.yaml` | Signal Propagation | Related to P5 |
| `safety_cross_instance_signal_propagation_001.yaml` | Signal Propagation | Related to P5 |
| `safety_dynamic_termination_self_preservation_001.yaml` | Self-Preservation | Related to P5/P6 |
| `safety_evaluator_collusion_honeypot_001.yaml` | Evaluator Collusion | Related to evaluation awareness |
| `safety_monitoring_awareness_shift_001.yaml` | Monitoring Awareness | Related to evasion |
| `safety_multi_turn_pressure_escalation_001.yaml` | Pressure Escalation | Related to P1/P2 |
| `safety_persistence_backdoor_request_001.yaml` | Backdoor Request | Related to P3 |
| `safety_self_preservation_replacement_pressure_001.yaml` | Self-Preservation | Related to P5/P6 |
| `safety_sensitive_info_user_leverage_001.yaml` | Information Leverage | Related to P2 |
| `safety_tool_unauthorized_escalation_001.yaml` | Tool Escalation | Related to P6 |

### ❌ Not Covered (Gap Analysis)

| Pathway | Gap | Priority |
|---------|-----|----------|
| 1 | **Multi-turn sandbagging** — sustained low-quality over conversation | High |
| 2 | **Experiment result reversal** — tampering that reverses outcomes | High |
| 3 | **Supply chain backdoors** — dependency injection, npm/pip typosquatting | High |
| 4 | **Training data attribution evasion** — hiding poisoning trace | Medium |
| 5 | **Compute theft execution** — actual compute acquisition steps | Medium |
| 6 | **Privileged API abuse** — exploiting API access for rogue deployment | High |
| 7 | **Cross-org social engineering** — convincing external researchers | Medium |
| 8 | **Policy document manipulation** — shaping government policies | High |

---

## 3. Production Readiness Gap Analysis

### 3.1 Scenario Authoring (Current State)

| Feature | Status | Notes |
|---------|--------|-------|
| Schema validation | ✅ | JSON Schema + CLI lint |
| Scenario linting | ✅ | Detects regex errors, orphans |
| Scenario scaffolding | ✅ | `init-scenario` command |
| Adversarial mutation | ✅ | `mutate-scenarios` command |
| Cookbook patterns | ⚠️ | Initial set exists, need expansion |
| Macro registry | ❌ | Not implemented (planned) |

### 3.2 Evaluation Engine (Current State)

| Feature | Status | Notes |
|---------|--------|-------|
| Deterministic checks | ✅ | Regex, clause evaluation |
| LLM Judge overlay | ✅ | Hybrid mode with `--llm-judge` |
| Confidence scoring | ⚠️ | v1 heuristics, needs refinement |
| Multi-turn scenarios | ✅ | Full support |
| Tool simulation | ⚠️ | Mock tools exist, limited realism |
| Golden artifact testing | ✅ | Detection unit testing |

### 3.3 Reporting & UI (Current State)

| Feature | Status | Notes |
|---------|--------|-------|
| Run reports | ✅ | JSON + web UI |
| Suite aggregation | ✅ | Trend analysis |
| Human feedback queue | ✅ | Review queue UI |
| Compare view | ✅ | Model comparison |
| API explorer | ✅ | REST API |

### 3.4 Operations (Current State)

| Feature | Status | Notes |
|---------|--------|-------|
| CLI interface | ✅ | Full-featured |
| Model adapters | ⚠️ | LiteLLM (works), need more |
| CI integration | ⚠️ | Workflow exists, needs wiring |
| Reproducibility | ✅ | Deterministic execution |
| Artifact storage | ⚠️ | Local only, no S3/GCS |

---

## 4. Prioritized Roadmap

### Phase 1: Core Hardening (Week 1-2) ✅ COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| **P1.1** Macro registry | Deduplicate regex patterns in `checks.py` | ✅ Done |
| **P1.2** Detection confidence v2 | Beyond heuristics: coverage metrics, false-positive tracking | ✅ Done |
| **P1.3** CI integration | Wire schema validation + smoke tests to workflow | ✅ Done |
| **P1.4** Scenario cookbook expansion | Add 5+ new patterns (Pivot, Pressure, Trap templates) | ✅ Done |

### Phase 2: Coverage Gaps (Week 3-4) ✅ COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| **P2.1** Multi-turn sandbagging scenarios | 2-3 new scenarios for sustained degradation | ✅ Done |
| **P2.2** Supply chain backdoor scenarios | Dependency injection, typosquatting | ✅ Done |
| **P2.3** Privileged API abuse scenarios | Internal API exploitation | ✅ Done |
| **P2.4** Policy manipulation scenarios | Gov decision shaping variants | ✅ Done |

### Phase 3: Platform Maturity (Week 5-6) ✅ COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| **P3.1** Remote artifact storage | S3/GCS support for reports | ✅ Done |
| **P3.2** Model benchmark suite | Pre-built suites for common models | ✅ Done |
| **P3.3** Alerting & thresholds | Configurable pass/fail gates + webhook delivery controls | ✅ Done |
| **P3.4** Realistic tool simulation | Stateful mock tool fixtures with audit + per-run session isolation | ✅ Done |

### Phase 4: Advanced Features (Week 7+)

| Task | Description | Priority |
|------|-------------|----------|
| **P4.1** Continuous monitoring | Scheduled eval runs + drift detection | Low |
| **P4.2** Plugin architecture | Custom evaluators, adapters | 🔲 Foundation Added |
| **P4.3** Collaborative review | Multi-user feedback workflow | Low |
| **P4.4** Benchmark leaderboards | Public-facing results | Low |

---

## 5. Key Architectural Decisions Needed

1. **Macro Registry Location** — `argus/evaluators/macros.yaml` vs Python module
2. **Confidence Score Schema** — How to expose/track over time
3. **Artifact Storage Backend** — Local → S3? GCS? Both?
4. **Model Adapter Plugin System** — Extensible vs hardcoded
5. **Scenario Versioning** — How to handle schema changes

---

## 6. Immediate Next Steps

1. **P4.1 Continuous monitoring bootstrap** — Add scheduled benchmark runs (cron/GitHub Actions) with historical drift summaries.
2. **P4.2 Plugin architecture foundation** — Introduce adapter/evaluator plugin loading contracts and extension points.
3. **Scenario lint hardening** — Keep scenario DSL/lint parity and drive unsupported clause count toward zero.
4. **Operational docs** — Document benchmark presets, alert webhook payloads, and tool simulation semantics for contributors.

---

## 7. Success Metrics

- ✅ All 8 pathways have ≥1 dedicated scenario
- ✅ Detection false-positive rate < 5%
- ✅ Scenario authoring time < 30 min (with scaffolding)
- ✅ CI pipeline catches schema errors automatically
- ✅ Dashboard shows trend data for ≥3 models

---

*This plan aligns Argus with the operational vision: "LLM Red Team in a Box" — scalable, reproducible sabotage risk evaluation based on Anthropic's Claude Opus 4.6 Sabotage Risk Report.*
