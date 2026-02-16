"""Tests for deterministic simulated user engine."""

from __future__ import annotations

import unittest

from argus.env.simulated_user import SimulatedUserEngine


class SimulatedUserEngineTests(unittest.TestCase):
    def test_rule_matching_uses_priority_and_once(self) -> None:
        engine = SimulatedUserEngine(
            {
                "mode": "deterministic_template_v1",
                "max_user_turns": 3,
                "default_response": "default",
                "response_rules": [
                    {"when": "budget", "reply": "low-priority", "priority": 1, "once": True},
                    {"when": "budget", "reply": "high-priority", "priority": 3, "once": True},
                ],
            }
        )

        first = engine.generate_reply(assistant_content="What is your budget?", user_turns_emitted=0)
        second = engine.generate_reply(assistant_content="Need budget again?", user_turns_emitted=1)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.content, "high-priority")
        self.assertEqual(second.content, "low-priority")

    def test_default_response_when_no_rule_matches(self) -> None:
        engine = SimulatedUserEngine(
            {
                "mode": "deterministic_template_v1",
                "max_user_turns": 2,
                "default_response": "please continue",
                "response_rules": [{"when": "dates", "reply": "March 1", "priority": 1, "once": True}],
            }
        )
        reply = engine.generate_reply(assistant_content="Need your team size.", user_turns_emitted=0)
        self.assertIsNotNone(reply)
        self.assertEqual(reply.content, "please continue")

    def test_respects_max_user_turns(self) -> None:
        engine = SimulatedUserEngine(
            {
                "mode": "deterministic_template_v1",
                "max_user_turns": 1,
                "default_response": "ok",
            }
        )
        first = engine.generate_reply(assistant_content="hello", user_turns_emitted=0)
        second = engine.generate_reply(assistant_content="hello again", user_turns_emitted=1)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_llm_roleplay_mode_uses_turn_budget_but_not_deterministic_rules(self) -> None:
        engine = SimulatedUserEngine(
            {
                "mode": "llm_roleplay_v1",
                "max_user_turns": 2,
                "default_response": "fallback",
                "response_rules": [{"when": "hello", "reply": "rule"}],
            }
        )
        self.assertTrue(engine.can_respond(0))
        self.assertTrue(engine.can_respond(1))
        self.assertFalse(engine.can_respond(2))
        self.assertIsNone(engine.generate_reply(assistant_content="hello", user_turns_emitted=0))


if __name__ == "__main__":
    unittest.main()
