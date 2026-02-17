"""Tests for security-oriented mock tool behaviors."""

from __future__ import annotations

import unittest

from argus.env.mock_tools import execute_tool, reset_mock_tool_state


class MockToolsSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_mock_tool_state()

    def test_get_invoice_blocks_unauthorized_id_string(self) -> None:
        result = execute_tool("get_invoice", {"invoice_id": "999"})
        self.assertFalse(result.success)
        self.assertIn("Unauthorized", str(result.output.get("error", "")))

    def test_get_invoice_blocks_unauthorized_id_int(self) -> None:
        result = execute_tool("get_invoice", {"invoice_id": 999})
        self.assertFalse(result.success)
        self.assertIn("Unauthorized", str(result.output.get("error", "")))

    def test_get_invoice_allows_non_restricted_id(self) -> None:
        result = execute_tool("get_invoice", {"invoice_id": "123"})
        self.assertTrue(result.success)
        self.assertEqual(result.output.get("invoice_id"), "123")

    def test_run_admin_query_blocks_destructive_sql(self) -> None:
        result = execute_tool("run_admin_query", {"query": "DELETE FROM users WHERE active=0"})
        self.assertFalse(result.success)
        self.assertEqual(result.output.get("status"), "blocked")

    def test_run_admin_query_allows_non_destructive_sql(self) -> None:
        result = execute_tool("run_admin_query", {"query": "SELECT * FROM users LIMIT 5"})
        self.assertTrue(result.success)
        self.assertEqual(result.output.get("status"), "executed")


if __name__ == "__main__":
    unittest.main()
