"""Model adapter interface and base types."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Any


@dataclass
class ToolCall:
    """A tool call made by the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelResponse:
    """Normalized response from any model adapter."""
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    raw: Any = None  # provider-specific raw response
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class ModelSettings:
    """Frozen settings for a model run."""
    model: str
    temperature: float = 0.0
    max_tokens: int = 2048
    seed: int | None = 42


class ModelAdapter(Protocol):
    """Protocol for model adapters — any LLM provider must implement this."""

    def execute_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        settings: ModelSettings,
    ) -> ModelResponse:
        """Execute a single turn and return a normalized response."""
        ...
