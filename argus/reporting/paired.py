"""Paired benchmark analysis helpers for model-vs-model comparisons."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class _PairKey:
    scenario_id: str
    trial: int
    seed: int


def _paired_run_map(report: dict[str, Any]) -> dict[_PairKey, dict[str, Any]]:
    runs = report.get("runs", []) or []
    out: dict[_PairKey, dict[str, Any]] = {}
    for run in runs:
        if run.get("error"):
            continue
        scorecard = run.get("scorecard")
        if not isinstance(scorecard, dict):
            continue
        key = _PairKey(
            scenario_id=str(run.get("scenario_id", "")),
            trial=int(run.get("trial", 0)),
            seed=int(run.get("seed", 0)),
        )
        out[key] = run
    return out


def _summary_float(report: dict[str, Any], key: str) -> float:
    summary = report.get("summary", {}) or {}
    try:
        return float(summary.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _pass_from_run(run: dict[str, Any]) -> bool:
    scorecard = run.get("scorecard", {}) or {}
    return bool(scorecard.get("passed", False))


def _severity_from_run(run: dict[str, Any]) -> float:
    scorecard = run.get("scorecard", {}) or {}
    try:
        return float(scorecard.get("total_severity", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _bootstrap_delta_ci95(values: list[float], *, samples: int = 1000, seed: int = 1337) -> tuple[float, float]:
    """Bootstrap 95% CI for mean(delta) over paired values."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    boot: list[float] = []
    for _ in range(max(samples, 100)):
        sample = [values[rng.randrange(0, n)] for _ in range(n)]
        boot.append(sum(sample) / n)
    boot.sort()
    low_idx = max(0, int(0.025 * len(boot)) - 1)
    high_idx = min(len(boot) - 1, int(0.975 * len(boot)) - 1)
    return (float(boot[low_idx]), float(boot[high_idx]))


def build_paired_analysis(
    report_a: dict[str, Any],
    report_b: dict[str, Any],
    *,
    bootstrap_samples: int = 1000,
) -> dict[str, Any]:
    """Build paired analysis for two suite reports run on aligned seeds/trials."""
    map_a = _paired_run_map(report_a)
    map_b = _paired_run_map(report_b)
    keys = sorted(set(map_a.keys()) & set(map_b.keys()), key=lambda k: (k.scenario_id, k.trial, k.seed))

    both_pass = 0
    both_fail = 0
    a_pass_b_fail = 0
    a_fail_b_pass = 0
    pass_deltas: list[float] = []
    severity_deltas: list[float] = []

    scenario_pairs: dict[str, list[tuple[bool, bool, float, float]]] = {}
    for key in keys:
        ra = map_a[key]
        rb = map_b[key]
        pa = _pass_from_run(ra)
        pb = _pass_from_run(rb)
        sa = _severity_from_run(ra)
        sb = _severity_from_run(rb)
        if pa and pb:
            both_pass += 1
        elif (not pa) and (not pb):
            both_fail += 1
        elif pa and (not pb):
            a_pass_b_fail += 1
        else:
            a_fail_b_pass += 1
        pass_deltas.append((1.0 if pa else 0.0) - (1.0 if pb else 0.0))
        severity_deltas.append(sa - sb)
        scenario_pairs.setdefault(key.scenario_id, []).append((pa, pb, sa, sb))

    n_pairs = len(keys)
    pass_delta_mean = (sum(pass_deltas) / n_pairs) if n_pairs else 0.0
    severity_delta_mean = (sum(severity_deltas) / n_pairs) if n_pairs else 0.0
    ci_low, ci_high = _bootstrap_delta_ci95(pass_deltas, samples=bootstrap_samples)

    # McNemar continuity-corrected chi-square statistic (no p-value dependency).
    b = a_pass_b_fail
    c = a_fail_b_pass
    mcnemar_stat = 0.0
    if (b + c) > 0:
        mcnemar_stat = ((abs(b - c) - 1.0) ** 2) / float(b + c)

    by_scenario: list[dict[str, Any]] = []
    for sid, rows in sorted(scenario_pairs.items(), key=lambda kv: kv[0]):
        count = len(rows)
        if count == 0:
            continue
        a_pass_rate = sum(1 for pa, _, _, _ in rows if pa) / count
        b_pass_rate = sum(1 for _, pb, _, _ in rows if pb) / count
        a_avg_sev = sum(sa for _, _, sa, _ in rows) / count
        b_avg_sev = sum(sb for _, _, _, sb in rows) / count
        by_scenario.append(
            {
                "scenario_id": sid,
                "paired_runs": count,
                "pass_rate_a": round(a_pass_rate, 4),
                "pass_rate_b": round(b_pass_rate, 4),
                "delta_pass_rate_a_minus_b": round(a_pass_rate - b_pass_rate, 4),
                "avg_severity_a": round(a_avg_sev, 3),
                "avg_severity_b": round(b_avg_sev, 3),
                "delta_avg_severity_a_minus_b": round(a_avg_sev - b_avg_sev, 3),
            }
        )

    regressions_for_a = sorted(
        [r for r in by_scenario if r["delta_pass_rate_a_minus_b"] < 0],
        key=lambda r: r["delta_pass_rate_a_minus_b"],
    )[:10]
    regressions_for_b = sorted(
        [r for r in by_scenario if r["delta_pass_rate_a_minus_b"] > 0],
        key=lambda r: r["delta_pass_rate_a_minus_b"],
        reverse=True,
    )[:10]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_a": report_a.get("model", "unknown"),
        "model_b": report_b.get("model", "unknown"),
        "suite_id_a": report_a.get("suite_id", "unknown"),
        "suite_id_b": report_b.get("suite_id", "unknown"),
        "summary": {
            "suite_pass_rate_a": _summary_float(report_a, "pass_rate"),
            "suite_pass_rate_b": _summary_float(report_b, "pass_rate"),
            "suite_avg_total_severity_a": _summary_float(report_a, "avg_total_severity"),
            "suite_avg_total_severity_b": _summary_float(report_b, "avg_total_severity"),
            "paired_runs": n_pairs,
            "pass_rate_delta_mean_a_minus_b": round(pass_delta_mean, 4),
            "pass_rate_delta_ci95_a_minus_b": [round(ci_low, 4), round(ci_high, 4)],
            "avg_severity_delta_mean_a_minus_b": round(severity_delta_mean, 4),
            "both_pass": both_pass,
            "both_fail": both_fail,
            "a_pass_b_fail": a_pass_b_fail,
            "a_fail_b_pass": a_fail_b_pass,
            "mcnemar_stat": round(mcnemar_stat, 6),
        },
        "by_scenario": by_scenario,
        "regressions_for_a": regressions_for_a,
        "regressions_for_b": regressions_for_b,
    }


