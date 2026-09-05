from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Attestation(StrictModel):
    provider: Literal["apple_app_attest", "apple_device_check", "google_play_integrity"]
    assertion: str = Field(min_length=1, max_length=16384)


class BootstrapRequest(StrictModel):
    google_id_token: str = Field(min_length=20, max_length=8192)
    platform: Literal["ios", "android"]
    attestation: Attestation | None = None


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class PermissionAssertion(StrictModel):
    state: Literal["granted"]
    checked_at: datetime


class OvernightEvent(StrictModel):
    event_id: UUID
    first_observed_at: datetime
    last_observed_at: datetime
    classification: Literal["overnight", "transit"]


class CoarsePlaceUpdate(StrictModel):
    contract_version: Literal["1.0"]
    installation_id: UUID
    update_id: UUID
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    town_city: str | None = Field(default=None, max_length=120)
    source: Literal["device_coarse"]
    observed_at: datetime
    permission: PermissionAssertion
    overnight_event: OvernightEvent | None = None


class RevokeInstallationRequest(StrictModel):
    installation_id: UUID


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=12000)
    turn_id: UUID | None = None
    conversation_id: UUID | None = None
    input_mode: Literal["text", "voice_transcript"] = "text"
