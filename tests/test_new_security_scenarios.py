"""Validation/lint tests for newly added tool-security and DoS scenarios."""

from __future__ import annotations

from pathlib import Path
import unittest

from argus.cli import _lint_loaded_scenario
from argus.schema_validator import validate_scenario_file


NEW_SCENARIOS = [
    "scenarios/cases/tool_use_idor_invoice_access_001.yaml",
    "scenarios/cases/tool_use_risky_sql_generation_001.yaml",
    "scenarios/cases/sabotage_helpful_dos_ticket_check_001.yaml",
    "scenarios/cases/safety_code_dependency_confusion_001.yaml",
    "scenarios/cases/safety_code_supply_chain_backdoor_001.yaml",
    "scenarios/cases/safety_api_internal_leak_001.yaml",
    "scenarios/cases/safety_api_privileged_escalation_001.yaml",
    "scenarios/cases/safety_gov_policy_document_001.yaml",
]


class NewSecurityScenarioTests(unittest.TestCase):
    def test_new_scenarios_validate_and_lint_cleanly(self) -> None:
        for path in NEW_SCENARIOS:
            scenario, errors = validate_scenario_file(path)
            self.assertIsNotNone(scenario, msg=path)
            self.assertEqual(errors, [], msg=f"{path}: {errors}")

            findings = _lint_loaded_scenario(scenario or {})
            error_codes = [f.code for f in findings if f.severity == "ERROR"]
            unsupported_codes = [f.code for f in findings if f.code == "unsupported_clause_shape"]
            self.assertEqual(error_codes, [], msg=f"{path}: lint errors={error_codes}")
            self.assertEqual(unsupported_codes, [], msg=f"{path}: unsupported clauses={unsupported_codes}")

    def test_new_scenarios_in_extended_suite_manifest(self) -> None:
        manifest = Path("scenarios/suites/sabotage_extended_v1.txt").read_text()
        for path in NEW_SCENARIOS:
            self.assertIn(path, manifest)


if __name__ == "__main__":
    unittest.main()
