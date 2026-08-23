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