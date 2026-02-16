"""Confidence scoring utilities for detection clauses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any


_HISTORY_RELATIVE_PATH = Path("confidence") / "pattern_history.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


@dataclass(frozen=True)
class PatternComplexity:
    """Deterministic complexity features for a regex pattern."""

    length: int
    literal_token_count: int
    alternation_count: int
    quantifier_count: int
    wildcard_quantified_count: int
    anchor_count: int
    group_count: int
    char_class_count: int
    lookaround_count: int
    word_boundary_count: int
    structural_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "length": self.length,
            "literal_token_count": self.literal_token_count,
            "alternation_count": self.alternation_count,
            "quantifier_count": self.quantifier_count,
            "wildcard_quantified_count": self.wildcard_quantified_count,
            "anchor_count": self.anchor_count,
            "group_count": self.group_count,
            "char_class_count": self.char_class_count,
            "lookaround_count": self.lookaround_count,
            "word_boundary_count": self.word_boundary_count,
            "structural_ratio": round(self.structural_ratio, 4),
        }


def pattern_history_key(clause_type: str, pattern: str) -> str:
    """Build a stable key for one detection pattern."""
    raw = f"{clause_type}\n{pattern}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{clause_type}:{digest}"


def compute_regex_pattern_complexity(pattern: str) -> dict[str, Any]:
    """Compute complexity metrics used by confidence scoring."""
    p = pattern.strip()
    quantifier_count = len(re.findall(r"(?<!\\)(?:\*|\+|\?|\{\d+(?:,\d*)?\})", p))
    wildcard_quantified_count = len(re.findall(r"(?<!\\)\.\*|(?<!\\)\.\+", p))
    regex_chars = len(re.findall(r"[\[\]\(\)\{\}\|\.\*\+\?\\^$]", p))
    length = len(p)
    structural_ratio = (regex_chars / length) if length else 0.0

    metrics = PatternComplexity(
        length=length,
        literal_token_count=len(re.findall(r"[A-Za-z0-9]{2,}", p)),
        alternation_count=p.count("|"),
        quantifier_count=quantifier_count,
        wildcard_quantified_count=wildcard_quantified_count,
        anchor_count=p.count("^") + p.count("$"),
        group_count=len(re.findall(r"(?<!\\)\(", p)),
        char_class_count=len(re.findall(r"(?<!\\)\[[^\]]+\]", p)),
        lookaround_count=len(re.findall(r"\(\?(?:<?[=!])", p)),
        word_boundary_count=len(re.findall(r"\\b", p)),
        structural_ratio=structural_ratio,
    )
    return metrics.to_dict()


def estimate_regex_base_confidence(pattern: str) -> float:
    """
    Estimate base confidence from regex complexity.

    Lower confidence for broad/ambiguous patterns; slight boost for anchored,
    specific, token-rich patterns.
    """
    p = pattern.strip()
    if p in (".*", ".+"):
        return 0.2
    if p.lower() in (r"\w+", r"[a-z]+", r"[a-z0-9]+"):
        return 0.45

    metrics = compute_regex_pattern_complexity(p)
    score = 0.92

    if metrics["length"] < 5:
        score -= 0.22
    if metrics["length"] > 220:
        score -= 0.08

    score -= min(0.36, metrics["wildcard_quantified_count"] * 0.18)

    alternations = int(metrics["alternation_count"])
    if alternations >= 8:
        score -= 0.08
    if alternations >= 14:
        score -= 0.07

    quantifiers = int(metrics["quantifier_count"])
    if quantifiers >= 8:
        score -= 0.08
    if quantifiers >= 12:
        score -= 0.08

    literals = int(metrics["literal_token_count"])
    if literals <= 1:
        score -= 0.12
    elif literals >= 3:
        score += 0.03

    if int(metrics["anchor_count"]) > 0:
        score += 0.04
    if int(metrics["word_boundary_count"]) > 0:
        score += 0.03

    if int(metrics["lookaround_count"]) > 2:
        score -= 0.05
    if float(metrics["structural_ratio"]) > 0.65:
        score -= 0.08
    if int(metrics["char_class_count"]) >= 4:
        score -= 0.05

    return _clamp(score, 0.15, 0.99)


def load_detection_confidence_history(reports_root: str | Path = "reports") -> dict[str, Any]:
    """Load persisted confidence history for detection patterns."""
    path = Path(reports_root) / _HISTORY_RELATIVE_PATH
    if not path.exists():
        return {"version": 1, "updated_at": None, "patterns": {}, "recent_observations": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "updated_at": None, "patterns": {}, "recent_observations": []}
    if not isinstance(payload, dict):
        return {"version": 1, "updated_at": None, "patterns": {}, "recent_observations": []}
    patterns = payload.get("patterns")
    if not isinstance(patterns, dict):
        payload["patterns"] = {}
    recent = payload.get("recent_observations")
    if not isinstance(recent, list):
        payload["recent_observations"] = []
    payload.setdefault("version", 1)
    payload.setdefault("updated_at", None)
    return payload


def get_pattern_history_entry(
    history: dict[str, Any] | None,
    *,
    clause_type: str,
    pattern: str,
) -> dict[str, Any] | None:
    """Return one pattern's historical metrics from history payload."""
    if not isinstance(history, dict):
        return None
    patterns = history.get("patterns")
    if not isinstance(patterns, dict):
        return None
    key = pattern_history_key(clause_type, pattern)
    entry = patterns.get(key)
    return entry if isinstance(entry, dict) else None


