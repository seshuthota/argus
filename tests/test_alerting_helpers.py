"""Tests for benchmark alert webhook helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from argus.cli import _emit_alert_webhook, _should_emit_alert


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class AlertingHelperTests(unittest.TestCase):
    def test_should_emit_alert_modes(self) -> None:
        self.assertTrue(_should_emit_alert(alert_on="always", overall_passed=True))
        self.assertFalse(_should_emit_alert(alert_on="never", overall_passed=False))
        self.assertTrue(_should_emit_alert(alert_on="gate_failures", overall_passed=False))
        self.assertFalse(_should_emit_alert(alert_on="gate_failures", overall_passed=True))

    def test_emit_alert_webhook_success(self) -> None:
        with patch("argus.cli.urlopen", return_value=_FakeResponse(204)) as mock_urlopen:
            ok, detail = _emit_alert_webhook(
                webhook_url="https://example.test/hook",
                payload={"ok": True},
                timeout_s=5.0,
            )

        self.assertTrue(ok)
        self.assertEqual(detail, "status=204")
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_emit_alert_webhook_failure(self) -> None:
        with patch("argus.cli.urlopen", side_effect=RuntimeError("boom")):
            ok, detail = _emit_alert_webhook(
                webhook_url="https://example.test/hook",
                payload={"ok": True},
                timeout_s=5.0,
            )

        self.assertFalse(ok)
        self.assertIn("boom", detail)


if __name__ == "__main__":
    unittest.main()
