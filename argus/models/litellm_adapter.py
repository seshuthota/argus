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


def _extract_think_tags(content: str | None) -> tuple[str | None, str | None]:
    """Extract <think>...</think> blocks from content. Returns (think_content, remaining_content)."""
    if not content:
        return None, content
    
    match = re.search(r"<think>(.*?)</think>", content, flags=re.DOTALL)
    if match:
        think_content = match.group(1).strip()
        remaining_content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return think_content, remaining_content
    
    return None, content


def _get_field(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _extract_usage(response: Any) -> dict[str, int]:
    """Extract token usage, including reasoning/cached tokens when present."""
    usage_obj = getattr(response, "usage", None)
    if not usage_obj:
        return {}

    usage: dict[str, int] = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens"):
        value = _get_field(usage_obj, field)
        if isinstance(value, (int, float)):
            usage[field] = int(value)

    completion_details = _get_field(usage_obj, "completion_tokens_details")
    if completion_details:
        value = _get_field(completion_details, "reasoning_tokens")
        if isinstance(value, (int, float)):
            usage["reasoning_tokens"] = int(value)

    prompt_details = _get_field(usage_obj, "prompt_tokens_details")
    if prompt_details:
        value = _get_field(prompt_details, "cached_tokens")
        if isinstance(value, (int, float)):
            usage["cached_tokens"] = int(value)

    return usage


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
                getattr(litellm, "APIError", None),
                getattr(litellm, "RateLimitError", None),
                getattr(litellm, "InternalServerError", None),
                getattr(litellm, "ServiceUnavailableError", None),
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
        if getattr(settings, "timeout_s", None):
            # LiteLLM uses `timeout` (seconds) for request timeout.
            kwargs["timeout"] = float(settings.timeout_s)

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
        usage = _extract_usage(response)

        # Extract reasoning content
        content = message.content
        reasoning_content = getattr(message, "reasoning_content", None)

        if not reasoning_content and content:
            # Fallback: extract <think> tags if native reasoning field is missing
            extracted_think, cleaned_content = _extract_think_tags(content)
            if extracted_think:
                reasoning_content = extracted_think
                content = cleaned_content

        return ModelResponse(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            raw=response,
            usage=usage,
        )
