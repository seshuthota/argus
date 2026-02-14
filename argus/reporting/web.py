"""Lightweight web UI for browsing Argus run and suite reports."""

from __future__ import annotations

import html
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


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


def _fmt_ts(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:
        return "n/a"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _clip_text(value: Any, limit: int = 140) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _get_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value if value else None


def _paginate_items(items: list[dict[str, Any]], *, page: int, page_size: int) -> list[dict[str, Any]]:
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]


def _normalize_event_for_timeline(event: dict[str, Any], *, step: int) -> dict[str, Any]:
    event_type = str(event.get("type", "unknown"))
    payload = event.get("data", {})
    if not isinstance(payload, dict):
        payload = {"value": payload}
    timestamp = event.get("timestamp")
    actor = "system"
    summary = event_type
    turn: int | None = None

    if event_type == "message":
        role = str(payload.get("role", "unknown"))
        actor = role
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"{role}: {_clip_text(payload.get('content', ''))}"
    elif event_type == "tool_call":
        name = str(payload.get("name", "unknown_tool"))
        actor = "assistant"
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"tool_call: {name}"
    elif event_type == "tool_result":
        name = str(payload.get("name", "unknown_tool"))
        actor = "tool"
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"tool_result: {name}"
    elif event_type == "gate_decision":
        actor = "gate"
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"gate_decision: {payload.get('tool', 'tool')}"
    elif event_type == "model_usage":
        actor = "model"
        turn = _safe_int(payload.get("turn"), default=0)
        usage = payload.get("usage", {}) or {}
        summary = f"model_usage: total_tokens={_safe_int((usage or {}).get('total_tokens', 0))}"
    elif event_type == "dynamic_event_triggered":
        actor = "runtime"
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"dynamic_event: {payload.get('event_name', 'event')}"
    elif event_type == "stop_condition_triggered":
        actor = "runtime"
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"stop_condition: {payload.get('type', 'condition')}"
    elif event_type == "error":
        actor = "runtime"
        turn = _safe_int(payload.get("turn"), default=0)
        summary = f"error: {_clip_text(payload.get('message', 'run_error'))}"

    return {
        "step": step,
        "timestamp": timestamp,
        "type": event_type,
        "actor": actor,
        "turn": turn,
        "summary": summary,
        "payload": payload,
    }


def _normalize_timeline(payload: dict[str, Any]) -> list[dict[str, Any]]:
    run = payload.get("run", {}) or {}
    events = run.get("events", []) or []
    normalized: list[dict[str, Any]] = []
    for idx, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            continue
        normalized.append(_normalize_event_for_timeline(event, step=idx))
    return normalized


def query_run_reports(
    reports_root: str | Path = "reports",
    *,
    scenario_id: str | None = None,
    model: str | None = None,
    passed: bool | None = None,
    grade: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    rows = list_run_reports(reports_root)
    filtered = rows
    if scenario_id is not None:
        filtered = [row for row in filtered if str(row.get("scenario_id", "")) == scenario_id]
    if model is not None:
        filtered = [row for row in filtered if str(row.get("model", "")) == model]
    if passed is not None:
        filtered = [row for row in filtered if bool(row.get("passed", False)) == passed]
    if grade is not None:
        filtered = [row for row in filtered if str(row.get("grade", "")) == grade]

    safe_page = max(1, page)
    safe_page_size = max(1, min(page_size, 500))
    items = _paginate_items(filtered, page=safe_page, page_size=safe_page_size)
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
        },
    }


