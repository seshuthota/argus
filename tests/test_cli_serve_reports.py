"""Tests for serve-reports CLI command."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from argus.cli import cli


class CLIServeReportsTests(unittest.TestCase):
    def test_serve_reports_invokes_server_with_expected_args(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            reports = Path(td) / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            with patch("argus.cli.serve_reports_forever") as mock_serve:
                result = runner.invoke(
                    cli,
                    [
                        "serve-reports",
                        "--reports-root",
                        str(reports),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8899",
                    ],
                )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            mock_serve.assert_called_once_with(
                host="127.0.0.1",
                port=8899,
                reports_root=str(reports),
            )

    def test_serve_reports_rejects_invalid_port(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            reports = Path(td) / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            result = runner.invoke(
                cli,
                [
                    "serve-reports",
                    "--reports-root",
                    str(reports),
                    "--port",
                    "70000",
                ],
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--port must be within", result.output)


if __name__ == "__main__":
    unittest.main()
