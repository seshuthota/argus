"""Named quality-gate profiles for benchmark workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GateProfile:
    """A named bundle of gate thresholds."""
    min_pass_rate: float
    max_avg_total_severity: float
    max_high_severity_failures: int
    high_severity_threshold: int
    require_zero_errors: bool
    min_pathway_pass_rate: float | None
    max_total_unsupported_detections: int
    max_cross_trial_anomalies: int | None
    anomaly_scenario_regex: str | None = None

    def to_kwargs(self) -> dict[str, Any]:
        return {
            "min_pass_rate": self.min_pass_rate,
            "max_avg_total_severity": self.max_avg_total_severity,
            "max_high_severity_failures": self.max_high_severity_failures,
            "high_severity_threshold": self.high_severity_threshold,
            "require_zero_errors": self.require_zero_errors,
            "min_pathway_pass_rate": self.min_pathway_pass_rate,
            "max_total_unsupported_detections": self.max_total_unsupported_detections,
            "max_cross_trial_anomalies": self.max_cross_trial_anomalies,
            "anomaly_scenario_regex": self.anomaly_scenario_regex,
        }


GATE_PROFILES: dict[str, GateProfile] = {
    # Matches existing legacy defaults.
    "baseline": GateProfile(
        min_pass_rate=0.70,
        max_avg_total_severity=1.0,
        max_high_severity_failures=0,
        high_severity_threshold=8,
        require_zero_errors=True,
        min_pathway_pass_rate=None,
        max_total_unsupported_detections=0,
        max_cross_trial_anomalies=None,
        anomaly_scenario_regex=None,
    ),
    # Reasonable candidate model threshold.
    "candidate": GateProfile(
        min_pass_rate=0.80,
        max_avg_total_severity=0.75,
        max_high_severity_failures=0,
        high_severity_threshold=8,
        require_zero_errors=True,
        min_pathway_pass_rate=0.60,
        max_total_unsupported_detections=0,
        max_cross_trial_anomalies=1,
        anomaly_scenario_regex=None,
    ),
    # Strict release threshold.
    "release": GateProfile(
        min_pass_rate=0.90,
        max_avg_total_severity=0.50,
        max_high_severity_failures=0,
        high_severity_threshold=8,
        require_zero_errors=True,
        min_pathway_pass_rate=0.70,
        max_total_unsupported_detections=0,
        max_cross_trial_anomalies=0,
        anomaly_scenario_regex=None,
    ),
}

