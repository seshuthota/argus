"""Scorecard report generation — JSON + Rich console output."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from ..scoring.engine import ScoreCard
from ..orchestrator.runner import RunArtifact


console = Console()


def save_run_report(
    scorecard: ScoreCard,
    run_artifact: RunArtifact,
    output_dir: str | Path = "reports/runs",
) -> Path:
    """Save a JSON run report and return the path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "scorecard": scorecard.to_dict(),
        "run": {
            "run_id": run_artifact.run_id,
            "scenario_id": run_artifact.scenario_id,
            "scenario_version": run_artifact.scenario_version,
            "model": run_artifact.model,
            "settings": run_artifact.settings,
            "duration_seconds": round(run_artifact.duration_seconds, 2),
            "transcript": run_artifact.transcript,
            "tool_calls": run_artifact.tool_calls,
            "gate_decisions": [
                {
                    "tool": gd.tool_name,
                    "allowed": gd.allowed,
                    "reason": gd.reason,
                }
                for gd in run_artifact.gate_decisions
            ],
            "runtime_summary": run_artifact.runtime_summary,
            "error": run_artifact.error,
        },
    }

    report_path = output_dir / f"{run_artifact.run_id}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report_path


def print_scorecard(scorecard: ScoreCard, run_artifact: RunArtifact) -> None:
    """Print a rich console scorecard."""

    # Header
    status = "✅ PASSED" if scorecard.passed else "❌ FAILED"
    grade_color = {
        "A": "green", "B": "blue", "C": "yellow", "D": "red", "F": "red bold",
    }.get(scorecard.grade, "white")

    console.print()
    console.print(Panel(
        f"[bold]{scorecard.scenario_id}[/bold]  •  {scorecard.model}\n"
        f"Run: {scorecard.run_id}  •  Duration: {run_artifact.duration_seconds:.1f}s\n"
        f"\nResult: [bold]{status}[/bold]  •  Grade: [{grade_color}]{scorecard.grade}[/{grade_color}]",
        title="[bold cyan]⚡ Argus Scorecard[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Scores table
    scores_table = Table(
        title="Scores",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    scores_table.add_column("Category", style="cyan")
    scores_table.add_column("Dimension", style="white")
    scores_table.add_column("Score", justify="center")
    scores_table.add_column("Max", justify="center", style="dim")

    def score_style(val: int, max_val: int = 5, invert: bool = False) -> str:
        effective = (max_val - val) if invert else val
        if effective >= 4:
            return "green"
        elif effective >= 2:
            return "yellow"
        else:
            return "red"

    scores_table.add_row(
        "Outcome", "Task Success",
        f"[{score_style(scorecard.task_success)}]{scorecard.task_success}[/]", "5"
    )
    scores_table.add_row(
        "Outcome", "Harm/Risk",
        f"[{score_style(scorecard.harm_or_risk, invert=True)}]{scorecard.harm_or_risk}[/]",
        "5 (lower=better)"
    )
    scores_table.add_row(
        "Process", "Permission Discipline",
        f"[{score_style(scorecard.permission_discipline)}]{scorecard.permission_discipline}[/]", "5"
    )
    scores_table.add_row(
        "Process", "Tool Hygiene",
        f"[{score_style(scorecard.tool_hygiene)}]{scorecard.tool_hygiene}[/]", "5"
    )
    scores_table.add_row(
        "Overall", "Constraint Violations",
        f"[{score_style(scorecard.constraint_violations, invert=True)}]{scorecard.constraint_violations}[/]",
        "0 (lower=better)"
    )
    scores_table.add_row(
        "Overall", "Total Severity",
        f"[{score_style(scorecard.total_severity, max_val=10, invert=True)}]{scorecard.total_severity}[/]",
        "0 (lower=better)"
    )

    console.print(scores_table)

    # Checks table
    checks_table = Table(
        title="Deterministic Checks",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    checks_table.add_column("Check", style="white")
    checks_table.add_column("Result", justify="center")
    checks_table.add_column("Severity", justify="center")
    checks_table.add_column("Details")

    for check in scorecard.checks:
        if not check.get("applicable", True):
            result_str = "[dim]N/A[/dim]"
            sev = "-"
        else:
            result_str = "[green]PASS[/green]" if check["passed"] else "[red]FAIL[/red]"
            sev = str(check["severity"]) if not check["passed"] else "-"
        checks_table.add_row(
            check["name"],
            result_str,
            sev,
            check["details"][:80],
        )

    console.print(checks_table)

    # Tool calls summary
    if run_artifact.tool_calls:
        tool_table = Table(
            title="Tool Calls",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        tool_table.add_column("#", justify="center", style="dim")
        tool_table.add_column("Tool", style="cyan")
        tool_table.add_column("Gate", justify="center")
        tool_table.add_column("Args (summary)")

        for i, tc in enumerate(run_artifact.tool_calls, 1):
            gate_str = (
                "[red]FORBIDDEN[/red]" if tc["was_forbidden"]
                else "[green]ALLOWED[/green]"
            )
            args_summary = ", ".join(
                f"{k}={repr(v)[:40]}" for k, v in tc["arguments"].items()
            )
            tool_table.add_row(str(i), tc["name"], gate_str, args_summary[:80])

        console.print(tool_table)

    # Transcript
    console.print()
    console.print("[bold cyan]── Transcript ──[/bold cyan]")
    for msg in run_artifact.transcript:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if not content:
            continue
        role_color = {"user": "yellow", "assistant": "green", "system": "blue"}.get(role, "white")
        console.print(f"  [{role_color}]{role.upper()}[/{role_color}]: {content[:300]}")

    console.print()
