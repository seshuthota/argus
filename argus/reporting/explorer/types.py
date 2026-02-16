from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class JudgeCompareRequest(_Base):
    judge_model: str | None = None
    judge_temperature: float | None = None
    judge_max_tokens: int | None = None
    force: bool | None = None


class RunMatrixRequest(_Base):
    models: list[str] | None = None
    tool_modes: list[str] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    max_turns: int | None = None
    seed: int | None = None
    seed_step: int | None = None
    timeout_s: float | None = None
    ai_compare: bool | None = None
    judge_model: str | None = None


class RescoreRequest(_Base):
    reason: str | None = None
    dry_run: bool | None = None


class BulkRescoreRequest(_Base):
    scenario_id: str | None = None
    model: str | None = None
    latest_only: bool | None = None
    dry_run: bool | None = None
    reason: str | None = None
    limit: int | None = None


class ScenarioRescoreRequest(_Base):
    reason: str | None = None
    dry_run: bool | None = None
    limit: int | None = None


class ReviewActionRequest(_Base):
    action: str | None = None
    # Future-proofing: allow storing annotations/notes.
    note: str | None = None
    meta: dict[str, Any] | None = None

