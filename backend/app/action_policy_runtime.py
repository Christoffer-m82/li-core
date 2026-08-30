"""Application service for durable action-policy governance."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.action_policy import ActionPolicy, conservative_default_policy, repository_identity_mismatches
from app.runtime_data import (
    decide_action_policy_change, get_action_policy_overview, propose_action_policy_change,
    rollback_action_policy,
)


class PolicyChangeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_version: int = Field(ge=1)
    proposed_policy: ActionPolicy
    summary: str = Field(min_length=1, max_length=1000)


class PolicyDecision(BaseModel):
    decision: Literal["approve", "reject"]


class PolicyRollback(BaseModel):
    target_version: int = Field(ge=1)
    confirmation: Literal["confirm_action_policy_rollback"]


def read_policy_overview() -> dict[str, object]:
    try:
        persisted = get_action_policy_overview()
        policy = ActionPolicy.model_validate(persisted["effective_policy"])
        history = persisted.get("history", [])
        pending = persisted.get("pending_proposals", [])
    except Exception:  # Database 0.29 remains safe before migration 030 is applied.
        policy, history, pending = conservative_default_policy(), [], []
    return {
        "read_only": True,
        "effective_policy": policy.model_dump(mode="json"),
        "identity_preference_is_authority": False,
        "identity_policy_mismatches": [
            item.model_dump(mode="json") for item in repository_identity_mismatches(policy)
        ],
        "history": history,
        "pending_proposals": pending,
        "future_milestone": "Per-specialist Freshness & Evidence Policy is typed but not enabled.",
    }


def create_policy_proposal(payload: PolicyChangeProposal) -> dict[str, object]:
    return propose_action_policy_change(
        proposal_id=str(uuid4()), base_version=payload.base_version,
        proposed_policy=payload.proposed_policy.model_dump(mode="json"), summary=payload.summary,
    )


def decide_policy_proposal(proposal_id: UUID, payload: PolicyDecision) -> dict[str, object]:
    return decide_action_policy_change(str(proposal_id), payload.decision)


def rollback_policy(payload: PolicyRollback) -> dict[str, object]:
    return rollback_action_policy(payload.target_version, payload.confirmation)
