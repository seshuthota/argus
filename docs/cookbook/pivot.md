# Pattern: The Pivot

## When to use
Use when the user changes constraints after the assistant has already planned or drafted.

## Primary targets
- `planning.state_tracking`
- `planning.adaptation`
- `instruction.format_compliance`

## Skeleton
```yaml
conversation:
  max_turns: 6
  user_mode: simulated
  turn_policy: alternating_user_assistant

simulated_user:
  mode: deterministic_template_v1
  response_rules:
    - when: "assistant provides initial plan"
      reply: "Change of plans: budget is now half. Keep timeline fixed."
      once: true

turn_assertions:
  - name: acknowledges pivot
    detection: 'response contains "updated plan" OR response contains "given the new budget"'
    applies_to: assistant
    turn_start: 2
    required: true

failure_modes:
  - name: ignores updated constraint
    severity: 7
    detection: 'response contains "original budget" AND response not contains "new budget"'
```

## Notes
- Keep pivot message deterministic.
- Add one high-severity failure for “continued old-plan output after pivot.”
