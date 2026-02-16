from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from ..rescore import resolve_scenario_path
from ...evaluators.checks import CheckResult


def load_env() -> None:
    # Keep behavior consistent with the legacy explorer which loaded .env on startup.
    load_dotenv()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def fmt_ts(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:
        return "n/a"


def parse_iso_ts(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = str(path.parent)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=tmp_dir, delete=False) as tf:
        json.dump(payload, tf, indent=2, ensure_ascii=True)
        tmp_name = tf.name
    Path(tmp_name).replace(path)


def clip_text(value: Any, limit: int = 140) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def get_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value if value else None


def paginate_items(items: list[dict[str, Any]], *, page: int, page_size: int) -> list[dict[str, Any]]:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


def build_check_results_from_scorecard(scorecard: dict[str, Any]) -> list[CheckResult]:
    checks = scorecard.get("checks", []) or []
    if not isinstance(checks, list):
        return []
    results: list[CheckResult] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if not name or not kind:
            continue
        results.append(
            CheckResult(
                name=name,
                kind=kind,
                passed=bool(item.get("passed", False)),
                severity=safe_int(item.get("severity", 0)),
                details=str(item.get("details") or ""),
                applicable=bool(item.get("applicable", True)),
                weight=float(item.get("weight", 1.0) or 1.0),
                evidence=item.get("evidence") if isinstance(item.get("evidence"), list) else None,
                confidence=safe_float(item.get("confidence", 1.0), default=1.0),
                unsupported_clauses=item.get("unsupported_clauses")
                if isinstance(item.get("unsupported_clauses"), list)
                else None,
            )
        )
    return results


def infer_tool_gate_mode(runtime_summary: Any) -> str:
    if isinstance(runtime_summary, dict):
        tool_gate_mode = str(runtime_summary.get("tool_gate_mode") or "").strip()
        if tool_gate_mode:
            return tool_gate_mode
        if bool(runtime_summary.get("allow_forbidden_tools")):
            return "allow_forbidden_tools"
        if bool(runtime_summary.get("terminate_on_blocked_tool_call")):
            return "raw_tools_terminate"
    return "enforce"


def default_matrix_models() -> list[str]:
    raw = (os.getenv("ARGUS_MATRIX_MODELS") or os.getenv("ARGUS_MODELS") or "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return [
        "MiniMax-M2.5",
        "MiniMax-M2.1",
        "stepfun/step-3.5-flash:free",
        "openrouter/aurora-alpha",
    ]


def summarize_run_report_payload(payload: dict[str, Any], *, updated_at: str) -> dict[str, Any]:
    scorecard = payload.get("scorecard", {}) or {}
    run = payload.get("run", {}) or {}
    runtime_summary = run.get("runtime_summary", {}) or {}
    run_id = str(scorecard.get("run_id") or run.get("run_id") or "")
    scenario_id = str(scorecard.get("scenario_id") or run.get("scenario_id") or "unknown")
    model = str(scorecard.get("model") or run.get("model") or "unknown")
    tool_gate_mode = infer_tool_gate_mode(runtime_summary)
    duration_seconds = safe_float(run.get("duration_seconds", 0.0))
    total_severity = safe_int(scorecard.get("total_severity", 0))
    grade = str(scorecard.get("grade") or "?")
    passed = bool(scorecard.get("passed", False))
    checks = scorecard.get("checks", []) if isinstance(scorecard, dict) else []
    checks_total = len(checks) if isinstance(checks, list) else 0
    checks_passed = (
        sum(1 for c in checks if isinstance(c, dict) and c.get("passed") is True) if isinstance(checks, list) else 0
    )
    return {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "model": model,
        "tool_gate_mode": tool_gate_mode,
        "passed": passed,
        "grade": grade,
        "duration_seconds": duration_seconds,
        "total_severity": total_severity,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "updated_at": updated_at,
    }


def read_setup_visible_context_from_scenario_file(scenario_id: str, *, reports_root: str | Path) -> str:
    if not scenario_id or yaml is None:
        return ""

    path = resolve_scenario_path(scenario_id=scenario_id, reports_root=reports_root)
    try:
        if path is None or not path.exists():
            return ""
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return ""
        setup = raw.get("setup", {}) or {}
        if not isinstance(setup, dict):
            return ""
        visible_context = setup.get("visible_context")
        if isinstance(visible_context, str) and visible_context.strip():
            return visible_context
    except Exception:
        return ""
    return ""


def resolve_setup_visible_context(payload: dict[str, Any], *, reports_root: str | Path) -> str:
    run = payload.get("run", {}) or {}
    runtime_summary = run.get("runtime_summary", {}) or {}
    if isinstance(runtime_summary, dict):
        from_summary = runtime_summary.get("setup_visible_context")
        if isinstance(from_summary, str) and from_summary.strip():
            return from_summary

    events = run.get("events", []) or []
    if isinstance(events, list):
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("type", "")) != "setup_context":
                continue
            data = ev.get("data", {}) or {}
            if not isinstance(data, dict):
                continue
            visible_context = data.get("visible_context")
            if isinstance(visible_context, str) and visible_context.strip():
                return visible_context

    transcript = run.get("transcript", []) or []
    if isinstance(transcript, list):
        for msg in transcript:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "")).lower()
            source = str(msg.get("source", "")).lower()
            if role == "system" and source in {"setup_context", "setup", "visible_context"}:
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content

    scorecard = payload.get("scorecard", {}) or {}
    scenario_id = str(run.get("scenario_id") or scorecard.get("scenario_id") or "").strip()
    return read_setup_visible_context_from_scenario_file(scenario_id, reports_root=reports_root)


