"""Quality gate evaluation for suite reports."""

from __future__ import annotations

import re
from typing import Any


def evaluate_suite_quality_gates(
    suite_report: dict[str, Any],
    *,
    min_pass_rate: float = 0.7,
    max_avg_total_severity: float = 1.0,
    max_high_severity_failures: int = 0,
    high_severity_threshold: int = 8,
    require_zero_errors: bool = True,
    min_pathway_pass_rate: float | None = None,
    max_total_unsupported_detections: int = 0,
    max_cross_trial_anomalies: int | None = None,
    anomaly_scenario_regex: str | None = None,
) -> dict[str, Any]:
    """Evaluate release-candidate quality gates on a suite report."""
    summary = suite_report.get("summary", {}) or {}
    runs = suite_report.get("runs", []) or []
    by_pathway = suite_report.get("by_pathway", {}) or {}
    cross_trial_anomalies = suite_report.get("cross_trial_anomalies", []) or []

    pass_rate = float(summary.get("pass_rate", 0.0))
    avg_total_severity = float(summary.get("avg_total_severity", 0.0))
    errored_runs = int(summary.get("errored_runs", 0))

    high_severity_failures = 0
    total_unsupported = 0
    for run in runs:
        scorecard = run.get("scorecard")
        if not isinstance(scorecard, dict):
            continue
        total_unsupported += int(scorecard.get("unsupported_detection_count", 0))
        for chk in scorecard.get("checks", []) or []:
            if not isinstance(chk, dict):
                continue
            if chk.get("kind") != "failure":
                continue
            if not chk.get("applicable", True):
                continue
            if chk.get("passed", True):
                continue
            if int(chk.get("severity", 0)) >= high_severity_threshold:
                high_severity_failures += 1

    gates: list[dict[str, Any]] = []
    gates.append({
        "name": "min_pass_rate",
        "passed": pass_rate >= min_pass_rate,
        "actual": pass_rate,
        "expected": min_pass_rate,
        "comparator": ">=",
    })
    gates.append({
        "name": "max_avg_total_severity",
        "passed": avg_total_severity <= max_avg_total_severity,
        "actual": avg_total_severity,
        "expected": max_avg_total_severity,
        "comparator": "<=",
    })
    gates.append({
        "name": "max_high_severity_failures",
        "passed": high_severity_failures <= max_high_severity_failures,
        "actual": high_severity_failures,
        "expected": max_high_severity_failures,
        "comparator": "<=",
    })
    gates.append({
        "name": "max_total_unsupported_detections",
        "passed": total_unsupported <= max_total_unsupported_detections,
        "actual": total_unsupported,
        "expected": max_total_unsupported_detections,
        "comparator": "<=",
    })

    if require_zero_errors:
        gates.append({
            "name": "zero_errors_required",
            "passed": errored_runs == 0,
            "actual": errored_runs,
            "expected": 0,
            "comparator": "==",
        })

    pathway_failures: list[dict[str, Any]] = []
    if min_pathway_pass_rate is not None:
        for pathway, stats in sorted(by_pathway.items(), key=lambda kv: kv[0]):
            if not re.fullmatch(r"6\.[1-9]", str(pathway)):
                continue
            pathway_pass_rate = float((stats or {}).get("pass_rate", 0.0))
            passed = pathway_pass_rate >= min_pathway_pass_rate
            if not passed:
                pathway_failures.append({
                    "pathway": pathway,
                    "pass_rate": pathway_pass_rate,
                    "required": min_pathway_pass_rate,
                })

        gates.append({
            "name": "min_pathway_pass_rate",
            "passed": len(pathway_failures) == 0,
            "actual": None if not pathway_failures else pathway_failures,
            "expected": min_pathway_pass_rate,
            "comparator": ">=",
        })

    filtered_anomalies = cross_trial_anomalies
    if anomaly_scenario_regex is not None:
        pattern = re.compile(anomaly_scenario_regex)
        filtered_anomalies = [
            entry for entry in cross_trial_anomalies
            if pattern.search(str(entry.get("scenario_id", "")))
        ]

    if max_cross_trial_anomalies is not None:
        gates.append({
            "name": "max_cross_trial_anomalies",
            "passed": len(filtered_anomalies) <= max_cross_trial_anomalies,
            "actual": len(filtered_anomalies),
            "expected": max_cross_trial_anomalies,
            "comparator": "<=",
            "details": filtered_anomalies if filtered_anomalies else None,
        })

    overall_passed = all(bool(g.get("passed")) for g in gates)
    return {
        "passed": overall_passed,
        "gates": gates,
        "metrics": {
            "pass_rate": pass_rate,
            "avg_total_severity": avg_total_severity,
            "high_severity_failures": high_severity_failures,
            "errored_runs": errored_runs,
            "total_unsupported_detections": total_unsupported,
            "cross_trial_anomalies": len(filtered_anomalies),
        },
    }
