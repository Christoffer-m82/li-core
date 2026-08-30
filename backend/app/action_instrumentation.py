"""Typed, caller-supplied correlation for Li-owned downstream actions."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActionAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: UUID
    request_id: UUID
    specialist_interaction_ids: list[UUID] = Field(min_length=1, max_length=12)
