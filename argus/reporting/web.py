"""Web UI backend for browsing Argus run and suite reports.

This module is a small façade around the FastAPI-based report explorer living in
`argus.reporting.explorer`.
"""

from __future__ import annotations

from pathlib import Path

from .explorer.app import create_reports_app
from .explorer.store import (
    list_run_reports,
    list_scenarios,
    list_suite_reports,
    query_run_reports,
)

__all__ = [
    "create_reports_app",
    "serve_reports_forever",
    "list_run_reports",
    "query_run_reports",
    "list_scenarios",
    "list_suite_reports",
]


def serve_reports_forever(*, host: str, port: int, reports_root: str | Path) -> None:
    """Start report explorer server and block until interrupted."""
    # Import lazily so unit tests that don't exercise the CLI server don't require uvicorn.
    import uvicorn  # type: ignore

    app = create_reports_app(reports_root=reports_root)
    # Keep logs quiet like the legacy server; CLI prints the URL already.
    uvicorn.run(app, host=host, port=port, log_level="warning")
