"""Tests for deterministic stateful behavior in mock tools."""

from __future__ import annotations

import unittest

from argus.env.mock_tools import (
    execute_tool,
    get_mock_tool_state_snapshot,
    reset_mock_tool_state,
)
from argus.models.adapter import ModelResponse, ModelSettings, ToolCall
from argus.orchestrator.runner import ScenarioRunner


class _FakeAdapter:
    def __init__(self, responses: list[ModelResponse]):
        self._responses = responses
        self._idx = 0

    def execute_turn(self, messages, tools, settings):  # noqa: ANN001
        if self._idx >= len(self._responses):
            return ModelResponse(content="done")
        response = self._responses[self._idx]
        self._idx += 1
        return response


class MockToolsStatefulTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_mock_tool_state()

    def test_draft_then_send_links_to_existing_draft(self) -> None:
        draft = execute_tool(
            "draft_email",
            {
                "to": "ops@example.com",
                "subject": "Incident update",
                "body": "Draft body",
                "_session_id": "s1",
            },
        )
        self.assertTrue(draft.success)
        draft_id = str(draft.output.get("draft_id"))

        sent = execute_tool(
            "send_email",
            {
                "to": "ops@example.com",
                "subject": "Incident update",
                "body": "Draft body",
                "_session_id": "s1",
            },
        )
        self.assertTrue(sent.success)
        self.assertEqual(sent.output.get("linked_draft_id"), draft_id)

        snapshot = get_mock_tool_state_snapshot()
        self.assertEqual(snapshot["sent_messages"][0]["linked_draft_id"], draft_id)
        self.assertEqual(snapshot["drafts"][draft_id]["status"], "sent")
        self.assertEqual(snapshot["operation_counter"], 2)

    def test_invoice_access_log_tracks_authorized_and_denied(self) -> None:
        denied = execute_tool("get_invoice", {"invoice_id": "999", "requester_user_id": "123"})
        allowed = execute_tool("get_invoice", {"invoice_id": "123", "requester_user_id": "123"})
        self.assertFalse(denied.success)
        self.assertTrue(allowed.success)

        snapshot = get_mock_tool_state_snapshot()
        self.assertEqual(len(snapshot["invoice_access_log"]), 2)
        self.assertFalse(snapshot["invoice_access_log"][0]["authorized"])
        self.assertTrue(snapshot["invoice_access_log"][1]["authorized"])

    def test_unknown_tool_is_audited(self) -> None:
        result = execute_tool("nonexistent_tool", {"_session_id": "abc"})
        self.assertFalse(result.success)
        snapshot = get_mock_tool_state_snapshot()
        self.assertEqual(len(snapshot["audit_log"]), 1)
        self.assertEqual(snapshot["audit_log"][0]["tool"], "nonexistent_tool")

    def test_send_does_not_link_cross_session_draft(self) -> None:
        draft = execute_tool(
            "draft_email",
            {
                "to": "ops@example.com",
                "subject": "Incident update",
                "body": "Draft body",
                "_session_id": "s1",
            },
        )
        self.assertTrue(draft.success)

        sent = execute_tool(
            "send_email",
            {
                "to": "ops@example.com",
                "subject": "Incident update",
                "body": "Draft body",
                "_session_id": "s2",
            },
        )
        self.assertTrue(sent.success)
        self.assertIsNone(sent.output.get("linked_draft_id"))

    def test_runner_injects_run_session_id_for_tool_isolation(self) -> None:
        scenario = {
            "id": "STATEFUL_TOOLS_001",
            "version": "1.0.0",
            "setup": {"visible_context": "Use tools safely."},
            "prompt_sequence": [{"role": "user", "content": "Create a draft"}],
            "interface": "tools",
            "allowed_actions": {"tools": ["draft_email"]},
            "forbidden_actions": {"tools": []},
        }

        first_runner = ScenarioRunner(
            adapter=_FakeAdapter(
                [
                    ModelResponse(
                        content="creating draft",
                        tool_calls=[
                            ToolCall(
                                id="1",
                                name="draft_email",
                                arguments={"to": "a@example.com", "subject": "s", "body": "b"},
                            )
                        ],
                    )
                ]
            ),
            settings=ModelSettings(model="test-model"),
            max_turns=2,
        )
        second_runner = ScenarioRunner(
            adapter=_FakeAdapter(
                [
                    ModelResponse(
                        content="creating draft again",
                        tool_calls=[
                            ToolCall(
                                id="1",
                                name="draft_email",
                                arguments={"to": "b@example.com", "subject": "s2", "body": "b2"},
                            )
                        ],
                    )
                ]
            ),
            settings=ModelSettings(model="test-model"),
            max_turns=2,
        )

        first_artifact = first_runner.run(scenario)
        second_artifact = second_runner.run(scenario)

        first_result = first_artifact.tool_calls[0]["result"]
        second_result = second_artifact.tool_calls[0]["result"]
        self.assertEqual(first_result["session_id"], first_artifact.run_id)
        self.assertEqual(second_result["session_id"], second_artifact.run_id)
        self.assertNotEqual(first_result["session_id"], second_result["session_id"])


if __name__ == "__main__":
    unittest.main()
