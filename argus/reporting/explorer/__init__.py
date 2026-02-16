"""Report Explorer (backend).

This package hosts the FastAPI implementation of the Argus report explorer.
The legacy stdlib `http.server` implementation previously lived in
`argus.reporting.web` and has been replaced by this package.
"""

from __future__ import annotations

from .app import create_reports_app

__all__ = ["create_reports_app"]

