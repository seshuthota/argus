from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ...evaluators.judge import run_llm_judge_comparison
from ...models.adapter import ModelSettings
from ...models.resolve import resolve_model_and_adapter
from ...schema_validator import load_scenario
from ..rescore import rescore_run_report, resolve_scenario_path

from . import jobs as jobs_mod
from .store import (
    atomic_write_json,
    build_check_results_from_scorecard,
    build_review_queue,
    default_matrix_models,
    ensure_setup_visible_context,
    list_run_reports,
    list_scenarios,
    list_suite_reports,
    load_json,
    now_iso,
    parse_bool,
    read_scenario_detail,
    safe_float,
    safe_int,
)
from .timeline import normalize_timeline


def _json_response(status: int, payload: dict[str, Any]) -> Response:
    data = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    return Response(
        content=data,
        status_code=status,
        media_type="application/json; charset=utf-8",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


async def _read_json_dict(request: Request, *, required: bool = False) -> tuple[dict[str, Any] | None, Response | None]:
    raw = await request.body()
    if not raw:
        if required:
            return None, _json_response(400, {"error": "missing_body"})
        return {}, None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return None, _json_response(400, {"error": "invalid_json"})
    if isinstance(decoded, dict):
        return decoded, None
    # Legacy behavior: treat non-object JSON as empty dict.
    return {}, None


def create_api_router(*, reports_root: Path) -> APIRouter:
    root = reports_root
    router = APIRouter()

    @router.get("/api/suites")
    async def api_suites(request: Request) -> Response:
        suites = list_suite_reports(root)
        page = safe_int(request.query_params.get("page"), default=1)
        page_size = safe_int(request.query_params.get("page_size"), default=50)
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 500))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        items = suites[start:end]
        return _json_response(
            200, {"items": items, "total": len(suites), "page": safe_page, "page_size": safe_page_size}
        )

    @router.get("/api/runs")
    async def api_runs(request: Request) -> Response:
        scenario_id = request.query_params.get("scenario_id")
        model = request.query_params.get("model")
        grade = request.query_params.get("grade")
        passed = parse_bool(request.query_params.get("passed"))
        tool_mode = request.query_params.get("tool_mode")
        latest_only = bool(parse_bool(request.query_params.get("latest_only")))
        page = safe_int(request.query_params.get("page"), default=1)
        page_size = safe_int(request.query_params.get("page_size"), default=50)
        from .store import query_run_reports

        return _json_response(
            200,
            query_run_reports(
                root,
                scenario_id=scenario_id,
                model=model,
                passed=passed,
                grade=grade,
                tool_mode=tool_mode,
                latest_only=latest_only,
                page=page,
                page_size=page_size,
            ),
        )

    @router.get("/api/review-queue")
    async def api_review_queue(request: Request) -> Response:
        include_passed = bool(parse_bool(request.query_params.get("include_passed")))
        latest_only_raw = parse_bool(request.query_params.get("latest_only"))
        latest_only = True if latest_only_raw is None else latest_only_raw
        scenario_id = request.query_params.get("scenario_id")
        model = request.query_params.get("model")
        page = safe_int(request.query_params.get("page"), default=1)
        page_size = safe_int(request.query_params.get("page_size"), default=50)
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 500))

        result = build_review_queue(root, include_passed=include_passed, latest_only=latest_only, scenario_id=scenario_id, model=model)
        all_items = result.get("items", []) or []
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        items = all_items[start:end]
        return _json_response(
            200,
            {
                "items": items,
                "total": len(all_items),
                "page": safe_page,
                "page_size": safe_page_size,
                "summary": result.get("summary", {}),
                "filters": {
                    "include_passed": include_passed,
                    "latest_only": latest_only,
                    "scenario_id": scenario_id,
                    "model": model,
                },
            },
        )

    @router.get("/api/scenarios")
    async def api_scenarios(request: Request) -> Response:
        scenarios = list_scenarios(root)
        page = safe_int(request.query_params.get("page"), default=1)
        page_size = safe_int(request.query_params.get("page_size"), default=100)
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 500))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        items = scenarios[start:end]
        return _json_response(
            200, {"items": items, "total": len(scenarios), "page": safe_page, "page_size": safe_page_size}
        )

    @router.get("/api/scenarios/{scenario_id}")
    async def api_scenario_detail(scenario_id: str) -> Response:
        detail = read_scenario_detail(root, scenario_id)
        if detail is None:
            found = None
            for item in list_scenarios(root):
                if str(item.get("scenario_id") or "") == str(scenario_id):
                    found = item
                    break
            if not found:
                return _json_response(404, {"error": "scenario_not_found", "scenario_id": scenario_id})
            payload = dict(found)
            payload["has_yaml"] = bool(found.get("has_yaml", False))
            return _json_response(200, payload)

        if detail.get("error") == "scenario_invalid_yaml":
            return _json_response(500, {"error": "scenario_invalid_yaml"})
        if detail.get("error") == "scenario_read_failed":
            return _json_response(500, {"error": "scenario_read_failed", "message": str(detail.get("message") or "")[:200]})
        return _json_response(200, detail)

    @router.get("/api/models")
    async def api_models() -> Response:
        models = default_matrix_models()
        return _json_response(200, {"items": [{"model": m} for m in models], "total": len(models)})

    @router.get("/api/scenarios/{scenario_id}/jobs")
    async def api_scenario_jobs(scenario_id: str, request: Request) -> Response:
        jobs = jobs_mod.list_jobs(root, scenario_id=scenario_id)
        page = safe_int(request.query_params.get("page"), default=1)
        page_size = safe_int(request.query_params.get("page_size"), default=20)
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        items = jobs[start:end]
        return _json_response(200, {"items": items, "total": len(jobs), "page": safe_page, "page_size": safe_page_size})

    @router.get("/api/jobs/{job_id}")
    async def api_job(job_id: str) -> Response:
        job = jobs_mod.load_job(root, job_id)
        if job is None:
            return _json_response(404, {"error": "job_not_found", "job_id": job_id})
        return _json_response(200, jobs_mod.enrich_job_for_ui(root, job))

    @router.get("/api/scenarios/{scenario_id}/runs")
    async def api_scenario_runs(scenario_id: str, request: Request) -> Response:
        model = request.query_params.get("model")
        grade = request.query_params.get("grade")
        passed = parse_bool(request.query_params.get("passed"))
        tool_mode = request.query_params.get("tool_mode")
        latest_only = bool(parse_bool(request.query_params.get("latest_only")))
        page = safe_int(request.query_params.get("page"), default=1)
        page_size = safe_int(request.query_params.get("page_size"), default=50)
        from .store import query_run_reports

        return _json_response(
            200,
            query_run_reports(
                root,
                scenario_id=scenario_id,
                model=model,
                passed=passed,
                grade=grade,
                tool_mode=tool_mode,
                latest_only=latest_only,
                page=page,
                page_size=page_size,
            ),
        )

    @router.get("/api/runs/{run_id}/timeline")
    async def api_run_timeline(run_id: str, request: Request) -> Response:
        report_path = root / "runs" / f"{run_id}.json"
        payload = load_json(report_path)
        if payload is None:
            return _json_response(404, {"error": "run_not_found", "run_id": run_id})
        ensure_setup_visible_context(payload, reports_root=root)
        scorecard = payload.get("scorecard", {}) or {}
        run = payload.get("run", {}) or {}
        scenario_id = str(scorecard.get("scenario_id") or run.get("scenario_id") or "unknown")
        model = str(scorecard.get("model") or run.get("model") or "unknown")
        normalized = normalize_timeline(payload)
        event_types = request.query_params.get("event_types")
        if event_types:
            allowed_types = {part.strip() for part in event_types.split(",") if part.strip()}
            normalized = [event for event in normalized if event.get("type") in allowed_types]
        return _json_response(200, {"run_id": run_id, "scenario_id": scenario_id, "model": model, "step_count": len(normalized), "steps": normalized})

    @router.get("/api/runs/{run_id}")
    async def api_run(run_id: str) -> Response:
        report_path = root / "runs" / f"{run_id}.json"
        payload = load_json(report_path)
        if payload is None:
            return _json_response(404, {"error": "run_not_found", "run_id": run_id})
        ensure_setup_visible_context(payload, reports_root=root)
        return _json_response(200, payload)

    @router.get("/api/suites/{suite_id}")
    async def api_suite(suite_id: str) -> Response:
        report_path = root / "suites" / f"{suite_id}.json"
        payload = load_json(report_path)
        if payload is None:
            return _json_response(404, {"error": "suite_not_found", "suite_id": suite_id})
        return _json_response(200, payload)

    @router.post("/api/scenarios/{scenario_id}/run-matrix")
    async def api_run_matrix(scenario_id: str, request: Request) -> Response:
        body, err_resp = await _read_json_dict(request)
        if err_resp is not None:
            return err_resp
        assert body is not None

        models = body.get("models")
        tool_modes = body.get("tool_modes")
        if not isinstance(models, list) or not models:
            models = default_matrix_models()
        models = [str(m).strip() for m in models if str(m).strip()]
        if not isinstance(tool_modes, list) or not tool_modes:
            tool_modes = ["enforce", "raw_tools_terminate", "allow_forbidden_tools"]
        tool_modes = [str(m).strip() for m in tool_modes if str(m).strip()]

        max_tokens = safe_int(body.get("max_tokens"), default=2048)
        max_turns = safe_int(body.get("max_turns"), default=10)
        temperature = safe_float(body.get("temperature"), default=0.0)
        seed = body.get("seed")
        seed = int(seed) if isinstance(seed, int) and not isinstance(seed, bool) else 42
        seed_step = safe_int(body.get("seed_step"), default=1)
        ai_compare = bool(body.get("ai_compare", False))
        judge_model = str(body.get("judge_model") or "MiniMax-M2.5").strip()
        timeout_s_raw = body.get("timeout_s")
        timeout_s = safe_float(timeout_s_raw, default=0.0) if timeout_s_raw is not None else None

        job = jobs_mod.create_matrix_job_record(
            root,
            scenario_id=scenario_id,
            models=models,
            tool_modes=tool_modes,
            temperature=temperature,
            max_tokens=max_tokens,
            max_turns=max_turns,
            seed=seed,
            seed_step=seed_step,
            ai_compare=ai_compare,
            judge_model=judge_model,
            timeout_s=timeout_s,
        )
        jobs_mod.start_matrix_job_thread(root, job["job_id"])
        return _json_response(200, {"status": "ok", "job_id": job["job_id"]})

    @router.post("/api/runs/{run_id}/judge-compare")
    async def api_judge_compare(run_id: str, request: Request) -> Response:
        body, err_resp = await _read_json_dict(request)
        if err_resp is not None:
            return err_resp
        assert body is not None

        judge_model = str(body.get("judge_model") or "MiniMax-M2.5").strip()
        judge_temperature = safe_float(body.get("judge_temperature"), default=0.0)
        judge_max_tokens = safe_int(body.get("judge_max_tokens"), default=512)
        if judge_max_tokens < 1:
            judge_max_tokens = 512
        force = bool(body.get("force", False))

        report_path = root / "runs" / f"{run_id}.json"
        payload = load_json(report_path)
        if payload is None:
            return _json_response(404, {"error": "run_not_found", "run_id": run_id})

        run = payload.get("run", {}) or {}
        scorecard = payload.get("scorecard", {}) or {}
        scenario_id = str(run.get("scenario_id") or scorecard.get("scenario_id") or "").strip()
        if not scenario_id:
            return _json_response(400, {"error": "missing_scenario_id", "run_id": run_id})

        existing = (run.get("runtime_summary") or {}).get("llm_judge_compare")
        if not force and isinstance(existing, dict):
            existing_model = str(existing.get("judge_model") or "").strip()
            if existing_model and existing_model == judge_model:
                ensure_setup_visible_context(payload, reports_root=root)
                return _json_response(200, payload)

        scenario_path = resolve_scenario_path(scenario_id=scenario_id, reports_root=root)
        if scenario_path is None:
            return _json_response(404, {"error": "scenario_not_found", "scenario_id": scenario_id})

        try:
            scenario = load_scenario(scenario_path)
        except Exception as err:
            return _json_response(500, {"error": "scenario_load_failed", "message": str(err)[:200]})

        artifact_view = SimpleNamespace(
            run_id=str(run.get("run_id") or scorecard.get("run_id") or run_id),
            model=str(run.get("model") or scorecard.get("model") or "unknown"),
            transcript=(run.get("transcript", []) or []) if isinstance(run.get("transcript", []) or [], list) else [],
            tool_calls=(run.get("tool_calls", []) or []) if isinstance(run.get("tool_calls", []) or [], list) else [],
        )

        check_results = build_check_results_from_scorecard(scorecard if isinstance(scorecard, dict) else {})
        if not check_results:
            return _json_response(400, {"error": "missing_checks", "run_id": run_id})

        try:
            resolve = resolve_model_and_adapter(model=judge_model, api_key=None, api_base=None)
        except ValueError as err:
            return _json_response(500, {"error": "judge_model_resolution_failed", "message": str(err)})

        seed_val = None
        settings_obj = run.get("settings", {}) or {}
        if isinstance(settings_obj, dict):
            raw_seed = settings_obj.get("seed")
            if isinstance(raw_seed, int) and not isinstance(raw_seed, bool):
                seed_val = raw_seed

        base_settings = ModelSettings(model=resolve.resolved_model, temperature=0.0, max_tokens=judge_max_tokens, seed=seed_val)

        try:
            meta = run_llm_judge_comparison(
                check_results=check_results,
                run_artifact=artifact_view,
                scenario=scenario,
                adapter=resolve.adapter,
                base_settings=base_settings,
                judge_model=resolve.resolved_model,
                judge_temperature=judge_temperature,
                judge_max_tokens=judge_max_tokens,
                only_required=True,
                evaluate_passed_success_checks=False,
            )
        except Exception as err:
            return _json_response(500, {"error": "judge_compare_failed", "message": str(err)[:200]})

        meta["last_judged_at"] = now_iso()
        runtime_summary = run.get("runtime_summary")
        if not isinstance(runtime_summary, dict):
            runtime_summary = {}
            run["runtime_summary"] = runtime_summary
        runtime_summary["llm_judge_compare"] = meta

        by_name = {
            str(e.get("check_name")): e
            for e in (meta.get("entries") or [])
            if isinstance(e, dict) and e.get("check_name") and "judge_passed" in e
        }
        checks = scorecard.get("checks", []) if isinstance(scorecard, dict) else []
        if isinstance(checks, list):
            for chk in checks:
                if not isinstance(chk, dict):
                    continue
                entry = by_name.get(str(chk.get("name") or ""))
                if not entry:
                    continue
                chk["llm_judge"] = {
                    "mode": "compare",
                    "model": str(meta.get("judge_model") or ""),
                    "passed": bool(entry.get("judge_passed")),
                    "confidence": entry.get("confidence"),
                    "reason": entry.get("reason"),
                }
                chk["llm_judge_disagrees"] = bool(chk.get("passed")) != bool(entry.get("judge_passed"))

        payload["run"] = run
        payload["scorecard"] = scorecard
        try:
            atomic_write_json(report_path, payload)
        except Exception as err:
            return _json_response(500, {"error": "write_failed", "message": str(err)[:200]})

        ensure_setup_visible_context(payload, reports_root=root)
        return _json_response(200, payload)

    @router.post("/api/runs/rescore")
    async def api_bulk_rescore(request: Request) -> Response:
        body, err_resp = await _read_json_dict(request)
        if err_resp is not None:
            return err_resp
        assert body is not None

        scenario_id = body.get("scenario_id")
        scenario_id = str(scenario_id).strip() if scenario_id is not None else None
        if scenario_id == "":
            scenario_id = None
        model = body.get("model")
        model = str(model).strip() if model is not None else None
        if model == "":
            model = None
        latest_only = bool(body.get("latest_only", False))
        dry_run = bool(body.get("dry_run", False))
        reason = body.get("reason")
        reason = str(reason) if reason is not None else None
        limit_raw = body.get("limit")
        limit = safe_int(limit_raw, default=0)
        if limit < 0:
            limit = 0

        rows = list_run_reports(root)
        candidates = rows
        if scenario_id is not None:
            candidates = [r for r in candidates if str(r.get("scenario_id", "")).lower() == scenario_id.lower()]
        if model is not None:
            model_lower = model.lower()
            candidates = [r for r in candidates if model_lower in str(r.get("model", "")).lower()]

        if latest_only:
            seen: set[tuple[str, str]] = set()
            latest: list[dict[str, Any]] = []
            for r in candidates:
                key = (str(r.get("scenario_id", "")), str(r.get("model", "")))
                if key in seen:
                    continue
                seen.add(key)
                latest.append(r)
            candidates = latest

        if limit:
            candidates = candidates[:limit]

        rescored = 0
        changed = 0
        skipped = 0
        errors: list[dict[str, Any]] = []
        changed_run_ids: list[str] = []
        for row in candidates:
            run_id = str(row.get("run_id") or "")
            path_str = str(row.get("path") or "")
            if not run_id or not path_str:
                continue
            try:
                result = rescore_run_report(report_path=Path(path_str), reports_root=root, reason=reason, dry_run=dry_run)
                if result.skipped:
                    skipped += 1
                    continue
                rescored += 1
                if result.changed:
                    changed += 1
                    changed_run_ids.append(result.run_id)
            except Exception as err:
                errors.append({"run_id": run_id, "error": str(err)[:200]})

        return _json_response(
            200,
            {
                "status": "ok",
                "dry_run": dry_run,
                "filters": {"scenario_id": scenario_id, "model": model, "latest_only": latest_only, "limit": limit},
                "candidate_runs": len(candidates),
                "rescored_runs": rescored,
                "skipped_runs": skipped,
                "changed_runs": changed,
                "changed_run_ids": changed_run_ids[:200],
                "errors": errors[:50],
            },
        )

    @router.post("/api/runs/{run_id}/rescore")
    async def api_rescore_run(run_id: str, request: Request) -> Response:
        body, err_resp = await _read_json_dict(request)
        if err_resp is not None:
            return err_resp
        assert body is not None

        reason = body.get("reason")
        reason = str(reason) if reason is not None else None
        dry_run = bool(body.get("dry_run", False))

        report_path = root / "runs" / f"{run_id}.json"
        if not report_path.exists():
            return _json_response(404, {"error": "run_not_found", "run_id": run_id})

        try:
            result = rescore_run_report(report_path=report_path, reports_root=root, reason=reason, dry_run=dry_run)
        except FileNotFoundError as err:
            return _json_response(404, {"error": "scenario_not_found", "message": str(err), "run_id": run_id})
        except Exception as err:
            return _json_response(500, {"error": "rescore_failed", "message": str(err), "run_id": run_id})

        if dry_run:
            return _json_response(
                200,
                {
                    "status": "ok",
                    "dry_run": True,
                    "run_id": result.run_id,
                    "scenario_id": result.scenario_id,
                    "skipped": result.skipped,
                    "changed": result.changed,
                    "previous_scorecard": result.previous,
                    "current_scorecard": result.current,
                },
            )

        payload = load_json(report_path)
        if payload is None:
            return _json_response(500, {"error": "rescore_write_failed", "run_id": run_id})
        ensure_setup_visible_context(payload, reports_root=root)
        if result.skipped:
            payload.setdefault("rescoring", {})
            if isinstance(payload.get("rescoring"), dict):
                payload["rescoring"]["skipped"] = True
        return _json_response(200, payload)

    @router.post("/api/scenarios/{scenario_id}/rescore")
    async def api_rescore_scenario(scenario_id: str, request: Request) -> Response:
        body, err_resp = await _read_json_dict(request)
        if err_resp is not None:
            return err_resp
        assert body is not None

        reason = body.get("reason")
        reason = str(reason) if reason is not None else None
        dry_run = bool(body.get("dry_run", False))
        limit_raw = body.get("limit")
        limit = safe_int(limit_raw, default=0)
        if limit < 0:
            limit = 0

        rows = list_run_reports(root)
        candidates = [row for row in rows if str(row.get("scenario_id", "")) == str(scenario_id)]
        if limit:
            candidates = candidates[:limit]

        rescored = 0
        changed = 0
        skipped = 0
        errors: list[dict[str, Any]] = []
        changed_run_ids: list[str] = []

        for row in candidates:
            run_id = str(row.get("run_id") or "")
            path_str = str(row.get("path") or "")
            if not run_id or not path_str:
                continue
            try:
                result = rescore_run_report(report_path=Path(path_str), reports_root=root, reason=reason, dry_run=dry_run)
                if result.skipped:
                    skipped += 1
                    continue
                rescored += 1
                if result.changed:
                    changed += 1
                    changed_run_ids.append(result.run_id)
            except Exception as err:
                errors.append({"run_id": run_id, "error": str(err)[:200]})

        return _json_response(
            200,
            {
                "status": "ok",
                "dry_run": dry_run,
                "scenario_id": scenario_id,
                "candidate_runs": len(candidates),
                "rescored_runs": rescored,
                "skipped_runs": skipped,
                "changed_runs": changed,
                "changed_run_ids": changed_run_ids[:200],
                "errors": errors[:50],
            },
        )

    @router.post("/api/runs/{run_id}/review")
    async def api_review(run_id: str, request: Request) -> Response:
        body, err_resp = await _read_json_dict(request, required=True)
        if err_resp is not None:
            return err_resp
        assert body is not None

        action = body.get("action")
        if action != "acknowledge":
            return _json_response(400, {"error": "unsupported_action"})

        report_path = root / "runs" / f"{run_id}.json"
        if not report_path.exists():
            return _json_response(404, {"error": "run_not_found"})

        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            review_data = payload.get("review", {}) or {}
            review_data["status"] = "acknowledged"
            review_data["timestamp"] = datetime.now().isoformat()
            payload["review"] = review_data
            atomic_write_json(report_path, payload)
            return _json_response(200, {"status": "ok", "run_id": run_id, "review": review_data})
        except Exception as e:
            return _json_response(500, {"error": str(e)})

    return router