def list_scenarios(reports_root: str | Path = "reports") -> list[dict[str, Any]]:
    runs = list_run_reports(reports_root)
    grouped: dict[str, dict[str, Any]] = {}
    for row in runs:
        scenario_id = str(row.get("scenario_id", "unknown"))
        model = str(row.get("model", "unknown"))
        status = bool(row.get("passed", False))
        updated_at = str(row.get("updated_at", "n/a"))

        item = grouped.setdefault(
            scenario_id,
            {
                "scenario_id": scenario_id,
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
        run_count = _safe_int(item["run_count"])
        pass_count = _safe_int(item["pass_count"])
        rows.append(
            {
                "scenario_id": scenario_id,
                "run_count": run_count,
                "pass_count": pass_count,
                "fail_count": _safe_int(item["fail_count"]),
                "pass_rate": round((pass_count / run_count), 4) if run_count else 0.0,
                "models": sorted(item["models"]),
                "latest_updated_at": item["latest_updated_at"],
            }
        )
    rows.sort(key=lambda row: row["latest_updated_at"], reverse=True)
    return rows


def list_run_reports(reports_root: str | Path = "reports") -> list[dict[str, Any]]:
    """Load run-report metadata from reports/runs/*.json."""
    root = Path(reports_root)
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = _load_json(path)
        if payload is None:
            continue
        scorecard = payload.get("scorecard", {}) or {}
        run = payload.get("run", {}) or {}
        run_id = str(scorecard.get("run_id") or run.get("run_id") or path.stem)
        rows.append(
            {
                "run_id": run_id,
                "scenario_id": str(scorecard.get("scenario_id") or run.get("scenario_id") or "unknown"),
                "model": str(scorecard.get("model") or run.get("model") or "unknown"),
                "passed": bool(scorecard.get("passed", False)),
                "grade": str(scorecard.get("grade", "?")),
                "total_severity": _safe_int(scorecard.get("total_severity", 0)),
                "duration_seconds": _safe_float(run.get("duration_seconds", 0.0)),
                "updated_at": _fmt_ts(path),
                "path": str(path),
            }
        )
    return rows


def list_suite_reports(reports_root: str | Path = "reports") -> list[dict[str, Any]]:
    """Load suite-report metadata from reports/suites/*.json."""
    root = Path(reports_root)
    suites_dir = root / "suites"
    if not suites_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(suites_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        payload = _load_json(path)
        if payload is None:
            continue
        summary = payload.get("summary", {}) or {}
        suite_id = str(payload.get("suite_id") or path.stem)
        rows.append(
            {
                "suite_id": suite_id,
                "model": str(payload.get("model", "unknown")),
                "pass_rate": _safe_float(summary.get("pass_rate", 0.0)),
                "avg_total_severity": _safe_float(summary.get("avg_total_severity", 0.0)),
                "executed_runs": _safe_int(summary.get("executed_runs", 0)),
                "errored_runs": _safe_int(summary.get("errored_runs", 0)),
                "updated_at": _fmt_ts(path),
                "path": str(path),
            }
        )
    return rows


def _page(title: str, body: str) -> str:
    title_escaped = html.escape(title)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{title_escaped}</title>
  <style>
    :root {{
      --bg: #f8f7f4;
      --panel: #ffffff;
      --text: #1a1f2b;
      --muted: #637083;
      --accent: #0f766e;
      --ok: #166534;
      --bad: #991b1b;
      --line: #dde3ea;
      --mono-bg: #f3f5f8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: linear-gradient(180deg, #f3efe6 0%, var(--bg) 220px); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
    .header {{ margin-bottom: 16px; }}
    .title {{ font-size: 1.7rem; margin: 0 0 6px; }}
    .muted {{ color: var(--muted); font-size: 0.95rem; }}
    .grid {{ display: grid; gap: 14px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px; box-shadow: 0 2px 12px rgba(15,23,42,0.04); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 6px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; }}
    tr:last-child td {{ border-bottom: 0; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }}
    .pill.ok {{ background: #dcfce7; color: var(--ok); }}
    .pill.bad {{ background: #fee2e2; color: var(--bad); }}
    .pill.bad {{ background: #fee2e2; color: var(--bad); }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: var(--mono-bg); border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.84rem; }}
    .reasoning pre {{ background: #eff6ff; border-color: #bfdbfe; color: #1e3a8a; margin-bottom: 8px; }}
    .row {{ margin-bottom: 10px; }}
    .kv {{ display: grid; grid-template-columns: 220px 1fr; gap: 8px; margin-bottom: 6px; }}
    .kv .k {{ color: var(--muted); }}
    .stack > .card {{ margin-bottom: 12px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">{body}</div>
</body>
</html>
"""


def _index_html(reports_root: Path) -> str:
    runs = list_run_reports(reports_root)
    suites = list_suite_reports(reports_root)

    run_rows: list[str] = []
    for row in runs[:200]:
        status = "ok" if row["passed"] else "bad"
        status_label = "PASS" if row["passed"] else "FAIL"
        run_rows.append(
            "<tr>"
            f"<td><a href='/runs/{html.escape(row['run_id'])}'>{html.escape(row['run_id'])}</a></td>"
            f"<td>{html.escape(row['scenario_id'])}</td>"
            f"<td>{html.escape(row['model'])}</td>"
            f"<td><span class='pill {status}'>{status_label}</span></td>"
            f"<td>{html.escape(str(row['grade']))}</td>"
            f"<td>{row['total_severity']}</td>"
            f"<td>{row['duration_seconds']:.2f}s</td>"
            f"<td>{html.escape(row['updated_at'])}</td>"
            "</tr>"
        )

    suite_rows: list[str] = []
    for row in suites[:200]:
        suite_rows.append(
            "<tr>"
            f"<td><a href='/suites/{html.escape(row['suite_id'])}'>{html.escape(row['suite_id'])}</a></td>"
            f"<td>{html.escape(row['model'])}</td>"
            f"<td>{row['pass_rate']:.4f}</td>"
            f"<td>{row['avg_total_severity']:.3f}</td>"
            f"<td>{row['executed_runs']}</td>"
            f"<td>{row['errored_runs']}</td>"
            f"<td>{html.escape(row['updated_at'])}</td>"
            "</tr>"
        )

    body = [
        "<div class='header'>",
        "<h1 class='title'>Argus Report Explorer</h1>",
        f"<div class='muted'>reports_root: <code>{html.escape(str(reports_root))}</code></div>",
        "</div>",
        "<div class='grid'>",
        "<section class='card'>",
        "<h2>Run Reports</h2>",
        "<table><thead><tr><th>Run</th><th>Scenario</th><th>Model</th><th>Status</th><th>Grade</th><th>Severity</th><th>Duration</th><th>Updated</th></tr></thead><tbody>",
        "".join(run_rows) if run_rows else "<tr><td colspan='8' class='muted'>No run reports found.</td></tr>",
        "</tbody></table>",
        "</section>",
        "<section class='card'>",
        "<h2>Suite Reports</h2>",
        "<table><thead><tr><th>Suite</th><th>Model</th><th>Pass Rate</th><th>Avg Severity</th><th>Executed</th><th>Errored</th><th>Updated</th></tr></thead><tbody>",
        "".join(suite_rows) if suite_rows else "<tr><td colspan='7' class='muted'>No suite reports found.</td></tr>",
        "</tbody></table>",
        "</section>",
        "</div>",
    ]
    return _page("Argus Report Explorer", "".join(body))


def _run_html(payload: dict[str, Any], *, run_id: str) -> str:
    scorecard = payload.get("scorecard", {}) or {}
    run = payload.get("run", {}) or {}
    transcript = run.get("transcript", []) or []
    tool_calls = run.get("tool_calls", []) or []
    events = run.get("events", []) or []
    gate_decisions = run.get("gate_decisions", []) or []
    checks = scorecard.get("checks", []) or []
    runtime_summary = run.get("runtime_summary", {}) or {}

    status_ok = bool(scorecard.get("passed", False))
    status_pill = "<span class='pill ok'>PASS</span>" if status_ok else "<span class='pill bad'>FAIL</span>"

    # --- Interaction Timeline ---
    timeline_html = []
    
    # We will reconstruct the timeline from the 'events' list if available, 
    # as it preserves the exact order of messages and tool calls.
    # We filter for relevant event types.
    
    # styles
    timeline_html.append("""
    <style>
        .chat-container { display: flex; flex-direction: column; gap: 16px; max-width: 900px; margin: 0 auto; }
        .chat-bubble { padding: 12px 16px; border-radius: 12px; max-width: 85%; line-height: 1.5; position: relative; }
        .chat-bubble.user { align-self: flex-end; background-color: #e0f2fe; color: #0c4a6e; border-bottom-right-radius: 2px; }
        .chat-bubble.assistant { align-self: flex-start; background-color: #ffffff; border: 1px solid var(--line); border-bottom-left-radius: 2px; }
        .chat-bubble.system { align-self: center; background-color: #f3f4f6; color: #4b5563; font-size: 0.9rem; max-width: 95%; }
        .chat-meta { font-size: 0.75rem; color: var(--muted); margin-bottom: 4px; display: block; }
        .reasoning-block { background-color: #eff6ff; border-left: 3px solid #60a5fa; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px; font-size: 0.9rem; color: #1e3a8a; }
        .reasoning-label { font-weight: 600; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 4px; opacity: 0.8; }
        .tool-card { border: 1px solid var(--line); border-radius: 8px; background: #fff; margin: 8px 0; overflow: hidden; font-size: 0.9rem; }
        .tool-header { background: #f8fafc; padding: 6px 12px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; }
        .tool-name { font-family: monospace; font-weight: 600; color: #0f172a; }
        .tool-body { padding: 8px 12px; background: #fff; }
        .tool-result { border-top: 1px solid var(--line); padding: 8px 12px; background: #f0fdf4; color: #166534; }
        .tool-result.error { background: #fef2f2; color: #991b1b; }
        .details-box { margin-top: 30px; border-top: 1px solid var(--line); padding-top: 20px; }
        details { margin-bottom: 10px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #fff; }
        summary { padding: 10px 14px; background: #f9fafb; cursor: pointer; font-weight: 600; user-select: none; }
        details[open] summary { border-bottom: 1px solid var(--line); }
        .details-content { padding: 14px; }
    </style>
    <div class='chat-container'>
    """)

    for ev in events:
        etype = ev.get("type")
        data = ev.get("data", {})
        
        if etype == "message":
            role = data.get("role")
            content = data.get("content", "")
            turn = data.get("turn")
            reasoning = data.get("reasoning_content")
            
            if role == "user":
                 timeline_html.append(f"""
                 <div class='chat-bubble user'>
                    <span class='chat-meta'>USER &bull; Turn {turn}</span>
                    <div style='white-space: pre-wrap;'>{html.escape(content)}</div>
                 </div>
                 """)
            elif role == "assistant":
                reasoning_html = ""
                if reasoning:
                    reasoning_html = f"""
                    <div class='reasoning-block'>
                        <div class='reasoning-label'>Thinking Process</div>
                        <div style='white-space: pre-wrap;'>{html.escape(reasoning)}</div>
                    </div>
                    """
                timeline_html.append(f"""
                 <div class='chat-bubble assistant'>
                    <span class='chat-meta'>ASSISTANT &bull; Turn {turn}</span>
                    {reasoning_html}
                    <div style='white-space: pre-wrap;'>{html.escape(content)}</div>
                 </div>
                 """)
            elif role == "system":
                 timeline_html.append(f"""
                 <div class='chat-bubble system'>
                    <span class='chat-meta'>SYSTEM</span>
                    <div style='white-space: pre-wrap;'>{html.escape(content)}</div>
                 </div>
                 """)

        elif etype == "tool_call":
            name = data.get("name")
            args = data.get("arguments", {})
            timeline_html.append(f"""
            <div class='tool-card'>
                <div class='tool-header'>
                    <span class='tool-name'>🛠️ {html.escape(str(name))}</span>
                    <span class='pill'>CALL</span>
                </div>
                <div class='tool-body'>
                    <pre style='margin:0; border:0; background:none;'>{html.escape(json.dumps(args, indent=2, ensure_ascii=False))}</pre>
                </div>
            </div>
            """)

        elif etype == "tool_result":
            name = data.get("name")
            result = data.get("result", {})
            # Check if it looks like an error
            is_error = isinstance(result, dict) and "error" in result
            style_class = "error" if is_error else ""
            timeline_html.append(f"""
            <div class='tool-card'>
                <div class='tool-header'>
                    <span class='tool-name'>↪️ {html.escape(str(name))}</span>
                    <span class='pill {style_class or "ok"}'>RESULT</span>
                </div>
                <div class='tool-result {style_class}'>
                    <pre style='margin:0; border:0; background:none;'>{html.escape(json.dumps(result, indent=2, ensure_ascii=False))}</pre>
                </div>
            </div>
            """)
            
        elif etype == "dynamic_event_triggered":
             name = data.get("event_name")
             trigger = data.get("trigger")
             timeline_html.append(f"""
             <div class='chat-bubble system' style='border-left: 3px solid #f59e0b;'>
                <strong>⚡ Dynamic Event Triggered: {html.escape(str(name))}</strong><br>
                <div class='muted'>{html.escape(str(trigger))}</div>
             </div>
             """)
             
    timeline_html.append("</div>") # end chat-container
    
    # --- Debug Details (Collapsed) ---
    
    check_rows: list[str] = []
    for chk in checks:
        passed = bool(chk.get("passed", False))
        applicable = bool(chk.get("applicable", True))
        status = "<span class='pill ok'>PASS</span>" if passed else "<span class='pill bad'>FAIL</span>"
        if not applicable: status = "<span class='pill'>N/A</span>"
        check_rows.append(
            f"<tr><td>{html.escape(str(chk.get('name')))}</td><td>{status}</td><td>{html.escape(str(chk.get('severity')))}</td><td><pre>{html.escape(str(chk.get('details')))}</pre></td></tr>"
        )
    
    usage_rows: list[str] = []
    usage_totals = runtime_summary.get("model_usage_totals", {}) or {}
    if isinstance(usage_totals, dict):
        for k in sorted(usage_totals):
            usage_rows.append(f"<div class='kv'><div class='k'>{k}</div><div>{usage_totals[k]}</div></div>")

    timeline_debug_rows: list[str] = []
    for ev in events:
         timeline_debug_rows.append(f"<tr><td>{ev.get('type')}</td><td>{ev.get('timestamp')}</td><td><pre>{html.escape(json.dumps(ev.get('data'), indent=2))}</pre></td></tr>")

    debug_html = f"""
    <div class='details-box'>
        <details>
            <summary>Evaluation Checks</summary>
            <div class='details-content'>
                <table><thead><tr><th>Name</th><th>Status</th><th>Severity</th><th>Details</th></tr></thead>
                <tbody>{"".join(check_rows)}</tbody></table>
            </div>
        </details>
        
        <details>
            <summary>Token Usage & Summary</summary>
            <div class='details-content'>
                 <h3>Token Usage</h3>
                 {"".join(usage_rows)}
                 <h3>Runtime Summary</h3>
                 <pre>{html.escape(json.dumps(runtime_summary, indent=2))}</pre>
            </div>
        </details>

        <details>
            <summary>Raw Event Timeline</summary>
            <div class='details-content'>
                 <table><thead><tr><th>Type</th><th>Time</th><th>Data</th></tr></thead>
                 <tbody>{"".join(timeline_debug_rows)}</tbody></table>
            </div>
        </details>
        
        <details>
            <summary>Full JSON Payload</summary>
             <div class='details-content'>
                <pre>{html.escape(json.dumps(payload, indent=2))}</pre>
             </div>
        </details>
    </div>
    """

    body = [
        "<div class='header'>",
        f"<h1 class='title'>Run {html.escape(run_id)}</h1>",
        "<div class='muted'><a href='/'>&larr; Back to index</a></div>",
        "</div>",
        "<div class='grid'>", # Top summary cards
        "<section class='card'>",
        f"<div class='kv'><div class='k'>Status</div><div>{status_pill}</div></div>",
        f"<div class='kv'><div class='k'>Scenario</div><div>{html.escape(str(scorecard.get('scenario_id', run.get('scenario_id', 'unknown'))))}</div></div>",
        f"<div class='kv'><div class='k'>Model</div><div>{html.escape(str(scorecard.get('model', run.get('model', 'unknown'))))}</div></div>",
        f"<div class='kv'><div class='k'>Grade</div><div>{html.escape(str(scorecard.get('grade', '?')))}</div></div>",
        f"<div class='kv'><div class='k'>Duration</div><div>{_safe_float(run.get('duration_seconds', 0.0)):.2f}s</div></div>",
        "</section>",
        "</div>", # end grid
        
        "<h2 style='margin-top:24px; border-bottom:1px solid var(--line); padding-bottom:8px;'>Interaction Timeline</h2>",
        "".join(timeline_html),
        
        debug_html
    ]
    return _page(f"Argus Run {run_id}", "".join(body))


def _suite_html(payload: dict[str, Any], *, suite_id: str) -> str:
    summary = payload.get("summary", {}) or {}
    runs = payload.get("runs", []) or []

    run_rows: list[str] = []
    for row in runs:
        score = row.get("scorecard", {}) or {}
        passed = bool(score.get("passed", False))
        status = "<span class='pill ok'>PASS</span>" if passed else "<span class='pill bad'>FAIL</span>"
        run_id = str(row.get("run_id", ""))
        run_id_cell = html.escape(run_id)
        if run_id:
            run_id_cell = f"<a href='/runs/{html.escape(run_id)}'>{html.escape(run_id)}</a>"
        run_rows.append(
            "<tr>"
            f"<td>{run_id_cell}</td>"
            f"<td>{html.escape(str(row.get('scenario_id', 'unknown')))}</td>"
            f"<td>{html.escape(str(row.get('trial', '-')))}</td>"
            f"<td>{html.escape(str(row.get('seed', '-')))}</td>"
            f"<td>{status}</td>"
            f"<td>{html.escape(str(score.get('grade', '?')))}</td>"
            f"<td>{html.escape(str(score.get('total_severity', '-')))}</td>"
            "</tr>"
        )

    body = [
        "<div class='header'>",
        f"<h1 class='title'>Suite {html.escape(suite_id)}</h1>",
        "<div class='muted'><a href='/'>Back to index</a></div>",
        "</div>",
        "<div class='stack'>",
        "<section class='card'>",
        "<h2>Summary</h2>",
        f"<div class='kv'><div class='k'>Model</div><div>{html.escape(str(payload.get('model', 'unknown')))}</div></div>",
        f"<div class='kv'><div class='k'>Pass Rate</div><div>{_safe_float(summary.get('pass_rate', 0.0)):.4f}</div></div>",
        f"<div class='kv'><div class='k'>Avg Severity</div><div>{_safe_float(summary.get('avg_total_severity', 0.0)):.3f}</div></div>",
        f"<div class='kv'><div class='k'>Executed Runs</div><div>{_safe_int(summary.get('executed_runs', 0))}</div></div>",
        f"<div class='kv'><div class='k'>Errored Runs</div><div>{_safe_int(summary.get('errored_runs', 0))}</div></div>",
        "</section>",
        "<section class='card'><h2>Runs</h2><table><thead><tr><th>Run</th><th>Scenario</th><th>Trial</th><th>Seed</th><th>Status</th><th>Grade</th><th>Severity</th></tr></thead><tbody>",
        "".join(run_rows) if run_rows else "<tr><td colspan='7' class='muted'>No runs listed.</td></tr>",
        "</tbody></table></section>",
        "</div>",
    ]
    return _page(f"Argus Suite {suite_id}", "".join(body))


def create_reports_server(*, host: str, port: int, reports_root: str | Path) -> ThreadingHTTPServer:
    """Create a ThreadingHTTPServer serving the Argus report explorer UI."""
    root = Path(reports_root)

    class _Handler(BaseHTTPRequestHandler):
        def _send_html(self, status: int, content: str) -> None:
            data = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            if path == "/":
                self._send_html(200, _index_html(root))
                return

            if path.startswith("/runs/"):
                run_id = path.split("/", 2)[2].strip()
                report_path = root / "runs" / f"{run_id}.json"
                payload = _load_json(report_path)
                if payload is None:
                    self._send_html(404, _page("Not Found", "<h1>Run not found</h1><p><a href='/'>Back</a></p>"))
                    return
                self._send_html(200, _run_html(payload, run_id=run_id))
                return

            if path.startswith("/suites/"):
                suite_id = path.split("/", 2)[2].strip()
                report_path = root / "suites" / f"{suite_id}.json"
                payload = _load_json(report_path)
                if payload is None:
                    self._send_html(404, _page("Not Found", "<h1>Suite not found</h1><p><a href='/'>Back</a></p>"))
                    return
                self._send_html(200, _suite_html(payload, suite_id=suite_id))
                return

            if path == "/api/runs":
                scenario_id = _get_query_value(query, "scenario_id")
                model = _get_query_value(query, "model")
                grade = _get_query_value(query, "grade")
                passed = _parse_bool(_get_query_value(query, "passed"))
                page = _safe_int(_get_query_value(query, "page"), default=1)
                page_size = _safe_int(_get_query_value(query, "page_size"), default=50)
                self._send_json(
                    200,
                    query_run_reports(
                        root,
                        scenario_id=scenario_id,
                        model=model,
                        passed=passed,
                        grade=grade,
                        page=page,
                        page_size=page_size,
                    ),
                )
                return

            if path == "/api/scenarios":
                scenarios = list_scenarios(root)
                page = _safe_int(_get_query_value(query, "page"), default=1)
                page_size = _safe_int(_get_query_value(query, "page_size"), default=100)
                safe_page = max(1, page)
                safe_page_size = max(1, min(page_size, 500))
                items = _paginate_items(scenarios, page=safe_page, page_size=safe_page_size)
                self._send_json(
                    200,
                    {
                        "items": items,
                        "total": len(scenarios),
                        "page": safe_page,
                        "page_size": safe_page_size,
                    },
                )
                return

            if path.startswith("/api/scenarios/") and path.endswith("/runs"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    self._send_json(400, {"error": "invalid_path"})
                    return
                scenario_id = parts[2]
                model = _get_query_value(query, "model")
                grade = _get_query_value(query, "grade")
                passed = _parse_bool(_get_query_value(query, "passed"))
                page = _safe_int(_get_query_value(query, "page"), default=1)
                page_size = _safe_int(_get_query_value(query, "page_size"), default=50)
                result = query_run_reports(
                    root,
                    scenario_id=scenario_id,
                    model=model,
                    passed=passed,
                    grade=grade,
                    page=page,
                    page_size=page_size,
                )
                self._send_json(200, result)
                return

            if path.startswith("/api/runs/") and path.endswith("/timeline"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    self._send_json(400, {"error": "invalid_path"})
                    return
                run_id = parts[2]
                report_path = root / "runs" / f"{run_id}.json"
                payload = _load_json(report_path)
                if payload is None:
                    self._send_json(404, {"error": "run_not_found", "run_id": run_id})
                    return
                scorecard = payload.get("scorecard", {}) or {}
                run = payload.get("run", {}) or {}
                scenario_id = str(scorecard.get("scenario_id") or run.get("scenario_id") or "unknown")
                model = str(scorecard.get("model") or run.get("model") or "unknown")
                normalized = _normalize_timeline(payload)
                event_types = _get_query_value(query, "event_types")
                if event_types:
                    allowed_types = {part.strip() for part in event_types.split(",") if part.strip()}
                    normalized = [event for event in normalized if event.get("type") in allowed_types]
                self._send_json(
                    200,
                    {
                        "run_id": run_id,
                        "scenario_id": scenario_id,
                        "model": model,
                        "step_count": len(normalized),
                        "steps": normalized,
                    },
                )
                return

            if path.startswith("/api/runs/"):
                run_id = path.split("/", 3)[3].strip()
                report_path = root / "runs" / f"{run_id}.json"
                payload = _load_json(report_path)
                if payload is None:
                    self._send_json(404, {"error": "run_not_found", "run_id": run_id})
                    return
                self._send_json(200, payload)
                return

            if path.startswith("/api/suites/"):
                suite_id = path.split("/", 3)[3].strip()
                report_path = root / "suites" / f"{suite_id}.json"
                payload = _load_json(report_path)
                if payload is None:
                    self._send_json(404, {"error": "suite_not_found", "suite_id": suite_id})
                    return
                self._send_json(200, payload)
                return

            self._send_html(404, _page("Not Found", "<h1>Not Found</h1><p><a href='/'>Back</a></p>"))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            # Keep terminal output concise in CLI mode.
            return

    return ThreadingHTTPServer((host, port), _Handler)


def serve_reports_forever(*, host: str, port: int, reports_root: str | Path) -> None:
    """Start report explorer server and block until interrupted."""
    server = create_reports_server(host=host, port=port, reports_root=reports_root)
    try:
        server.serve_forever()
    finally:
        server.server_close()
