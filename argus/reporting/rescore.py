"""Rescoring utilities for existing run reports.

This lets us recompute scorecards for historical runs after scenario YAML changes
without rerunning the model. It reuses the deterministic evaluator + scoring
engine on the stored transcript/tool_calls.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ..evaluators.checks import run_all_checks
from ..scoring.engine import compute_scores
from ..schema_validator import load_scenario


@dataclass(frozen=True)
class RescoreResult:
    run_id: str
    scenario_id: str
    skipped: bool
    changed: bool
    previous: dict[str, Any] | None
    current: dict[str, Any]
    report_path: Path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_scenario_path(*, scenario_id: str, reports_root: str | Path) -> Path | None:
    """Resolve scenario YAML path for a scenario_id."""
    if not scenario_id:
        return None
    file_name = f"{scenario_id.lower()}.yaml"
    candidates = [
        Path(reports_root).parent / "scenarios" / "cases" / file_name,
        Path(reports_root).parent / "scenarios" / "archive" / "cases" / file_name,
        Path("scenarios") / "cases" / file_name,
        Path("scenarios") / "archive" / "cases" / file_name,
    ]
    for path in candidates:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def _build_artifact_view_from_report(report: dict[str, Any]) -> Any:
    """Create a lightweight RunArtifact-like object for evaluator/scorer."""
    run = report.get("run", {}) or {}
    run_id = str(run.get("run_id") or (report.get("scorecard", {}) or {}).get("run_id") or "")
    model = str(run.get("model") or (report.get("scorecard", {}) or {}).get("model") or "unknown")
    transcript = run.get("transcript", []) or []
    tool_calls = run.get("tool_calls", []) or []
    return SimpleNamespace(
        run_id=run_id,
        model=model,
        transcript=transcript if isinstance(transcript, list) else [],
        tool_calls=tool_calls if isinstance(tool_calls, list) else [],
    )


def rescore_run_report(
    *,
    report_path: str | Path,
    reports_root: str | Path,
    reason: str | None = None,
    dry_run: bool = False,
    skip_if_up_to_date: bool = True,
) -> RescoreResult:
    """Rescore a single run report JSON file in-place (unless dry_run)."""
    report_path = Path(report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("run report payload is not a JSON object")

    run = payload.get("run", {}) or {}
    scorecard_prev = payload.get("scorecard", {}) or {}
    run_id = str(run.get("run_id") or scorecard_prev.get("run_id") or report_path.stem)
    scenario_id = str(run.get("scenario_id") or scorecard_prev.get("scenario_id") or "").strip()
    if not scenario_id:
        raise ValueError("missing scenario_id in run report")

    scenario_path = resolve_scenario_path(scenario_id=scenario_id, reports_root=reports_root)
    if scenario_path is None:
        raise FileNotFoundError(f"scenario YAML not found for {scenario_id}")

    scenario_raw_text = scenario_path.read_text(encoding="utf-8")
    scenario_sha256 = _sha256_text(scenario_raw_text)
    scenario = load_scenario(scenario_path)
    if not isinstance(scenario, dict):
        raise ValueError(f"scenario YAML did not parse to a dict: {scenario_path}")

    artifact_view = _build_artifact_view_from_report(payload)
    check_results = run_all_checks(artifact_view, scenario)
    scorecard = compute_scores(artifact_view, check_results, scenario)
    scorecard_dict = scorecard.to_dict()

    rescoring_prev = payload.get("rescoring", {}) or {}
    prev_sha = rescoring_prev.get("scenario_sha256") if isinstance(rescoring_prev, dict) else None
    skipped = False
    if skip_if_up_to_date and isinstance(prev_sha, str) and prev_sha == scenario_sha256:
        if isinstance(scorecard_prev, dict) and scorecard_prev == scorecard_dict:
            skipped = True

    changed = (
        bool(scorecard_prev.get("passed")) != bool(scorecard_dict.get("passed"))
        or str(scorecard_prev.get("grade")) != str(scorecard_dict.get("grade"))
        or int(scorecard_prev.get("total_severity", 0)) != int(scorecard_dict.get("total_severity", 0))
    )

    now_iso = datetime.now().isoformat(timespec="seconds")
    rescoring_meta = {
        "last_rescored_at": now_iso,
        "reason": reason or "",
        "scenario_id": scenario_id,
        "scenario_version_used": str(scenario.get("version") or ""),
        "scenario_path": str(scenario_path),
        "scenario_sha256": scenario_sha256,
        "changed": changed,
        "skipped": skipped,
    }

    if dry_run:
        return RescoreResult(
            run_id=run_id,
            scenario_id=scenario_id,
            skipped=skipped,
            changed=changed,
            previous=scorecard_prev if isinstance(scorecard_prev, dict) else None,
            current=scorecard_dict,
            report_path=report_path,
        )

    if skipped:
        return RescoreResult(
            run_id=run_id,
            scenario_id=scenario_id,
            skipped=True,
            changed=False,
            previous=scorecard_prev if isinstance(scorecard_prev, dict) else None,
            current=scorecard_dict,
            report_path=report_path,
        )

    history = payload.get("scorecard_history")
    if not isinstance(history, list):
        history = []
    # Only append history when the scorecard actually changes.
    if isinstance(scorecard_prev, dict) and scorecard_prev and scorecard_prev != scorecard_dict:
        history.append(
            {
                "replaced_at": now_iso,
                "reason": reason or "",
                "scorecard": scorecard_prev,
            }
        )
    payload["scorecard_history"] = history
    payload["scorecard"] = scorecard_dict
    payload["rescoring"] = rescoring_meta

    # Atomic-ish write: write into same directory then replace.
    tmp_dir = str(report_path.parent)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=tmp_dir, delete=False) as tf:
        json.dump(payload, tf, indent=2, ensure_ascii=True)
        tmp_name = tf.name
    Path(tmp_name).replace(report_path)

    return RescoreResult(
        run_id=run_id,
        scenario_id=scenario_id,
        skipped=False,
        changed=changed,
        previous=scorecard_prev if isinstance(scorecard_prev, dict) else None,
        current=scorecard_dict,
        report_path=report_path,
    )
