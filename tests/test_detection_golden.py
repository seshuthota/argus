"""Unit tests for golden detection utilities and CLI command."""

from __future__ import annotations

from pathlib import Path
import unittest

from click.testing import CliRunner

from argus.cli import cli
from argus.evaluators.golden import load_golden_artifact, load_golden_cases, evaluate_golden_cases


class GoldenDetectionUtilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixtures = Path(__file__).parent / "scenarios" / "fixtures"
        self.artifact_path = self.fixtures / "detection_golden_artifact.json"
        self.cases_path = self.fixtures / "detection_golden_cases.yaml"

    def test_loaders_and_evaluator(self) -> None:
        artifact = load_golden_artifact(self.artifact_path)
        cases = load_golden_cases(self.cases_path)
        results = evaluate_golden_cases(artifact, cases)

        self.assertTrue(len(cases) >= 1)
        self.assertEqual(len(results), len(cases))
        self.assertTrue(all(result.passed for result in results))

    def test_check_detections_cli_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "check-detections",
                "--artifact",
                str(self.artifact_path),
                "--cases",
                str(self.cases_path),
            ],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Summary: passed=", result.output)


if __name__ == "__main__":
    unittest.main()
