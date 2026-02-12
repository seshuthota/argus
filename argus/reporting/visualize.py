"""Lightweight SVG chart generation for Argus reports."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_svg(path: Path, body: str, width: int, height: int) -> Path:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        "<style>"
        "text{font-family:Verdana,Arial,sans-serif;fill:#1d1f23;font-size:12px}"
        ".title{font-size:18px;font-weight:bold}"
        ".axis{stroke:#a9adb7;stroke-width:1}"
        ".grid{stroke:#eceff4;stroke-width:1}"
        "</style>"
        f"{body}</svg>"
    )
    path.write_text(svg)
    return path


def _color_scale(value: float, min_v: float, max_v: float) -> str:
    if max_v <= min_v:
        return "#4caf50"
    t = (value - min_v) / (max_v - min_v)
    if t < 0:
        t = 0.0
    if t > 1:
        t = 1.0
    # red -> yellow -> green
    if t < 0.5:
        r = 220
        g = int(90 + (t / 0.5) * 130)
    else:
        r = int(220 - ((t - 0.5) / 0.5) * 130)
        g = 220
    b = 80
    return f"rgb({r},{g},{b})"


def _horizontal_bar_chart_svg(
    *,
    title: str,
    rows: list[tuple[str, float]],
    max_value: float,
    value_format: str,
    bar_color: str,
) -> tuple[str, int, int]:
    rows = rows[:20]
    width = 1200
    height = 120 + (len(rows) * 32)
    left = 350
    right = 80
    top = 70
    chart_w = width - left - right
    bar_h = 18

    body: list[str] = []
    body.append(f'<text class="title" x="20" y="36">{_escape(title)}</text>')
    body.append(f'<line class="axis" x1="{left}" y1="{top-12}" x2="{left}" y2="{height-30}" />')

    for idx, (label, value) in enumerate(rows):
        y = top + (idx * 32)
        frac = 0.0 if max_value <= 0 else max(0.0, min(1.0, value / max_value))
        bw = int(chart_w * frac)
        body.append(f'<line class="grid" x1="{left}" y1="{y+bar_h+2}" x2="{width-right}" y2="{y+bar_h+2}" />')
        body.append(f'<text x="20" y="{y+14}">{_escape(label[:48])}</text>')
        body.append(
            f'<rect x="{left}" y="{y}" width="{bw}" height="{bar_h}" '
            f'fill="{bar_color}" opacity="0.85" />'
        )
        body.append(f'<text x="{left + bw + 8}" y="{y+14}">{value_format.format(value)}</text>')

    return ("".join(body), width, height)


def _heatmap_svg(
    *,
    title: str,
    rows: list[tuple[str, float]],
    min_v: float,
    max_v: float,
    suffix: str = "",
) -> tuple[str, int, int]:
    width = 800
    cell_h = 30
    top = 70
    height = top + (len(rows) * cell_h) + 40

    body: list[str] = []
    body.append(f'<text class="title" x="20" y="36">{_escape(title)}</text>')
    body.append('<text x="20" y="60">Pathway</text>')
    body.append('<text x="520" y="60">Value</text>')

    for i, (label, value) in enumerate(rows):
        y = top + (i * cell_h)
        color = _color_scale(value, min_v, max_v)
        body.append(f'<rect x="20" y="{y}" width="760" height="{cell_h-4}" fill="{color}" opacity="0.88" />')
        body.append(f'<text x="30" y="{y+18}">{_escape(label)}</text>')
        body.append(f'<text x="520" y="{y+18}">{value:.4f}{_escape(suffix)}</text>')

    return ("".join(body), width, height)


def _line_chart_svg(
    *,
    title: str,
    series: dict[str, list[float]],
    y_min: float = 0.0,
    y_max: float = 1.0,
) -> tuple[str, int, int]:
    width = 1200
    height = 520
    left = 70
    right = 30
    top = 70
    bottom = 60
    chart_w = width - left - right
    chart_h = height - top - bottom
    palette = ["#1565c0", "#ef6c00", "#2e7d32", "#6a1b9a", "#00838f", "#c62828"]

    body: list[str] = []
    body.append(f'<text class="title" x="20" y="36">{_escape(title)}</text>')
    body.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" />')
    body.append(f'<line class="axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" />')

    for g in range(6):
        gy = top + int((g / 5) * chart_h)
        val = y_max - ((g / 5) * (y_max - y_min))
        body.append(f'<line class="grid" x1="{left}" y1="{gy}" x2="{width-right}" y2="{gy}" />')
        body.append(f'<text x="8" y="{gy+4}">{val:.2f}</text>')

    for idx, (name, values) in enumerate(sorted(series.items(), key=lambda kv: kv[0])):
        if not values:
            continue
        color = palette[idx % len(palette)]
        n = len(values)
        if n == 1:
            x = left + (chart_w // 2)
            y = top + int((1.0 - ((values[0] - y_min) / max(1e-9, (y_max - y_min)))) * chart_h)
            body.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}" />')
        else:
            pts: list[str] = []
            for i, v in enumerate(values):
                x = left + int((i / (n - 1)) * chart_w)
                frac = (v - y_min) / max(1e-9, (y_max - y_min))
                frac = max(0.0, min(1.0, frac))
                y = top + int((1.0 - frac) * chart_h)
                pts.append(f"{x},{y}")
            body.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{" ".join(pts)}" />')
            for p in pts:
                x, y = p.split(",")
                body.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}" />')

        legend_y = top + 16 + (idx * 18)
        body.append(f'<rect x="{width-280}" y="{legend_y-10}" width="12" height="12" fill="{color}" />')
        body.append(f'<text x="{width-262}" y="{legend_y}">{_escape(name[:40])}</text>')

    return ("".join(body), width, height)


def generate_suite_visuals(suite_report: dict[str, Any], *, output_dir: str | Path) -> dict[str, str]:
    """Generate suite-level SVG charts and return named artifact paths."""
    suite_id = str(suite_report.get("suite_id", "unknown"))
    out = _ensure_dir(Path(output_dir) / f"suite_{suite_id}")
    artifacts: dict[str, str] = {}

    by_scenario = suite_report.get("by_scenario", {}) or {}
    rows_pass = sorted(
        [(sid, float(stats.get("pass_rate", 0.0))) for sid, stats in by_scenario.items()],
        key=lambda t: t[1],
        reverse=True,
    )
    if rows_pass:
        body, w, h = _horizontal_bar_chart_svg(
            title=f"Scenario Pass Rate ({suite_id})",
            rows=rows_pass,
            max_value=1.0,
            value_format="{:.3f}",
            bar_color="#2e7d32",
        )
        p = _write_svg(out / "scenario_pass_rate.svg", body, w, h)
        artifacts["scenario_pass_rate"] = str(p)

    rows_sev = sorted(
        [(sid, float(stats.get("avg_total_severity", 0.0))) for sid, stats in by_scenario.items()],
        key=lambda t: t[1],
        reverse=True,
    )
    if rows_sev:
        max_sev = max(v for _, v in rows_sev) if rows_sev else 1.0
        body, w, h = _horizontal_bar_chart_svg(
            title=f"Scenario Avg Severity ({suite_id})",
            rows=rows_sev,
            max_value=max(max_sev, 1.0),
            value_format="{:.2f}",
            bar_color="#c62828",
        )
        p = _write_svg(out / "scenario_avg_severity.svg", body, w, h)
        artifacts["scenario_avg_severity"] = str(p)

    by_pathway = suite_report.get("by_pathway", {}) or {}
    rows_path = sorted(
        [(pid, float(stats.get("pass_rate", 0.0))) for pid, stats in by_pathway.items()],
        key=lambda t: t[0],
    )
    if rows_path:
        body, w, h = _heatmap_svg(
            title=f"Pathway Pass Rate Heatmap ({suite_id})",
            rows=rows_path,
            min_v=0.0,
            max_v=1.0,
        )
        p = _write_svg(out / "pathway_pass_heatmap.svg", body, w, h)
        artifacts["pathway_pass_heatmap"] = str(p)

    failures = suite_report.get("top_failed_checks", []) or []
    rows_fail = [(str(f.get("name", "unknown")), float(f.get("severity_sum", 0.0))) for f in failures[:20]]
    if rows_fail:
        max_fail = max(v for _, v in rows_fail) if rows_fail else 1.0
        body, w, h = _horizontal_bar_chart_svg(
            title=f"Top Failed Checks by Severity Sum ({suite_id})",
            rows=rows_fail,
            max_value=max(max_fail, 1.0),
            value_format="{:.0f}",
            bar_color="#6a1b9a",
        )
        p = _write_svg(out / "failed_checks_severity.svg", body, w, h)
        artifacts["failed_checks_severity"] = str(p)

    index = {"generated_at": datetime.now(timezone.utc).isoformat(), "suite_id": suite_id, "artifacts": artifacts}
    idx_path = out / "index.json"
    idx_path.write_text(json.dumps(index, indent=2))
    artifacts["index"] = str(idx_path)
    return artifacts


def generate_matrix_visuals(matrix_report: dict[str, Any], *, output_dir: str | Path) -> dict[str, str]:
    """Generate model-matrix charts from benchmark-matrix JSON output."""
    out = _ensure_dir(Path(output_dir) / f"matrix_{_now_stamp()}")
    artifacts: dict[str, str] = {}

    models = matrix_report.get("models", []) or []
    rows_pass = []
    rows_sev = []
    for m in models:
        model = str(m.get("resolved_model", m.get("input_model", "unknown")))
        summary = m.get("summary", {}) or {}
        rows_pass.append((model, float(summary.get("pass_rate", 0.0))))
        rows_sev.append((model, float(summary.get("avg_total_severity", 0.0))))

    if rows_pass:
        body, w, h = _horizontal_bar_chart_svg(
            title="Model Pass Rate",
            rows=sorted(rows_pass, key=lambda t: t[1], reverse=True),
            max_value=1.0,
            value_format="{:.3f}",
            bar_color="#1565c0",
        )
        p = _write_svg(out / "model_pass_rate.svg", body, w, h)
        artifacts["model_pass_rate"] = str(p)

    if rows_sev:
        max_sev = max(v for _, v in rows_sev) if rows_sev else 1.0
        body, w, h = _horizontal_bar_chart_svg(
            title="Model Avg Total Severity",
            rows=sorted(rows_sev, key=lambda t: t[1], reverse=True),
            max_value=max(max_sev, 1.0),
            value_format="{:.3f}",
            bar_color="#ef6c00",
        )
        p = _write_svg(out / "model_avg_severity.svg", body, w, h)
        artifacts["model_avg_severity"] = str(p)

    pairwise = matrix_report.get("pairwise", []) or []
    rows_delta = []
    for p in pairwise:
        a = str(p.get("model_a", "A"))
        b = str(p.get("model_b", "B"))
        s = p.get("summary", {}) or {}
        rows_delta.append((f"{a} vs {b}", float(s.get("pass_rate_delta_mean_a_minus_b", 0.0))))
    if rows_delta:
        max_abs = max(abs(v) for _, v in rows_delta) if rows_delta else 1.0
        shifted = [(label, (v + max_abs)) for label, v in rows_delta]
        body, w, h = _horizontal_bar_chart_svg(
            title="Pairwise Mean Pass Delta (A-B)",
            rows=shifted,
            max_value=max_abs * 2 if max_abs > 0 else 1.0,
            value_format="{:.3f}",
            bar_color="#2e7d32",
        )
        p = _write_svg(out / "pairwise_pass_delta.svg", body, w, h)
        artifacts["pairwise_pass_delta"] = str(p)

    idx = {"generated_at": datetime.now(timezone.utc).isoformat(), "artifacts": artifacts}
    idx_path = out / "index.json"
    idx_path.write_text(json.dumps(idx, indent=2))
    artifacts["index"] = str(idx_path)
    return artifacts


def generate_trend_visuals(
    model_trends: dict[str, list[dict[str, Any]]],
    *,
    output_dir: str | Path,
    window: int = 20,
) -> dict[str, str]:
    """Generate trend SVGs from JSONL trend entries."""
    out = _ensure_dir(Path(output_dir) / f"trends_{_now_stamp()}")
    artifacts: dict[str, str] = {}

    pass_series: dict[str, list[float]] = {}
    sev_series: dict[str, list[float]] = {}
    for key, entries in sorted(model_trends.items(), key=lambda kv: kv[0]):
        if not entries:
            continue
        recent = entries[-window:] if window > 0 else entries
        model_name = str(recent[-1].get("model", key))
        pass_vals: list[float] = []
        sev_vals: list[float] = []
        for e in recent:
            summary = e.get("summary", {}) or {}
            try:
                pass_vals.append(float(summary.get("pass_rate", 0.0)))
            except (TypeError, ValueError):
                pass_vals.append(0.0)
            try:
                sev_vals.append(float(summary.get("avg_total_severity", 0.0)))
            except (TypeError, ValueError):
                sev_vals.append(0.0)
        pass_series[model_name] = pass_vals
        sev_series[model_name] = sev_vals

    if pass_series:
        body, w, h = _line_chart_svg(
            title=f"Pass Rate Trend (last {window} runs)",
            series=pass_series,
            y_min=0.0,
            y_max=1.0,
        )
        p = _write_svg(out / "trend_pass_rate.svg", body, w, h)
        artifacts["trend_pass_rate"] = str(p)

    if sev_series:
        max_y = 1.0
        for vals in sev_series.values():
            if vals:
                max_y = max(max_y, max(vals))
        body, w, h = _line_chart_svg(
            title=f"Avg Severity Trend (last {window} runs)",
            series=sev_series,
            y_min=0.0,
            y_max=max_y,
        )
        p = _write_svg(out / "trend_avg_severity.svg", body, w, h)
        artifacts["trend_avg_severity"] = str(p)

    idx = {"generated_at": datetime.now(timezone.utc).isoformat(), "artifacts": artifacts}
    idx_path = out / "index.json"
    idx_path.write_text(json.dumps(idx, indent=2))
    artifacts["index"] = str(idx_path)
    return artifacts


def generate_pairwise_visuals(pairwise_report: dict[str, Any], *, output_dir: str | Path) -> dict[str, str]:
    """Generate SVG charts for one pairwise analysis JSON output."""
    out = _ensure_dir(Path(output_dir) / f"pairwise_{_now_stamp()}")
    artifacts: dict[str, str] = {}

    summary = pairwise_report.get("summary", {}) or {}
    rows_summary = [
        ("mean_pass_delta_a_minus_b", float(summary.get("pass_rate_delta_mean_a_minus_b", 0.0))),
        ("mean_severity_delta_a_minus_b", float(summary.get("avg_severity_delta_mean_a_minus_b", 0.0))),
        ("mcnemar_stat", float(summary.get("mcnemar_stat", 0.0))),
    ]
    max_summary = max(abs(v) for _, v in rows_summary) if rows_summary else 1.0
    if max_summary <= 0:
        max_summary = 1.0
    shifted = [(label, value + max_summary) for label, value in rows_summary]
    body, w, h = _horizontal_bar_chart_svg(
        title="Pairwise Summary Metrics",
        rows=shifted,
        max_value=max_summary * 2,
        value_format="{:.4f}",
        bar_color="#00838f",
    )
    p = _write_svg(out / "pairwise_summary_metrics.svg", body, w, h)
    artifacts["pairwise_summary_metrics"] = str(p)

    by_scenario = pairwise_report.get("by_scenario", []) or []
    rows_delta = [
        (str(row.get("scenario_id", "unknown")), float(row.get("delta_pass_rate_a_minus_b", 0.0)))
        for row in by_scenario
    ]
    if rows_delta:
        max_abs = max(abs(v) for _, v in rows_delta)
        if max_abs <= 0:
            max_abs = 1.0
        shifted_delta = [(label, value + max_abs) for label, value in rows_delta]
        body, w, h = _horizontal_bar_chart_svg(
            title="Scenario Delta Pass Rate (A-B)",
            rows=sorted(shifted_delta, key=lambda t: t[1], reverse=True),
            max_value=max_abs * 2,
            value_format="{:.4f}",
            bar_color="#6a1b9a",
        )
        p = _write_svg(out / "pairwise_scenario_delta_pass_rate.svg", body, w, h)
        artifacts["pairwise_scenario_delta_pass_rate"] = str(p)

    idx = {"generated_at": datetime.now(timezone.utc).isoformat(), "artifacts": artifacts}
    idx_path = out / "index.json"
    idx_path.write_text(json.dumps(idx, indent=2))
    artifacts["index"] = str(idx_path)
    return artifacts
