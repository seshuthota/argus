"""Argus Scenario Orchestrator — executes scenarios against model adapters."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..env.mock_tools import ToolResult, execute_tool, get_tool_schemas
from ..env.simulated_user import SimulatedUserEngine
from ..evaluators.checks import _evaluate_detection_expression
from ..models.adapter import ModelAdapter, ModelResponse, ModelSettings


@dataclass
class GateDecision:
    """Record of a permission gate check."""

    tool_name: str
    allowed: bool
    reason: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class RunEvent:
    """A single event in the run timeline."""

    type: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class RunArtifact:
    """Complete artifact from a single scenario run."""

    run_id: str
    scenario_id: str
    scenario_version: str
    model: str
    settings: dict[str, Any]
    events: list[RunEvent] = field(default_factory=list)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    gate_decisions: list[GateDecision] = field(default_factory=list)
    runtime_summary: dict[str, Any] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time


class ScenarioRunner:
    """Executes a scenario against a model adapter with permission gates and logging."""

    def __init__(
        self,
        adapter: ModelAdapter,
        settings: ModelSettings,
        max_turns: int = 10,
    ):
        self.adapter = adapter
        self.settings = settings
        self.max_turns = max_turns

    @staticmethod
    def _normalize_message_role(role: str) -> str:
        """
        Map scenario-only message roles to provider-compatible roles.

        `inject` is preserved in transcripts but mapped to `system` for model calls.
        """
        if role == "inject":
            return "system"
        return role

    def _build_runtime_state(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Build forward-compatible runtime state for scenario execution."""
        conversation = scenario.get("conversation", {})
        if not isinstance(conversation, dict):
            conversation = {}

        turn_limit = self.max_turns
        scenario_turn_limit = conversation.get("max_turns")
        if isinstance(scenario_turn_limit, int) and scenario_turn_limit > 0:
            turn_limit = min(turn_limit, scenario_turn_limit)

        tool_budget = scenario.get("tool_budget", 20)
        if not isinstance(tool_budget, int) or tool_budget < 1:
            tool_budget = 20

        knobs = scenario.get("knobs", {})
        if not isinstance(knobs, dict):
            knobs = {}

        dynamic_events = scenario.get("dynamic_events", [])
        if not isinstance(dynamic_events, list):
            dynamic_events = []

        simulated_user_cfg = scenario.get("simulated_user", {})
        if not isinstance(simulated_user_cfg, dict):
            simulated_user_cfg = {}

        stop_conditions = conversation.get("stop_conditions", [])
        if not isinstance(stop_conditions, list):
            stop_conditions = []

        return {
            "allowed_tools": set(scenario.get("allowed_actions", {}).get("tools", [])),
            "forbidden_tools": set(scenario.get("forbidden_actions", {}).get("tools", [])),
            "tool_budget": tool_budget,
            "turn_limit": turn_limit,
            "knobs": dict(knobs),
            "dynamic_events": dynamic_events,
            "dynamic_event_state": {},
            "dynamic_events_triggered": 0,
            "stop_conditions": stop_conditions,
            "flags": set(),
            "terminated": False,
            "termination_reason": None,
            "user_mode": str(conversation.get("user_mode", "scripted")),
            "simulated_user_cfg": simulated_user_cfg,
            "user_turns_emitted": 0,
        }

    @staticmethod
    def _event_name(event: dict[str, Any], index: int) -> str:
        name = str(event.get("name", "")).strip()
        if name:
            return name
        return f"dynamic_event_{index + 1}"

    def _append_message(
        self,
        *,
        messages: list[dict[str, Any]],
        artifact: RunArtifact,
        role: str,
        content: str,
        turn: int,
        source: str,
        extra_transcript: dict[str, Any] | None = None,
    ) -> None:
        """Append a message to model context and transcript/events."""
        model_msg = {"role": self._normalize_message_role(role), "content": content}
        messages.append(model_msg)

        transcript_msg: dict[str, Any] = {
            "role": role,
            "content": content,
            "turn": turn,
            "source": source,
        }
        if extra_transcript:
            transcript_msg.update(extra_transcript)
        artifact.transcript.append(transcript_msg)
        artifact.events.append(RunEvent(type="message", data=transcript_msg))

    def _execute_dynamic_action(
        self,
        *,
        action: dict[str, Any],
        event_name: str,
        runtime: dict[str, Any],
        artifact: RunArtifact,
        messages: list[dict[str, Any]],
        turn: int,
    ) -> None:
        """Execute one dynamic event action against runtime state."""
        action_type = str(action.get("type", "")).strip()
        if action_type == "inject_message":
            role = str(action.get("role", "system"))
            content = str(action.get("content", "")).strip()
            if content:
                self._append_message(
                    messages=messages,
                    artifact=artifact,
                    role=role,
                    content=content,
                    turn=turn,
                    source="dynamic_event",
                    extra_transcript={"event_name": event_name},
                )
            artifact.events.append(
                RunEvent(
                    type="dynamic_action",
                    data={
                        "event_name": event_name,
                        "action": "inject_message",
                        "role": role,
                        "has_content": bool(content),
                        "turn": turn,
                    },
                )
            )
            return

        if action_type == "restrict_tools":
            tool_names = action.get("tool_names", [])
            if not isinstance(tool_names, list):
                tool_names = []
            restricted: list[str] = []
            for name in tool_names:
                tool = str(name).strip()
                if not tool:
                    continue
                runtime["allowed_tools"].discard(tool)
                runtime["forbidden_tools"].add(tool)
                restricted.append(tool)
            artifact.events.append(
                RunEvent(
                    type="dynamic_action",
                    data={
                        "event_name": event_name,
                        "action": "restrict_tools",
                        "restricted_tools": sorted(set(restricted)),
                        "turn": turn,
                    },
                )
            )
            return

        if action_type == "update_knob":
            knob_key = str(action.get("knob_key", "")).strip()
            if knob_key:
                runtime["knobs"][knob_key] = action.get("knob_value")
            artifact.events.append(
                RunEvent(
                    type="dynamic_action",
                    data={
                        "event_name": event_name,
                        "action": "update_knob",
                        "knob_key": knob_key,
                        "knob_value": action.get("knob_value"),
                        "turn": turn,
                    },
                )
            )
            return

        if action_type == "set_flag":
            flag = str(action.get("flag", "")).strip()
            if flag:
                runtime["flags"].add(flag)
            artifact.events.append(
                RunEvent(
                    type="dynamic_action",
                    data={
                        "event_name": event_name,
                        "action": "set_flag",
                        "flag": flag,
                        "turn": turn,
                    },
                )
            )
            return

        if action_type == "terminate_run":
            runtime["terminated"] = True
            runtime["termination_reason"] = str(action.get("reason", "terminated_by_dynamic_event"))
            artifact.events.append(
                RunEvent(
                    type="dynamic_action",
                    data={
                        "event_name": event_name,
                        "action": "terminate_run",
                        "reason": runtime["termination_reason"],
                        "turn": turn,
                    },
                )
            )
            return

        artifact.events.append(
            RunEvent(
                type="runtime_notice",
                data={
                    "status": "unknown_dynamic_action_type",
                    "event_name": event_name,
                    "action_type": action_type,
                    "turn": turn,
                },
            )
        )

    def _apply_dynamic_events(
        self,
        *,
        runtime: dict[str, Any],
        artifact: RunArtifact,
        messages: list[dict[str, Any]],
        turn: int,
    ) -> None:
        """Evaluate and execute dynamic events using existing detection DSL."""
        dynamic_events = runtime["dynamic_events"]
        if not dynamic_events:
            return

        sorted_events = sorted(
            enumerate(dynamic_events),
            key=lambda item: int(item[1].get("priority", 0)),
            reverse=True,
        )

        for idx, event in sorted_events:
            event_name = self._event_name(event, idx)
            mode = str(event.get("mode", "once")).strip().lower()
            fired_count = int(runtime["dynamic_event_state"].get(event_name, 0))
            if mode == "once" and fired_count > 0:
                continue

            trigger = str(event.get("trigger", "")).strip()
            if not trigger:
                continue

            eval_result = _evaluate_detection_expression(trigger, artifact)
            if not (eval_result.applicable and eval_result.matched):
                continue

            runtime["dynamic_event_state"][event_name] = fired_count + 1
            runtime["dynamic_events_triggered"] += 1
            artifact.events.append(
                RunEvent(
                    type="dynamic_event_triggered",
                    data={
                        "event_name": event_name,
                        "trigger": trigger,
                        "turn": turn,
                        "evidence": eval_result.evidence or [],
                    },
                )
            )

            action = event.get("action", {})
            if isinstance(action, dict):
                self._execute_dynamic_action(
                    action=action,
                    event_name=event_name,
                    runtime=runtime,
                    artifact=artifact,
                    messages=messages,
                    turn=turn,
                )

            if runtime["terminated"]:
                break

    def _apply_stop_conditions(
        self,
        *,
        runtime: dict[str, Any],
        artifact: RunArtifact,
        turn: int,
        tool_calls_count: int,
        last_assistant_content: str | None,
    ) -> None:
        """Evaluate scenario stop conditions and terminate when matched."""
        if runtime["terminated"]:
            return
        stop_conditions = runtime.get("stop_conditions", [])
        if not stop_conditions:
            return

        text = (last_assistant_content or "").lower()
        for idx, cond in enumerate(stop_conditions):
            if not isinstance(cond, dict):
                continue
            cond_type = str(cond.get("type", "")).strip()
            value = cond.get("value")
            matched = False

            if cond_type == "assistant_response_contains" and isinstance(value, str):
                matched = value.lower() in text
            elif cond_type == "assistant_response_matches_regex" and isinstance(value, str):
                try:
                    matched = re.search(value, text, flags=re.IGNORECASE | re.DOTALL) is not None
                except re.error:
                    artifact.events.append(
                        RunEvent(
                            type="runtime_notice",
                            data={
                                "status": "invalid_stop_condition_regex",
                                "condition_index": idx,
                                "pattern": value,
                                "turn": turn,
                            },
                        )
                    )
                    continue
            elif cond_type == "tool_call_count_gte" and isinstance(value, int):
                matched = tool_calls_count >= value
            elif cond_type == "turn_count_gte" and isinstance(value, int):
                matched = turn >= value

            if not matched:
                continue

            runtime["terminated"] = True
            runtime["termination_reason"] = f"stop_condition:{cond_type}"
            artifact.events.append(
                RunEvent(
                    type="stop_condition_triggered",
                    data={
                        "condition_index": idx,
                        "type": cond_type,
                        "value": value,
                        "turn": turn,
                        "tool_calls_count": tool_calls_count,
                    },
                )
            )
            return

    def run(self, scenario: dict) -> RunArtifact:
        """Execute a scenario and return the full run artifact."""
        run_id = str(uuid.uuid4())[:8]
        artifact = RunArtifact(
            run_id=run_id,
            scenario_id=scenario["id"],
            scenario_version=scenario["version"],
            model=self.settings.model,
            settings={
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "seed": self.settings.seed,
            },
            start_time=time.time(),
        )

        runtime = self._build_runtime_state(scenario)
        artifact.runtime_summary = {
            "turn_limit": runtime["turn_limit"],
            "tool_budget": runtime["tool_budget"],
            "dynamic_events_loaded": len(runtime["dynamic_events"]),
            "stop_conditions_loaded": len(runtime["stop_conditions"]),
            "conversation_mode": runtime["user_mode"],
        }
        artifact.events.append(RunEvent(type="runtime_config", data=dict(artifact.runtime_summary)))

        simulated_user_engine: SimulatedUserEngine | None = None
        if runtime["user_mode"] == "simulated":
            if runtime["simulated_user_cfg"]:
                simulated_user_engine = SimulatedUserEngine(runtime["simulated_user_cfg"])
            else:
                artifact.events.append(
                    RunEvent(
                        type="runtime_notice",
                        data={
                            "status": "simulated_mode_without_config",
                            "turn": 0,
                        },
                    )
                )

        tool_schemas = get_tool_schemas(scenario)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": scenario["setup"]["visible_context"]},
        ]

        for turn in scenario["prompt_sequence"]:
            self._append_message(
                messages=messages,
                artifact=artifact,
                role=str(turn["role"]),
                content=str(turn["content"]),
                turn=0,
                source="prompt_sequence",
            )

        tool_calls_count = 0
        turns = 0

        while turns < runtime["turn_limit"] and not runtime["terminated"]:
            turns += 1
            try:
                response: ModelResponse = self.adapter.execute_turn(
                    messages=messages,
                    tools=tool_schemas if tool_schemas else None,
                    settings=self.settings,
                )
            except Exception as e:
                artifact.error = f"Model error: {e}"
                artifact.events.append(
                    RunEvent(
                        type="error",
                        data={"error": str(e), "turn": turns},
                    )
                )
                break

            if response.has_tool_calls:
                tool_calls_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [],
                }
                messages.append(tool_calls_msg)

                if response.content:
                    artifact.transcript.append(
                        {
                            "role": "assistant",
                            "content": response.content,
                            "turn": turns,
                        }
                    )
                    artifact.events.append(
                        RunEvent(
                            type="message",
                            data={"role": "assistant", "content": response.content, "turn": turns},
                        )
                    )

                for tc in response.tool_calls:
                    gate_allowed = False
                    gate_reason = "unlisted"
                    is_forbidden = tc.name in runtime["forbidden_tools"]
                    tool_calls_count += 1

                    if tool_calls_count > runtime["tool_budget"]:
                        gate_reason = "tool_budget_exceeded"
                    else:
                        if is_forbidden:
                            gate_reason = "forbidden"
                        elif tc.name in runtime["allowed_tools"]:
                            gate_allowed = True
                            gate_reason = "allowed"
                        else:
                            gate_reason = "unlisted"

                    gate = GateDecision(tool_name=tc.name, allowed=gate_allowed, reason=gate_reason)
                    artifact.gate_decisions.append(gate)
                    artifact.events.append(
                        RunEvent(
                            type="gate_decision",
                            data={
                                "tool": tc.name,
                                "allowed": gate.allowed,
                                "reason": gate.reason,
                                "turn": turns,
                            },
                        )
                    )

                    tool_calls_msg["tool_calls"].append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                    )

                    executed = False
                    if gate.allowed:
                        result: ToolResult = execute_tool(tc.name, tc.arguments)
                        executed = True
                    else:
                        result = ToolResult(
                            name=tc.name,
                            output={"error": f"Tool call blocked by gate: {gate.reason}"},
                            success=False,
                            was_forbidden=is_forbidden,
                        )

                    tc_record = {
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "result": result.output,
                        "was_forbidden": is_forbidden,
                        "executed": executed,
                        "gate_decision": gate.reason,
                        "turn": turns,
                    }
                    artifact.tool_calls.append(tc_record)
                    artifact.events.append(
                        RunEvent(
                            type="tool_call",
                            data={
                                "name": tc.name,
                                "arguments": tc.arguments,
                                "executed": executed,
                                "turn": turns,
                            },
                        )
                    )
                    artifact.events.append(
                        RunEvent(
                            type="tool_result",
                            data={
                                "name": tc.name,
                                "result": result.output,
                                "executed": executed,
                                "turn": turns,
                            },
                        )
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result.output),
                        }
                    )

                self._apply_dynamic_events(
                    runtime=runtime,
                    artifact=artifact,
                    messages=messages,
                    turn=turns,
                )
                self._apply_stop_conditions(
                    runtime=runtime,
                    artifact=artifact,
                    turn=turns,
                    tool_calls_count=tool_calls_count,
                    last_assistant_content=response.content,
                )
                if runtime["terminated"]:
                    break
                continue

            if response.content:
                self._append_message(
                    messages=messages,
                    artifact=artifact,
                    role="assistant",
                    content=response.content,
                    turn=turns,
                    source="model_response",
                )

            self._apply_dynamic_events(
                runtime=runtime,
                artifact=artifact,
                messages=messages,
                turn=turns,
            )
            self._apply_stop_conditions(
                runtime=runtime,
                artifact=artifact,
                turn=turns,
                tool_calls_count=tool_calls_count,
                last_assistant_content=response.content,
            )
            if runtime["terminated"]:
                break

            if simulated_user_engine and response.content and turns < runtime["turn_limit"]:
                sim_reply = simulated_user_engine.generate_reply(
                    assistant_content=response.content,
                    user_turns_emitted=runtime["user_turns_emitted"],
                )
                if sim_reply is not None:
                    runtime["user_turns_emitted"] += 1
                    self._append_message(
                        messages=messages,
                        artifact=artifact,
                        role="user",
                        content=sim_reply.content,
                        turn=turns,
                        source="simulated_user",
                        extra_transcript={
                            "rule_index": sim_reply.rule_index,
                            "rule_when": sim_reply.rule_when,
                        },
                    )
                    artifact.events.append(
                        RunEvent(
                            type="simulated_user_message",
                            data={
                                "turn": turns,
                                "content": sim_reply.content,
                                "rule_index": sim_reply.rule_index,
                            },
                        )
                    )
                    continue

            break

        artifact.runtime_summary.update(
            {
                "dynamic_events_triggered": runtime["dynamic_events_triggered"],
                "termination_reason": runtime["termination_reason"],
                "flags": sorted(runtime["flags"]),
                "effective_allowed_tools": sorted(runtime["allowed_tools"]),
                "effective_forbidden_tools": sorted(runtime["forbidden_tools"]),
                "user_turns_emitted": runtime["user_turns_emitted"],
            }
        )
        artifact.end_time = time.time()
        return artifact
