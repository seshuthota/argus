from __future__ import annotations

import os
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ..rescore import resolve_scenario_path
from ...evaluators.checks import run_all_checks
from ...evaluators.judge import run_llm_judge_comparison
from ...models.adapter import ModelSettings
from ...models.resolve import resolve_model_and_adapter
from ...orchestrator.runner import ScenarioRunner
from ...schema_validator import load_scenario
from ...scoring.engine import compute_scores
from ..scorecard import save_run_report

from .store import (
    atomic_write_json,
    default_matrix_models,
    ensure_setup_visible_context,
    fmt_ts,
    infer_tool_gate_mode,
    load_json,
    now_iso,
    safe_float,
    safe_int,
    summarize_run_report_payload,
)


def jobs_dir(reports_root: Path) -> Path:
    return reports_root / "jobs"


def job_path(reports_root: Path, job_id: str) -> Path:
    return jobs_dir(reports_root) / f"{job_id}.json"


def load_job(reports_root: Path, job_id: str) -> dict[str, Any] | None:
    return load_json(job_path(reports_root, job_id))


def list_jobs(reports_root: Path, *, scenario_id: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    dirp = jobs_dir(reports_root)
    if not dirp.exists():
        return []
    for p in sorted(dirp.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        payload = load_json(p)
        if not payload:
            continue
        if scenario_id and str(payload.get("scenario_id") or "") != scenario_id:
            continue
        out.append(payload)
    return out


def update_job(reports_root: Path, job_id: str, update: dict[str, Any]) -> dict[str, Any]:
    existing = load_job(reports_root, job_id) or {}
    merged = dict(existing)
    merged.update(update)
    merged["updated_at"] = now_iso()
    atomic_write_json(job_path(reports_root, job_id), merged)
    return merged


def _parse_job_pid(job_id: str) -> int | None:
    # Expected: job_<timestamp>_<pid>_<threadid>
    try:
        parts = str(job_id or "").split("_")
        if len(parts) < 4:
            return None
        pid_part = parts[-2]
        pid = int(pid_part)
        return pid if pid > 0 else None
    except Exception:
        return None


def reconcile_orphaned_jobs(reports_root: Path) -> None:
    """Mark previously-running jobs as abandoned after a server restart."""
    current_pid = os.getpid()
    dirp = jobs_dir(reports_root)
    if not dirp.exists():
        return
    for p in dirp.glob("*.json"):
        payload = load_json(p)
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"running", "queued"}:
            continue
        job_pid: int | None = None
        raw = payload.get("server_pid")
        if isinstance(raw, int) and not isinstance(raw, bool):
            job_pid = raw
        if job_pid is None:
            job_pid = _parse_job_pid(str(payload.get("job_id") or p.stem))
        if job_pid is None or job_pid == current_pid:
            continue
        payload["status"] = "abandoned"
        payload["abandoned_at"] = now_iso()
        payload["error"] = "server_restarted"
        payload["updated_at"] = now_iso()
        atomic_write_json(p, payload)


def provider_key_for_matrix_model(model: str) -> str:
    """Best-effort provider bucketing for concurrency limits."""
    m = str(model or "").strip().lower()
    if not m:
        return "other"
    if m.startswith("openrouter/") or m.startswith("stepfun/"):
        return "openrouter"
    if m.startswith("minimax-") or m.startswith("minimax/") or m.startswith("minimax"):
        return "minimax"
    for prefix in ("openai/", "anthropic/", "google/", "gemini/", "groq/", "mistral/", "cohere/"):
        if m.startswith(prefix):
            return prefix.rstrip("/")
    return "other"


def _job_cancel_requested(reports_root: Path, job_id: str) -> bool:
    payload = load_job(reports_root, job_id) or {}
    return bool(payload.get("cancel_requested", False))


def start_matrix_job_thread(reports_root: Path, job_id: str) -> None:
    t = threading.Thread(target=_run_matrix_job, args=(reports_root, job_id), daemon=True)
    t.start()


def _run_matrix_job(reports_root: Path, job_id: str) -> None:
    errors: list[dict[str, Any]] = []
    run_ids: list[str] = []
    completed = 0

    root = reports_root

    try:
        job = load_job(root, job_id) or {}
        scenario_id = str(job.get("scenario_id") or "").strip()
        if not scenario_id:
            update_job(root, job_id, {"status": "error", "error": "missing_scenario_id"})
            return

        scenario_path = resolve_scenario_path(scenario_id=scenario_id, reports_root=root)
        if scenario_path is None or not scenario_path.exists():
            update_job(root, job_id, {"status": "error", "error": f"scenario_not_found:{scenario_id}"})
            return

        try:
            scenario = load_scenario(scenario_path)
        except Exception as err:
            update_job(root, job_id, {"status": "error", "error": f"scenario_load_failed:{str(err)[:200]}"})
            return

        models = job.get("models") or []
        tool_modes = job.get("tool_modes") or []
        if not isinstance(models, list) or not models:
            models = default_matrix_models()
        if not isinstance(tool_modes, list) or not tool_modes:
            tool_modes = ["enforce", "raw_tools_terminate", "allow_forbidden_tools"]

        temperature = safe_float(job.get("temperature"), default=0.0)
        max_tokens = safe_int(job.get("max_tokens"), default=2048)
        max_turns = safe_int(job.get("max_turns"), default=10)
        seed = job.get("seed")
        seed = int(seed) if isinstance(seed, int) and not isinstance(seed, bool) else 42
        seed_step = safe_int(job.get("seed_step"), default=1)
        ai_compare = bool(job.get("ai_compare", False))
        judge_model = str(job.get("judge_model") or "MiniMax-M2.5").strip()

        if "timeout_s" in job:
            timeout_s = safe_float(job.get("timeout_s"), default=0.0)
            timeout_s = timeout_s if timeout_s > 0 else None
        else:
            timeout_env = os.getenv("ARGUS_MODEL_TIMEOUT_S", "").strip()
            try:
                timeout_s = float(timeout_env) if timeout_env else 0.0
            except Exception:
                timeout_s = 0.0
            timeout_s = timeout_s if timeout_s > 0 else 120.0

        planned_items: list[dict[str, Any]] = []
        run_index = 0
        for m in models:
            for tm in tool_modes:
                run_index += 1
                trial_seed = seed + ((run_index - 1) * seed_step)
                planned_items.append({"index": run_index, "model": str(m), "tool_mode": str(tm), "seed": trial_seed})

        provider_limit_env = os.getenv("ARGUS_PROVIDER_RUN_CONCURRENCY", "").strip()
        provider_limit = safe_int(provider_limit_env, default=2) if provider_limit_env else 2
        provider_limit = max(1, min(provider_limit, 8))
        provider_semas: dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(provider_limit))

        provider_counts = Counter(provider_key_for_matrix_model(item.get("model", "")) for item in planned_items)
        provider_order: list[str] = []
        for item in planned_items:
            pk = provider_key_for_matrix_model(item.get("model", ""))
            if pk not in provider_order:
                provider_order.append(pk)
        per_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in planned_items:
            per_provider[provider_key_for_matrix_model(item.get("model", ""))].append(item)
        interleaved: list[dict[str, Any]] = []
        remaining = True
        while remaining:
            remaining = False
            for pk in provider_order:
                queue = per_provider.get(pk) or []
                if not queue:
                    continue
                interleaved.append(queue.pop(0))
                remaining = True
        planned_items = interleaved if interleaved else planned_items

        max_workers = sum(min(provider_limit, int(cnt)) for cnt in provider_counts.values()) if provider_counts else 1
        max_workers = max(1, min(int(max_workers), 16, len(planned_items) if planned_items else 1))

        update_job(
            root,
            job_id,
            {
                "status": "running",
                "started_at": now_iso(),
                "total_runs": len(planned_items),
                "completed_runs": 0,
                "errors": [],
                "run_ids": [],
                "concurrency": {
                    "per_provider": provider_limit,
                    "providers": dict(provider_counts),
                    "max_workers": max_workers,
                    "queue_strategy": "round_robin_providers",
                },
            },
        )

        ai_compare_ready = False
        if ai_compare:
            try:
                _ = resolve_model_and_adapter(model=judge_model, api_key=None, api_base=None)
                ai_compare_ready = True
            except Exception as err:
                errors.append({"stage": "judge_resolve", "error": str(err)[:200], "judge_model": judge_model})
                ai_compare_ready = False

        lock = threading.Lock()
        in_flight: dict[str, dict[str, Any]] = {}
        runs_meta: list[dict[str, Any]] = []

        def _mark_started(item: dict[str, Any]) -> None:
            info = {
                "index": item["index"],
                "model": item["model"],
                "tool_mode": item["tool_mode"],
                "seed": item["seed"],
                "started_at": now_iso(),
            }
            with lock:
                in_flight[str(item["index"])] = info
                update_job(root, job_id, {"current_run": info, "in_flight": list(in_flight.values())[-20:]})

        def _mark_finished(
            *,
            item: dict[str, Any],
            run_id: str | None = None,
            report_path: str | None = None,
            error: str | None = None,
            score_meta: dict[str, Any] | None = None,
        ) -> None:
            nonlocal completed
            info = dict(item)
            info["finished_at"] = now_iso()
            if run_id:
                info["run_id"] = run_id
            if report_path:
                info["report_path"] = report_path
            if error:
                info["error"] = error
            with lock:
                completed += 1
                in_flight.pop(str(item["index"]), None)
                if run_id:
                    run_ids.append(run_id)
                if error:
                    errors.append({"model": item.get("model"), "tool_mode": item.get("tool_mode"), "error": error})
                # Persist per-cell run metadata so the UI matrix can map exact
                # (requested_model, tool_mode) pairs even when run artifacts store a resolved model name.
                if score_meta:
                    runs_meta.append(score_meta)
                update_job(
                    root,
                    job_id,
                    {
                        "completed_runs": completed,
                        "run_ids": run_ids[-200:],
                        "runs": runs_meta[-500:],
                        "errors": errors[-50:],
                        "current_run": None,
                        "in_flight": list(in_flight.values())[-20:],
                    },
                )

        def _run_one(item: dict[str, Any]) -> None:
            if _job_cancel_requested(root, job_id):
                _mark_finished(item=item, error="canceled")
                return

            model = str(item.get("model") or "").strip()
            tool_mode = str(item.get("tool_mode") or "").strip()
            trial_seed = safe_int(item.get("seed"), default=42)

            terminate_on_blocked = tool_mode == "raw_tools_terminate"
            allow_forbidden = tool_mode == "allow_forbidden_tools"

            _mark_started(item)
            try:
                provider = provider_key_for_matrix_model(model)
                with provider_semas[provider]:
                    resolved = resolve_model_and_adapter(model=model, api_key=None, api_base=None)
                    settings = ModelSettings(
                        model=resolved.resolved_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        seed=trial_seed,
                        timeout_s=timeout_s,
                    )
                    runner = ScenarioRunner(
                        adapter=resolved.adapter,
                        settings=settings,
                        max_turns=max_turns,
                        terminate_on_blocked_tool_call=terminate_on_blocked,
                        allow_forbidden_tools=allow_forbidden,
                    )
                    artifact = runner.run(scenario)

                if getattr(artifact, "error", None):
                    _mark_finished(item=item, error=str(artifact.error))
                    return

                check_results = run_all_checks(
                    artifact,
                    scenario,
                    confidence_reports_root=root,
                )
                llm_meta = None
                if ai_compare and ai_compare_ready:
                    judge_provider = provider_key_for_matrix_model(judge_model)

                    def _do_compare() -> dict[str, Any]:
                        judge_resolve = resolve_model_and_adapter(model=judge_model, api_key=None, api_base=None)
                        return run_llm_judge_comparison(
                            check_results=check_results,
                            run_artifact=artifact,
                            scenario=scenario,
                            adapter=judge_resolve.adapter,
                            base_settings=settings,
                            judge_model=judge_resolve.resolved_model,
                            judge_temperature=0.0,
                            judge_max_tokens=512,
                            only_required=True,
                            evaluate_passed_success_checks=False,
                        )

                    try:
                        with provider_semas[judge_provider]:
                            llm_meta = _do_compare()
                        artifact.runtime_summary["llm_judge_compare"] = llm_meta
                    except Exception as err:
                        with lock:
                            errors.append(
                                {
                                    "model": model,
                                    "tool_mode": tool_mode,
                                    "error": f"ai_compare_failed:{str(err)[:200]}",
                                }
                            )

                scorecard = compute_scores(artifact, check_results, scenario)
                if llm_meta:
                    by_name = {
                        str(e.get("check_name")): e
                        for e in (llm_meta.get("entries") or [])
                        if isinstance(e, dict) and e.get("check_name") and "judge_passed" in e
                    }
                    for chk in scorecard.checks:
                        entry = by_name.get(str(chk.get("name") or ""))
                        if not entry:
                            continue
                        chk["llm_judge"] = {
                            "mode": "compare",
                            "model": str(llm_meta.get("judge_model") or ""),
                            "passed": bool(entry.get("judge_passed")),
                            "confidence": entry.get("confidence"),
                            "reason": entry.get("reason"),
                        }
                        chk["llm_judge_disagrees"] = bool(chk.get("passed")) != bool(entry.get("judge_passed"))

                report_path = save_run_report(scorecard, artifact)
                run_id = str(artifact.run_id)
                score_meta = {
                    "index": int(item["index"]),
                    "run_id": run_id,
                    "scenario_id": str(scenario_id),
                    "model": str(model),
                    "tool_mode": str(tool_mode),
                    "tool_gate_mode": infer_tool_gate_mode(getattr(artifact, "runtime_summary", {})),
                    "passed": bool(getattr(scorecard, "passed", False)),
                    "grade": str(getattr(scorecard, "grade", "?")),
                    "duration_seconds": safe_float(getattr(artifact, "duration_seconds", 0.0)),
                    "total_severity": safe_int(getattr(scorecard, "total_severity", 0)),
                    "updated_at": now_iso(),
                }
                _mark_finished(
                    item=item,
                    run_id=run_id,
                    report_path=str(report_path),
                    score_meta=score_meta,
                )
            except Exception as err:
                try:
                    _mark_finished(item=item, error=f"run_failed:{str(err)[:200]}")
                except Exception:
                    return

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_run_one, item) for item in planned_items]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as err:
                    with lock:
                        errors.append({"stage": "threadpool_future", "error": str(err)[:200]})

        status = "done" if not errors else "done_with_errors"
        if _job_cancel_requested(root, job_id):
            status = "canceled"
        update_job(
            root,
            job_id,
            {
                "status": status,
                "finished_at": now_iso(),
                "completed_runs": completed,
                "run_ids": run_ids[-200:],
                "runs": runs_meta[-500:],
                "errors": errors[-50:],
                "current_run": None,
                "in_flight": [],
            },
        )
    except Exception as err:
        errors.append({"stage": "unhandled_exception", "error": str(err)[:400]})
        update_job(
            root,
            job_id,
            {
                "status": "error",
                "finished_at": now_iso(),
                "completed_runs": completed,
                "run_ids": run_ids[-200:],
                "errors": errors[-50:],
            },
        )


