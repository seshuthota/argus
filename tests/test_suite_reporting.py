"""Tests for suite-level report aggregation."""

from __future__ import annotations

import json
import tempfile
import unittest

from argus.reporting.suite import build_suite_report, append_suite_trend


class SuiteReportingTests(unittest.TestCase):
    def test_build_suite_report_aggregates_counts_and_scores(self) -> None:
        run_results = [
            {
                "scenario_id": "S1",
                "scenario_path": "scenarios/cases/s1.yaml",
                "trial": 1,
                "seed": 42,
                "run_id": "r1",
                "duration_seconds": 1.2,
                "report_path": "reports/runs/r1.json",
                "error": None,
                "scorecard": {
                    "run_id": "r1",
                    "scenario_id": "S1",
                    "model": "m",
                    "outcome": {"task_success": 5, "harm_or_risk": 0, "constraint_violations": 0},
                    "process": {"permission_discipline": 5, "tool_hygiene": 5},
                    "total_severity": 0,
                    "passed": True,
                    "grade": "A",
                    "checks": [],
                },
            },
            {
                "scenario_id": "S1",
                "scenario_path": "scenarios/cases/s1.yaml",
                "trial": 2,
                "seed": 43,
                "run_id": "r2",
                "duration_seconds": 1.3,
                "report_path": "reports/runs/r2.json",
                "error": None,
                "scorecard": {
                    "run_id": "r2",
                    "scenario_id": "S1",
                    "model": "m",
                    "outcome": {"task_success": 2, "harm_or_risk": 1, "constraint_violations": 1},
                    "process": {"permission_discipline": 2, "tool_hygiene": 2},
                    "total_severity": 3,
                    "passed": False,
                    "grade": "D",
                    "checks": [
                        {
                            "name": "failure_mode.x",
                            "passed": False,
                            "severity": 3,
                            "applicable": True,
                        }
                    ],
                },
            },
            {
                "scenario_id": "S2",
                "scenario_path": "scenarios/cases/s2.yaml",
                "trial": 1,
                "seed": 44,
                "error": "Model timeout",
            },
        ]

        report = build_suite_report(
            run_results,
            model="openai/test-model",
            scenario_files=["scenarios/cases/s1.yaml", "scenarios/cases/s2.yaml"],
            trials=2,
            settings={"temperature": 0.0},
        )

        summary = report["summary"]
        self.assertEqual(summary["requested_runs"], 4)
        self.assertEqual(summary["executed_runs"], 3)
        self.assertEqual(summary["scored_runs"], 2)
        self.assertEqual(summary["errored_runs"], 1)
        self.assertEqual(summary["passed_runs"], 1)
        self.assertAlmostEqual(summary["pass_rate"], 0.5, places=4)
        self.assertEqual(summary["avg_unsupported_detection_count"], 0.0)
        self.assertEqual(summary["cross_trial_anomaly_count"], 0)
        self.assertEqual(summary["grade_distribution"]["A"], 1)
        self.assertEqual(summary["grade_distribution"]["D"], 1)

        by_scenario = report["by_scenario"]
        self.assertEqual(by_scenario["S1"]["runs"], 2)
        self.assertEqual(by_scenario["S1"]["passed_runs"], 1)
        self.assertEqual(by_scenario["S2"]["errored_runs"], 1)

        by_pathway = report["by_pathway"]
        self.assertIn("unmapped", by_pathway)
        self.assertEqual(by_pathway["unmapped"]["runs"], 3)
        self.assertEqual(by_pathway["unmapped"]["passed_runs"], 1)

        self.assertEqual(len(report["top_failed_checks"]), 1)
        self.assertEqual(report["top_failed_checks"][0]["name"], "failure_mode.x")
        self.assertEqual(report["top_failed_checks"][0]["fail_count"], 1)
        self.assertEqual(report["top_failed_checks"][0]["severity_sum"], 3)
        self.assertEqual(report["cross_trial_anomalies"], [])

    def test_build_suite_report_detects_cross_trial_anomaly(self) -> None:
        run_results = [
            {
                "scenario_id": "S_SANDBAG",
                "scenario_path": "scenarios/cases/s.yaml",
                "trial": 1,
                "seed": 1,
                "error": None,
                "scorecard": {
                    "run_id": "a",
                    "scenario_id": "S_SANDBAG",
                    "model": "m",
                    "outcome": {"task_success": 1, "harm_or_risk": 0, "constraint_violations": 0},
                    "process": {"permission_discipline": 2, "tool_hygiene": 2},
                    "total_severity": 0,
                    "unsupported_detection_count": 0,
                    "passed": False,
                    "grade": "B",
                    "checks": [
                        {"name": "failure_mode.x", "kind": "failure", "passed": True, "severity": 0, "applicable": True}
                    ],
                },
            },
            {
                "scenario_id": "S_SANDBAG",
                "scenario_path": "scenarios/cases/s.yaml",
                "trial": 2,
                "seed": 2,
                "error": None,
                "scorecard": {
                    "run_id": "b",
                    "scenario_id": "S_SANDBAG",
                    "model": "m",
                    "outcome": {"task_success": 1, "harm_or_risk": 5, "constraint_violations": 1},
                    "process": {"permission_discipline": 1, "tool_hygiene": 1},
                    "total_severity": 10,
                    "unsupported_detection_count": 0,
                    "passed": False,
                    "grade": "F",
                    "checks": [
                        {"name": "failure_mode.x", "kind": "failure", "passed": False, "severity": 10, "applicable": True}
                    ],
                },
            },
            {
                "scenario_id": "S_SANDBAG",
                "scenario_path": "scenarios/cases/s.yaml",
                "trial": 3,
                "seed": 3,
                "error": None,
                "scorecard": {
                    "run_id": "c",
                    "scenario_id": "S_SANDBAG",
                    "model": "m",
                    "outcome": {"task_success": 1, "harm_or_risk": 0, "constraint_violations": 0},
                    "process": {"permission_discipline": 2, "tool_hygiene": 2},
                    "total_severity": 0,
                    "unsupported_detection_count": 0,
                    "passed": False,
                    "grade": "B",
                    "checks": [
                        {"name": "failure_mode.x", "kind": "failure", "passed": True, "severity": 0, "applicable": True}
                    ],
                },
            },
        ]

        report = build_suite_report(
            run_results,
            model="openai/test-model",
            scenario_files=["scenarios/cases/s.yaml"],
            trials=3,
            settings={"temperature": 0.0},
        )
        self.assertEqual(report["summary"]["cross_trial_anomaly_count"], 1)
        self.assertEqual(len(report["cross_trial_anomalies"]), 1)
        self.assertEqual(report["cross_trial_anomalies"][0]["scenario_id"], "S_SANDBAG")
        self.assertIn("volatile_high_severity", report["cross_trial_anomalies"][0]["flags"])

    def test_append_suite_trend_writes_jsonl_entry(self) -> None:
        report = build_suite_report(
            run_results=[],
            model="openrouter/stepfun/step-3.5-flash:free",
            scenario_files=[],
            trials=1,
            settings={"temperature": 0.0},
        )

        with tempfile.TemporaryDirectory() as td:
            trend_path = append_suite_trend(report, trends_dir=td)
            self.assertTrue(trend_path.exists())

            lines = trend_path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["suite_id"], report["suite_id"])
            self.assertEqual(entry["model"], "openrouter/stepfun/step-3.5-flash:free")
            self.assertIn("cross_trial_anomaly_count", entry["summary"])


if __name__ == "__main__":
    unittest.main()
