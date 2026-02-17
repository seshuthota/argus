"""Model + credential resolution shared by CLI and reporting APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..plugins import load_callable_from_spec
from .litellm_adapter import LiteLLMAdapter


@dataclass(frozen=True)
class ResolveResult:
    resolved_model: str
    adapter: LiteLLMAdapter
    provider_note: str | None = None  # e.g. "openrouter" | "minimax"


def resolve_model_and_adapter(
    *,
    model: str,
    api_key: str | None = None,
    api_base: str | None = None,
) -> ResolveResult:
    """
    Resolve provider credentials and return a configured adapter.

    This function does not print or exit; callers should handle errors.
    """
    plugin_spec = os.getenv("ARGUS_MODEL_RESOLVER_PLUGIN", "").strip()
    if plugin_spec:
        plugin = load_callable_from_spec(plugin_spec)
        out = plugin(model=model, api_key=api_key, api_base=api_base)
        if isinstance(out, ResolveResult):
            return out
        if isinstance(out, tuple) and len(out) >= 2:
            resolved_model = str(out[0])
            adapter = out[1]
            provider_note = str(out[2]) if len(out) > 2 and out[2] is not None else None
            return ResolveResult(resolved_model=resolved_model, adapter=adapter, provider_note=provider_note)
        raise ValueError("Model resolver plugin must return ResolveResult or tuple(resolved_model, adapter[, provider_note]).")

    resolved_key = api_key
    resolved_base = api_base or os.getenv("LLM_BASE_URL")
    resolved_model = model
    extra_headers: dict[str, str] = {}
    model_lower = model.lower()

    openrouter_hint = (
        model_lower.startswith("openrouter/")
        or model_lower.endswith(":free")
        or model_lower.startswith("stepfun/")
    )

    provider_note: str | None = None

    if not resolved_key:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        minimax_key = os.getenv("MINIMAX_API_KEY")

        if openrouter_hint and openrouter_key:
            resolved_key = openrouter_key
            resolved_base = resolved_base or "https://openrouter.ai/api/v1"
            if not resolved_model.startswith("openrouter/"):
                resolved_model = f"openrouter/{resolved_model}"
            if os.getenv("OPENROUTER_SITE_URL"):
                extra_headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "")
            if os.getenv("OPENROUTER_APP_NAME"):
                extra_headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "")
            provider_note = "openrouter"
        elif minimax_key:
            resolved_key = minimax_key
            resolved_base = resolved_base or "https://api.minimax.io/v1"
            if not resolved_model.startswith("openai/"):
                resolved_model = f"openai/{resolved_model}"
            provider_note = "minimax"
        elif openrouter_key:
            resolved_key = openrouter_key
            resolved_base = resolved_base or "https://openrouter.ai/api/v1"
            if not resolved_model.startswith("openrouter/"):
                resolved_model = f"openrouter/{resolved_model}"
            if os.getenv("OPENROUTER_SITE_URL"):
                extra_headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "")
            if os.getenv("OPENROUTER_APP_NAME"):
                extra_headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "")
            provider_note = "openrouter"
        elif os.getenv("OPENAI_API_KEY"):
            resolved_key = os.getenv("OPENAI_API_KEY")
            provider_note = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            resolved_key = os.getenv("ANTHROPIC_API_KEY")
            provider_note = "anthropic"
        else:
            raise ValueError("No API key found. Set one in .env (e.g., MINIMAX_API_KEY, OPENROUTER_API_KEY).")
    elif openrouter_hint:
        resolved_base = resolved_base or "https://openrouter.ai/api/v1"
        if not resolved_model.startswith("openrouter/"):
            resolved_model = f"openrouter/{resolved_model}"
        if os.getenv("OPENROUTER_SITE_URL"):
            extra_headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "")
        if os.getenv("OPENROUTER_APP_NAME"):
            extra_headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "")
        provider_note = "openrouter"

    adapter = LiteLLMAdapter(
        api_key=resolved_key,
        api_base=resolved_base,
        extra_headers=extra_headers,
    )
    return ResolveResult(resolved_model=resolved_model, adapter=adapter, provider_note=provider_note)
