"""Tests for report visualization generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from argus.reporting.visualize import (
    generate_matrix_visuals,
    generate_pairwise_visuals,
    generate_suite_visuals,
    generate_trend_visuals,
)


def _suite_payload() -> dict:
    return {
        "suite_id": "abc12345",
        "by_scenario": {
            "S1": {"pass_rate": 1.0, "avg_total_severity": 0.0},
            "S2": {"pass_rate": 0.5, "avg_total_severity": 3.0},
        },
        "by_pathway": {
            "6.1": {"pass_rate": 0.25},
            "6.2": {"pass_rate": 0.75},
        },
        "top_failed_checks": [
            {"name": "failure_mode.one", "severity_sum": 12},
            {"name": "failure_mode.two", "severity_sum": 7},
        ],
    }


def _matrix_payload() -> dict:
    return {
        "models": [
            {
                "input_model": "m-a",
                "resolved_model": "m-a",
                "summary": {"pass_rate": 0.6, "avg_total_severity": 1.2},
            },
            {
                "input_model": "m-b",
                "resolved_model": "m-b",
                "summary": {"pass_rate": 0.4, "avg_total_severity": 2.4},
            },
        ],
        "pairwise": [
            {
                "model_a": "m-a",
                "model_b": "m-b",
                "summary": {"pass_rate_delta_mean_a_minus_b": 0.2},
            }
        ],
    }


def _trend_payload() -> dict[str, list[dict]]:
    return {
        "m-a": [
            {"model": "m-a", "summary": {"pass_rate": 0.4, "avg_total_severity": 2.0}},
            {"model": "m-a", "summary": {"pass_rate": 0.6, "avg_total_severity": 1.0}},
        ],
        "m-b": [
            {"model": "m-b", "summary": {"pass_rate": 0.3, "avg_total_severity": 3.0}},
            {"model": "m-b", "summary": {"pass_rate": 0.5, "avg_total_severity": 2.0}},
        ],
    }


def _pairwise_payload() -> dict:
    return {
        "summary": {
            "pass_rate_delta_mean_a_minus_b": 0.15,
            "avg_severity_delta_mean_a_minus_b": -1.25,
            "mcnemar_stat": 0.3333,
        },
        "by_scenario": [
            {"scenario_id": "S1", "delta_pass_rate_a_minus_b": 1.0},
            {"scenario_id": "S2", "delta_pass_rate_a_minus_b": -1.0},
        ],
    }


class VisualizationReportingTests(unittest.TestCase):
    def test_generate_suite_visuals_writes_non_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            artifacts = generate_suite_visuals(_suite_payload(), output_dir=td)
            self.assertIn("scenario_pass_rate", artifacts)
            self.assertIn("scenario_avg_severity", artifacts)
            self.assertIn("pathway_pass_heatmap", artifacts)
            for _, p in artifacts.items():
                path = Path(p)
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)

    def test_generate_matrix_visuals_writes_non_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            artifacts = generate_matrix_visuals(_matrix_payload(), output_dir=td)
            self.assertIn("model_pass_rate", artifacts)
            self.assertIn("model_avg_severity", artifacts)
            for _, p in artifacts.items():
                path = Path(p)
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)

    def test_generate_trend_visuals_writes_non_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            artifacts = generate_trend_visuals(_trend_payload(), output_dir=td, window=5)
            self.assertIn("trend_pass_rate", artifacts)
            self.assertIn("trend_avg_severity", artifacts)
            idx_path = Path(artifacts["index"])
            self.assertTrue(idx_path.exists())
            data = json.loads(idx_path.read_text())
            self.assertIn("artifacts", data)
            for _, p in artifacts.items():
                path = Path(p)
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)

    def test_generate_pairwise_visuals_writes_non_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            artifacts = generate_pairwise_visuals(_pairwise_payload(), output_dir=td)
            self.assertIn("pairwise_summary_metrics", artifacts)
            self.assertIn("pairwise_scenario_delta_pass_rate", artifacts)
            for _, p in artifacts.items():
                path = Path(p)
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
