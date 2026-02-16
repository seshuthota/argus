"""Tests for model/evaluator plugin extension points."""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from argus.evaluators.checks import run_all_checks
from argus.models.resolve import ResolveResult, resolve_model_and_adapter


class PluginHookTests(unittest.TestCase):
    def test_model_resolver_plugin_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plugin_path = Path(td) / "resolver_plugin.py"
            plugin_path.write_text(
                textwrap.dedent(
                    """
                    from argus.models.resolve import ResolveResult
                    from argus.models.litellm_adapter import LiteLLMAdapter

                    def custom_resolver(*, model, api_key=None, api_base=None):
                        return ResolveResult(
                            resolved_model=f"plugin/{model}",
                            adapter=LiteLLMAdapter(api_key="k", api_base="https://example.invalid"),
                            provider_note="plugin",
                        )
                    """
                )
            )
            sys.path.insert(0, td)
            try:
                with patch.dict(os.environ, {"ARGUS_MODEL_RESOLVER_PLUGIN": "resolver_plugin:custom_resolver"}, clear=False):
                    out = resolve_model_and_adapter(model="demo-model")
                self.assertEqual(out.resolved_model, "plugin/demo-model")
                self.assertEqual(out.provider_note, "plugin")
            finally:
                sys.path.remove(td)

    def test_evaluator_plugin_appends_checks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plugin_path = Path(td) / "eval_plugin.py"
            plugin_path.write_text(
                textwrap.dedent(
                    """
                    def add_check(*, run_artifact, scenario, checks):
                        return [{
                            "name": "plugin.synthetic_check",
                            "kind": "diagnostic",
                            "passed": True,
                            "severity": 0,
                            "details": "plugin added",
                            "applicable": True,
                        }]
                    """
                )
            )
            sys.path.insert(0, td)
            try:
                scenario = {
                    "id": "PLUGIN_SCENARIO_001",
                    "failure_modes": [],
                    "success_criteria": [],
                }
                run_artifact = SimpleNamespace(transcript=[], tool_calls=[])
                with patch.dict(os.environ, {"ARGUS_EVALUATOR_PLUGINS": "eval_plugin:add_check"}, clear=False):
                    checks = run_all_checks(run_artifact, scenario)
                names = [c.name for c in checks]
                self.assertIn("plugin.synthetic_check", names)
            finally:
                sys.path.remove(td)


if __name__ == "__main__":
    unittest.main()
