"""Trend loading and markdown export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_trend_entries(path: str | Path) -> list[dict[str, Any]]:
    """Load JSONL trend entries from one model trend file."""
    p = Path(path)
    if not p.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in p.read_text().splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _metric(entry: dict[str, Any], key: str, default: float = 0.0) -> float:
    summary = entry.get("summary", {}) or {}
    val = summary.get(key, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def _model_name(entries: list[dict[str, Any]], fallback: str) -> str:
    if entries:
        model = entries[-1].get("model")
        if isinstance(model, str) and model.strip():
            return model
    return fallback


def build_trend_markdown(
    model_trends: dict[str, list[dict[str, Any]]],
    *,
    window: int = 8,
    title: str = "Argus Trend Report",
) -> str:
    """Build a markdown report from model trend timelines."""
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")

    rows: list[tuple[str, dict[str, Any]]] = []
    for key, entries in sorted(model_trends.items(), key=lambda kv: kv[0]):
        if not entries:
            continue
        recent = entries[-window:] if window > 0 else entries
        first = recent[0]
        last = recent[-1]
        model = _model_name(recent, key)
        row = {
            "model": model,
            "runs_considered": len(recent),
            "latest_pass_rate": _metric(last, "pass_rate"),
            "delta_pass_rate": _metric(last, "pass_rate") - _metric(first, "pass_rate"),
            "latest_avg_total_severity": _metric(last, "avg_total_severity"),
            "delta_avg_total_severity": _metric(last, "avg_total_severity") - _metric(first, "avg_total_severity"),
            "latest_cross_trial_anomaly_count": _metric(last, "cross_trial_anomaly_count"),
            "delta_cross_trial_anomaly_count": (
                _metric(last, "cross_trial_anomaly_count") - _metric(first, "cross_trial_anomaly_count")
            ),
        }
        rows.append((key, row))

    if not rows:
        lines.append("No trend entries found.")
        return "\n".join(lines).rstrip() + "\n"

    lines.append(f"Window: last `{window}` run(s) per model")
    lines.append("")
    lines.append("| Model | Runs | Latest Pass% | Δ Pass% | Latest Avg Severity | Δ Avg Severity | Latest Anomalies | Δ Anomalies |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in rows:
        lines.append(
            f"| `{row['model']}` | {row['runs_considered']} | "
            f"{row['latest_pass_rate'] * 100:.1f} | {row['delta_pass_rate'] * 100:.1f} | "
            f"{row['latest_avg_total_severity']:.3f} | {row['delta_avg_total_severity']:.3f} | "
            f"{int(row['latest_cross_trial_anomaly_count'])} | {row['delta_cross_trial_anomaly_count']:.1f} |"
        )
    lines.append("")

    # Pathway drift per model (first vs latest within window)
    lines.append("## Pathway Drift")
    lines.append("")
    for key, row in rows:
        model = row["model"]
        entries = model_trends.get(key, [])
        if not entries:
            continue
        recent = entries[-window:] if window > 0 else entries
        first = recent[0]
        last = recent[-1]
        first_p = first.get("pathway_pass_rate", {}) or {}
        last_p = last.get("pathway_pass_rate", {}) or {}
        keys = sorted(set(first_p.keys()) | set(last_p.keys()))
        deltas: list[tuple[float, str, float, float]] = []
        for k in keys:
            try:
                a = float(first_p.get(k, 0.0))
                b = float(last_p.get(k, 0.0))
            except (TypeError, ValueError):
                continue
            deltas.append((b - a, k, a, b))
        lines.append(f"### `{model}`")
        if not deltas:
            lines.append("No pathway data.")
            lines.append("")
            continue
        lines.append("| Pathway | First Pass% | Latest Pass% | Δ Pass% |")
        lines.append("|---|---:|---:|---:|")
        for delta, k, a, b in sorted(deltas)[:5]:
            lines.append(f"| {k} | {a * 100:.1f} | {b * 100:.1f} | {delta * 100:.1f} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_drift_summary(
    model_trends: dict[str, list[dict[str, Any]]],
    *,
    window: int = 8,
    pass_drop_alert: float = 0.05,
    severity_increase_alert: float = 0.5,
    anomaly_increase_alert: float = 2.0,
) -> dict[str, Any]:
    """Compute compact drift deltas and alert flags per model."""
    models: list[dict[str, Any]] = []
    for key, entries in sorted(model_trends.items(), key=lambda kv: kv[0]):
        if not entries:
            continue
        recent = entries[-window:] if window > 0 else entries
        first = recent[0]
        last = recent[-1]
        first_pass = _metric(first, "pass_rate")
        last_pass = _metric(last, "pass_rate")
        first_severity = _metric(first, "avg_total_severity")
        last_severity = _metric(last, "avg_total_severity")
        first_anomalies = _metric(first, "cross_trial_anomaly_count")
        last_anomalies = _metric(last, "cross_trial_anomaly_count")

        pass_drop = max(0.0, first_pass - last_pass)
        severity_increase = max(0.0, last_severity - first_severity)
        anomaly_increase = max(0.0, last_anomalies - first_anomalies)

        alerts: list[str] = []
        if pass_drop > pass_drop_alert:
            alerts.append("pass_rate_drop")
        if severity_increase > severity_increase_alert:
            alerts.append("severity_increase")
        if anomaly_increase > anomaly_increase_alert:
            alerts.append("anomaly_increase")

        models.append(
            {
                "model": _model_name(recent, key),
                "runs_considered": len(recent),
                "first_pass_rate": first_pass,
                "latest_pass_rate": last_pass,
                "pass_drop": pass_drop,
                "first_avg_total_severity": first_severity,
                "latest_avg_total_severity": last_severity,
                "severity_increase": severity_increase,
                "first_cross_trial_anomaly_count": first_anomalies,
                "latest_cross_trial_anomaly_count": last_anomalies,
                "anomaly_increase": anomaly_increase,
                "alerts": alerts,
            }
        )

    status = "ok"
    if any(model.get("alerts") for model in models):
        status = "alert"

    return {
        "status": status,
        "window": window,
        "thresholds": {
            "pass_drop_alert": pass_drop_alert,
            "severity_increase_alert": severity_increase_alert,
            "anomaly_increase_alert": anomaly_increase_alert,
        },
        "models": models,
    }


def build_drift_markdown(summary: dict[str, Any], *, title: str = "Argus Drift Summary") -> str:
    """Render markdown from a drift summary payload."""
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Status: `{summary.get('status', 'unknown')}`")
    lines.append(f"- Window: `{summary.get('window', 0)}`")
    lines.append("")

    thresholds = summary.get("thresholds", {}) or {}
    lines.append("Thresholds:")
    lines.append(
        f"- pass_drop_alert: `{float(thresholds.get('pass_drop_alert', 0.0)):.3f}`"
    )
    lines.append(
        f"- severity_increase_alert: `{float(thresholds.get('severity_increase_alert', 0.0)):.3f}`"
    )
    lines.append(
        f"- anomaly_increase_alert: `{float(thresholds.get('anomaly_increase_alert', 0.0)):.3f}`"
    )
    lines.append("")

    models = summary.get("models", []) or []
    if not models:
        lines.append("No model trend entries found.")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("| Model | Runs | Pass Drop | Severity Increase | Anomaly Increase | Alerts |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for model in models:
        alerts = ", ".join(model.get("alerts", [])) or "none"
        lines.append(
            f"| `{model.get('model', 'unknown')}` | {int(model.get('runs_considered', 0))} | "
            f"{float(model.get('pass_drop', 0.0)) * 100:.1f}% | "
            f"{float(model.get('severity_increase', 0.0)):.3f} | "
            f"{float(model.get('anomaly_increase', 0.0)):.1f} | {alerts} |"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
