from __future__ import annotations

from pathlib import Path

import json

from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api import create_api_router
from .jobs import jobs_dir, reconcile_orphaned_jobs
from .spa import load_app_html
from .store import load_env


def create_reports_app(*, reports_root: str | Path) -> FastAPI:
    """Create the FastAPI app for the Argus report explorer."""
    root = Path(reports_root).resolve()

    load_env()
    jobs_dir(root).mkdir(parents=True, exist_ok=True)
    reconcile_orphaned_jobs(root)

    app_html = load_app_html()

    app = FastAPI(title="Argus Report Explorer")
    app.state.reports_root = root

    api_router = create_api_router(reports_root=root)
    app.include_router(api_router)

    def _html_response(status: int, html: str) -> Response:
        return Response(content=html.encode("utf-8"), status_code=status, media_type="text/html; charset=utf-8")

    def _json_response(status: int, payload: dict) -> Response:
        data = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
        return Response(
            content=data,
            status_code=status,
            media_type="application/json; charset=utf-8",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404 and request.url.path.startswith("/api/"):
            return _json_response(404, {"error": "not_found"})
        if exc.status_code == 404:
            return _html_response(
                404,
                "<!doctype html><html><body><h1>Not Found</h1><p><a href='/'>Back</a></p></body></html>",
            )
        # Default: preserve status and message as JSON.
        if request.url.path.startswith("/api/"):
            return _json_response(exc.status_code, {"error": "http_error", "status": exc.status_code, "message": str(exc.detail)})
        return _html_response(exc.status_code, f"<!doctype html><html><body><h1>{exc.status_code}</h1><pre>{exc.detail}</pre></body></html>")

    @app.get("/")
    async def spa_root() -> Response:
        return _html_response(200, app_html)

    @app.get("/runs/{rest_of_path:path}")
    async def spa_runs(rest_of_path: str) -> Response:
        return _html_response(200, app_html)

    @app.get("/runs")
    async def spa_runs_root() -> Response:
        return _html_response(200, app_html)

    @app.get("/scenarios/{rest_of_path:path}")
    async def spa_scenarios(rest_of_path: str) -> Response:
        return _html_response(200, app_html)

    @app.get("/scenarios")
    async def spa_scenarios_root() -> Response:
        return _html_response(200, app_html)

    @app.get("/suites/{rest_of_path:path}")
    async def spa_suites(rest_of_path: str) -> Response:
        return _html_response(200, app_html)

    @app.get("/suites")
    async def spa_suites_root() -> Response:
        return _html_response(200, app_html)

    @app.get("/review-queue")
    async def spa_review_queue() -> Response:
        return _html_response(200, app_html)

    @app.get("/review-queue/{rest_of_path:path}")
    async def spa_review_queue_paths(rest_of_path: str) -> Response:
        return _html_response(200, app_html)

    @app.get("/jobs/{rest_of_path:path}")
    async def spa_jobs(rest_of_path: str) -> Response:
        return _html_response(200, app_html)

    @app.get("/jobs")
    async def spa_jobs_root() -> Response:
        return _html_response(200, app_html)

    @app.get("/compare")
    async def spa_compare_root() -> Response:
        return _html_response(200, app_html)

    @app.get("/compare/{rest_of_path:path}")
    async def spa_compare_paths(rest_of_path: str) -> Response:
        return _html_response(200, app_html)

    return app
