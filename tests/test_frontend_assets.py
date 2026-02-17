"""Frontend asset structure and hygiene checks."""

from __future__ import annotations

import unittest
from pathlib import Path


class FrontendAssetTests(unittest.TestCase):
    def test_index_shell_uses_module_and_no_inline_onclick(self) -> None:
        html = Path("argus/reporting/templates/index.html").read_text()
        self.assertIn('type="module" src="/static/js/dashboard-app.js"', html)
        self.assertNotIn("onclick=", html)

    def test_static_js_has_no_inline_onclick_templates(self) -> None:
        for path in Path("argus/reporting/static/js").rglob("*.js"):
            text = path.read_text()
            self.assertNotIn("onclick=", text, msg=f"inline onclick found in {path}")

    def test_dashboard_css_is_layered(self) -> None:
        css = Path("argus/reporting/static/css/dashboard.css").read_text()
        self.assertIn("layers/tokens.css", css)
        self.assertIn("layers/base.css", css)
        self.assertIn("layers/layout.css", css)
        self.assertIn("layers/components.css", css)


if __name__ == "__main__":
    unittest.main()