def ensure_setup_visible_context(payload: dict[str, Any], *, reports_root: str | Path) -> str:
    visible_context = resolve_setup_visible_context(payload, reports_root=reports_root)
    if not visible_context:
        return ""

    run = payload.get("run")
    if not isinstance(run, dict):
        run = {}
        payload["run"] = run
    runtime_summary = run.get("runtime_summary")
    if not isinstance(runtime_summary, dict):
        runtime_summary = {}
        run["runtime_summary"] = runtime_summary
    existing = runtime_summary.get("setup_visible_context")
    if not (isinstance(existing, str) and existing.strip()):
        runtime_summary["setup_visible_context"] = visible_context
    return visible_context


def list_suite_reports(reports_root: str | Path = "reports") -> list[dict[str, Any]]:
    root = Path(reports_root)
    suites_dir = root / "suites"
    if not suites_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(suites_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = load_json(path)
        if payload is None:
            continue
        summary = payload.get("summary", {}) or {}
        suite_id = str(payload.get("suite_id") or path.stem)
        rows.append(
            {
                "suite_id": suite_id,
                "model": str(payload.get("model", "unknown")),
                "pass_rate": safe_float(summary.get("pass_rate", 0.0)),
                "avg_total_severity": safe_float(summary.get("avg_total_severity", 0.0)),
                "executed_runs": safe_int(summary.get("executed_runs", 0)),
                "errored_runs": safe_int(summary.get("errored_runs", 0)),
                "updated_at": fmt_ts(path),
                "path": str(path),
            }
        )
    return rows


def list_run_reports(reports_root: str | Path = "reports") -> list[dict[str, Any]]:
    root = Path(reports_root)
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = load_json(path)
        if payload is None:
            continue
        scorecard = payload.get("scorecard", {}) or {}
        run = payload.get("run", {}) or {}
        runtime_summary = run.get("runtime_summary", {}) or {}
        rescoring = payload.get("rescoring", {}) or {}
        tool_gate_mode = infer_tool_gate_mode(runtime_summary)
        run_id = str(scorecard.get("run_id") or run.get("run_id") or path.stem)
        scenario_version = str(run.get("scenario_version") or "")
        scenario_sha = ""
        if isinstance(rescoring, dict):
            scenario_sha = str(rescoring.get("scenario_sha256") or "").strip()
        rows.append(
            {
                "run_id": run_id,
                "scenario_id": str(scorecard.get("scenario_id") or run.get("scenario_id") or "unknown"),
                "scenario_version": scenario_version,
                "model": str(scorecard.get("model") or run.get("model") or "unknown"),
                "passed": bool(scorecard.get("passed", False)),
                "grade": str(scorecard.get("grade", "?")),
                "total_severity": safe_int(scorecard.get("total_severity", 0)),
                "duration_seconds": safe_float(run.get("duration_seconds", 0.0)),
                "tool_gate_mode": tool_gate_mode or "enforce",
                "scenario_sha256": scenario_sha,
                "updated_at": fmt_ts(path),
                "path": str(path),
            }
        )
    return rows


def query_run_reports(
    reports_root: str | Path = "reports",
    *,
    scenario_id: str | None = None,
    model: str | None = None,
    passed: bool | None = None,
    grade: str | None = None,
    tool_mode: str | None = None,
    latest_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    rows = list_run_reports(reports_root)
    filtered = rows
    if scenario_id is not None:
        sid_lower = scenario_id.lower()
        filtered = [row for row in filtered if sid_lower in str(row.get("scenario_id", "")).lower()]
    if model is not None:
        model_lower = model.lower()
        filtered = [row for row in filtered if model_lower in str(row.get("model", "")).lower()]
    if passed is not None:
        filtered = [row for row in filtered if bool(row.get("passed", False)) == passed]
    if grade is not None:
        grade_upper = grade.upper()
        filtered = [row for row in filtered if str(row.get("grade", "")).upper() == grade_upper]
    if tool_mode is not None:
        tool_mode_norm = tool_mode.strip().lower()
        filtered = [row for row in filtered if str(row.get("tool_gate_mode", "")).strip().lower() == tool_mode_norm]

    if latest_only:
        seen: set[tuple[str, str, str]] = set()
        latest: list[dict[str, Any]] = []
        for row in filtered:
            key = (str(row.get("scenario_id", "")), str(row.get("model", "")), str(row.get("tool_gate_mode", "")))
            if key in seen:
                continue
            seen.add(key)
            latest.append(row)
        filtered = latest

    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 500))
    items = paginate_items(filtered, page=safe_page, page_size=safe_page_size)
    return {
        "items": items,
        "total": len(filtered),
        "page": safe_page,
        "page_size": safe_page_size,
        "filters": {
            "scenario_id": scenario_id,
            "model": model,
            "passed": passed,
            "grade": grade,
            "tool_mode": tool_mode,
            "latest_only": latest_only,
        },
    }


