"""Plugin loading utilities for Argus extension points."""

from .loader import load_callable_from_spec, load_callables_from_specs

__all__ = ["load_callable_from_spec", "load_callables_from_specs"]
