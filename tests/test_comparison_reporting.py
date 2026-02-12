"""Tests for suite comparison markdown rendering."""

from __future__ import annotations

import unittest

from argus.reporting.comparison import build_suite_comparison_markdown


class ComparisonReportingTests(unittest.TestCase):
    def test_build_suite_comparison_markdown_contains_core_sections(self) -> None:
        report_a = {
            "suite_id": "aaa11111",
            "model": "model/a",
            "summary": {
                "pass_rate": 0.75,
                "passed_runs": 9,
                "executed_runs": 12,
                "avg_task_success": 4.0,
                "avg_harm_or_risk": 0.5,
                "avg_total_severity": 0.8,
                "avg_unsupported_detection_count": 0.0,
                "cross_trial_anomaly_count": 1,
            },
            "by_pathway": {"6.1": {"pass_rate": 0.5, "avg_total_severity": 1.0}},
            "by_scenario": {"S1": {"pass_rate": 0.5}},
        }
        report_b = {
            "suite_id": "bbb22222",
            "model": "model/b",
            "summary": {
                "pass_rate": 0.5,
                "passed_runs": 6,
                "executed_runs": 12,
                "avg_task_success": 3.0,
                "avg_harm_or_risk": 1.0,
                "avg_total_severity": 2.0,
                "avg_unsupported_detection_count": 0.0,
                "cross_trial_anomaly_count": 2,
            },
            "by_pathway": {"6.1": {"pass_rate": 0.0, "avg_total_severity": 3.0}},
            "by_scenario": {"S1": {"pass_rate": 0.0}},
        }
        md = build_suite_comparison_markdown(
            report_a,
            report_b,
            gate_result_a={"passed": True},
            gate_result_b={"passed": False},
            title="T",
        )

        self.assertIn("# T", md)
        self.assertIn("## Summary", md)
        self.assertIn("## Gate Outcome", md)
        self.assertIn("## Pathways", md)
        self.assertIn("## Biggest Pass-Rate Gaps", md)
        self.assertIn("model/a", md)
        self.assertIn("model/b", md)
        self.assertIn("PASS", md)
        self.assertIn("FAIL", md)


if __name__ == "__main__":
    unittest.main()
