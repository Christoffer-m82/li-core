"""Governed rhythm definitions and privacy-minimised open-loop contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RhythmDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: Literal["morning", "friday", "monthly", "quarterly", "annual"]
    label: str
    cadence: str
    timezone: str = "Europe/Berlin"
    mode: Literal["preview_only", "disabled"] = "preview_only"
    external_mutations_permitted: Literal[False] = False
    creates_open_loop_work: bool = True


DEFAULT_RHYTHMS = (
    RhythmDefinition(key="morning", label="Morning review", cadence="weekdays 07:30"),
    RhythmDefinition(key="friday", label="Friday review", cadence="Friday 16:00"),
    RhythmDefinition(key="monthly", label="Monthly review", cadence="first day 09:00"),
    RhythmDefinition(key="quarterly", label="Quarterly review", cadence="quarter start 09:00"),
    RhythmDefinition(key="annual", label="Annual review", cadence="January 2 09:00"),
)


class OpenLoopCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commitment_summary: str = Field(min_length=1, max_length=500)
    owed_to: str | None = Field(default=None, max_length=200)
    source_conversation_id: UUID | None = None
    source_request_id: UUID | None = None
    next_action: str = Field(min_length=1, max_length=500)
    due_at: datetime | None = None
    urgency: Literal["low", "normal", "high"] = "normal"
    sensitive: bool = False
    commitment_kind: Literal["self", "other_person"] = "self"


class OpenLoop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    open_loop_id: UUID
    commitment_summary: str
    owed_to: str | None = None
    source_conversation_id: UUID | None = None
    source_request_id: UUID | None = None
    next_action: str
    due_at: datetime | None = None
    urgency: Literal["low", "normal", "high"]
    last_raised_at: datetime | None = None
    postponement_count: int = 0
    three_postponements_reached: bool = False
    status: Literal["open", "postponed", "closed"] = "open"
    created_at: datetime
    closed_at: datetime | None = None
    commitment_kind: Literal["self", "other_person"] = "self"
    suppressed_until: datetime | None = None
    suppression_reason: Literal["not_now", "later", "leave_it"] | None = None
    blocker_prompted_at: datetime | None = None


def three_postponement_hook(count: int) -> bool:
    """A signal only; presentation/nagging behavior remains deliberately unconfigured."""
    return count >= 3
