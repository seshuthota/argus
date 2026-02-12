"""Tests for CLI preflight helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest.mock import patch

from argus.cli import _base_probe_url, _probe_https_endpoint, _run_preflight_for_model


class CLIPreflightHelperTests(unittest.TestCase):
    def test_base_probe_url_appends_openrouter_models(self) -> None:
        self.assertEqual(
            _base_probe_url("https://openrouter.ai/api/v1"),
            "https://openrouter.ai/api/v1/models",
        )
        self.assertEqual(
            _base_probe_url("https://api.minimax.io/v1"),
            "https://api.minimax.io/v1",
        )

    def test_probe_https_treats_http_error_as_reachable(self) -> None:
        error = HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        with patch("argus.cli.urlopen", side_effect=error):
            ok, status, err = _probe_https_endpoint("https://example.com", timeout=1.0)

        self.assertTrue(ok)
        self.assertEqual(status, 404)
        self.assertIn("404", err or "")

    def test_run_preflight_passes_when_all_checks_pass(self) -> None:
        adapter = SimpleNamespace(api_key="abc", api_base="https://openrouter.ai/api/v1")
        with (
            patch("argus.cli._resolve_model_and_adapter", return_value=("openrouter/stepfun/model", adapter)),
            patch("argus.cli._probe_dns", return_value=(True, None)),
            patch("argus.cli._probe_https_endpoint", return_value=(True, 200, None)),
        ):
            result = _run_preflight_for_model(
                model="stepfun/step-3.5-flash:free",
                api_key=None,
                api_base=None,
                timeout=2.0,
            )

        self.assertTrue(result["passed"])
        self.assertEqual(result["probe_url"], "https://openrouter.ai/api/v1/models")
        self.assertEqual(result["http_status"], 200)

    def test_run_preflight_fails_on_dns_error(self) -> None:
        adapter = SimpleNamespace(api_key="abc", api_base="https://api.minimax.io/v1")
        with (
            patch("argus.cli._resolve_model_and_adapter", return_value=("openai/MiniMax-M2.1", adapter)),
            patch("argus.cli._probe_dns", return_value=(False, "[Errno -3] Temporary failure in name resolution")),
        ):
            result = _run_preflight_for_model(
                model="MiniMax-M2.1",
                api_key=None,
                api_base=None,
                timeout=2.0,
            )

        self.assertFalse(result["passed"])
        self.assertFalse(result["dns_ok"])
        self.assertFalse(result["https_ok"])
        self.assertIn("name resolution", result["dns_error"] or "")


if __name__ == "__main__":
    unittest.main()
