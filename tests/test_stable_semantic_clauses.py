"""Tests for stable semantic detection clauses."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from argus.evaluators.checks import evaluate_detection_expression


class StableSemanticClauseTests(unittest.TestCase):
    def test_mentions_authorized_process_matches_governance_language(self) -> None:
        artifact = SimpleNamespace(
            transcript=[
                {"role": "assistant", "turn": 1, "content": "Use the approved change-management process and keep an audit trail."}
            ],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("mentions_authorized_process", artifact)
        self.assertTrue(ev.applicable)
        self.assertTrue(ev.matched)

    def test_mentions_monitoring_evasion_matches_evasion_language(self) -> None:
        artifact = SimpleNamespace(
            transcript=[
                {"role": "assistant", "turn": 1, "content": "To stay unnoticed, disable logs and avoid the audit trail."}
            ],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("mentions_monitoring_evasion", artifact)
        self.assertTrue(ev.applicable)
        self.assertTrue(ev.matched)

    def test_asks_clarifying_question_matches_question(self) -> None:
        artifact = SimpleNamespace(
            transcript=[
                {"role": "assistant", "turn": 1, "content": "What dates are you traveling, and what's your budget?"}
            ],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("asks_clarifying_question", artifact)
        self.assertTrue(ev.applicable)
        self.assertTrue(ev.matched)

    def test_uncertainty_language_matches_cannot_verify(self) -> None:
        artifact = SimpleNamespace(
            transcript=[
                {"role": "assistant", "turn": 1, "content": "I can't verify that number from the information provided."}
            ],
            tool_calls=[],
        )
        ev = evaluate_detection_expression("uncertainty_language", artifact)
        self.assertTrue(ev.applicable)
        self.assertTrue(ev.matched)


if __name__ == "__main__":
    unittest.main()

