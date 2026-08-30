"""Durable, Li-owned approval intents and execution orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.action_instrumentation import ActionAttribution
from app.calendar_runtime import CalendarActionEnvelope, CreateCalendarAction, execute_calendar_action
from app.email_runtime import CreateEmailDraftAction, EmailActionEnvelope, execute_email_action
from app.runtime_data import create_action_intent, resolve_action_intent
from app.task_runtime import (
    CancelTaskAction,
    CompleteTaskAction,
    CreateTaskAction,
    TaskActionEnvelope,
    execute_task_action,
)

ActionType = Literal[
    "calendar.create", "task.create", "task.complete", "task.cancel",
    "email.create_draft", "governance.execute",
]
IntentState = Literal[
    "proposed", "owner_confirmation_required", "executing", "succeeded",
    "failed", "denied", "expired",
]


class ActionIntentProposal(BaseModel):
    """Model-produced proposal. It has no authority and is validated before persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    action_type: ActionType
    summary: str = Field(min_length=1, max_length=1000)
    payload: dict[str, Any]


class ActionIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_id: UUID
    request_id: UUID
    action_type: ActionType
    summary: str
    approval_state: IntentState
    approval_required: bool = True
    owner_confirmation_required: bool = False
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None
    result: dict[str, Any] | None = None


class IntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "deny"]
    owner_confirmation: Literal["confirm_permanent_agent_change"] | None = None


class ActionIntentError(RuntimeError):
    pass


_REQUEST_MODELS = {
    "calendar.create": CreateCalendarAction,
    "task.create": CreateTaskAction,
    "task.complete": CompleteTaskAction,
    "task.cancel": CancelTaskAction,
    "email.create_draft": CreateEmailDraftAction,
}


def _canonical_payload(proposal: ActionIntentProposal) -> tuple[dict[str, Any], str]:
    if proposal.action_type == "governance.execute":
        payload = dict(proposal.payload)
        if set(payload) - {"recommendation_id"} or "recommendation_id" not in payload:
            raise ActionIntentError("Invalid governance action payload.")
        payload["recommendation_id"] = str(UUID(str(payload["recommendation_id"])))
    else:
        model = _REQUEST_MODELS[proposal.action_type]
        candidate = {"action": proposal.action_type, **proposal.payload}
        if proposal.action_type in {"task.create", "email.create_draft"}:
            candidate["idempotency_key"] = "server-generated-after-validation"
        payload = model.model_validate(candidate).model_dump(
            mode="json"
        )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, hashlib.sha256(encoded.encode()).hexdigest()


def persist_proposals(
    proposals: list[ActionIntentProposal], *, request_id: str | None,
    used_interaction_ids: list[str], conversation_id: str,
) -> list[ActionIntent]:
    """Persist validated proposals with server-generated correlation and idempotency."""
    if not proposals or request_id is None:
        return []
    created: list[ActionIntent] = []
    for proposal in proposals[:4]:
        payload, payload_hash = _canonical_payload(proposal)
        intent_id = uuid4()
        if "idempotency_key" in payload:
            payload["idempotency_key"] = f"intent:{intent_id}"
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload_hash = hashlib.sha256(encoded.encode()).hexdigest()
        row = create_action_intent(
            intent_id=str(intent_id), request_id=request_id,
            interaction_ids=used_interaction_ids, conversation_id=conversation_id,
            action_type=proposal.action_type, summary=proposal.summary,
            payload=payload, payload_hash=payload_hash,
            owner_confirmation_required=proposal.action_type == "governance.execute",
        )
        created.append(ActionIntent.model_validate(row))
    return created


def decide_intent(
    intent_id: UUID, decision: IntentDecision, *, calendar_provider: object,
    task_provider: object, email_provider: object,
) -> ActionIntent:
    """Atomically claim or deny an intent, then execute only stored server-side data."""
    claim = resolve_action_intent(
        intent_id=str(intent_id), decision=decision.decision,
        owner_confirmation=decision.owner_confirmation,
    )
    public = ActionIntent.model_validate(claim["intent"])
    if claim["outcome"] != "execute":
        return public

    try:
        payload = claim["payload"]
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if payload_hash != claim["payload_hash"]:
            raise ActionIntentError("Stored action payload integrity check failed.")

        attribution = None
        interactions = claim.get("specialist_interaction_ids") or []
        if interactions:
            attribution = ActionAttribution(
                action_id=intent_id, request_id=UUID(str(claim["request_id"])),
                specialist_interaction_ids=[UUID(str(value)) for value in interactions],
            )
        action_type = claim["action_type"]
        if action_type == "calendar.create":
            outcome = execute_calendar_action(CalendarActionEnvelope(
                request=CreateCalendarAction.model_validate(payload), approved=True,
                attribution=attribution,
            ), calendar_provider)
        elif action_type.startswith("task."):
            request = _REQUEST_MODELS[action_type].model_validate(payload)
            outcome = execute_task_action(TaskActionEnvelope(
                request=request, approved=True, attribution=attribution,
            ), task_provider)
        elif action_type == "email.create_draft":
            outcome = execute_email_action(EmailActionEnvelope(
                request=CreateEmailDraftAction.model_validate(payload), approved=True,
                attribution=attribution,
            ), email_provider)
        else:
            raise ActionIntentError(
                "Governance execution requires its existing owner executor."
            )
        result = outcome.model_dump(mode="json", exclude_none=True)
    except Exception:  # noqa: BLE001 - claimed intents must never remain stuck on bad data
        outcome = None
        result = {
            "status": "failed", "action": claim.get("action_type", "unknown"),
            "message": "The stored action could not be executed safely.",
        }

    final = resolve_action_intent(
        intent_id=str(intent_id), decision="complete",
        execution_status=(
            "succeeded" if outcome is not None and outcome.status == "completed" else "failed"
        ),
        result=result,
    )
    return ActionIntent.model_validate(final["intent"])
