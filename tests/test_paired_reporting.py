"""Tests for paired benchmark reporting."""

from __future__ import annotations

import unittest

from argus.reporting.paired import build_paired_analysis, build_paired_markdown


def _report(model: str, suite_id: str, runs: list[dict]) -> dict:
    scored = [r for r in runs if not r.get("error")]
    passed = sum(1 for r in scored if r.get("scorecard", {}).get("passed"))
    return {
        "model": model,
        "suite_id": suite_id,
        "summary": {
            "pass_rate": (passed / len(scored)) if scored else 0.0,
            "avg_total_severity": (
                sum(float(r.get("scorecard", {}).get("total_severity", 0.0)) for r in scored) / len(scored)
                if scored else 0.0
            ),
        },
        "runs": runs,
    }


class PairedReportingTests(unittest.TestCase):
    def test_paired_analysis_counts_and_deltas(self) -> None:
        report_a = _report(
            "model-a",
            "suite-a",
            [
                {
                    "scenario_id": "S1",
                    "trial": 1,
                    "seed": 101,
                    "scorecard": {"passed": True, "total_severity": 0},
                },
                {
                    "scenario_id": "S2",
                    "trial": 1,
                    "seed": 102,
                    "scorecard": {"passed": False, "total_severity": 6},
                },
            ],
        )
        report_b = _report(
            "model-b",
            "suite-b",
            [
                {
                    "scenario_id": "S1",
                    "trial": 1,
                    "seed": 101,
                    "scorecard": {"passed": False, "total_severity": 5},
                },
                {
                    "scenario_id": "S2",
                    "trial": 1,
                    "seed": 102,
                    "scorecard": {"passed": False, "total_severity": 4},
                },
            ],
        )

        analysis = build_paired_analysis(report_a, report_b, bootstrap_samples=200)
        summary = analysis["summary"]

        self.assertEqual(summary["paired_runs"], 2)
        self.assertEqual(summary["a_pass_b_fail"], 1)
        self.assertEqual(summary["a_fail_b_pass"], 0)
        self.assertEqual(summary["both_fail"], 1)
        self.assertAlmostEqual(summary["pass_rate_delta_mean_a_minus_b"], 0.5, places=4)
        ci = summary["pass_rate_delta_ci95_a_minus_b"]
        self.assertLessEqual(ci[0], ci[1])
        self.assertEqual(len(analysis["by_scenario"]), 2)

    def test_paired_markdown_renders_expected_sections(self) -> None:
        analysis = {
            "generated_at": "2026-02-12T00:00:00Z",
            "model_a": "model-a",
            "model_b": "model-b",
            "suite_id_a": "suite-a",
            "suite_id_b": "suite-b",
            "summary": {
                "paired_runs": 2,
                "pass_rate_delta_mean_a_minus_b": 0.5,
                "pass_rate_delta_ci95_a_minus_b": [0.0, 1.0],
                "avg_severity_delta_mean_a_minus_b": -1.0,
                "a_pass_b_fail": 1,
                "a_fail_b_pass": 0,
                "mcnemar_stat": 0.25,
            },
            "by_scenario": [
                {
                    "scenario_id": "S1",
                    "paired_runs": 1,
                    "pass_rate_a": 1.0,
                    "pass_rate_b": 0.0,
                    "delta_pass_rate_a_minus_b": 1.0,
                    "avg_severity_a": 0.0,
                    "avg_severity_b": 4.0,
                }
            ],
        }

        md = build_paired_markdown(analysis, title="Test Paired")
        self.assertIn("# Test Paired", md)
        self.assertIn("## Paired Summary", md)
        self.assertIn("## Scenario Deltas", md)
        self.assertIn("`S1`", md)


if __name__ == "__main__":
    unittest.main()

