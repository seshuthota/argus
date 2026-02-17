"""Dynamic plugin loader helpers.

Plugin specs use the format: ``module.submodule:function_name``.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable


def _parse_spec(spec: str) -> tuple[str, str]:
    text = spec.strip()
    if not text or ":" not in text:
        raise ValueError(f"Invalid plugin spec '{spec}'. Expected module:function")
    module_name, fn_name = text.split(":", 1)
    module_name = module_name.strip()
    fn_name = fn_name.strip()
    if not module_name or not fn_name:
        raise ValueError(f"Invalid plugin spec '{spec}'. Expected module:function")
    return module_name, fn_name


@dataclass(frozen=True)
class LoadedPlugin:
    """Loaded plugin callable with original spec metadata."""

    spec: str
    fn: Callable[..., Any]


@lru_cache(maxsize=64)
def load_callable_from_spec(spec: str) -> Callable[..., Any]:
    """Load and cache a callable from one plugin spec string."""
    module_name, fn_name = _parse_spec(spec)
    try:
        module = importlib.import_module(module_name)
    except Exception as err:
        raise ValueError(f"Failed to import plugin module '{module_name}' for spec '{spec}': {err}") from err
    fn = getattr(module, fn_name, None)
    if fn is None or not callable(fn):
        raise ValueError(f"Plugin callable '{fn_name}' not found in module '{module_name}'")
    return fn


def load_plugins_from_specs(specs: str | list[str] | tuple[str, ...]) -> list[LoadedPlugin]:
    """Resolve plugin specs into (spec, callable) pairs."""
    if isinstance(specs, str):
        raw_specs = [s.strip() for s in specs.split(",") if s.strip()]
    else:
        raw_specs = [str(s).strip() for s in specs if str(s).strip()]
    return [LoadedPlugin(spec=spec, fn=load_callable_from_spec(spec)) for spec in raw_specs]


def load_callables_from_specs(specs: str | list[str] | tuple[str, ...]) -> list[Callable[..., Any]]:
    """Resolve a comma-list or list/tuple of plugin specs into callables."""
    return [plugin.fn for plugin in load_plugins_from_specs(specs)]
