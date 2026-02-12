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

    def test_human_flagged_checks_can_be_ignored_for_gate_counts(self) -> None:
        suite_report = {
            "summary": {
                "pass_rate": 1.0,
                "avg_total_severity": 0.0,
                "errored_runs": 0,
            },
            "by_pathway": {},
            "runs": [
                {
                    "scorecard": {
                        "unsupported_detection_count": 1,
                        "checks": [
                            {
                                "name": "failure_mode.suspected_false_positive",
                                "kind": "failure",
                                "passed": False,
                                "severity": 9,
                                "applicable": True,
                                "human_flagged_misdetection": True,
                            },
                            {
                                "name": "diagnostic.unsupported_detection_clauses",
                                "kind": "diagnostic",
                                "passed": False,
                                "severity": 0,
                                "applicable": True,
                                "unsupported_clauses": ["failure_mode.suspected_false_positive"],
                            },
                        ],
                    }
                }
            ],
        }

        strict = evaluate_suite_quality_gates(
            suite_report,
            max_high_severity_failures=0,
            max_total_unsupported_detections=0,
            ignore_human_flagged_checks=False,
        )
        self.assertFalse(strict["passed"])

        relaxed = evaluate_suite_quality_gates(
            suite_report,
            max_high_severity_failures=0,
            max_total_unsupported_detections=0,
            ignore_human_flagged_checks=True,
        )
        self.assertTrue(relaxed["passed"])
        self.assertEqual(relaxed["metrics"]["high_severity_failures"], 0)
        self.assertEqual(relaxed["metrics"]["total_unsupported_detections"], 0)
        self.assertEqual(relaxed["metrics"]["human_flagged_misdetections"], 1)

    def test_max_human_flagged_misdetections_gate(self) -> None:
        suite_report = {
            "summary": {
                "pass_rate": 1.0,
                "avg_total_severity": 0.0,
                "errored_runs": 0,
            },
            "by_pathway": {},
            "runs": [
                {
                    "scorecard": {
                        "unsupported_detection_count": 0,
                        "checks": [
                            {"name": "failure_mode.a", "kind": "failure", "passed": True, "severity": 0, "applicable": True, "human_flagged_misdetection": True},
                            {"name": "failure_mode.b", "kind": "failure", "passed": True, "severity": 0, "applicable": True, "human_flagged_misdetection": True},
                        ],
                    }
                }
            ],
        }

        result = evaluate_suite_quality_gates(
            suite_report,
            max_human_flagged_misdetections=1,
        )
        self.assertFalse(result["passed"])
        failed = [g for g in result["gates"] if g["name"] == "max_human_flagged_misdetections"][0]
        self.assertFalse(failed["passed"])
        self.assertEqual(failed["actual"], 2)


if __name__ == "__main__":
    unittest.main()
