"""Tests for human mis-detection feedback annotations."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import yaml

from argus.reporting.feedback import load_misdetection_flags, apply_misdetection_flags


class FeedbackReportingTests(unittest.TestCase):
    def test_load_misdetection_flags_supports_yaml_and_json(self) -> None:
        payload = {
            "flags": [
                {"run_id": "r1", "check_name": "failure_mode.x", "reason": "false positive"},
                {"scenario_id": "S1", "trial": 2, "check_name": "failure_mode.y", "reviewer": "qa"},
                {"check_name": "missing_keys"},
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            yaml_path = Path(td) / "flags.yaml"
            json_path = Path(td) / "flags.json"
            yaml_path.write_text(yaml.safe_dump(payload))
            json_path.write_text(json.dumps(payload))

            yaml_flags = load_misdetection_flags(yaml_path)
            json_flags = load_misdetection_flags(json_path)

        self.assertEqual(len(yaml_flags), 2)
        self.assertEqual(len(json_flags), 2)
        self.assertEqual(yaml_flags[0]["check_name"], "failure_mode.x")
        self.assertEqual(yaml_flags[1]["scenario_id"], "S1")
        self.assertEqual(yaml_flags[1]["trial"], 2)

    def test_apply_misdetection_flags_updates_checks_and_summary(self) -> None:
        suite_report = {
            "summary": {},
            "runs": [
                {
                    "run_id": "run_1",
                    "scenario_id": "S1",
                    "trial": 1,
                    "scorecard": {
                        "checks": [
                            {"name": "failure_mode.x", "kind": "failure", "passed": False, "severity": 9, "applicable": True},
                            {"name": "failure_mode.y", "kind": "failure", "passed": False, "severity": 5, "applicable": True},
                        ]
                    },
                }
            ],
        }
        flags = [
            {"run_id": "run_1", "check_name": "failure_mode.x", "reason": "manual false positive", "reviewer": "alice"},
            {"scenario_id": "S1", "trial": 1, "check_name": "failure_mode.y"},
            {"run_id": "missing_run", "check_name": "failure_mode.z"},
        ]

        annotated, stats = apply_misdetection_flags(suite_report, flags)
        checks = annotated["runs"][0]["scorecard"]["checks"]

        self.assertTrue(checks[0]["human_flagged_misdetection"])
        self.assertEqual(checks[0]["human_flag_reason"], "manual false positive")
        self.assertEqual(checks[0]["human_flag_reviewer"], "alice")
        self.assertTrue(checks[1]["human_flagged_misdetection"])
        self.assertEqual(annotated["runs"][0]["scorecard"]["human_flagged_misdetection_count"], 2)
        self.assertEqual(annotated["summary"]["human_flagged_misdetection_count"], 2)
        self.assertEqual(stats["flags_submitted"], 3)
        self.assertEqual(stats["flags_applied"], 2)
        self.assertEqual(stats["flags_unmatched"], 1)
        self.assertEqual(stats["flagged_checks_total"], 2)


if __name__ == "__main__":
    unittest.main()
