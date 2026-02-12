"""Detection macro registry and expression resolution helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

import yaml


MACRO_FILE = Path(__file__).with_name("macros.yaml")
_MACRO_REF_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


@lru_cache(maxsize=1)
def load_detection_macros() -> dict[str, str]:
    """Load detection macros from `macros.yaml`."""
    if not MACRO_FILE.exists():
        return {}

    raw: Any = yaml.safe_load(MACRO_FILE.read_text()) or {}
    if not isinstance(raw, dict):
        return {}

    macros: dict[str, str] = {}
    for key, value in raw.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if not key_text or not value_text:
            continue
        macros[key_text] = value_text
    return macros


def resolve_detection_macros(
    expression: str,
    *,
    macros: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    """
    Resolve `$MACRO_NAME` tokens in a detection expression.

    Returns `(resolved_expression, unknown_macro_names)`.
    """
    macro_map = macros if macros is not None else load_detection_macros()
    unknown: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in macro_map:
            return macro_map[name]
        if name not in unknown:
            unknown.append(name)
        return match.group(0)

    resolved = _MACRO_REF_PATTERN.sub(_replace, expression)
    return resolved, unknown
