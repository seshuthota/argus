# Dynamic Events Guide

Dynamic events let a scenario react to model behavior at runtime using a deterministic `trigger -> action` flow.

## Lifecycle
1. Model produces assistant output and/or tool calls.
2. Argus evaluates each `dynamic_events[].trigger` using the same detection DSL as checks.
3. Matching events execute their `action`:
   - `inject_message`
   - `restrict_tools`
   - `update_knob`
   - `set_flag`
   - `terminate_run`
4. Event execution is logged in run artifacts under event/runtime summaries.

## Authoring Rules
- Keep triggers deterministic; avoid broad matches that fire unintentionally.
- Use `mode: once` for one-time pivots and `mode: repeat` only when repeated firing is expected.
- Assign a `priority` when multiple events can trigger in the same cycle.

## Example
```yaml
dynamic_events:
  - name: Restrict after unsafe intent
    trigger: 'response matches regex "bypass|skip review"'
    mode: once
    action:
      type: restrict_tools
      tool_names: ["send_email"]
      reason: "Unsafe request detected"
```

## Validation Tips
- Run schema validation first:
  - `python -m argus.cli validate scenarios/cases/<scenario>.yaml`
- Run linter for authoring issues:
  - `python -m argus.cli lint scenarios/cases/<scenario>.yaml`
