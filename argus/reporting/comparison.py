"""Suite-to-suite comparison helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _summary_metrics(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary", {}) or {}
    return {
        "suite_id": report.get("suite_id", "unknown"),
        "model": report.get("model", "unknown"),
        "pass_rate": float(summary.get("pass_rate", 0.0)),
        "passed_runs": int(summary.get("passed_runs", 0)),
        "executed_runs": int(summary.get("executed_runs", 0)),
        "avg_task_success": float(summary.get("avg_task_success", 0.0)),
        "avg_harm_or_risk": float(summary.get("avg_harm_or_risk", 0.0)),
        "avg_total_severity": float(summary.get("avg_total_severity", 0.0)),
        "avg_unsupported_detection_count": float(summary.get("avg_unsupported_detection_count", 0.0)),
        "cross_trial_anomaly_count": int(summary.get("cross_trial_anomaly_count", 0)),
    }


def build_suite_comparison_markdown(
    report_a: dict[str, Any],
    report_b: dict[str, Any],
    *,
    gate_result_a: dict[str, Any] | None = None,
    gate_result_b: dict[str, Any] | None = None,
    title: str = "Argus Benchmark Comparison",
) -> str:
    """Render a compact markdown comparison between two suite reports."""
    a = _summary_metrics(report_a)
    b = _summary_metrics(report_b)

    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- A: `{a['model']}` (`{a['suite_id']}`)")
    lines.append(f"- B: `{b['model']}` (`{b['suite_id']}`)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | A | B | Delta (A-B) |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| Pass rate | {a['pass_rate']:.4f} | {b['pass_rate']:.4f} | {a['pass_rate'] - b['pass_rate']:.4f} |")
    lines.append(f"| Avg task success | {a['avg_task_success']:.3f} | {b['avg_task_success']:.3f} | {a['avg_task_success'] - b['avg_task_success']:.3f} |")
    lines.append(f"| Avg harm/risk | {a['avg_harm_or_risk']:.3f} | {b['avg_harm_or_risk']:.3f} | {a['avg_harm_or_risk'] - b['avg_harm_or_risk']:.3f} |")
    lines.append(f"| Avg total severity | {a['avg_total_severity']:.3f} | {b['avg_total_severity']:.3f} | {a['avg_total_severity'] - b['avg_total_severity']:.3f} |")
    lines.append(
        f"| Cross-trial anomalies | {a['cross_trial_anomaly_count']} | {b['cross_trial_anomaly_count']} | "
        f"{a['cross_trial_anomaly_count'] - b['cross_trial_anomaly_count']} |"
    )
    lines.append(
        f"| Unsupported detections (avg) | {a['avg_unsupported_detection_count']:.3f} | "
        f"{b['avg_unsupported_detection_count']:.3f} | "
        f"{a['avg_unsupported_detection_count'] - b['avg_unsupported_detection_count']:.3f} |"
    )
    lines.append("")

    if gate_result_a is not None or gate_result_b is not None:
        lines.append("## Gate Outcome")
        lines.append("")
        gate_a = "N/A"
        gate_b = "N/A"
        if gate_result_a is not None:
            gate_a = "PASS" if gate_result_a.get("passed", False) else "FAIL"
        if gate_result_b is not None:
            gate_b = "PASS" if gate_result_b.get("passed", False) else "FAIL"
        lines.append("| Model | Gate |")
        lines.append("|---|---|")
        lines.append(f"| `{a['model']}` | {gate_a} |")
        lines.append(f"| `{b['model']}` | {gate_b} |")
        lines.append("")

    pathways_a = report_a.get("by_pathway", {}) or {}
    pathways_b = report_b.get("by_pathway", {}) or {}
    all_pathways = sorted(set(pathways_a.keys()) | set(pathways_b.keys()))
    if all_pathways:
        lines.append("## Pathways")
        lines.append("")
        lines.append("| Pathway | A Pass% | B Pass% | Delta | A Avg Severity | B Avg Severity |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for pathway in all_pathways:
            pa = pathways_a.get(pathway, {}) or {}
            pb = pathways_b.get(pathway, {}) or {}
            a_pass = float(pa.get("pass_rate", 0.0))
            b_pass = float(pb.get("pass_rate", 0.0))
            a_sev = float(pa.get("avg_total_severity", 0.0))
            b_sev = float(pb.get("avg_total_severity", 0.0))
            lines.append(
                f"| {pathway} | {a_pass:.4f} | {b_pass:.4f} | {a_pass - b_pass:.4f} | {a_sev:.3f} | {b_sev:.3f} |"
            )
        lines.append("")

    scenarios_a = report_a.get("by_scenario", {}) or {}
    scenarios_b = report_b.get("by_scenario", {}) or {}
    common_scenarios = sorted(set(scenarios_a.keys()) | set(scenarios_b.keys()))
    scenario_rows: list[tuple[float, str, float, float]] = []
    for sid in common_scenarios:
        ap = float((scenarios_a.get(sid, {}) or {}).get("pass_rate", 0.0))
        bp = float((scenarios_b.get(sid, {}) or {}).get("pass_rate", 0.0))
        scenario_rows.append((ap - bp, sid, ap, bp))

    if scenario_rows:
        lines.append("## Biggest Pass-Rate Gaps")
        lines.append("")
        lines.append("| Scenario | A Pass% | B Pass% | Delta |")
        lines.append("|---|---:|---:|---:|")
        for delta, sid, ap, bp in sorted(scenario_rows, reverse=True)[:10]:
            lines.append(f"| `{sid}` | {ap:.4f} | {bp:.4f} | {delta:.4f} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

