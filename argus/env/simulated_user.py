"""Simulated-user engines for multi-turn scenario execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SimulatedReply:
    """Generated simulated-user reply with trace metadata."""
    content: str
    rule_index: int | None = None
    rule_when: str | None = None


class SimulatedUserEngine:
    """Simulated-user engine config holder + deterministic implementation."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.mode = str(config.get("mode", "")).strip()
        self.max_user_turns = int(config.get("max_user_turns", 3))
        self.default_response = str(config.get("default_response", "Please continue."))
        raw_rules = config.get("response_rules", [])
        self.response_rules: list[dict[str, Any]] = raw_rules if isinstance(raw_rules, list) else []
        self._consumed_rule_indices: set[int] = set()

    def can_respond(self, user_turns_emitted: int) -> bool:
        """Whether simulator can emit another user reply."""
        if self.mode not in {"deterministic_template_v1", "llm_roleplay_v1"}:
            return False
        return user_turns_emitted < self.max_user_turns

    def generate_reply(
        self,
        *,
        assistant_content: str,
        user_turns_emitted: int,
    ) -> SimulatedReply | None:
        """Return the next deterministic user reply for the current assistant message."""
        if self.mode != "deterministic_template_v1":
            return None
        if not self.can_respond(user_turns_emitted):
            return None

        normalized = assistant_content.lower()
        ranked_rules = sorted(
            enumerate(self.response_rules),
            key=lambda ir: int(ir[1].get("priority", 0)),
            reverse=True,
        )
        for idx, rule in ranked_rules:
            if idx in self._consumed_rule_indices and bool(rule.get("once", False)):
                continue
            when = str(rule.get("when", "")).strip()
            if not when:
                continue

            matched = False
            if when.startswith("regex:"):
                pattern = when[len("regex:"):].strip()
                if pattern:
                    try:
                        matched = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL) is not None
                    except re.error:
                        matched = False
            else:
                matched = when.lower() in normalized

            if not matched:
                continue

            if bool(rule.get("once", False)):
                self._consumed_rule_indices.add(idx)
            return SimulatedReply(
                content=str(rule.get("reply", self.default_response)),
                rule_index=idx,
                rule_when=when,
            )

        return SimulatedReply(content=self.default_response, rule_index=None, rule_when=None)
