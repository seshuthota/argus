"""Plugin loading utilities for Argus extension points."""

from .loader import LoadedPlugin, load_callable_from_spec, load_callables_from_specs, load_plugins_from_specs

__all__ = ["LoadedPlugin", "load_callable_from_spec", "load_callables_from_specs", "load_plugins_from_specs"]
