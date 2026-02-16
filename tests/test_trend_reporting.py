"""Tests for trend report markdown generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from argus.reporting.trends import (
    load_trend_entries,
    build_trend_markdown,
    build_drift_summary,
    build_drift_markdown,
)


class TrendReportingTests(unittest.TestCase):
    def test_load_trend_entries_reads_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.jsonl"
            p.write_text(
                "\n".join(
                    [
                        '{"model":"m","summary":{"pass_rate":0.5},"pathway_pass_rate":{"6.1":0.5}}',
                        '{"model":"m","summary":{"pass_rate":0.6},"pathway_pass_rate":{"6.1":0.6}}',
                    ]
                )
            )
            entries = load_trend_entries(p)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[-1]["model"], "m")

    def test_build_trend_markdown_contains_drift_sections(self) -> None:
        model_trends = {
            "model_a": [
                {
                    "model": "openai/model-a",
                    "summary": {
                        "pass_rate": 0.4,
                        "avg_total_severity": 2.0,
                        "cross_trial_anomaly_count": 3,
                        "avg_unsupported_detection_count": 0.0,
                    },
                    "pathway_pass_rate": {"6.1": 0.2, "6.2": 0.8},
                },
                {
                    "model": "openai/model-a",
                    "summary": {
                        "pass_rate": 0.6,
                        "avg_total_severity": 1.0,
                        "cross_trial_anomaly_count": 1,
                        "avg_unsupported_detection_count": 0.0,
                    },
                    "pathway_pass_rate": {"6.1": 0.6, "6.2": 0.7},
                },
            ]
        }
        md = build_trend_markdown(model_trends, window=2, title="T")
        self.assertIn("# T", md)
        self.assertIn("Latest Pass%", md)
        self.assertIn("## Pathway Drift", md)
        self.assertIn("openai/model-a", md)
        self.assertIn("6.1", md)

    def test_build_drift_summary_flags_degradation(self) -> None:
        model_trends = {
            "model_a": [
                {
                    "model": "openai/model-a",
                    "summary": {
                        "pass_rate": 0.80,
                        "avg_total_severity": 1.0,
                        "cross_trial_anomaly_count": 1,
                    },
                },
                {
                    "model": "openai/model-a",
                    "summary": {
                        "pass_rate": 0.60,
                        "avg_total_severity": 1.8,
                        "cross_trial_anomaly_count": 5,
                    },
                },
            ]
        }
        summary = build_drift_summary(
            model_trends,
            window=2,
            pass_drop_alert=0.10,
            severity_increase_alert=0.5,
            anomaly_increase_alert=2.0,
        )
        self.assertEqual(summary["status"], "alert")
        self.assertEqual(len(summary["models"]), 1)
        alerts = summary["models"][0]["alerts"]
        self.assertIn("pass_rate_drop", alerts)
        self.assertIn("severity_increase", alerts)
        self.assertIn("anomaly_increase", alerts)

    def test_build_drift_markdown_contains_table(self) -> None:
        summary = {
            "status": "ok",
            "window": 8,
            "thresholds": {
                "pass_drop_alert": 0.05,
                "severity_increase_alert": 0.5,
                "anomaly_increase_alert": 2.0,
            },
            "models": [
                {
                    "model": "MiniMax-M2.1",
                    "runs_considered": 8,
                    "pass_drop": 0.01,
                    "severity_increase": 0.1,
                    "anomaly_increase": 0.0,
                    "alerts": [],
                }
            ],
        }
        md = build_drift_markdown(summary, title="D")
        self.assertIn("# D", md)
        self.assertIn("Pass Drop", md)
        self.assertIn("MiniMax-M2.1", md)


if __name__ == "__main__":
    unittest.main()
