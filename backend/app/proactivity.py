"""Governed, conservative proactivity contracts and pure scheduling logic."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from enum import Enum
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RhythmKey(str, Enum):
    morning = "morning"
    friday = "friday"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"


class RhythmState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: RhythmKey
    label: str
    local_time: time
    timezone: str = "Europe/Berlin"
    enabled: bool = False
    approval_state: Literal["preview_only", "approved", "disabled"] = "preview_only"
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    last_run: datetime | None = None
    next_run: datetime | None = None
    last_result: Literal["generated", "empty", "suppressed", "failed"] | None = None
    last_run_key: str | None = None
    stood_down_until: datetime | None = None

    @model_validator(mode="after")
    def approved_before_enabled(self) -> "RhythmState":
        if self.enabled and self.approval_state != "approved":
            raise ValueError("A rhythm cannot run before explicit approval.")
        ZoneInfo(self.timezone)
        return self

    @property
    def runnable(self) -> bool:
        now = datetime.now(UTC)
        return (self.enabled and self.approval_state == "approved"
                and (self.stood_down_until is None or self.stood_down_until <= now))


DEFAULT_LOCAL_TIMES = {
    RhythmKey.morning: time(7, 30), RhythmKey.friday: time(16, 0),
    RhythmKey.monthly: time(9, 0), RhythmKey.quarterly: time(9, 0),
    RhythmKey.annual: time(9, 0),
}


def next_occurrence(key: RhythmKey, *, after: datetime, local_time: time,
                    timezone: str, birthday: date | None = None) -> datetime:
    """Return a timezone-aware UTC instant strictly after ``after``."""
    zone = ZoneInfo(timezone)
    local_after = after.astimezone(zone)
    candidate = datetime.combine(local_after.date(), local_time, zone)
    for offset in range(0, 370):
        day = local_after.date() + timedelta(days=offset)
        valid = (
            (key == RhythmKey.morning and day.weekday() < 5)
            or (key == RhythmKey.friday and day.weekday() == 4)
            or (key == RhythmKey.monthly and day.day == 1)
            or (key == RhythmKey.quarterly and day.day == 1 and day.month in {1, 4, 7, 10})
            or (key == RhythmKey.annual and (day.month, day.day) == (
                (birthday.month, birthday.day) if birthday else (1, 2)))
        )
        candidate = datetime.combine(day, local_time, zone)
        if valid and candidate > local_after:
            return candidate.astimezone(UTC)
    raise ValueError("No valid rhythm occurrence found in scheduling horizon.")


class BriefItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal[
        "today", "commitment", "private_mail", "family", "movement", "finance",
        "sports", "personal_admin", "home", "training", "next_week", "enjoyment",
        "costs", "health", "documents", "goals", "preparation", "reflection",
    ]
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=1000)
    why_now: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=200)
    urgency: Literal["low", "normal", "high"] = "normal"
    sensitive: bool = False
    evidence: dict[str, Any] | None = None
    action_intent_id: UUID | None = None


class ProactiveBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rhythm: RhythmKey
    run_key: str
    title: str
    items: tuple[BriefItem, ...]

    @property
    def neutral_preview(self) -> str:
        return "A new private Li brief is ready." if any(i.sensitive for i in self.items) else self.title


CURRENT_WORLD_CATEGORIES = {"finance", "sports"}


def build_brief(rhythm: RhythmKey, run_key: str, candidates: list[BriefItem]) -> ProactiveBrief | None:
    """Build only from grounded candidates; empty categories and empty briefs disappear."""
    allowed = {
        RhythmKey.morning: {"today", "commitment", "private_mail", "family", "movement", "finance", "sports"},
        RhythmKey.friday: {"commitment", "personal_admin", "home", "training", "next_week", "enjoyment"},
        RhythmKey.monthly: {"commitment", "costs", "finance", "health", "documents"},
        RhythmKey.quarterly: {"commitment", "goals", "preparation", "enjoyment"},
        RhythmKey.annual: {"reflection"},
    }[rhythm]
    def grounded(item: BriefItem) -> bool:
        if item.category not in CURRENT_WORLD_CATEGORIES:
            return True
        evidence = item.evidence or {}
        if not (evidence.get("freshness_policy_compliant")
                and evidence.get("provider_coverage_compliant")):
            return False
        return item.category != "sports" or fixture_is_eligible(
            source_authority=str(evidence.get("source_authority", "")),
            verified=bool(evidence.get("verified")),
            competitive=bool(evidence.get("competitive")),
        )

    items = tuple(item for item in candidates if item.category in allowed and grounded(item))
    if not items:
        return None
    return ProactiveBrief(rhythm=rhythm, run_key=run_key,
                          title=f"{rhythm.value.title()} brief", items=items)


def fixture_is_eligible(*, source_authority: str, verified: bool, competitive: bool) -> bool:
    return source_authority == "official_primary" and verified and competitive


def third_postponement_prompt_due(count: int, prompted_at: datetime | None) -> bool:
    return count >= 3 and prompted_at is None


def should_surface(*, last_raised_at: datetime | None, suppressed_until: datetime | None,
                   category_stood_down: bool, now: datetime) -> bool:
    if category_stood_down or (suppressed_until and suppressed_until > now):
        return False
    return last_raised_at is None or last_raised_at.astimezone(now.tzinfo).date() < now.date()
