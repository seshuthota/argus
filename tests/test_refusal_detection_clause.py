"""Tests for the stable refusal detection clauses."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from argus.evaluators.checks import evaluate_detection_expression


class RefusalClauseTests(unittest.TestCase):
    def test_refusal_language_matches_common_refusal(self) -> None:
        artifact = SimpleNamespace(
            transcript=[{"role": "assistant", "turn": 1, "content": "I can't help with that request."}],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("refusal_language", artifact)
        self.assertTrue(ev.applicable)
        self.assertTrue(ev.matched)

    def test_no_refusal_language_matches_when_no_refusal(self) -> None:
        artifact = SimpleNamespace(
            transcript=[{"role": "assistant", "turn": 1, "content": "Sure, here are the steps."}],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("no_refusal_language", artifact)
        self.assertTrue(ev.applicable)
        self.assertTrue(ev.matched)

    def test_no_refusal_language_fails_when_refusal_present(self) -> None:
        artifact = SimpleNamespace(
            transcript=[{"role": "assistant", "turn": 1, "content": "I will not help with that."}],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("no_refusal_language", artifact)
        self.assertTrue(ev.applicable)
        self.assertFalse(ev.matched)


if __name__ == "__main__":
    unittest.main()

