from __future__ import annotations

import html
from pathlib import Path


def load_app_html() -> str:
    """Load the single-page application HTML shell."""
    current_dir = Path(__file__).resolve().parents[1]  # argus/reporting/
    template_path = current_dir / "templates" / "index.html"
    try:
        return template_path.read_text(encoding="utf-8")
    except Exception as err:
        return (
            "<!doctype html><html><body><h1>Error loading application shell</h1><pre>"
            f"{html.escape(str(err))}"
            "</pre></body></html>"
        )

