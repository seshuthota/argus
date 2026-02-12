"""LiteLLM-based model adapter — works with OpenAI, Anthropic, Gemini, local models, etc."""

from __future__ import annotations
import json
import re
import litellm
from .adapter import ModelAdapter, ModelResponse, ModelSettings, ToolCall
from typing import Any


# Suppress litellm's noisy logging
litellm.suppress_debug_info = True


def _strip_think_tags(content: str | None) -> str | None:
    """Strip <think>...</think> blocks from MiniMax M2.1 responses."""
    if not content:
        return content
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


class LiteLLMAdapter:
    """Adapter that uses LiteLLM to call any supported LLM provider."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.extra_headers = extra_headers or {}

    def execute_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        settings: ModelSettings,
    ) -> ModelResponse:
        """Execute a turn via LiteLLM."""

        kwargs: dict[str, Any] = {
            "model": settings.model,
            "messages": messages,
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
        }

        if settings.seed is not None:
            kwargs["seed"] = settings.seed

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = litellm.completion(**kwargs)

        # Extract the response
        choice = response.choices[0]
        message = choice.message

        # Normalize tool calls
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(ToolCall(
                    id=tc.id or f"call_{len(tool_calls)}",
                    name=tc.function.name,
                    arguments=args,
                ))

        # Extract usage
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        return ModelResponse(
            content=_strip_think_tags(message.content),
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            raw=response,
            usage=usage,
        )