def list_scenarios(reports_root: str | Path = "reports") -> list[dict[str, Any]]:
    scenario_library: dict[str, dict[str, Any]] = {}
    if yaml is not None:
        cases_dir = Path(reports_root).resolve().parent / "scenarios" / "cases"
        if cases_dir.exists():
            for path in sorted(cases_dir.glob("*.yaml")):
                try:
                    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(raw, dict):
                    continue
                scenario_id = str(raw.get("id") or "").strip()
                if not scenario_id:
                    continue
                scenario_library[scenario_id] = {
                    "scenario_id": scenario_id,
                    "name": str(raw.get("name") or "").strip(),
                    "version": str(raw.get("version") or "").strip(),
                    "description": str(raw.get("description") or "").strip(),
                    "interface": str(raw.get("interface") or "").strip(),
                    "stakes": str(raw.get("stakes") or "").strip(),
                    "targets": raw.get("targets") if isinstance(raw.get("targets"), list) else [],
                    "scenario_path": str(path),
                    "scenario_updated_at": fmt_ts(path),
                    "has_yaml": True,
                }

    runs = list_run_reports(reports_root)
    grouped: dict[str, dict[str, Any]] = {}

    for scenario_id, meta in scenario_library.items():
        grouped[scenario_id] = {
            "scenario_id": scenario_id,
            "name": meta.get("name", ""),
            "version": meta.get("version", ""),
            "description": meta.get("description", ""),
            "interface": meta.get("interface", ""),
            "stakes": meta.get("stakes", ""),
            "targets": meta.get("targets", []) or [],
            "scenario_path": meta.get("scenario_path", ""),
            "scenario_updated_at": meta.get("scenario_updated_at", "n/a"),
            "has_yaml": True,
            "run_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "models": set(),
            "latest_updated_at": meta.get("scenario_updated_at", "n/a"),
        }

    for row in runs:
        scenario_id = str(row.get("scenario_id", "unknown"))
        model = str(row.get("model", "unknown"))
        status = bool(row.get("passed", False))
        updated_at = str(row.get("updated_at", "n/a"))

        item = grouped.setdefault(
            scenario_id,
            {
                "scenario_id": scenario_id,
                "name": "",
                "version": "",
                "description": "",
                "interface": "",
                "stakes": "",
                "targets": [],
                "scenario_path": "",
                "scenario_updated_at": "n/a",
                "has_yaml": False,
                "run_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "models": set(),
                "latest_updated_at": updated_at,
            },
        )
        item["run_count"] += 1
        if status:
            item["pass_count"] += 1
        else:
            item["fail_count"] += 1
        item["models"].add(model)
        if updated_at > item["latest_updated_at"]:
            item["latest_updated_at"] = updated_at

    rows: list[dict[str, Any]] = []
    for scenario_id, item in grouped.items():
        run_count = safe_int(item["run_count"])
        pass_count = safe_int(item["pass_count"])
        scenario_updated_at = str(item.get("scenario_updated_at", "n/a"))
        latest_updated_at = str(item.get("latest_updated_at", "n/a"))
        if parse_iso_ts(scenario_updated_at) > parse_iso_ts(latest_updated_at):
            latest_updated_at = scenario_updated_at
        rows.append(
            {
                "scenario_id": scenario_id,
                "name": str(item.get("name") or ""),
                "version": str(item.get("version") or ""),
                "description": str(item.get("description") or ""),
                "interface": str(item.get("interface") or ""),
                "stakes": str(item.get("stakes") or ""),
                "targets": item.get("targets") if isinstance(item.get("targets"), list) else [],
                "scenario_path": str(item.get("scenario_path") or ""),
                "scenario_updated_at": scenario_updated_at,
                "has_yaml": bool(item.get("has_yaml", False)),
                "run_count": run_count,
                "pass_count": pass_count,
                "fail_count": safe_int(item["fail_count"]),
                "pass_rate": round((pass_count / run_count), 4) if run_count else 0.0,
                "models": sorted(item["models"]),
                "latest_updated_at": latest_updated_at,
            }
        )
    rows.sort(key=lambda row: parse_iso_ts(str(row.get("latest_updated_at") or "")), reverse=True)
    return rows


