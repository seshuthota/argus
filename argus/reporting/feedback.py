"""Human feedback utilities for mis-detection annotations on suite reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_misdetection_flags(path: str | Path) -> list[dict[str, Any]]:
    """Load mis-detection flags from YAML or JSON file."""
    p = Path(path)
    raw_text = p.read_text()
    if p.suffix.lower() == ".json":
        data = json.loads(raw_text)
    else:
        data = yaml.safe_load(raw_text)

    rows: list[Any]
    if isinstance(data, dict):
        rows = data.get("flags", [])
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        run_id = row.get("run_id")
        check_name = row.get("check_name")
        scenario_id = row.get("scenario_id")
        trial = row.get("trial")
        reason = str(row.get("reason", "")).strip()
        reviewer = str(row.get("reviewer", "")).strip()

        if not isinstance(check_name, str) or not check_name.strip():
            continue
        valid_run = isinstance(run_id, str) and run_id.strip()
        valid_scenario_trial = isinstance(scenario_id, str) and scenario_id.strip() and isinstance(trial, int) and trial > 0
        if not valid_run and not valid_scenario_trial:
            continue

        normalized.append(
            {
                "id": row.get("id") or f"flag_{idx}",
                "run_id": str(run_id).strip() if valid_run else None,
                "scenario_id": str(scenario_id).strip() if isinstance(scenario_id, str) else None,
                "trial": int(trial) if isinstance(trial, int) else None,
                "check_name": str(check_name).strip(),
                "reason": reason or None,
                "reviewer": reviewer or None,
            }
        )

    return normalized


def apply_misdetection_flags(
    suite_report: dict[str, Any],
    flags: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, int]]:
    """
    Apply mis-detection flags to a suite report and return (report, summary_stats).

    Flag matching supports:
    - exact `run_id` + `check_name`
    - fallback `scenario_id` + `trial` + `check_name`
    """
    applied = 0
    unmatched = 0
    seen_keys: set[tuple[str | None, str | None, int | None, str]] = set()

    runs = suite_report.get("runs", []) or []
    for flag in flags:
        key = (
            flag.get("run_id"),
            flag.get("scenario_id"),
            flag.get("trial"),
            flag.get("check_name"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)

        matched_any = False
        for run in runs:
            run_id = run.get("run_id")
            scenario_id = run.get("scenario_id")
            trial = run.get("trial")
            check_name = flag.get("check_name")

            run_match = isinstance(flag.get("run_id"), str) and run_id == flag.get("run_id")
            scenario_trial_match = (
                isinstance(flag.get("scenario_id"), str)
                and isinstance(flag.get("trial"), int)
                and scenario_id == flag.get("scenario_id")
                and trial == flag.get("trial")
            )
            if not run_match and not scenario_trial_match:
                continue

            scorecard = run.get("scorecard")
            if not isinstance(scorecard, dict):
                continue
            checks = scorecard.get("checks", []) or []
            for check in checks:
                if not isinstance(check, dict):
                    continue
                if check.get("name") != check_name:
                    continue
                check["human_flagged_misdetection"] = True
                if flag.get("reason"):
                    check["human_flag_reason"] = flag["reason"]
                if flag.get("reviewer"):
                    check["human_flag_reviewer"] = flag["reviewer"]
                matched_any = True

        if matched_any:
            applied += 1
        else:
            unmatched += 1

    all_flagged_checks = 0
    for run in runs:
        scorecard = run.get("scorecard")
        if not isinstance(scorecard, dict):
            continue
        flagged = 0
        for check in scorecard.get("checks", []) or []:
            if isinstance(check, dict) and check.get("human_flagged_misdetection"):
                flagged += 1
        scorecard["human_flagged_misdetection_count"] = flagged
        all_flagged_checks += flagged

    feedback_summary = {
        "flags_submitted": len(flags),
        "flags_applied": applied,
        "flags_unmatched": unmatched,
        "flagged_checks_total": all_flagged_checks,
    }
    suite_report["mis_detections"] = {
        "flags": flags,
        "summary": feedback_summary,
    }
    summary = suite_report.get("summary")
    if isinstance(summary, dict):
        summary["human_flagged_misdetection_count"] = all_flagged_checks
    return suite_report, feedback_summary
