"""Tests for scenario authoring CLI commands."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
