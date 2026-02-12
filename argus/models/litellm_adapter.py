"""LiteLLM-based model adapter — works with OpenAI, Anthropic, Gemini, local models, etc."""

from __future__ import annotations
import json
import re
import time
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
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        retry_backoff_multiplier: float = 2.0,
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.extra_headers = extra_headers or {}
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.retry_backoff_multiplier = max(1.0, float(retry_backoff_multiplier))

    def _is_retryable_error(self, exc: Exception) -> bool:
        message = str(exc).lower()

        non_retry_tokens = (
            "invalid api key",
            "authentication",
            "unauthorized",
            "forbidden",
            "bad request",
            "invalid request",
        )
        if any(token in message for token in non_retry_tokens):
            return False

        retry_tokens = (
            "connection error",
            "name resolution",
            "timeout",
            "timed out",
            "temporarily unavailable",
            "rate limit",
            "too many requests",
            "429",
            "500",
            "502",
            "503",
            "504",
            "internal server error",
        )
        if any(token in message for token in retry_tokens):
            return True

        retryable_types = tuple(
            t
            for t in (
                getattr(litellm, "APIConnectionError", None),
                getattr(litellm, "RateLimitError", None),
                getattr(litellm, "InternalServerError", None),
                getattr(litellm, "Timeout", None),
            )
            if t is not None
        )
        return isinstance(exc, retryable_types) if retryable_types else False

    def execute_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        settings: ModelSettings,
    ) -> ModelResponse:
        """Execute a turn via LiteLLM."""

        model_name = settings.model
        # OpenRouter-owned top-level aliases (e.g., aurora-alpha) need an extra
        # namespace segment with LiteLLM to preserve full model id at provider.
        if model_name == "openrouter/aurora-alpha":
            model_name = "openrouter/openrouter/aurora-alpha"

        kwargs: dict[str, Any] = {
            "model": model_name,
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

        response = None
        for attempt in range(self.max_retries + 1):
            try:
                response = litellm.completion(**kwargs)
                break
            except Exception as exc:
                should_retry = attempt < self.max_retries and self._is_retryable_error(exc)
                if not should_retry:
                    raise
                backoff = self.retry_backoff_seconds * (self.retry_backoff_multiplier ** attempt)
                if backoff > 0:
                    time.sleep(backoff)

        if response is None:
            raise RuntimeError("No response returned from LiteLLM completion call.")

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
