"""Tests for model provider resolution in CLI."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from argus.cli import _resolve_model_and_adapter


class CLIProviderResolutionTests(unittest.TestCase):
    def test_stepfun_free_prefers_openrouter_when_both_keys_exist(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "or-test-key",
                "MINIMAX_API_KEY": "mm-test-key",
                "OPENROUTER_SITE_URL": "https://argus.local",
                "OPENROUTER_APP_NAME": "Argus",
            },
            clear=False,
        ):
            resolved_model, adapter = _resolve_model_and_adapter(
                model="stepfun/step-3.5-flash:free",
                api_key=None,
                api_base=None,
            )

        self.assertEqual(resolved_model, "openrouter/stepfun/step-3.5-flash:free")
        self.assertEqual(adapter.api_key, "or-test-key")
        self.assertEqual(adapter.api_base, "https://openrouter.ai/api/v1")
        self.assertEqual(adapter.extra_headers.get("HTTP-Referer"), "https://argus.local")
        self.assertEqual(adapter.extra_headers.get("X-Title"), "Argus")

    def test_minimax_prefixed_to_openai_when_minimax_key_exists(self) -> None:
        with patch.dict(
            os.environ,
            {"MINIMAX_API_KEY": "mm-test-key"},
            clear=False,
        ):
            resolved_model, adapter = _resolve_model_and_adapter(
                model="MiniMax-M2.1",
                api_key=None,
                api_base=None,
            )

        self.assertEqual(resolved_model, "openai/MiniMax-M2.1")
        self.assertEqual(adapter.api_key, "mm-test-key")
        self.assertEqual(adapter.api_base, "https://api.minimax.io/v1")


if __name__ == "__main__":
    unittest.main()
