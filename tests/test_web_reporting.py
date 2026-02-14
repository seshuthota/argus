"""Tests for Argus web reporting explorer."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import urlopen

from argus.reporting.web import (
    create_reports_server,
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

            try:
                server = create_reports_server(host="127.0.0.1", port=0, reports_root=root)
            except PermissionError:
                self.skipTest("Socket binding is not permitted in this test runtime.")
            except OSError as err:
                if getattr(err, "errno", None) in {1, 13}:
                    self.skipTest("Socket binding is not permitted in this test runtime.")
                raise
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address

                with urlopen(f"http://{host}:{port}/") as resp:
                    home = resp.read().decode("utf-8")
                self.assertIn("Argus Report Explorer", home)
                self.assertIn("run_1", home)
                self.assertIn("suite_1", home)

                with urlopen(f"http://{host}:{port}/runs/run_1") as resp:
                    run_html = resp.read().decode("utf-8")
                self.assertIn("Run run_1", run_html)
                self.assertIn("Interaction Timeline", run_html)
                self.assertIn("USER &bull; Turn 0", run_html)
                self.assertIn("thinking...", run_html)
                self.assertIn("Evaluation Checks", run_html)
                self.assertIn("Token Usage & Summary", run_html)
                self.assertIn("thinking...", run_html)

                with urlopen(f"http://{host}:{port}/suites/suite_1") as resp:
                    suite_html = resp.read().decode("utf-8")
                self.assertIn("Suite suite_1", suite_html)
                self.assertIn("Runs", suite_html)

                with urlopen(f"http://{host}:{port}/api/runs/run_1") as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(payload["scorecard"]["run_id"], "run_1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

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

            try:
                server = create_reports_server(host="127.0.0.1", port=0, reports_root=root)
            except PermissionError:
                self.skipTest("Socket binding is not permitted in this test runtime.")
            except OSError as err:
                if getattr(err, "errno", None) in {1, 13}:
                    self.skipTest("Socket binding is not permitted in this test runtime.")
                raise
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address

                with urlopen(
                    f"http://{host}:{port}/api/runs?scenario_id=SCENARIO_A&passed=false&page=1&page_size=20"
                ) as resp:
                    runs_payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(runs_payload["total"], 1)
                self.assertEqual(runs_payload["items"][0]["run_id"], "run_2")

                with urlopen(f"http://{host}:{port}/api/scenarios") as resp:
                    scenarios_payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(scenarios_payload["total"], 2)
                scenario_ids = {item["scenario_id"] for item in scenarios_payload["items"]}
                self.assertEqual(scenario_ids, {"SCENARIO_A", "SCENARIO_B"})

                with urlopen(f"http://{host}:{port}/api/scenarios/SCENARIO_A/runs?passed=true") as resp:
                    scenario_runs_payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(scenario_runs_payload["total"], 1)
                self.assertEqual(scenario_runs_payload["items"][0]["run_id"], "run_1")

                with urlopen(f"http://{host}:{port}/api/runs/run_1/timeline") as resp:
                    timeline_payload = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(timeline_payload["run_id"], "run_1")
                self.assertGreaterEqual(timeline_payload["step_count"], 1)
                self.assertEqual(timeline_payload["steps"][0]["step"], 1)

                with urlopen(f"http://{host}:{port}/api/runs/run_1/timeline?event_types=message") as resp:
                    filtered_timeline = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(filtered_timeline["step_count"], 1)
                self.assertEqual(filtered_timeline["steps"][0]["type"], "message")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