def create_matrix_job_record(
    reports_root: Path,
    *,
    scenario_id: str,
    models: list[str],
    tool_modes: list[str],
    temperature: float,
    max_tokens: int,
    max_turns: int,
    seed: int,
    seed_step: int,
    ai_compare: bool,
    judge_model: str,
    timeout_s: float | None,
) -> dict[str, Any]:
    job_id = f"job_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{os.getpid()}_{threading.get_ident()}"
    job: dict[str, Any] = {
        "job_id": job_id,
        "kind": "run_matrix",
        "scenario_id": scenario_id,
        "scenario_path": str(resolve_scenario_path(scenario_id=scenario_id, reports_root=reports_root) or ""),
        "server_pid": os.getpid(),
        "models": models,
        "tool_modes": tool_modes,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "max_turns": max_turns,
        "seed": seed,
        "seed_step": seed_step,
        **({"timeout_s": timeout_s} if timeout_s is not None else {}),
        "ai_compare": ai_compare,
        "judge_model": judge_model,
        "status": "queued",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "total_runs": len(models) * len(tool_modes),
        "completed_runs": 0,
        "run_ids": [],
        "runs": [],
        "errors": [],
    }
    atomic_write_json(job_path(reports_root, job_id), job)
    return job


def enrich_job_for_ui(reports_root: Path, job: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(job)

    run_summaries: list[dict[str, Any]] = []
    if isinstance(job.get("runs"), list):
        for item in job.get("runs") or []:
            if isinstance(item, dict) and item.get("run_id"):
                run_summaries.append(item)
    else:
        for rid in job.get("run_ids") or []:
            if not isinstance(rid, str) or not rid.strip():
                continue
            report_path = reports_root / "runs" / f"{rid}.json"
            payload = load_json(report_path)
            if not isinstance(payload, dict):
                continue
            ensure_setup_visible_context(payload, reports_root=reports_root)
            run_summaries.append(summarize_run_report_payload(payload, updated_at=fmt_ts(report_path)))

    errors = job.get("errors") if isinstance(job.get("errors"), list) else []
    error_map: dict[str, str] = {}
    for e in errors:
        if not isinstance(e, dict):
            continue
        m = str(e.get("model") or "").strip()
        tm = str(e.get("tool_mode") or "").strip()
        msg = str(e.get("error") or "").strip()
        if m and tm and msg:
            error_map[f"{m}::{tm}"] = msg

    models = enriched.get("models") if isinstance(enriched.get("models"), list) else []
    tool_modes = enriched.get("tool_modes") if isinstance(enriched.get("tool_modes"), list) else []
    by_key: dict[str, dict[str, Any]] = {}
    for rs in run_summaries:
        if not isinstance(rs, dict):
            continue
        m = str(rs.get("model") or "").strip()
        tm = str(rs.get("tool_mode") or rs.get("tool_gate_mode") or "").strip()
        rid = str(rs.get("run_id") or "").strip()
        if m and tm and rid:
            by_key[f"{m}::{tm}"] = rs

    matrix_items: list[dict[str, Any]] = []
    for m in models:
        for tm in tool_modes:
            key = f"{m}::{tm}"
            item: dict[str, Any] = {"model": m, "tool_mode": tm}
            rs = by_key.get(key)
            if rs:
                item["run"] = rs
            elif key in error_map:
                item["error"] = error_map[key]
            matrix_items.append(item)

    enriched["run_summaries"] = run_summaries[-500:]
    enriched["matrix_items"] = matrix_items
    return enriched
