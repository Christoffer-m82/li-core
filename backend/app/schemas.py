from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ExplicitMemoryClass = Literal[
    "explicit_fact",
    "explicit_preference",
    "explicit_opinion",
]

MemorySensitivity = Literal[
    "low",
    "personal",
]


class ExplicitMemoryCreate(BaseModel):
    memory_class: ExplicitMemoryClass
    domain: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=5000)
    title: str | None = Field(default=None, max_length=250)
    sensitivity: MemorySensitivity = "personal"
    private_to_li: bool = False
    source_reference: str | None = Field(default=None, max_length=500)


class ExplicitMemoryCreated(BaseModel):
    status: Literal["stored"] = "stored"
    memory_id: UUID


class RecalledMemory(BaseModel):
    memory_id: UUID
    memory_class: str
    domain: str
    title: str | None
    value_text: str | None
    truth_status: str
    temporal_status: str
    sensitivity: str
    private_to_li: bool
    confidence: float
    source_type: str
    source_reference: str | None
    confirmed_by_user: bool
    valid_from: datetime | None
    valid_until: datetime | None
    created_at: datetime
    relevance: float

class MemoryProposalCreate(BaseModel):
    proposed_by_agent: str = Field(min_length=1, max_length=100)
    memory_class: str = Field(min_length=1, max_length=100)
    domain: str = Field(min_length=1, max_length=100)
    value_text: str = Field(min_length=1, max_length=5000)
    reason: str | None = Field(default=None, max_length=2000)
    truth_status: str | None = Field(default=None, max_length=100)
    temporal_status: str | None = Field(default=None, max_length=100)
    sensitivity: str = Field(default="personal", max_length=100)
    source_reference: str | None = Field(default=None, max_length=500)


class MemoryProposalCreated(BaseModel):
    status: Literal["proposed"] = "proposed"
    proposal_id: UUID


class PendingMemoryProposal(BaseModel):
    proposal_id: UUID
    proposed_by_agent: str
    proposed_class: str
    proposed_domain: str
    proposed_value_text: str
    proposed_truth_status: str
    proposed_temporal_status: str
    proposed_sensitivity: str
    reason: str | None
    source_reference: str | None
    created_at: datetime


class MemoryProposalReview(BaseModel):
    decision: Literal[
        "approve",
        "reject",
        "needs_user_confirmation",
    ]
    review_note: str | None = Field(default=None, max_length=2000)
    final_truth_status: str | None = Field(default=None, max_length=100)
    final_temporal_status: str | None = Field(default=None, max_length=100)
    final_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryProposalReviewResult(BaseModel):
    proposal_id: UUID
    proposal_status: str
    memory_id: UUID | None
    outcome: str