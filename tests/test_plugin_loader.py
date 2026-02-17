"""Tests for plugin loader helpers."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
import sys

from argus.plugins.loader import load_callable_from_spec, load_plugins_from_specs


class PluginLoaderTests(unittest.TestCase):
    def test_load_plugins_from_specs_includes_spec_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plugin_path = Path(td) / "loader_ok.py"
            plugin_path.write_text(
                textwrap.dedent(
                    """
                    def fn_a():
                        return 1
                    """
                )
            )
            sys.path.insert(0, td)
            try:
                loaded = load_plugins_from_specs("loader_ok:fn_a")
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0].spec, "loader_ok:fn_a")
                self.assertEqual(loaded[0].fn(), 1)
            finally:
                sys.path.remove(td)

    def test_invalid_spec_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            _ = load_callable_from_spec("bad_spec")

    def test_missing_module_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            _ = load_callable_from_spec("no_such_module:fn")


if __name__ == "__main__":
    unittest.main()