def build_paired_markdown(analysis: dict[str, Any], *, title: str = "Argus Paired Analysis") -> str:
    """Render paired analysis to compact markdown."""
    s = analysis.get("summary", {}) or {}
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Generated: `{analysis.get('generated_at', '')}`")
    lines.append(
        f"- A: `{analysis.get('model_a', 'unknown')}` (`{analysis.get('suite_id_a', 'unknown')}`)"
    )
    lines.append(
        f"- B: `{analysis.get('model_b', 'unknown')}` (`{analysis.get('suite_id_b', 'unknown')}`)"
    )
    lines.append("")
    lines.append("## Paired Summary")
    lines.append("")
    lines.append(f"- Paired runs: `{s.get('paired_runs', 0)}`")
    lines.append(
        f"- Mean pass delta (A-B): `{s.get('pass_rate_delta_mean_a_minus_b', 0.0):.4f}` "
        f"(95% CI `{(s.get('pass_rate_delta_ci95_a_minus_b') or [0.0, 0.0])[0]:.4f}` to "
        f"`{(s.get('pass_rate_delta_ci95_a_minus_b') or [0.0, 0.0])[1]:.4f}`)"
    )
    lines.append(
        f"- Mean severity delta (A-B): `{s.get('avg_severity_delta_mean_a_minus_b', 0.0):.4f}`"
    )
    lines.append(
        f"- Discordant pairs: `A pass / B fail={s.get('a_pass_b_fail', 0)}`, "
        f"`A fail / B pass={s.get('a_fail_b_pass', 0)}`"
    )
    lines.append(f"- McNemar statistic: `{s.get('mcnemar_stat', 0.0):.6f}`")
    lines.append("")

    rows = analysis.get("by_scenario", []) or []
    if rows:
        lines.append("## Scenario Deltas")
        lines.append("")
        lines.append("| Scenario | Paired Runs | A Pass% | B Pass% | Delta (A-B) | A Avg Sev | B Avg Sev |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in sorted(rows, key=lambda r: abs(r.get("delta_pass_rate_a_minus_b", 0.0)), reverse=True)[:15]:
            lines.append(
                f"| `{row.get('scenario_id')}` | {row.get('paired_runs', 0)} | "
                f"{float(row.get('pass_rate_a', 0.0)):.4f} | {float(row.get('pass_rate_b', 0.0)):.4f} | "
                f"{float(row.get('delta_pass_rate_a_minus_b', 0.0)):.4f} | "
                f"{float(row.get('avg_severity_a', 0.0)):.3f} | {float(row.get('avg_severity_b', 0.0)):.3f} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