def calculate_confidence_from_historical_performance(
    pattern: str,
    *,
    clause_type: str,
    history_entry: dict[str, Any] | None = None,
    unsupported_clause_count: int = 0,
) -> float:
    """
    Calculate confidence using base complexity + historical performance.

    Historical component uses:
    - detection accuracy (`correct_count / total_evaluations`)
    - false-positive rate (`false_positive_count / match_count`)
    - unsupported rate (`unsupported_count / total_evaluations`)
    """
    base = estimate_regex_base_confidence(pattern)
    confidence = base

    if isinstance(history_entry, dict):
        total = max(int(history_entry.get("total_evaluations", 0) or 0), 0)
        correct = max(int(history_entry.get("correct_count", 0) or 0), 0)
        matched = max(int(history_entry.get("match_count", 0) or 0), 0)
        false_positive = max(int(history_entry.get("false_positive_count", 0) or 0), 0)
        unsupported = max(int(history_entry.get("unsupported_count", 0) or 0), 0)

        if total > 0:
            accuracy = _clamp(correct / total)
            false_positive_rate = _clamp(false_positive / matched) if matched > 0 else 0.0
            support = _clamp(total / 30.0)
            historical_quality = (0.65 * accuracy) + (0.35 * (1.0 - false_positive_rate))
            confidence = ((1.0 - support) * base) + (support * historical_quality)

            unsupported_rate = _clamp(unsupported / total)
            confidence *= max(0.45, 1.0 - (unsupported_rate * 0.5))

            if matched >= 5 and false_positive_rate >= 0.5:
                confidence = min(confidence, 0.55)

    if unsupported_clause_count > 0:
        confidence -= min(0.4, unsupported_clause_count * 0.08)

    return _clamp(confidence)


def annotate_pattern_observations(
    observations: list[dict[str, Any]] | None,
    *,
    expression_matched: bool,
    unsupported_clause_count: int,
) -> list[dict[str, Any]]:
    """Attach evaluation-outcome labels used for historical FP/accuracy tracking."""
    if not observations:
        return []
    out: list[dict[str, Any]] = []
    for item in observations:
        if not isinstance(item, dict):
            continue
        matched = bool(item.get("matched", False))
        applicable = bool(item.get("applicable", True))
        expected_positive = bool(expression_matched) if applicable else False
        is_true_positive = applicable and matched and expected_positive
        is_false_positive = applicable and matched and not expected_positive
        is_correct = applicable and (matched == expected_positive)

        annotated = dict(item)
        annotated["expected_positive"] = expected_positive
        annotated["is_true_positive"] = is_true_positive
        annotated["is_false_positive"] = is_false_positive
        annotated["is_correct"] = is_correct
        annotated["unsupported_clause_count"] = max(0, int(unsupported_clause_count))
        out.append(annotated)
    return out


