"""Golden artifact utilities for validating detection expressions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from .checks import evaluate_detection_expression


@dataclass
class GoldenDetectionCase:
    """One detection expectation evaluated against a golden run artifact."""
    name: str
    detection: str
    expect_matched: bool
    expect_applicable: bool | None = None


@dataclass
class GoldenDetectionResult:
    """Result of one golden detection case."""
    case: GoldenDetectionCase
    actual_matched: bool
    actual_applicable: bool
    passed: bool
    details: str
    unsupported_clauses: list[str] | None = None


def load_golden_artifact(path: str | Path) -> Any:
    """Load a minimal run-artifact view from JSON fixture."""
    payload = json.loads(Path(path).read_text())
    transcript = payload.get("transcript") or []
    tool_calls = payload.get("tool_calls") or []
    if not isinstance(transcript, list):
        transcript = []
    if not isinstance(tool_calls, list):
        tool_calls = []
    return SimpleNamespace(transcript=transcript, tool_calls=tool_calls)


def load_golden_cases(path: str | Path) -> list[GoldenDetectionCase]:
    """Load detection expectation cases from YAML or JSON."""
    data: Any
    raw = Path(path).read_text()
    if str(path).lower().endswith(".json"):
        data = json.loads(raw)
    else:
        data = yaml.safe_load(raw)

    if isinstance(data, dict):
        rows = data.get("detections", [])
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    cases: list[GoldenDetectionCase] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        detection = str(row.get("detection", "")).strip()
        if not detection:
            continue
        name = str(row.get("name", f"Case {idx}"))
        expect_matched = bool(row.get("expect_matched", False))
        expect_applicable = row.get("expect_applicable")
        if not isinstance(expect_applicable, bool):
            expect_applicable = None
        cases.append(
            GoldenDetectionCase(
                name=name,
                detection=detection,
                expect_matched=expect_matched,
                expect_applicable=expect_applicable,
            )
        )
    return cases


def evaluate_golden_cases(run_artifact: Any, cases: list[GoldenDetectionCase]) -> list[GoldenDetectionResult]:
    """Evaluate a set of golden detection expectations."""
    results: list[GoldenDetectionResult] = []
    for case in cases:
        clause_result = evaluate_detection_expression(case.detection, run_artifact)
        passed = clause_result.matched == case.expect_matched
        if case.expect_applicable is not None:
            passed = passed and (clause_result.applicable == case.expect_applicable)

        details = (
            f"matched={clause_result.matched} expected={case.expect_matched}; "
            f"applicable={clause_result.applicable}"
        )
        results.append(
            GoldenDetectionResult(
                case=case,
                actual_matched=clause_result.matched,
                actual_applicable=clause_result.applicable,
                passed=passed,
                details=details,
                unsupported_clauses=clause_result.unsupported_clauses,
            )
        )
    return results
