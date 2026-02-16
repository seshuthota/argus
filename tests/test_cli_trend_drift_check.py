"""Tests for trend-drift-check CLI command."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from click.testing import CliRunner

from argus.cli import cli


class CLITrendDriftCheckTests(unittest.TestCase):
    def test_trend_drift_check_writes_reports(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            trend_dir = Path(tmp_dir) / "trends"
            trend_dir.mkdir(parents=True, exist_ok=True)
            trend_file = trend_dir / "model_a.jsonl"
            trend_file.write_text(
                "\n".join(
                    [
                        '{"model":"model_a","summary":{"pass_rate":0.60,"avg_total_severity":1.0,"cross_trial_anomaly_count":1}}',
                        '{"model":"model_a","summary":{"pass_rate":0.58,"avg_total_severity":1.1,"cross_trial_anomaly_count":1}}',
                    ]
                )
            )

            out_md = Path(tmp_dir) / "drift.md"
            out_json = Path(tmp_dir) / "drift.json"
            result = runner.invoke(
                cli,
                [
                    "trend-drift-check",
                    "--trend-dir",
                    str(trend_dir),
                    "--window",
                    "2",
                    "--max-pass-drop",
                    "0.10",
                    "--max-severity-increase",
                    "0.5",
                    "--max-anomaly-increase",
                    "2",
                    "--output",
                    str(out_md),
                    "--output-json",
                    str(out_json),
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(out_md.exists())
            self.assertTrue(out_json.exists())
            payload = json.loads(out_json.read_text())
            self.assertEqual(payload.get("status"), "ok")

    def test_trend_drift_check_strict_exits_nonzero_on_alert(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            trend_dir = Path(tmp_dir) / "trends"
            trend_dir.mkdir(parents=True, exist_ok=True)
            trend_file = trend_dir / "model_a.jsonl"
            trend_file.write_text(
                "\n".join(
                    [
                        '{"model":"model_a","summary":{"pass_rate":0.80,"avg_total_severity":1.0,"cross_trial_anomaly_count":1}}',
                        '{"model":"model_a","summary":{"pass_rate":0.50,"avg_total_severity":2.0,"cross_trial_anomaly_count":5}}',
                    ]
                )
            )

            result = runner.invoke(
                cli,
                [
                    "trend-drift-check",
                    "--trend-dir",
                    str(trend_dir),
                    "--window",
                    "2",
                    "--max-pass-drop",
                    "0.05",
                    "--max-severity-increase",
                    "0.5",
                    "--max-anomaly-increase",
                    "2",
                    "--strict",
                ],
            )
            self.assertEqual(result.exit_code, 2, msg=result.output)
            self.assertIn("Drift alerts detected", result.output)


if __name__ == "__main__":
    unittest.main()
