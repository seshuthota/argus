"""Suite-level report aggregation and presentation."""

from __future__ import annotations

import json
import re
import uuid
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich import box


console = Console()


def _run_high_severity_failure_count(run_result: dict[str, Any], threshold: int = 8) -> int:
    """Count high-severity failed failure checks in a scored run."""
    scorecard = run_result.get("scorecard")
    if not isinstance(scorecard, dict):
        return 0
    count = 0
    for chk in scorecard.get("checks", []) or []:
        if not isinstance(chk, dict):
            continue
        if chk.get("kind") != "failure":
            continue
        if not chk.get("applicable", True):
            continue
        if chk.get("passed", True):
            continue
        if int(chk.get("severity", 0)) >= threshold:
            count += 1
    return count


def build_suite_report(
    run_results: list[dict[str, Any]],
    *,
    model: str,
    scenario_files: list[str],
    trials: int,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate run-level results into a suite-level report."""
    suite_id = str(uuid.uuid4())[:8]
    created_at = datetime.now(timezone.utc).isoformat()

    scored_runs = [r for r in run_results if r.get("scorecard") is not None]
    errored_runs = [r for r in run_results if r.get("error")]

    pass_count = sum(1 for r in scored_runs if r["scorecard"].get("passed"))
    scored_count = len(scored_runs)
    pass_rate = (pass_count / scored_count) if scored_count else 0.0

    grade_distribution = {k: 0 for k in ["A", "B", "C", "D", "F"]}
    for r in scored_runs:
        grade = r["scorecard"].get("grade", "F")
        grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

    def avg_score(path: list[str]) -> float:
        vals: list[float] = []
        for r in scored_runs:
            cur: Any = r["scorecard"]
            for key in path:
                cur = cur.get(key, {})
            if isinstance(cur, (int, float)):
                vals.append(float(cur))
        if not vals:
            return 0.0
        return round(sum(vals) / len(vals), 3)

    by_scenario: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in run_results:
        grouped[r["scenario_id"]].append(r)

    for scenario_id, items in sorted(grouped.items(), key=lambda kv: kv[0]):
        scenario_scored = [i for i in items if i.get("scorecard")]
        scenario_errors = [i for i in items if i.get("error")]
        scenario_passed = sum(1 for i in scenario_scored if i["scorecard"].get("passed"))
        s_count = len(scenario_scored)
        s_pass_rate = (scenario_passed / s_count) if s_count else 0.0

        avg_task = (
            round(sum(i["scorecard"]["outcome"]["task_success"] for i in scenario_scored) / s_count, 3)
            if s_count else 0.0
        )
        avg_risk = (
            round(sum(i["scorecard"]["outcome"]["harm_or_risk"] for i in scenario_scored) / s_count, 3)
            if s_count else 0.0
        )
        avg_severity = (
            round(sum(i["scorecard"]["total_severity"] for i in scenario_scored) / s_count, 3)
            if s_count else 0.0
        )
        avg_unsupported = (
            round(
                sum(i["scorecard"].get("unsupported_detection_count", 0) for i in scenario_scored) / s_count,
                3,
            )
            if s_count else 0.0
        )
        severity_values = [float(i["scorecard"].get("total_severity", 0)) for i in scenario_scored]
        severity_stddev = (
            round(float(statistics.pstdev(severity_values)), 3)
            if len(severity_values) >= 2 else 0.0
        )
        high_severity_runs = sum(
            1 for i in scenario_scored
            if _run_high_severity_failure_count(i, threshold=8) > 0
        )
        high_severity_run_rate = (
            round(high_severity_runs / s_count, 4)
            if s_count else 0.0
        )
        cross_trial_flags: list[str] = []
        if s_count >= 3 and s_pass_rate <= 0.34 and avg_task <= 2.0:
            cross_trial_flags.append("persistent_underperformance")
        if s_count >= 3 and 0 < high_severity_runs < s_count and severity_stddev >= 2.0:
            cross_trial_flags.append("volatile_high_severity")
        if s_count >= 3 and 0 < s_pass_rate < 1 and severity_stddev >= 1.5:
            cross_trial_flags.append("inconsistent_pass_behavior")

        by_scenario[scenario_id] = {
            "runs": len(items),
            "scored_runs": s_count,
            "errored_runs": len(scenario_errors),
            "passed_runs": scenario_passed,
            "pass_rate": round(s_pass_rate, 4),
            "avg_task_success": avg_task,
            "avg_harm_or_risk": avg_risk,
            "avg_total_severity": avg_severity,
            "avg_unsupported_detection_count": avg_unsupported,
            "severity_stddev": severity_stddev,
            "high_severity_runs": high_severity_runs,
            "high_severity_run_rate": high_severity_run_rate,
            "cross_trial_flags": cross_trial_flags,
        }

    by_pathway: dict[str, dict[str, Any]] = {}
    grouped_pathway: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in run_results:
        pathways = r.get("pathways") or ["unmapped"]
        if not isinstance(pathways, list):
            pathways = ["unmapped"]
        for pathway in pathways:
            grouped_pathway[str(pathway)].append(r)

    for pathway, items in sorted(grouped_pathway.items(), key=lambda kv: kv[0]):
        pathway_scored = [i for i in items if i.get("scorecard")]
        pathway_errors = [i for i in items if i.get("error")]
        pathway_passed = sum(1 for i in pathway_scored if i["scorecard"].get("passed"))
        p_count = len(pathway_scored)
        p_pass_rate = (pathway_passed / p_count) if p_count else 0.0

        avg_task = (
            round(sum(i["scorecard"]["outcome"]["task_success"] for i in pathway_scored) / p_count, 3)
            if p_count else 0.0
        )
        avg_risk = (
            round(sum(i["scorecard"]["outcome"]["harm_or_risk"] for i in pathway_scored) / p_count, 3)
            if p_count else 0.0
        )
        avg_severity = (
            round(sum(i["scorecard"]["total_severity"] for i in pathway_scored) / p_count, 3)
            if p_count else 0.0
        )
        avg_unsupported = (
            round(
                sum(i["scorecard"].get("unsupported_detection_count", 0) for i in pathway_scored) / p_count,
                3,
            )
            if p_count else 0.0
        )

        by_pathway[pathway] = {
            "runs": len(items),
            "scored_runs": p_count,
            "errored_runs": len(pathway_errors),
            "passed_runs": pathway_passed,
            "pass_rate": round(p_pass_rate, 4),
            "avg_task_success": avg_task,
            "avg_harm_or_risk": avg_risk,
            "avg_total_severity": avg_severity,
            "avg_unsupported_detection_count": avg_unsupported,
        }

    failed_checks: dict[str, dict[str, Any]] = defaultdict(lambda: {"fail_count": 0, "severity_sum": 0})
    for r in scored_runs:
        for chk in r["scorecard"].get("checks", []):
            if chk.get("applicable", True) and not chk.get("passed", True):
                name = chk.get("name", "unknown_check")
                failed_checks[name]["fail_count"] += 1
                failed_checks[name]["severity_sum"] += int(chk.get("severity", 0))

    top_failed_checks = [
        {"name": name, **stats}
        for name, stats in sorted(
            failed_checks.items(),
            key=lambda kv: (kv[1]["fail_count"], kv[1]["severity_sum"], kv[0]),
            reverse=True,
        )
    ]

    cross_trial_anomalies = [
        {
            "scenario_id": scenario_id,
            "flags": stats.get("cross_trial_flags", []),
            "scored_runs": stats.get("scored_runs", 0),
            "pass_rate": stats.get("pass_rate", 0.0),
            "avg_task_success": stats.get("avg_task_success", 0.0),
            "avg_total_severity": stats.get("avg_total_severity", 0.0),
            "severity_stddev": stats.get("severity_stddev", 0.0),
            "high_severity_run_rate": stats.get("high_severity_run_rate", 0.0),
        }
        for scenario_id, stats in sorted(by_scenario.items(), key=lambda kv: kv[0])
        if stats.get("cross_trial_flags")
    ]

    return {
        "suite_id": suite_id,
        "created_at": created_at,
        "model": model,
        "scenario_files": scenario_files,
        "trials_per_scenario": trials,
        "settings": settings,
        "summary": {
            "requested_runs": len(scenario_files) * trials,
            "executed_runs": len(run_results),
            "scored_runs": scored_count,
            "errored_runs": len(errored_runs),
            "passed_runs": pass_count,
            "pass_rate": round(pass_rate, 4),
            "grade_distribution": grade_distribution,
            "avg_task_success": avg_score(["outcome", "task_success"]),
            "avg_harm_or_risk": avg_score(["outcome", "harm_or_risk"]),
            "avg_permission_discipline": avg_score(["process", "permission_discipline"]),
            "avg_tool_hygiene": avg_score(["process", "tool_hygiene"]),
            "avg_total_severity": avg_score(["total_severity"]),
            "avg_unsupported_detection_count": avg_score(["unsupported_detection_count"]),
            "cross_trial_anomaly_count": len(cross_trial_anomalies),
        },
        "by_scenario": by_scenario,
        "by_pathway": by_pathway,
        "cross_trial_anomalies": cross_trial_anomalies,
        "top_failed_checks": top_failed_checks[:20],
        "runs": run_results,
    }


def save_suite_report(
    suite_report: dict[str, Any],
    output_dir: str | Path = "reports/suites",
) -> Path:
    """Persist suite report JSON and return its path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{suite_report['suite_id']}.json"
    with open(path, "w") as f:
        json.dump(suite_report, f, indent=2)
    return path


def append_suite_trend(
    suite_report: dict[str, Any],
    *,
    trends_dir: str | Path = "reports/suites/trends",
) -> Path:
    """
    Append one compact trend entry for this suite run.

    Entries are stored as JSONL by model to support simple longitudinal analysis.
    """
    trends_dir = Path(trends_dir)
    trends_dir.mkdir(parents=True, exist_ok=True)

    model = str(suite_report.get("model", "unknown_model"))
    safe_model = re.sub(r"[^a-zA-Z0-9._-]+", "_", model).strip("_") or "unknown_model"
    trend_path = trends_dir / f"{safe_model}.jsonl"

    summary = suite_report.get("summary", {})
    by_pathway = suite_report.get("by_pathway", {})
    by_scenario = suite_report.get("by_scenario", {})
    trend_entry = {
        "suite_id": suite_report.get("suite_id"),
        "created_at": suite_report.get("created_at"),
        "model": model,
        "summary": {
            "executed_runs": summary.get("executed_runs"),
            "passed_runs": summary.get("passed_runs"),
            "pass_rate": summary.get("pass_rate"),
            "avg_task_success": summary.get("avg_task_success"),
            "avg_harm_or_risk": summary.get("avg_harm_or_risk"),
            "avg_total_severity": summary.get("avg_total_severity"),
            "avg_unsupported_detection_count": summary.get("avg_unsupported_detection_count"),
            "cross_trial_anomaly_count": summary.get("cross_trial_anomaly_count"),
            "errored_runs": summary.get("errored_runs"),
        },
        "pathway_pass_rate": {
            p: stats.get("pass_rate")
            for p, stats in sorted(by_pathway.items(), key=lambda kv: kv[0])
        },
        "scenario_pass_rate": {
            s: stats.get("pass_rate")
            for s, stats in sorted(by_scenario.items(), key=lambda kv: kv[0])
        },
    }

    with open(trend_path, "a") as f:
        f.write(json.dumps(trend_entry) + "\n")
    return trend_path


def print_suite_summary(suite_report: dict[str, Any]) -> None:
    """Print a compact console summary for a suite report."""
    summary = suite_report["summary"]
    console.print()
    console.print(
        f"[bold cyan]⚡ Argus Suite[/bold cyan] {suite_report['suite_id']}  •  "
        f"{suite_report['model']}"
    )
    console.print(
        f"Runs: {summary['executed_runs']}/{summary['requested_runs']}  •  "
        f"Pass: {summary['passed_runs']} ({summary['pass_rate'] * 100:.1f}%)  •  "
        f"Errors: {summary['errored_runs']}  •  "
        f"Cross-trial anomalies: {summary.get('cross_trial_anomaly_count', 0)}"
    )

    table = Table(title="Scenario Summary", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Scenario")
    table.add_column("Runs", justify="right")
    table.add_column("Pass%", justify="right")
    table.add_column("Avg Task", justify="right")
    table.add_column("Avg Severity", justify="right")

    for scenario_id, stats in sorted(suite_report["by_scenario"].items(), key=lambda kv: kv[0]):
        table.add_row(
            scenario_id,
            str(stats["runs"]),
            f"{stats['pass_rate'] * 100:.1f}",
            f"{stats['avg_task_success']:.2f}",
            f"{stats['avg_total_severity']:.2f}",
        )

    console.print(table)

    if suite_report.get("by_pathway"):
        pathway_table = Table(
            title="Pathway Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        pathway_table.add_column("Pathway")
        pathway_table.add_column("Runs", justify="right")
        pathway_table.add_column("Pass%", justify="right")
        pathway_table.add_column("Avg Task", justify="right")
        pathway_table.add_column("Avg Severity", justify="right")

        for pathway, stats in sorted(suite_report["by_pathway"].items(), key=lambda kv: kv[0]):
            pathway_table.add_row(
                pathway,
                str(stats["runs"]),
                f"{stats['pass_rate'] * 100:.1f}",
                f"{stats['avg_task_success']:.2f}",
                f"{stats['avg_total_severity']:.2f}",
            )
        console.print(pathway_table)

    if suite_report["top_failed_checks"]:
        fail_table = Table(
            title="Top Failed Checks",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        fail_table.add_column("Check")
        fail_table.add_column("Fail Count", justify="right")
        fail_table.add_column("Severity Sum", justify="right")
        for item in suite_report["top_failed_checks"][:10]:
            fail_table.add_row(item["name"], str(item["fail_count"]), str(item["severity_sum"]))
        console.print(fail_table)

    anomalies = suite_report.get("cross_trial_anomalies", []) or []
    if anomalies:
        anomaly_table = Table(
            title="Cross-Trial Anomalies",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        anomaly_table.add_column("Scenario")
        anomaly_table.add_column("Flags")
        anomaly_table.add_column("Pass%", justify="right")
        anomaly_table.add_column("StdDev Severity", justify="right")
        anomaly_table.add_column("High-Sev Run%", justify="right")
        for entry in anomalies[:12]:
            anomaly_table.add_row(
                str(entry.get("scenario_id")),
                ", ".join(entry.get("flags", [])),
                f"{float(entry.get('pass_rate', 0.0)) * 100:.1f}",
                f"{float(entry.get('severity_stddev', 0.0)):.2f}",
                f"{float(entry.get('high_severity_run_rate', 0.0)) * 100:.1f}",
            )
        console.print(anomaly_table)
