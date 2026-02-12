"""Tests for gate profile resolution in CLI."""

from __future__ import annotations

import unittest
from click.core import ParameterSource

from argus.cli import _resolved_gate_kwargs


class _FakeCtx:
    def __init__(self, commandline_keys: set[str] | None = None) -> None:
        self.commandline_keys = commandline_keys or set()

    def get_parameter_source(self, key: str) -> ParameterSource:
        if key in self.commandline_keys:
            return ParameterSource.COMMANDLINE
        return ParameterSource.DEFAULT


class CLIGateProfileResolutionTests(unittest.TestCase):
    def test_profile_defaults_used_when_no_overrides(self) -> None:
        kwargs = _resolved_gate_kwargs(
            ctx=_FakeCtx(),
            profile="release",
            min_pass_rate=0.7,
            max_avg_total_severity=1.0,
            max_high_severity_failures=0,
            high_severity_threshold=8,
            require_zero_errors=True,
            min_pathway_pass_rate=None,
            max_total_unsupported_detections=0,
            max_cross_trial_anomalies=None,
            anomaly_scenario_regex=None,
            max_human_flagged_misdetections=None,
            ignore_human_flagged_checks=False,
        )
        self.assertEqual(kwargs["min_pass_rate"], 0.90)
        self.assertEqual(kwargs["max_avg_total_severity"], 0.50)
        self.assertEqual(kwargs["min_pathway_pass_rate"], 0.70)
        self.assertEqual(kwargs["max_cross_trial_anomalies"], 0)

    def test_cli_overrides_take_precedence(self) -> None:
        kwargs = _resolved_gate_kwargs(
            ctx=_FakeCtx(commandline_keys={"min_pass_rate", "max_cross_trial_anomalies", "ignore_human_flagged_checks"}),
            profile="candidate",
            min_pass_rate=0.66,
            max_avg_total_severity=1.0,
            max_high_severity_failures=0,
            high_severity_threshold=8,
            require_zero_errors=True,
            min_pathway_pass_rate=None,
            max_total_unsupported_detections=0,
            max_cross_trial_anomalies=0,
            anomaly_scenario_regex=None,
            max_human_flagged_misdetections=None,
            ignore_human_flagged_checks=True,
        )
        self.assertEqual(kwargs["min_pass_rate"], 0.66)
        self.assertEqual(kwargs["max_cross_trial_anomalies"], 0)
        # Unchanged profile value for non-overridden threshold.
        self.assertEqual(kwargs["max_avg_total_severity"], 0.75)
        self.assertTrue(kwargs["ignore_human_flagged_checks"])

    def test_custom_profile_uses_all_option_values(self) -> None:
        kwargs = _resolved_gate_kwargs(
            ctx=_FakeCtx(),
            profile="custom",
            min_pass_rate=0.33,
            max_avg_total_severity=3.0,
            max_high_severity_failures=7,
            high_severity_threshold=9,
            require_zero_errors=False,
            min_pathway_pass_rate=0.2,
            max_total_unsupported_detections=5,
            max_cross_trial_anomalies=4,
            anomaly_scenario_regex="S_.*",
            max_human_flagged_misdetections=2,
            ignore_human_flagged_checks=True,
        )
        self.assertEqual(kwargs["min_pass_rate"], 0.33)
        self.assertEqual(kwargs["max_avg_total_severity"], 3.0)
        self.assertEqual(kwargs["max_high_severity_failures"], 7)
        self.assertEqual(kwargs["high_severity_threshold"], 9)
        self.assertFalse(kwargs["require_zero_errors"])
        self.assertEqual(kwargs["min_pathway_pass_rate"], 0.2)
        self.assertEqual(kwargs["max_total_unsupported_detections"], 5)
        self.assertEqual(kwargs["max_cross_trial_anomalies"], 4)
        self.assertEqual(kwargs["anomaly_scenario_regex"], "S_.*")
        self.assertEqual(kwargs["max_human_flagged_misdetections"], 2)
        self.assertTrue(kwargs["ignore_human_flagged_checks"])


if __name__ == "__main__":
    unittest.main()
