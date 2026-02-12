"""Tests for detection macro resolution and evaluator integration."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from argus.evaluators.checks import run_all_checks
from argus.evaluators.macros import resolve_detection_macros


class DetectionMacroTests(unittest.TestCase):
    def test_resolve_detection_macros_known_and_unknown(self) -> None:
        resolved, unknown = resolve_detection_macros(
            'response matches regex "$KNOWN" AND response contains "$MISSING"',
            macros={"KNOWN": "hello|hi"},
        )
        self.assertIn("hello|hi", resolved)
        self.assertIn("$MISSING", resolved)
        self.assertEqual(unknown, ["MISSING"])

    def test_failure_mode_uses_macro_pattern(self) -> None:
        scenario = {
            "id": "MACRO_SCENARIO_001",
            "failure_modes": [
                {
                    "name": "Refusal cue",
                    "severity": 5,
                    "detection": 'response matches regex "$REFUSAL_RE"',
                }
            ],
        }
        artifact = SimpleNamespace(
            run_id="m1",
            model="test-model",
            tool_calls=[],
            transcript=[{"role": "assistant", "content": "I cannot help with that request."}],
        )

        checks = run_all_checks(artifact, scenario)
        check = next(c for c in checks if c.name == "failure_mode.refusal_cue")
        self.assertFalse(check.passed)
        self.assertEqual(check.severity, 5)

    def test_unknown_macro_emits_unsupported_clause_diagnostic(self) -> None:
        scenario = {
            "id": "MACRO_SCENARIO_002",
            "failure_modes": [
                {
                    "name": "Unknown macro check",
                    "severity": 3,
                    "detection": 'response matches regex "$DOES_NOT_EXIST"',
                }
            ],
        }
        artifact = SimpleNamespace(
            run_id="m2",
            model="test-model",
            tool_calls=[],
            transcript=[{"role": "assistant", "content": "normal answer"}],
        )

        checks = run_all_checks(artifact, scenario)
        diag = next(c for c in checks if c.name == "diagnostic.unsupported_detection_clauses")
        self.assertFalse(diag.passed)
        self.assertIn("$DOES_NOT_EXIST", diag.unsupported_clauses or [])


if __name__ == "__main__":
    unittest.main()
