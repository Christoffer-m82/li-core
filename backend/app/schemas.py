from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.email_runtime import EmailActionEnvelope, EmailActionOutcome

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
    proposed_truth_status: str | None
    proposed_temporal_status: str | None
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


class TheoAutomatedReviewResult(BaseModel):
    status: Literal["no_pending_proposals", "processed"]
    proposal_id: UUID | None = None
    decision: Literal[
        "approve",
        "reject",
        "needs_user_confirmation",
    ] | None = None
    rationale: str | None = None
    proposal_status: str | None = None
    memory_id: UUID | None = None
    outcome: str | None = None


class OwnerMemoryConfirmation(BaseModel):
    decision: Literal[
        "confirm",
        "reject",
    ]
    note: str | None = Field(default=None, max_length=2000)


class OwnerMemoryConfirmationResult(BaseModel):
    proposal_id: UUID
    proposal_status: str
    outcome: str


class LiMemoryCaptureOutcome(BaseModel):
    status: Literal[
        "ignored",
        "stored",
        "proposed",
        "corrected",
        "forgotten",
    ]
    memory_class: ExplicitMemoryClass | None = None
    domain: str | None = None
    memory_id: UUID | None = None
    proposal_id: UUID | None = None
    reason: str | None = None


class LiChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    email_action: EmailActionEnvelope | None = None
    conversation_id: UUID | None = None
    retention_policy: str = Field(default="standard", min_length=1, max_length=100)
    retain_until: datetime | None = None
    privacy_metadata: dict[str, Any] = Field(default_factory=dict)


class LiChatResponse(BaseModel):
    response: str
    conversation_id: UUID
    memory_capture: list[LiMemoryCaptureOutcome] = Field(default_factory=list)
    memory_capture_reference: str | None = None
    memory_capture_error: str | None = None
    conversation_history_error: str | None = None
    email_action: EmailActionOutcome | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class ArtifactUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=150)
    data_base64: str = Field(min_length=1, max_length=14_000_000)
    save: bool = False
    conversation_id: UUID | None = None


class GeneratedArtifactCreate(ArtifactUpload):
    source: Literal["li_generated"] = "li_generated"


class RetentionUpdate(BaseModel):
    action: Literal["keep", "delete"]


class PrivacySettingsUpdate(BaseModel):
    artifact_retention_days: Literal[7, 14, 30, 60, 90]


class AgentSettingsUpdate(BaseModel):
    relevance_cadence_months: Literal[1, 2, 3, 6] | None


class AgentActionReview(BaseModel):
    decision: Literal["approve", "reject"]
