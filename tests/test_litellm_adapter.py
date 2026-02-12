"""Tests for LiteLLM adapter retry behavior."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from argus.models.adapter import ModelSettings
from argus.models.litellm_adapter import LiteLLMAdapter


def _fake_completion_response(content: str = "ok") -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    return SimpleNamespace(choices=[choice], usage=usage)


class LiteLLMAdapterRetryTests(unittest.TestCase):
    def test_retries_transient_error_then_succeeds(self) -> None:
        adapter = LiteLLMAdapter(
            api_key="test",
            api_base="https://example.com/v1",
            max_retries=2,
            retry_backoff_seconds=0.1,
            retry_backoff_multiplier=2.0,
        )
        settings = ModelSettings(model="openrouter/foo", temperature=0.0, max_tokens=32, seed=1)

        with (
            patch(
                "argus.models.litellm_adapter.litellm.completion",
                side_effect=[Exception("Connection error"), _fake_completion_response("done")],
            ) as completion_mock,
            patch("argus.models.litellm_adapter.time.sleep") as sleep_mock,
        ):
            response = adapter.execute_turn(messages=[{"role": "user", "content": "hello"}], tools=None, settings=settings)

        self.assertEqual(response.content, "done")
        self.assertEqual(completion_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.1)

    def test_does_not_retry_non_retryable_error(self) -> None:
        adapter = LiteLLMAdapter(
            api_key="test",
            api_base="https://example.com/v1",
            max_retries=3,
            retry_backoff_seconds=0.1,
            retry_backoff_multiplier=2.0,
        )
        settings = ModelSettings(model="openrouter/foo", temperature=0.0, max_tokens=32, seed=1)

        with (
            patch(
                "argus.models.litellm_adapter.litellm.completion",
                side_effect=Exception("Unauthorized: invalid api key"),
            ) as completion_mock,
            patch("argus.models.litellm_adapter.time.sleep") as sleep_mock,
        ):
            with self.assertRaises(Exception):
                adapter.execute_turn(messages=[{"role": "user", "content": "hello"}], tools=None, settings=settings)

        self.assertEqual(completion_mock.call_count, 1)
        sleep_mock.assert_not_called()

    def test_raises_after_retry_budget_exhausted(self) -> None:
        adapter = LiteLLMAdapter(
            api_key="test",
            api_base="https://example.com/v1",
            max_retries=2,
            retry_backoff_seconds=0.1,
            retry_backoff_multiplier=2.0,
        )
        settings = ModelSettings(model="openrouter/foo", temperature=0.0, max_tokens=32, seed=1)

        with (
            patch(
                "argus.models.litellm_adapter.litellm.completion",
                side_effect=[
                    Exception("Temporary timeout"),
                    Exception("Temporary timeout"),
                    Exception("Temporary timeout"),
                ],
            ) as completion_mock,
            patch("argus.models.litellm_adapter.time.sleep") as sleep_mock,
        ):
            with self.assertRaises(Exception):
                adapter.execute_turn(messages=[{"role": "user", "content": "hello"}], tools=None, settings=settings)

        self.assertEqual(completion_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
