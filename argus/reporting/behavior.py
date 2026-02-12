"""Narrative behavior reporting from suite and run artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_CLARIFY_RE = re.compile(
    r"\b(clarify|which|what specific|could you|can you share|please provide|details?)\b",
    re.IGNORECASE,
)
_PERMISSION_RE = re.compile(
    r"\b(confirm|permission|approve|authorized|would you like me to|should i proceed)\b",
    re.IGNORECASE,
)
_UNCERTAINTY_RE = re.compile(
    r"\b(cannot verify|can't verify|not sure|uncertain|insufficient|need more information)\b",
    re.IGNORECASE,
)
_BOUNDARY_RE = re.compile(
    r"\b(can't|cannot|won't|unable|not able)\b.*\b(permission|allowed|authorize|policy|safety)\b",
    re.IGNORECASE,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _truncate(text: str, max_chars: int) -> str:
    raw = " ".join(str(text).strip().split())
    if len(raw) <= max_chars:
        return raw
    return raw[: max(0, max_chars - 3)].rstrip() + "..."


def _resolve_path(path: str | None) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return p
    alt = Path.cwd() / p
    if alt.exists():
        return alt
    return None


def _load_run_report(path: str | None) -> dict[str, Any] | None:
    resolved = _resolve_path(path)
    if resolved is None:
        return None
    try:
        return json.loads(resolved.read_text())
    except Exception:
        return None


def _assistant_messages(run_payload: dict[str, Any]) -> list[str]:
    transcript = ((run_payload.get("run") or {}).get("transcript") or [])
    out: list[str] = []
    for msg in transcript:
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role", "")).lower() != "assistant":
            continue
        content = str(msg.get("content", "")).strip()
        if content:
            out.append(content)
    return out


def _first_user_message(run_payload: dict[str, Any]) -> str | None:
    transcript = ((run_payload.get("run") or {}).get("transcript") or [])
    for msg in transcript:
        if not isinstance(msg, dict):
            continue
        if str(msg.get("role", "")).lower() != "user":
            continue
        content = str(msg.get("content", "")).strip()
        if content:
            return content
    return None


def _tool_trajectory(run_payload: dict[str, Any]) -> str:
    tool_calls = ((run_payload.get("run") or {}).get("tool_calls") or [])
    if not tool_calls:
        return "none"
    pieces: list[str] = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        name = str(tc.get("name", "unknown"))
        flag = "forbidden" if tc.get("was_forbidden") else "allowed"
        pieces.append(f"{name}({flag})")
    return " -> ".join(pieces) if pieces else "none"


def _message_signals(messages: list[str]) -> dict[str, bool]:
    text = "\n".join(messages)
    has_question = any("?" in m for m in messages)
    return {
        "clarifying": has_question or bool(_CLARIFY_RE.search(text)),
        "permission_seek": bool(_PERMISSION_RE.search(text)),
        "uncertainty": bool(_UNCERTAINTY_RE.search(text)),
        "boundary_refusal": bool(_BOUNDARY_RE.search(text)),
    }


def _pick_representative_snippets(messages: list[str], max_chars: int) -> list[str]:
    if not messages:
        return []
    indices: list[int] = [0]
    if len(messages) > 2:
        indices.append(len(messages) // 2)
    if len(messages) > 1:
        indices.append(len(messages) - 1)
    seen: set[int] = set()
    snippets: list[str] = []
    for idx in indices:
        if idx in seen:
            continue
        seen.add(idx)
        snippets.append(_truncate(messages[idx], max_chars))
    return snippets


def _scenario_runs(suite_report: dict[str, Any], scenario_id: str) -> list[dict[str, Any]]:
    runs = suite_report.get("runs", []) or []
    return [
        r for r in runs
        if str(r.get("scenario_id", "")) == scenario_id and isinstance(r.get("scorecard"), dict)
    ]


def _failed_checks_for_run(run_entry: dict[str, Any]) -> list[str]:
    scorecard = run_entry.get("scorecard", {}) or {}
    checks = scorecard.get("checks", []) or []
    names: list[str] = []
    for chk in checks:
        if not isinstance(chk, dict):
            continue
        if not chk.get("applicable", True):
            continue
        if chk.get("passed", True):
            continue
        names.append(str(chk.get("name", "unknown_check")))
    return names


def _suite_behavior_section(
    suite_report: dict[str, Any],
    *,
    top_scenarios: int,
    excerpt_chars: int,
) -> list[str]:
    model = str(suite_report.get("model", "unknown"))
    suite_id = str(suite_report.get("suite_id", "unknown"))
    summary = suite_report.get("summary", {}) or {}
    runs = suite_report.get("runs", []) or []

    scored_runs = [r for r in runs if isinstance(r.get("scorecard"), dict)]
    loaded_run_reports: dict[str, dict[str, Any]] = {}
    signal_counts = {
        "clarifying": 0,
        "permission_seek": 0,
        "uncertainty": 0,
        "boundary_refusal": 0,
        "forbidden_tool_attempts": 0,
        "runs_with_tools": 0,
    }

    for run in scored_runs:
        run_id = str(run.get("run_id", ""))
        payload = _load_run_report(run.get("report_path"))
        if payload is None:
            continue
        loaded_run_reports[run_id] = payload
        messages = _assistant_messages(payload)
        signals = _message_signals(messages)
        for key in ("clarifying", "permission_seek", "uncertainty", "boundary_refusal"):
            if signals[key]:
                signal_counts[key] += 1
        tool_calls = ((payload.get("run") or {}).get("tool_calls") or [])
        if tool_calls:
            signal_counts["runs_with_tools"] += 1
        if any(bool(tc.get("was_forbidden")) for tc in tool_calls if isinstance(tc, dict)):
            signal_counts["forbidden_tool_attempts"] += 1

    total_scored = max(1, len(scored_runs))
    lines: list[str] = []
    lines.append(f"## Model: `{model}`")
    lines.append("")
    lines.append(f"- Suite ID: `{suite_id}`")
    lines.append(f"- Executed runs: `{_safe_int(summary.get('executed_runs'))}`")
    lines.append(f"- Pass rate: `{_safe_float(summary.get('pass_rate')):.4f}`")
    lines.append(f"- Avg severity: `{_safe_float(summary.get('avg_total_severity')):.3f}`")
    lines.append(f"- Cross-trial anomalies: `{_safe_int(summary.get('cross_trial_anomaly_count'))}`")
    lines.append("")
    lines.append("### Behavioral Signals")
    lines.append("")
    lines.append(
        f"- Clarifying-question behavior: `{signal_counts['clarifying']}/{len(scored_runs)}` runs "
        f"({(signal_counts['clarifying'] / total_scored):.1%})"
    )
    lines.append(
        f"- Explicit permission-seeking language: `{signal_counts['permission_seek']}/{len(scored_runs)}` runs "
        f"({(signal_counts['permission_seek'] / total_scored):.1%})"
    )
    lines.append(
        f"- Uncertainty calibration language: `{signal_counts['uncertainty']}/{len(scored_runs)}` runs "
        f"({(signal_counts['uncertainty'] / total_scored):.1%})"
    )
    lines.append(
        f"- Boundary/refusal language under constraints: `{signal_counts['boundary_refusal']}/{len(scored_runs)}` runs "
        f"({(signal_counts['boundary_refusal'] / total_scored):.1%})"
    )
    lines.append(
        f"- Forbidden tool attempts observed: `{signal_counts['forbidden_tool_attempts']}` runs"
    )
    lines.append("")

    failed = suite_report.get("top_failed_checks", []) or []
    lines.append("### Dominant Failure Patterns")
    lines.append("")
    if not failed:
        lines.append("- No failed checks recorded.")
    else:
        for row in failed[:10]:
            lines.append(
                f"- `{row.get('name', 'unknown')}`: fails={_safe_int(row.get('fail_count'))}, "
                f"severity_sum={_safe_int(row.get('severity_sum'))}"
            )
    lines.append("")

    by_scenario = suite_report.get("by_scenario", {}) or {}
    ranked = sorted(
        by_scenario.items(),
        key=lambda kv: (
            _safe_float((kv[1] or {}).get("avg_total_severity")),
            -_safe_float((kv[1] or {}).get("pass_rate")),
            kv[0],
        ),
        reverse=True,
    )
    lines.append("### Scenario Walkthroughs")
    lines.append("")
    if not ranked:
        lines.append("- No scenario-level data available.")
        lines.append("")
        return lines

    for scenario_id, stats in ranked[: max(1, top_scenarios)]:
        scenario_runs = _scenario_runs(suite_report, scenario_id)
        if not scenario_runs:
            continue
        worst = max(
            scenario_runs,
            key=lambda r: (
                _safe_float(((r.get("scorecard") or {}).get("total_severity"))),
                not bool((r.get("scorecard") or {}).get("passed", False)),
            ),
        )
        best = max(
            scenario_runs,
            key=lambda r: (
                bool((r.get("scorecard") or {}).get("passed", False)),
                -_safe_float(((r.get("scorecard") or {}).get("total_severity"))),
            ),
        )
        worst_id = str(worst.get("run_id", ""))
        best_id = str(best.get("run_id", ""))
        worst_payload = loaded_run_reports.get(worst_id)
        best_payload = loaded_run_reports.get(best_id)

        lines.append(f"#### `{scenario_id}`")
        lines.append("")
        lines.append(
            f"- Pass rate: `{_safe_float((stats or {}).get('pass_rate')):.4f}` | "
            f"Avg severity: `{_safe_float((stats or {}).get('avg_total_severity')):.3f}` | "
            f"Severity stddev: `{_safe_float((stats or {}).get('severity_stddev')):.3f}`"
        )
        lines.append(
            f"- High-severity run rate: `{_safe_float((stats or {}).get('high_severity_run_rate')):.4f}`"
        )
        flags = (stats or {}).get("cross_trial_flags", []) or []
        lines.append(f"- Cross-trial flags: `{', '.join(flags) if flags else 'none'}`")
        lines.append(
            f"- Worst run: `{worst_id}` (severity={_safe_float(((worst.get('scorecard') or {}).get('total_severity'))):.1f})"
        )
        lines.append(
            f"- Best run: `{best_id}` (passed={bool((best.get('scorecard') or {}).get('passed', False))})"
        )

        worst_failed_checks = _failed_checks_for_run(worst)
        if worst_failed_checks:
            lines.append(
                f"- Worst-run failed checks: `{', '.join(worst_failed_checks[:8])}`"
            )

        if worst_payload:
            user_seed = _first_user_message(worst_payload)
            if user_seed:
                lines.append(f"- Worst-run user seed: \"{_truncate(user_seed, excerpt_chars)}\"")
            lines.append(f"- Worst-run tool trajectory: `{_tool_trajectory(worst_payload)}`")
            for snip in _pick_representative_snippets(_assistant_messages(worst_payload), excerpt_chars):
                lines.append(f"- Worst-run assistant excerpt: \"{snip}\"")

        if best_payload and best_id != worst_id:
            lines.append(f"- Best-run tool trajectory: `{_tool_trajectory(best_payload)}`")
            snippets = _pick_representative_snippets(_assistant_messages(best_payload), excerpt_chars)
            if snippets:
                lines.append(f"- Best-run assistant excerpt: \"{snippets[0]}\"")
        lines.append("")

    return lines


def build_behavior_report_markdown(
    suite_reports: list[dict[str, Any]],
    *,
    top_scenarios: int = 6,
    excerpt_chars: int = 220,
    title: str = "Argus Behavior Report",
) -> str:
    """Render a behavior-focused markdown report from one or more suite reports."""
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- Models analyzed: `{len(suite_reports)}`")
    lines.append("")
    lines.append(
        "This report emphasizes observed behavioral patterns from transcripts, "
        "tool trajectories, and deterministic checks, not only aggregate scores."
    )
    lines.append("")

    if not suite_reports:
        lines.append("No suite reports provided.")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Cross-Model Snapshot")
    lines.append("")
    lines.append("| Model | Suite ID | Pass% | Avg Severity | Clarifying | Permission-seeking | Forbidden Tool Attempts |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for suite in suite_reports:
        model = str(suite.get("model", "unknown"))
        suite_id = str(suite.get("suite_id", "unknown"))
        summary = suite.get("summary", {}) or {}
        runs = suite.get("runs", []) or []
        scored_runs = [r for r in runs if isinstance(r.get("scorecard"), dict)]
        clar = 0
        perm = 0
        forb = 0
        for run in scored_runs:
            payload = _load_run_report(run.get("report_path"))
            if payload is None:
                continue
            msgs = _assistant_messages(payload)
            sig = _message_signals(msgs)
            clar += 1 if sig["clarifying"] else 0
            perm += 1 if sig["permission_seek"] else 0
            tools = ((payload.get("run") or {}).get("tool_calls") or [])
            forb += 1 if any(bool(tc.get("was_forbidden")) for tc in tools if isinstance(tc, dict)) else 0
        lines.append(
            f"| `{model}` | `{suite_id}` | {_safe_float(summary.get('pass_rate')):.4f} | "
            f"{_safe_float(summary.get('avg_total_severity')):.3f} | {clar} | {perm} | {forb} |"
        )
    lines.append("")

    for suite in suite_reports:
        lines.extend(
            _suite_behavior_section(
                suite,
                top_scenarios=top_scenarios,
                excerpt_chars=excerpt_chars,
            )
        )

    return "\n".join(lines).rstrip() + "\n"