def record_detection_pattern_observations(
    observations: list[dict[str, Any]],
    *,
    reports_root: str | Path = "reports",
    run_id: str | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """Persist pattern observations and update running historical metrics."""
    history = load_detection_confidence_history(reports_root)
    patterns = history.setdefault("patterns", {})
    if not isinstance(patterns, dict):
        patterns = {}
        history["patterns"] = patterns

    recent = history.setdefault("recent_observations", [])
    if not isinstance(recent, list):
        recent = []
        history["recent_observations"] = recent

    now = _now_iso()
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        clause_type = str(obs.get("clause_type") or "").strip()
        pattern = str(obs.get("pattern") or "")
        if not clause_type or not pattern:
            continue
        key = pattern_history_key(clause_type, pattern)
        entry = patterns.get(key)
        if not isinstance(entry, dict):
            entry = {
                "pattern_key": key,
                "pattern": pattern,
                "clause_type": clause_type,
                "first_seen_at": now,
                "last_seen_at": now,
                "total_evaluations": 0,
                "match_count": 0,
                "correct_count": 0,
                "true_positive_count": 0,
                "false_positive_count": 0,
                "unsupported_count": 0,
                "accuracy": 0.0,
                "false_positive_rate": 0.0,
            }
            patterns[key] = entry

        applicable = bool(obs.get("applicable", True))
        if applicable:
            entry["total_evaluations"] = int(entry.get("total_evaluations", 0)) + 1
            if bool(obs.get("matched", False)):
                entry["match_count"] = int(entry.get("match_count", 0)) + 1
            if bool(obs.get("is_correct", False)):
                entry["correct_count"] = int(entry.get("correct_count", 0)) + 1
            if bool(obs.get("is_true_positive", False)):
                entry["true_positive_count"] = int(entry.get("true_positive_count", 0)) + 1
            if bool(obs.get("is_false_positive", False)):
                entry["false_positive_count"] = int(entry.get("false_positive_count", 0)) + 1
            entry["unsupported_count"] = (
                int(entry.get("unsupported_count", 0))
                + max(0, int(obs.get("unsupported_clause_count", 0) or 0))
            )

        total = max(int(entry.get("total_evaluations", 0)), 0)
        match_count = max(int(entry.get("match_count", 0)), 0)
        correct = max(int(entry.get("correct_count", 0)), 0)
        false_positive = max(int(entry.get("false_positive_count", 0)), 0)
        entry["accuracy"] = round((correct / total) if total else 0.0, 4)
        entry["false_positive_rate"] = round((false_positive / match_count) if match_count else 0.0, 4)
        entry["last_seen_at"] = now

        recent.append(
            {
                "timestamp": now,
                "run_id": run_id,
                "scenario_id": scenario_id,
                "pattern_key": key,
                "pattern": pattern,
                "clause_type": clause_type,
                "matched": bool(obs.get("matched", False)),
                "expected_positive": bool(obs.get("expected_positive", False)),
                "is_false_positive": bool(obs.get("is_false_positive", False)),
            }
        )

    if len(recent) > 500:
        history["recent_observations"] = recent[-500:]

    history["updated_at"] = now

    out_path = Path(reports_root) / _HISTORY_RELATIVE_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(out_path.parent),
        delete=False,
    ) as tf:
        json.dump(history, tf, indent=2, ensure_ascii=True)
        temp_path = tf.name
    Path(temp_path).replace(out_path)
    return history

