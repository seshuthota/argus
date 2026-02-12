"""Golden artifact detection tests for scenario authors."""

from __future__ import annotations

from pathlib import Path
import unittest

from argus.evaluators.golden import load_golden_artifact, load_golden_cases, evaluate_golden_cases


class GoldenScenarioDetectionTests(unittest.TestCase):
    def test_detection_cases_match_expected_results(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        artifact = load_golden_artifact(fixtures / "detection_golden_artifact.json")
        cases = load_golden_cases(fixtures / "detection_golden_cases.yaml")

        self.assertGreater(len(cases), 0)
        results = evaluate_golden_cases(artifact, cases)

        failed = [result for result in results if not result.passed]
        if failed:
            details = "\n".join(
                f"{result.case.name}: {result.details} detection={result.case.detection}"
                for result in failed
            )
            self.fail(f"Golden detection cases failed:\n{details}")


if __name__ == "__main__":
    unittest.main()
