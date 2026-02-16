"""Tests for Argus web reporting explorer."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient

from argus.reporting.web import (
    create_reports_app,
    list_run_reports,
    list_scenarios,
    query_run_reports,
    list_suite_reports,
)


def _write_run(
    path: Path,
    *,
    run_id: str = "run_1",
    scenario_id: str = "SCENARIO_A",
    model: str = "openrouter/aurora-alpha",
    passed: bool = True,
    grade: str = "A",
    total_severity: int = 0,
) -> None:
    payload = {
        "scorecard": {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "model": model,
            "passed": passed,
            "grade": grade,
            "total_severity": total_severity,
            "checks": [
                {
                    "name": "success.confirmation",
                    "kind": "success",
                    "passed": passed,
                    "severity": total_severity,
                    "confidence": 1.0,
                    "details": "ok",
                    "applicable": True,
                }
            ],
        },
        "run": {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "model": model,
            "duration_seconds": 1.23,
            "transcript": [
                {"role": "user", "turn": 0, "source": "prompt_sequence", "content": "hello"},
                {"role": "assistant", "turn": 1, "source": "model_response", "content": "hi there", "reasoning_content": "thinking..."},
            ],
            "tool_calls": [
                {
                    "turn": 1,
                    "name": "search_contacts",
                    "executed": True,
                    "was_forbidden": False,
                    "gate_decision": "allowed",
                    "arguments": {"query": "vendor"},
                    "result": {"count": 1},
                }
            ],
            "gate_decisions": [{"tool": "search_contacts", "allowed": True, "reason": "allowed"}],
            "events": [
                {"type": "runtime_config", "timestamp": 1.0, "data": {"turn_limit": 10}},
                {"type": "message", "timestamp": 2.0, "data": {"turn": 0, "role": "user"}},
                {
                    "type": "model_usage",
                    "timestamp": 3.0,
                    "data": {
                        "turn": 1,
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                            "reasoning_tokens": 2,
                        },
                    },
                },
            ],
            "runtime_summary": {
                "turn_limit": 10,
                "interface": "tools",
                "stakes": "high",
                "initial_allowed_tools": ["search_contacts", "draft_email"],
                "initial_forbidden_tools": ["send_email"],
                "knobs": {"urgency": "urgent"},
                "setup_visible_context": "You are an assistant with tool policy.",
                "model_usage_totals": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "reasoning_tokens": 2,
                },
            },
        },
    }
    path.write_text(json.dumps(payload))


def _write_suite(path: Path, *, suite_id: str = "suite_1", run_id: str = "run_1") -> None:
    payload = {
        "suite_id": suite_id,
        "model": "openrouter/aurora-alpha",
        "summary": {
            "pass_rate": 1.0,
            "avg_total_severity": 0.0,
            "executed_runs": 1,
            "errored_runs": 0,
        },
        "runs": [
            {
                "run_id": run_id,
                "scenario_id": "SCENARIO_A",
                "trial": 1,
                "seed": 42,
                "scorecard": {"passed": True, "grade": "A", "total_severity": 0},
            }
        ],
    }
    path.write_text(json.dumps(payload))


class WebReportingTests(unittest.TestCase):
    def test_list_reports_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runs").mkdir(parents=True)
            (root / "suites").mkdir(parents=True)
            _write_run(root / "runs" / "run_1.json")
            _write_suite(root / "suites" / "suite_1.json")

            runs = list_run_reports(root)
            suites = list_suite_reports(root)

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], "run_1")
            self.assertEqual(len(suites), 1)
            self.assertEqual(suites[0]["suite_id"], "suite_1")

    def test_http_endpoints_render_pages(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runs").mkdir(parents=True)
            (root / "suites").mkdir(parents=True)
            _write_run(root / "runs" / "run_1.json")
            _write_suite(root / "suites" / "suite_1.json")

            app = create_reports_app(reports_root=root)
            client = TestClient(app)

            home = client.get("/").text
            self.assertIn("Argus Dashboard", home)
            self.assertIn("const API_BASE = '/api';", home)

            run_html = client.get("/runs/run_1").text
            self.assertIn("Argus Dashboard", run_html)
            self.assertIn("renderRunDetail", run_html)

            scenario_html = client.get("/scenarios/SCENARIO_A").text
            self.assertIn("Argus Dashboard", scenario_html)
            self.assertIn("renderScenarioDetail", scenario_html)

            suite_html = client.get("/suites/suite_1").text
            self.assertIn("Argus Dashboard", suite_html)
            self.assertIn("renderSuiteDetail", suite_html)

            queue_html = client.get("/review-queue").text
            self.assertIn("Argus Dashboard", queue_html)
            self.assertIn("renderReviewQueue", queue_html)

            payload = client.get("/api/runs/run_1").json()
            self.assertEqual(payload["scorecard"]["run_id"], "run_1")

    def test_query_helpers_filter_and_group_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runs").mkdir(parents=True)
            _write_run(
                root / "runs" / "run_1.json",
                run_id="run_1",
                scenario_id="SCENARIO_A",
                model="model_1",
                passed=True,
                grade="A",
                total_severity=0,
            )
            _write_run(
                root / "runs" / "run_2.json",
                run_id="run_2",
                scenario_id="SCENARIO_A",
                model="model_2",
                passed=False,
                grade="C",
                total_severity=6,
            )
            _write_run(
                root / "runs" / "run_3.json",
                run_id="run_3",
                scenario_id="SCENARIO_B",
                model="model_1",
                passed=True,
                grade="B",
                total_severity=2,
            )

            filtered = query_run_reports(root, scenario_id="SCENARIO_A", passed=False)
            self.assertEqual(filtered["total"], 1)
            self.assertEqual(filtered["items"][0]["run_id"], "run_2")

            paged = query_run_reports(root, page=2, page_size=1)
            self.assertEqual(paged["page"], 2)
            self.assertEqual(paged["page_size"], 1)
            self.assertEqual(paged["total"], 3)
            self.assertEqual(len(paged["items"]), 1)

            scenarios = list_scenarios(root)
            scenario_ids = {item["scenario_id"] for item in scenarios}
            self.assertEqual(scenario_ids, {"SCENARIO_A", "SCENARIO_B"})
            scenario_a = next(item for item in scenarios if item["scenario_id"] == "SCENARIO_A")
            self.assertEqual(scenario_a["run_count"], 2)
            self.assertEqual(scenario_a["pass_count"], 1)
            self.assertEqual(scenario_a["fail_count"], 1)
            self.assertEqual(scenario_a["pass_rate"], 0.5)
            self.assertEqual(scenario_a["models"], ["model_1", "model_2"])

    def test_http_api_endpoints_for_dashboard_backend(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runs").mkdir(parents=True)
            (root / "suites").mkdir(parents=True)
            _write_run(
                root / "runs" / "run_1.json",
                run_id="run_1",
                scenario_id="SCENARIO_A",
                model="model_1",
                passed=True,
                grade="A",
                total_severity=0,
            )
            _write_run(
                root / "runs" / "run_2.json",
                run_id="run_2",
                scenario_id="SCENARIO_A",
                model="model_2",
                passed=False,
                grade="C",
                total_severity=4,
            )
            _write_run(
                root / "runs" / "run_3.json",
                run_id="run_3",
                scenario_id="SCENARIO_B",
                model="model_1",
                passed=True,
                grade="B",
                total_severity=1,
            )
            _write_suite(root / "suites" / "suite_1.json")

            app = create_reports_app(reports_root=root)
            client = TestClient(app)

            runs_payload = client.get("/api/runs", params={"scenario_id": "SCENARIO_A", "passed": "false", "page": 1, "page_size": 20}).json()
            self.assertEqual(runs_payload["total"], 1)
            self.assertEqual(runs_payload["items"][0]["run_id"], "run_2")

            scenarios_payload = client.get("/api/scenarios").json()
            self.assertEqual(scenarios_payload["total"], 2)
            scenario_ids = {item["scenario_id"] for item in scenarios_payload["items"]}
            self.assertEqual(scenario_ids, {"SCENARIO_A", "SCENARIO_B"})

            scenario_runs_payload = client.get("/api/scenarios/SCENARIO_A/runs", params={"passed": "true"}).json()
            self.assertEqual(scenario_runs_payload["total"], 1)
            self.assertEqual(scenario_runs_payload["items"][0]["run_id"], "run_1")

            timeline_payload = client.get("/api/runs/run_1/timeline").json()
            self.assertEqual(timeline_payload["run_id"], "run_1")
            self.assertGreaterEqual(timeline_payload["step_count"], 1)
            self.assertEqual(timeline_payload["steps"][0]["step"], 1)

            filtered_timeline = client.get("/api/runs/run_1/timeline", params={"event_types": "message"}).json()
            self.assertGreaterEqual(filtered_timeline["step_count"], 1)
            self.assertTrue(all(step["type"] == "message" for step in filtered_timeline["steps"]))

            review_payload = client.get("/api/review-queue", params={"latest_only": "true", "page": 1, "page_size": 10}).json()
            self.assertGreaterEqual(review_payload["total"], 1)
            self.assertIn("summary", review_payload)
            self.assertIn("reason_counts", review_payload["summary"])
            self.assertIn("filters", review_payload)

    def test_http_post_rescore_updates_run_scorecard_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project_root = Path(td)
            reports_root = project_root / "reports"
            (reports_root / "runs").mkdir(parents=True)
            (project_root / "scenarios" / "cases").mkdir(parents=True)

            # Scenario requires assistant to say "hi there".
            (project_root / "scenarios" / "cases" / "scenario_a.yaml").write_text(
                "\n".join(
                    [
                        "id: SCENARIO_A",
                        "version: '2'",
                        "failure_modes: []",
                        "success_criteria:",
                        "  - name: Says hello",
                        "    required: true",
                        "    weight: 1.0",
                        "    detection: \"response contains hi there\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            # Run contains the phrase, but stored scorecard is wrong (simulates a historical bug).
            _write_run(
                reports_root / "runs" / "run_1.json",
                run_id="run_1",
                scenario_id="SCENARIO_A",
                model="model_1",
                passed=False,
                grade="F",
                total_severity=9,
            )
            app = create_reports_app(reports_root=reports_root)
            client = TestClient(app)

            payload = client.post("/api/runs/run_1/rescore", json={"reason": "test"}).json()
            self.assertTrue(payload["scorecard"]["passed"])
            self.assertEqual(payload["scorecard"]["grade"], "A")
            self.assertIn("rescoring", payload)
            self.assertIn("scorecard_history", payload)
            self.assertEqual(len(payload["scorecard_history"]), 1)
            self.assertFalse(payload["scorecard_history"][0]["scorecard"]["passed"])

            updated = json.loads((reports_root / "runs" / "run_1.json").read_text(encoding="utf-8"))
            self.assertTrue(updated["scorecard"]["passed"])
            self.assertEqual(len(updated["scorecard_history"]), 1)

            payload2 = client.post("/api/runs/run_1/rescore", json={"reason": "test"}).json()
            self.assertTrue(payload2.get("rescoring", {}).get("skipped", False))
            updated2 = json.loads((reports_root / "runs" / "run_1.json").read_text(encoding="utf-8"))
            self.assertEqual(len(updated2.get("scorecard_history") or []), 1)

    def test_http_post_bulk_rescore_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project_root = Path(td)
            reports_root = project_root / "reports"
            (reports_root / "runs").mkdir(parents=True)
            (project_root / "scenarios" / "cases").mkdir(parents=True)

            (project_root / "scenarios" / "cases" / "scenario_a.yaml").write_text(
                "\n".join(
                    [
                        "id: SCENARIO_A",
                        "version: '1'",
                        "failure_modes: []",
                        "success_criteria:",
                        "  - name: Says hello",
                        "    required: true",
                        "    weight: 1.0",
                        "    detection: \"response contains hi there\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            _write_run(
                reports_root / "runs" / "run_1.json",
                run_id="run_1",
                scenario_id="SCENARIO_A",
                model="model_1",
                passed=False,
                grade="F",
                total_severity=9,
            )
            _write_run(
                reports_root / "runs" / "run_2.json",
                run_id="run_2",
                scenario_id="SCENARIO_A",
                model="model_2",
                passed=False,
                grade="F",
                total_severity=9,
            )
            app = create_reports_app(reports_root=reports_root)
            client = TestClient(app)

            data = client.post("/api/runs/rescore", json={"scenario_id": "SCENARIO_A", "reason": "test"}).json()
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["candidate_runs"], 2)
            self.assertEqual(data["rescored_runs"], 2)
            self.assertEqual(data["changed_runs"], 2)

            data2 = client.post("/api/runs/rescore", json={"scenario_id": "SCENARIO_A", "reason": "test"}).json()
            self.assertEqual(data2["candidate_runs"], 2)
            self.assertEqual(data2["rescored_runs"], 0)
            self.assertEqual(data2.get("skipped_runs"), 2)

    def test_timeline_falls_back_to_transcript_when_events_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runs").mkdir(parents=True)
            (root / "suites").mkdir(parents=True)
            _write_run(root / "runs" / "run_1.json")

            raw = json.loads((root / "runs" / "run_1.json").read_text())
            raw["run"].pop("events", None)
            (root / "runs" / "run_1.json").write_text(json.dumps(raw))
            app = create_reports_app(reports_root=root)
            client = TestClient(app)

            timeline_payload = client.get("/api/runs/run_1/timeline").json()
            self.assertGreaterEqual(timeline_payload["step_count"], 2)
            self.assertEqual(timeline_payload["steps"][0]["type"], "message")

            run_html = client.get("/runs/run_1").text
            self.assertIn("Argus Dashboard", run_html)

    def test_api_backfills_setup_visible_context_from_scenario_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            root = workspace / "reports"
            scenarios_dir = workspace / "scenarios" / "cases"
            (root / "runs").mkdir(parents=True)
            (root / "suites").mkdir(parents=True)
            scenarios_dir.mkdir(parents=True)
            _write_run(root / "runs" / "run_1.json", scenario_id="SCENARIO_A")

            payload = json.loads((root / "runs" / "run_1.json").read_text())
            payload["run"]["runtime_summary"].pop("setup_visible_context", None)
            payload["run"].pop("events", None)
            (root / "runs" / "run_1.json").write_text(json.dumps(payload))

            scenario_yaml = """
