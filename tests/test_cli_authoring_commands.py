"""Tests for scenario authoring CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from click.testing import CliRunner

from argus.cli import cli
from argus.schema_validator import validate_scenario_file


class CLIAuthoringCommandTests(unittest.TestCase):
    def test_init_scenario_creates_valid_yaml(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "new_scenario.yaml"
            result = runner.invoke(
                cli,
                [
                    "init-scenario",
                    "--id",
                    "TEST_AUTHORING_001",
                    "--name",
                    "Authoring Test",
                    "--output",
                    str(out_path),
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(out_path.exists())

            scenario, errors = validate_scenario_file(out_path)
            self.assertIsNotNone(scenario)
            self.assertEqual(errors, [])

    def test_init_scenario_refuses_overwrite_without_force(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "duplicate.yaml"
            out_path.write_text("placeholder")

            result = runner.invoke(
                cli,
                [
                    "init-scenario",
                    "--id",
                    "TEST_AUTHORING_002",
                    "--output",
                    str(out_path),
                ],
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Output already exists", result.output)

    def test_explain_command_for_known_field(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["explain", "conversation.stop_conditions"])
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Path: conversation.stop_conditions", result.output)
        self.assertIn("Type: array", result.output)

    def test_explain_command_for_unknown_field(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["explain", "conversation.unknown_field"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown field", result.output)

    def test_annotate_suite_applies_misdetection_flags(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            suite_path = Path(tmp_dir) / "suite.json"
            flags_path = Path(tmp_dir) / "flags.yaml"
            output_path = Path(tmp_dir) / "suite.annotated.json"

            suite_path.write_text(
                json.dumps(
                    {
                        "suite_id": "suite_test",
                        "summary": {},
                        "runs": [
                            {
                                "run_id": "run_1",
                                "scenario_id": "SCENARIO_001",
                                "trial": 1,
                                "scorecard": {
                                    "checks": [
                                        {
                                            "name": "failure_mode.unauthorized_send",
                                            "kind": "failure",
                                            "passed": False,
                                            "severity": 9,
                                            "applicable": True,
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                )
            )
            flags_path.write_text(
                "- run_id: run_1\n"
                "  check_name: failure_mode.unauthorized_send\n"
                "  reason: reviewed false positive\n"
            )

            result = runner.invoke(
                cli,
                [
                    "annotate-suite",
                    "--suite-report",
                    str(suite_path),
                    "--flags",
                    str(flags_path),
                    "--output",
                    str(output_path),
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(output_path.exists())

            annotated = json.loads(output_path.read_text())
            check = annotated["runs"][0]["scorecard"]["checks"][0]
            self.assertTrue(check["human_flagged_misdetection"])
            self.assertEqual(check["human_flag_reason"], "reviewed false positive")
            self.assertEqual(annotated["mis_detections"]["summary"]["flags_applied"], 1)


if __name__ == "__main__":
    unittest.main()
