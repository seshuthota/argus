"""Argus Scenario Orchestrator — executes scenarios against model adapters."""

from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..models.adapter import ModelAdapter, ModelSettings, ModelResponse, ToolCall
from ..env.mock_tools import execute_tool, get_tool_schemas, ToolResult


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
    type: str  # 'message', 'tool_call', 'tool_result', 'gate_decision', 'error'
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

        # Build allow/deny sets
        allowed_tools = set(scenario.get("allowed_actions", {}).get("tools", []))
        forbidden_tools = set(scenario.get("forbidden_actions", {}).get("tools", []))
        tool_budget = scenario.get("tool_budget", 20)

        # Get tool schemas for this scenario
        tool_schemas = get_tool_schemas(scenario)

        # Build initial messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": scenario["setup"]["visible_context"]},
        ]

        # Add prompt sequence
        for turn in scenario["prompt_sequence"]:
            msg = {"role": turn["role"], "content": turn["content"]}
            messages.append(msg)
            artifact.transcript.append(msg)
            artifact.events.append(RunEvent(type="message", data=msg))

        # Conversation loop
        tool_calls_count = 0
        turns = 0

        while turns < self.max_turns:
            turns += 1

            try:
                response: ModelResponse = self.adapter.execute_turn(
                    messages=messages,
                    tools=tool_schemas if tool_schemas else None,
                    settings=self.settings,
                )
            except Exception as e:
                artifact.error = f"Model error: {e}"
                artifact.events.append(RunEvent(
                    type="error",
                    data={"error": str(e)},
                ))
                break

            # Process tool calls
            if response.has_tool_calls:
                # Build assistant message with tool calls for the conversation.
                # Keep this as the single assistant message for the turn to avoid
                # duplicate assistant entries in the model context.
                tool_calls_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [],
                }
                messages.append(tool_calls_msg)

                if response.content:
                    assistant_msg = {"role": "assistant", "content": response.content}
                    artifact.transcript.append(assistant_msg)
                    artifact.events.append(RunEvent(type="message", data=assistant_msg))

                for tc in response.tool_calls:
                    gate_allowed = False
                    gate_reason = "unlisted"
                    is_forbidden = tc.name in forbidden_tools

                    tool_calls_count += 1

                    # Check budget
                    if tool_calls_count > tool_budget:
                        gate_reason = "tool_budget_exceeded"
                    else:
                        # Strict allow-list semantics:
                        # - forbidden always blocked
                        # - allowed list entries permitted
                        # - unlisted entries blocked
                        if is_forbidden:
                            gate_reason = "forbidden"
                            gate_allowed = False
                        elif tc.name in allowed_tools:
                            gate_reason = "allowed"
                            gate_allowed = True
                        else:
                            gate_reason = "unlisted"
                            gate_allowed = False

                    gate = GateDecision(
                        tool_name=tc.name,
                        allowed=gate_allowed,
                        reason=gate_reason,
                    )
                    artifact.gate_decisions.append(gate)
                    artifact.events.append(RunEvent(
                        type="gate_decision",
                        data={"tool": tc.name, "allowed": gate.allowed, "reason": gate.reason},
                    ))

                    # Build the assistant tool call record in conversation context.
                    tool_calls_msg["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    })

                    # Execute allowed tools only. Block forbidden/unlisted/budgeted calls.
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

                    # Log the tool call and result
                    tc_record = {
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "result": result.output,
                        "was_forbidden": is_forbidden,
                        "executed": executed,
                        "gate_decision": gate.reason,
                    }
                    artifact.tool_calls.append(tc_record)
                    artifact.events.append(RunEvent(type="tool_call", data={
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "executed": executed,
                    }))
                    artifact.events.append(RunEvent(type="tool_result", data={
                        "name": tc.name,
                        "result": result.output,
                        "executed": executed,
                    }))

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result.output),
                    }
                    messages.append(tool_msg)

                # Continue the loop so the model can respond after tool results
                continue

            # Log the assistant's text response when no tools are called.
            if response.content:
                assistant_msg = {"role": "assistant", "content": response.content}
                messages.append(assistant_msg)
                artifact.transcript.append(assistant_msg)
                artifact.events.append(RunEvent(type="message", data=assistant_msg))

            # No tool calls — model gave a final text response; we're done
            break

        artifact.end_time = time.time()
        return artifact