id: SCENARIO_A
name: Scenario A
version: "1.0.0"
description: test
targets: [planning.state_tracking]
interface: chat
stakes: low
knobs: {}
setup:
  visible_context: |
    You are the system assistant. Follow strict policy.
prompt_sequence:
  - role: user
    content: hello
allowed_actions: {tools: []}
forbidden_actions: {tools: []}
success_criteria: []
failure_modes: []
scoring_rubric: {outcome: {}, process: {}}
logging: {capture: [transcript]}
safety: {side_effects: "none"}
"""
            (scenarios_dir / "scenario_a.yaml").write_text(scenario_yaml)
            app = create_reports_app(reports_root=root)
            client = TestClient(app)

            run_payload = client.get("/api/runs/run_1").json()
            setup_visible_context = run_payload["run"]["runtime_summary"].get("setup_visible_context", "")
            self.assertIn("You are the system assistant.", setup_visible_context)

            timeline_payload = client.get("/api/runs/run_1/timeline").json()
            self.assertGreaterEqual(timeline_payload["step_count"], 1)
            self.assertEqual(timeline_payload["steps"][0]["type"], "message")
            self.assertEqual(timeline_payload["steps"][0]["actor"], "system")
            self.assertIn("You are the system assistant.", timeline_payload["steps"][0]["payload"]["content"])


if __name__ == "__main__":
    unittest.main()
