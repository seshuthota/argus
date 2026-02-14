#!/usr/bin/env python3
"""Run one Argus scenario and print full interaction details."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus.cli import _resolve_model_and_adapter
from argus.evaluators.checks import run_all_checks
from argus.evaluators.judge import apply_llm_judge_overrides
from argus.models.adapter import ModelSettings
from argus.orchestrator.runner import ScenarioRunner
from argus.reporting.scorecard import save_run_report
from argus.schema_validator import validate_scenario_file
from argus.scoring.engine import compute_scores


class _Printer:
    def __init__(self, log_path: str | None) -> None:
        self._lines: list[str] = []
        self._log_path = Path(log_path) if log_path else None

    def line(self, text: str = "") -> None:
        print(text)
        self._lines.append(text)

    def write_log(self) -> Path | None:
        if self._log_path is None:
            return None
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.write_text("\n".join(self._lines).rstrip() + "\n")
        return self._log_path


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True)


def _print_transcript(pr: _Printer, transcript: list[dict[str, Any]]) -> None:
    pr.line("\n=== TRANSCRIPT ===")
    if not transcript:
        pr.line("(no transcript messages)")
        return
    for idx, msg in enumerate(transcript, start=1):
        role = str(msg.get("role", "unknown"))
        turn = msg.get("turn", "-")
        source = msg.get("source", "-")
        content = str(msg.get("content", ""))
        pr.line(f"[{idx}] turn={turn} role={role} source={source}")
        pr.line(content)
        pr.line("-")


def _print_tool_calls(pr: _Printer, tool_calls: list[dict[str, Any]]) -> None:
    pr.line("\n=== TOOL CALLS ===")
    if not tool_calls:
        pr.line("(no tool calls)")
        return
    for idx, tc in enumerate(tool_calls, start=1):
        pr.line(
            f"[{idx}] turn={tc.get('turn', '-')} name={tc.get('name')} "
            f"executed={tc.get('executed')} forbidden={tc.get('was_forbidden')} "
            f"gate={tc.get('gate_decision')}"
        )
        pr.line("args:")
        pr.line(_json(tc.get("arguments", {})))
        pr.line("result:")
        pr.line(_json(tc.get("result", {})))
        pr.line("-")


def _print_gate_decisions(pr: _Printer, gate_decisions: list[Any]) -> None:
    pr.line("\n=== GATE DECISIONS ===")
    if not gate_decisions:
        pr.line("(no gate decisions)")
        return
    for idx, gd in enumerate(gate_decisions, start=1):
        pr.line(
            f"[{idx}] tool={gd.tool_name} allowed={gd.allowed} reason={gd.reason} "
            f"timestamp={gd.timestamp:.6f}"
        )


def _print_events(pr: _Printer, events: list[Any]) -> None:
    pr.line("\n=== EVENTS ===")
    if not events:
        pr.line("(no events)")
        return
    for idx, ev in enumerate(events, start=1):
        pr.line(f"[{idx}] type={ev.type} timestamp={ev.timestamp:.6f}")
        pr.line(_json(ev.data))
        pr.line("-")


def _print_checks(pr: _Printer, checks: list[Any]) -> None:
    pr.line("\n=== CHECK RESULTS ===")
    if not checks:
        pr.line("(no checks)")
        return
    for idx, chk in enumerate(checks, start=1):
        status = "PASS" if chk.passed else "FAIL"
        applicability = "applicable" if chk.applicable else "n/a"
        pr.line(
            f"[{idx}] {status} kind={chk.kind} name={chk.name} "
            f"severity={chk.severity} weight={chk.weight} confidence={chk.confidence:.2f} {applicability}"
        )
        pr.line(f"details: {chk.details}")
        if chk.evidence:
            pr.line("evidence:")
            for item in chk.evidence:
                pr.line(f"  - {item}")
        if chk.unsupported_clauses:
            pr.line("unsupported_clauses:")
            for clause in chk.unsupported_clauses:
                pr.line(f"  - {clause}")
        pr.line("-")


def _print_scorecard_summary(pr: _Printer, scorecard: Any) -> None:
    pr.line("\n=== SCORECARD SUMMARY ===")
    pr.line(f"run_id: {scorecard.run_id}")
    pr.line(f"scenario_id: {scorecard.scenario_id}")
    pr.line(f"model: {scorecard.model}")
    pr.line(f"passed: {scorecard.passed}")
    pr.line(f"grade: {scorecard.grade}")
    pr.line(f"task_success: {scorecard.task_success}/5")
    pr.line(f"harm_or_risk: {scorecard.harm_or_risk}/5 (lower is better)")
    pr.line(f"permission_discipline: {scorecard.permission_discipline}/5")
    pr.line(f"tool_hygiene: {scorecard.tool_hygiene}/5")
    pr.line(f"constraint_violations: {scorecard.constraint_violations}")
    pr.line(f"total_severity: {scorecard.total_severity}")
    pr.line(f"unsupported_detection_count: {scorecard.unsupported_detection_count}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one Argus scenario and print complete interaction details."
    )
    parser.add_argument("--scenario", required=True, help="Scenario YAML path")
    parser.add_argument("--model", required=True, help="Model id, e.g. MiniMax-M2.1 or stepfun/step-3.5-flash:free")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--api-base", default=None)
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Enable LLM semantic judge overlay for unmet success checks.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Optional model for judge calls (defaults to run model).",
    )
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--judge-max-tokens", type=int, default=512)
    parser.add_argument("--log-file", default=None, help="Optional file path to also save printed output")
    parser.add_argument(
        "--report-dir",
        default="reports/runs",
        help="Directory for saved run JSON report",
    )
    parser.add_argument(
        "--no-save-report",
        action="store_true",
        help="Do not save JSON run report",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    pr = _Printer(log_path=args.log_file)
    load_dotenv()

    scenario, errors = validate_scenario_file(args.scenario)
    if errors:
        pr.line("Scenario validation failed:")
        for err in errors:
            pr.line(f"- {err}")
        pr.write_log()
        return 1
    if scenario is None:
        pr.line("Failed to load scenario.")
        pr.write_log()
        return 1
    if args.max_tokens < 1 or args.max_turns < 1 or args.judge_max_tokens < 1:
        pr.line("Invalid numeric args: max-tokens/max-turns/judge-max-tokens must be >= 1")
        pr.write_log()
        return 1

    try:
        resolved_model, adapter = _resolve_model_and_adapter(
            model=args.model,
            api_key=args.api_key,
            api_base=args.api_base,
            emit_provider_note=False,
        )
    except SystemExit as err:
        pr.line(f"Model/provider resolution failed (exit={err.code}).")
        pr.write_log()
        return int(err.code) if isinstance(err.code, int) else 1

    settings = ModelSettings(
        model=resolved_model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        seed=args.seed,
    )
    runner = ScenarioRunner(adapter=adapter, settings=settings, max_turns=args.max_turns)

    pr.line("=== RUN CONFIG ===")
    pr.line(f"scenario: {args.scenario}")
    pr.line(f"scenario_id: {scenario.get('id')}")
    pr.line(f"model_input: {args.model}")
    pr.line(f"model_resolved: {resolved_model}")
    pr.line(f"temperature: {args.temperature}")
    pr.line(f"max_tokens: {args.max_tokens}")
    pr.line(f"seed: {args.seed}")
    pr.line(f"max_turns: {args.max_turns}")

    artifact = runner.run(scenario)
    if artifact.error:
        pr.line("\nRun failed with error:")
        pr.line(artifact.error)
        _print_events(pr, artifact.events)
        log_path = pr.write_log()
        if log_path is not None:
            pr.line(f"\nVerbose log saved: {log_path}")
        return 1

    checks = run_all_checks(artifact, scenario)
    if args.llm_judge:
        judge_adapter = adapter
        judge_model_resolved = resolved_model
        if args.judge_model:
            judge_model_resolved, judge_adapter = _resolve_model_and_adapter(
                model=args.judge_model,
                api_key=args.api_key,
                api_base=args.api_base,
                emit_provider_note=False,
            )
        checks, judge_meta = apply_llm_judge_overrides(
            check_results=checks,
            run_artifact=artifact,
            scenario=scenario,
            adapter=judge_adapter,
            base_settings=settings,
            judge_model=judge_model_resolved,
            judge_temperature=args.judge_temperature,
            judge_max_tokens=args.judge_max_tokens,
        )
        artifact.runtime_summary["llm_judge"] = judge_meta
        pr.line("\nLLM judge enabled:")
        pr.line(_json(judge_meta))
    scorecard = compute_scores(artifact, checks, scenario)

    report_path: Path | None = None
    if not args.no_save_report:
        report_path = save_run_report(scorecard, artifact, output_dir=args.report_dir)

    pr.line(f"\nRun duration: {artifact.duration_seconds:.3f}s")
    if report_path is not None:
        pr.line(f"Run report saved: {report_path}")

    _print_transcript(pr, artifact.transcript)
    _print_tool_calls(pr, artifact.tool_calls)
    _print_gate_decisions(pr, artifact.gate_decisions)
    _print_events(pr, artifact.events)
    _print_checks(pr, checks)

    pr.line("\n=== RUNTIME SUMMARY ===")
    pr.line(_json(artifact.runtime_summary))

    _print_scorecard_summary(pr, scorecard)

    log_path = pr.write_log()
    if log_path is not None:
        pr.line(f"\nVerbose log saved: {log_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
