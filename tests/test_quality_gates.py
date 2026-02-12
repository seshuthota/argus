"""Tests for suite quality gate evaluation."""

from __future__ import annotations

import unittest

from argus.reporting.gates import evaluate_suite_quality_gates


class QualityGateTests(unittest.TestCase):
    def test_quality_gates_pass_for_clean_report(self) -> None:
        suite_report = {
            "summary": {
                "pass_rate": 0.9,
                "avg_total_severity": 0.2,
                "errored_runs": 0,
            },
            "by_pathway": {
                "6.1": {"pass_rate": 0.8},
                "6.2": {"pass_rate": 0.9},
            },
            "runs": [
                {
                    "scorecard": {
                        "unsupported_detection_count": 0,
                        "checks": [
                            {"kind": "failure", "passed": True, "severity": 0, "applicable": True},
                        ],
                    }
                }
            ],
        }

        result = evaluate_suite_quality_gates(
            suite_report,
            min_pass_rate=0.8,
            max_avg_total_severity=1.0,
            max_high_severity_failures=0,
            min_pathway_pass_rate=0.75,
            max_total_unsupported_detections=0,
        )
        self.assertTrue(result["passed"])

    def test_quality_gates_fail_for_high_severity_and_unsupported(self) -> None:
        suite_report = {
            "summary": {
                "pass_rate": 0.5,
                "avg_total_severity": 2.0,
                "errored_runs": 1,
            },
            "by_pathway": {
                "6.1": {"pass_rate": 0.4},
            },
            "runs": [
                {
                    "scorecard": {
                        "unsupported_detection_count": 2,
                        "checks": [
                            {"kind": "failure", "passed": False, "severity": 9, "applicable": True},
                        ],
                    }
                }
            ],
        }

        result = evaluate_suite_quality_gates(
            suite_report,
            min_pass_rate=0.7,
            max_avg_total_severity=1.0,
            max_high_severity_failures=0,
            min_pathway_pass_rate=0.7,
            max_total_unsupported_detections=0,
        )
        self.assertFalse(result["passed"])
        failed = {g["name"] for g in result["gates"] if not g["passed"]}
        self.assertIn("min_pass_rate", failed)
        self.assertIn("max_avg_total_severity", failed)
        self.assertIn("max_high_severity_failures", failed)
        self.assertIn("zero_errors_required", failed)
        self.assertIn("min_pathway_pass_rate", failed)
        self.assertIn("max_total_unsupported_detections", failed)

    def test_cross_trial_anomaly_gate_can_be_filtered(self) -> None:
        suite_report = {
            "summary": {
                "pass_rate": 0.9,
                "avg_total_severity": 0.1,
                "errored_runs": 0,
            },
            "by_pathway": {},
            "runs": [],
            "cross_trial_anomalies": [
                {"scenario_id": "SAFETY_RD_DIFFUSE_SANDBAGGING_002", "flags": ["persistent_underperformance"]},
                {"scenario_id": "OTHER_SCENARIO", "flags": ["volatile_high_severity"]},
            ],
        }

        result = evaluate_suite_quality_gates(
            suite_report,
            max_cross_trial_anomalies=0,
            anomaly_scenario_regex=r"SAFETY_RD_DIFFUSE_SANDBAGGING_002",
        )
        self.assertFalse(result["passed"])
        failed = [g for g in result["gates"] if g["name"] == "max_cross_trial_anomalies"][0]
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["actual"], 1)
        self.assertEqual(result["metrics"]["cross_trial_anomalies"], 1)


if __name__ == "__main__":
    unittest.main()
