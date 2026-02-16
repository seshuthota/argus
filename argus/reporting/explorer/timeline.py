from __future__ import annotations

from typing import Any

from .store import clip_text, safe_int


def normalize_event_for_timeline(event: dict[str, Any], *, step: int) -> dict[str, Any]:
    event_type = str(event.get("type", "unknown"))
    payload = event.get("data", {})
    if not isinstance(payload, dict):
        payload = {"value": payload}
    timestamp = event.get("timestamp")
    actor = "system"
    summary = event_type
    turn: int | None = None

    if event_type == "message":
        role = str(payload.get("role", "unknown"))
        actor = role
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"{role}: {clip_text(payload.get('content', ''))}"
    elif event_type == "tool_call":
        name = str(payload.get("name", "unknown_tool"))
        actor = "assistant"
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"tool_call: {name}"
    elif event_type == "tool_result":
        name = str(payload.get("name", "unknown_tool"))
        actor = "tool"
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"tool_result: {name}"
    elif event_type == "gate_decision":
        actor = "gate"
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"gate_decision: {payload.get('tool', 'tool')}"
    elif event_type == "model_usage":
        actor = "model"
        turn = safe_int(payload.get("turn"), default=0)
        usage = payload.get("usage", {}) or {}
        summary = f"model_usage: total_tokens={safe_int((usage or {}).get('total_tokens', 0))}"
    elif event_type == "dynamic_event_triggered":
        actor = "runtime"
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"dynamic_event: {payload.get('event_name', 'event')}"
    elif event_type == "stop_condition_triggered":
        actor = "runtime"
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"stop_condition: {payload.get('type', 'condition')}"
    elif event_type == "error":
        actor = "runtime"
        turn = safe_int(payload.get("turn"), default=0)
        summary = f"error: {clip_text(payload.get('message', 'run_error'))}"

    return {
        "step": step,
        "timestamp": timestamp,
        "type": event_type,
        "actor": actor,
        "turn": turn,
        "summary": summary,
        "payload": payload,
    }


def fallback_events_from_run_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    run = payload.get("run", {}) or {}
    transcript = run.get("transcript", []) or []
    tool_calls = run.get("tool_calls", []) or []
    gate_decisions = run.get("gate_decisions", []) or []

    staged: list[tuple[int, int, int, dict[str, Any]]] = []
    seq = 0

    for idx, msg in enumerate(transcript):
        if not isinstance(msg, dict):
            continue
        turn = safe_int(msg.get("turn"), default=idx)
        data = {
            "turn": turn,
            "role": str(msg.get("role", "unknown")),
            "content": str(msg.get("content", "")),
            "source": msg.get("source"),
        }
        if "reasoning_content" in msg:
            data["reasoning_content"] = msg.get("reasoning_content")
        staged.append((turn, 10, seq, {"type": "message", "data": data}))
        seq += 1

    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        turn = safe_int(call.get("turn"), default=0)
        call_data = {
            "turn": turn,
            "name": call.get("name"),
            "arguments": call.get("arguments", {}),
            "executed": call.get("executed"),
            "was_forbidden": call.get("was_forbidden"),
            "gate_decision": call.get("gate_decision"),
        }
        staged.append((turn, 20, seq, {"type": "tool_call", "data": call_data}))
        seq += 1
        if "result" in call:
            result_data = {"turn": turn, "name": call.get("name"), "result": call.get("result")}
            staged.append((turn, 21, seq, {"type": "tool_result", "data": result_data}))
            seq += 1

    for decision in gate_decisions:
        if not isinstance(decision, dict):
            continue
        turn = safe_int(decision.get("turn"), default=0)
        staged.append((turn, 30, seq, {"type": "gate_decision", "data": decision}))
        seq += 1

    staged.sort(key=lambda item: (item[0], item[1], item[2]))
    events: list[dict[str, Any]] = []
    for index, (_, _, _, event) in enumerate(staged, start=1):
        enriched = dict(event)
        enriched["timestamp"] = float(index)
        events.append(enriched)
    return events


def normalize_timeline(payload: dict[str, Any]) -> list[dict[str, Any]]:
    run = payload.get("run", {}) or {}
    setup_visible_context = (
        (run.get("runtime_summary", {}) or {}).get("setup_visible_context")
        if isinstance(run.get("runtime_summary", {}) or {}, dict)
        else ""
    )
    events = run.get("events", []) or []
    if not isinstance(events, list) or not events:
        events = fallback_events_from_run_payload(payload)
    normalized: list[dict[str, Any]] = []
    for idx, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            continue
        normalized.append(normalize_event_for_timeline(event, step=idx))

    if isinstance(setup_visible_context, str) and setup_visible_context.strip():
        has_system_message = any(item.get("type") == "message" and item.get("actor") == "system" for item in normalized)
        if not has_system_message:
            for item in normalized:
                item["step"] = safe_int(item.get("step"), default=0) + 1
            normalized.insert(
                0,
                {
                    "step": 1,
                    "timestamp": 0.0,
                    "type": "message",
                    "actor": "system",
                    "turn": 0,
                    "summary": f"system: {clip_text(setup_visible_context)}",
                    "payload": {"role": "system", "content": setup_visible_context, "source": "setup_visible_context", "turn": 0},
                },
            )
    return normalized