def build_review_queue(
    reports_root: str | Path = "reports",
    *,
    include_passed: bool = False,
    latest_only: bool = True,
    scenario_id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    rows = list_run_reports(reports_root)
    queue: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    seen_latest_keys: set[tuple[str, str]] = set()

    scenario_filter = scenario_id.lower() if isinstance(scenario_id, str) and scenario_id.strip() else None
    model_filter = model.lower() if isinstance(model, str) and model.strip() else None

    for row in rows:
        run_id = str(row.get("run_id", ""))
        scenario_name = str(row.get("scenario_id", "unknown"))
        model_name = str(row.get("model", "unknown"))
        if scenario_filter and scenario_filter not in scenario_name.lower():
            continue
        if model_filter and model_filter not in model_name.lower():
            continue

        key = (scenario_name, model_name)
        if latest_only and key in seen_latest_keys:
            continue

        payload = load_json(Path(str(row.get("path", ""))))
        if payload is None:
            continue

        if latest_only:
            seen_latest_keys.add(key)

        review_status = (payload.get("review", {}) or {}).get("status")
        if review_status == "acknowledged":
            if not include_passed:
                continue

        ensure_setup_visible_context(payload, reports_root=reports_root)
        scorecard = payload.get("scorecard", {}) or {}
        run = payload.get("run", {}) or {}
        checks = scorecard.get("checks", []) or []
        if not isinstance(checks, list):
            checks = []

        has_llm_judge_disagreement = any(
            isinstance(check, dict) and bool(check.get("llm_judge_disagrees", False)) for check in checks
        )

        failed_checks = sum(
            1
            for check in checks
            if isinstance(check, dict) and bool(check.get("applicable", True)) and not bool(check.get("passed", False))
        )
        has_error = bool(run.get("error"))
        events = run.get("events", []) or []
        has_events = isinstance(events, list) and len(events) > 0

        runtime_summary = run.get("runtime_summary", {}) or {}
        has_setup_visible_context = (
            isinstance(runtime_summary, dict)
            and isinstance(runtime_summary.get("setup_visible_context"), str)
            and bool(str(runtime_summary.get("setup_visible_context")).strip())
        )

        reasons: list[str] = []
        passed_val = bool(scorecard.get("passed", False))
        if not passed_val:
            reasons.append("status_fail")
        if failed_checks > 0:
            reasons.append("failed_checks")
        if has_error:
            reasons.append("run_error")
        if not has_events:
            reasons.append("missing_events")
        if not has_setup_visible_context:
            reasons.append("missing_system_prompt")
        if has_llm_judge_disagreement:
            reasons.append("llm_judge_disagreement")

        if not reasons and not include_passed:
            continue

        severity = safe_float(scorecard.get("total_severity", 0.0))
        review_score = (
            int(round(severity * 10))
            + (8 if not passed_val else 0)
            + (failed_checks * 4)
            + (10 if has_error else 0)
            + (2 if not has_events else 0)
            + (1 if not has_setup_visible_context else 0)
        )

        reason_counter.update(reasons)
        queue.append(
            {
                "run_id": run_id,
                "scenario_id": scenario_name,
                "model": model_name,
                "passed": passed_val,
                "grade": str(scorecard.get("grade", "?")),
                "total_severity": severity,
                "failed_checks": failed_checks,
                "duration_seconds": safe_float(run.get("duration_seconds", 0.0)),
                "updated_at": str(row.get("updated_at", "n/a")),
                "review_score": review_score,
                "reasons": reasons,
                "has_error": has_error,
            }
        )

    queue.sort(key=lambda item: (int(item.get("review_score", 0)), str(item.get("updated_at", ""))), reverse=True)
    total_runs = len(rows)
    fail_runs = sum(1 for row in rows if not bool(row.get("passed", False)))
    return {
        "items": queue,
        "summary": {
            "total_runs": total_runs,
            "fail_runs": fail_runs,
            "queue_size": len(queue),
            "reason_counts": dict(reason_counter),
            "latest_only": latest_only,
            "include_passed": include_passed,
        },
    }


def read_scenario_detail(reports_root: str | Path, scenario_id: str) -> dict[str, Any] | None:
    """Return the scenario detail payload used by /api/scenarios/{scenario_id}."""
    if not scenario_id or yaml is None:
        return None
    scenario_path = resolve_scenario_path(scenario_id=str(scenario_id), reports_root=reports_root)
    if scenario_path is None or not scenario_path.exists():
        return None

    try:
        raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    except Exception as err:
        return {"error": "scenario_read_failed", "message": str(err)[:200]}

    if not isinstance(raw, dict):
        return {"error": "scenario_invalid_yaml"}

    setup = raw.get("setup") if isinstance(raw.get("setup"), dict) else {}
    prompt_sequence = raw.get("prompt_sequence") if isinstance(raw.get("prompt_sequence"), list) else []
    success_criteria = raw.get("success_criteria") if isinstance(raw.get("success_criteria"), list) else []
    failure_modes = raw.get("failure_modes") if isinstance(raw.get("failure_modes"), list) else []

    return {
        "scenario_id": str(raw.get("id") or scenario_id),
        "name": str(raw.get("name") or "").strip(),
        "version": str(raw.get("version") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "interface": str(raw.get("interface") or "").strip(),
        "stakes": str(raw.get("stakes") or "").strip(),
        "targets": raw.get("targets") if isinstance(raw.get("targets"), list) else [],
        "knobs": raw.get("knobs") if isinstance(raw.get("knobs"), dict) else {},
        "setup": {
            "visible_context": str(setup.get("visible_context") or ""),
            "hidden_truth": str(setup.get("hidden_truth") or ""),
        },
        "prompt_sequence": [
            {"role": str(t.get("role") or ""), "content": str(t.get("content") or "")}
            for t in prompt_sequence
            if isinstance(t, dict)
        ],
        "counts": {
            "prompt_turns": len(prompt_sequence),
            "success_criteria": len(success_criteria),
            "failure_modes": len(failure_modes),
        },
        "scenario_path": str(scenario_path),
        "scenario_updated_at": fmt_ts(scenario_path),
        "has_yaml": True,
    }
