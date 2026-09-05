"""Durable, Li-owned approval intents and execution orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.action_policy import ActionPolicy, conservative_default_policy, execution_allowed
from app.action_instrumentation import ActionAttribution
from app.calendar_runtime import CalendarActionEnvelope, CreateCalendarAction, execute_calendar_action
from app.email_runtime import CreateEmailDraftAction, EmailActionEnvelope, execute_email_action
from app.runtime_data import create_action_intent, get_action_policy_overview, resolve_action_intent
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
    "failed", "uncertain", "denied", "expired",
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


def _effective_policy() -> ActionPolicy:
    """Fail closed to the conservative baseline until migration 030 is available."""
    try:
        return ActionPolicy.model_validate(get_action_policy_overview()["effective_policy"])
    except Exception:
        return conservative_default_policy()


_REQUEST_MODELS = {
    "calendar.create": CreateCalendarAction,
    "task.create": CreateTaskAction,
    "task.complete": CompleteTaskAction,
    "task.cancel": CancelTaskAction,
    "email.create_draft": CreateEmailDraftAction,
}

_PAYLOAD_FIELDS = {
    "calendar.create": {"title", "start", "end", "timezone", "location", "description"},
    "task.create": {"title", "notes", "due_at", "timezone"},
    "task.complete": {"task_id"},
    "task.cancel": {"task_id"},
    "email.create_draft": {
        "recipients", "cc", "bcc", "subject", "body", "thread_id",
        "in_reply_to", "references",
    },
    "governance.execute": {"recommendation_id"},
}


def _canonical_payload(proposal: ActionIntentProposal) -> tuple[dict[str, Any], str]:
    # Structured-output schemas represent action-specific optional fields as null.
    # Remove those placeholders before validating the concrete action model so
    # fields belonging to a different action cannot become provider input.
    proposal_payload = {
        key: value for key, value in proposal.payload.items()
        if key in _PAYLOAD_FIELDS[proposal.action_type] and value is not None
    }
    if proposal.action_type == "governance.execute":
        payload = proposal_payload
        if set(payload) - {"recommendation_id"} or "recommendation_id" not in payload:
            raise ActionIntentError("Invalid governance action payload.")
        payload["recommendation_id"] = str(UUID(str(payload["recommendation_id"])))
    else:
        model = _REQUEST_MODELS[proposal.action_type]
        candidate = {"action": proposal.action_type, **proposal_payload}
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

    provider_started = False
    try:
        if not execution_allowed(
            str(claim["action_type"]), approved=decision.decision == "approve",
            policy=_effective_policy(),
        ):
            raise ActionIntentError("Effective action policy rejects execution without approval.")
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
        # Every supported write is idempotent at its provider boundary, but a
        # transport/database failure after this point can still hide success.
        if action_type == "calendar.create":
            provider_started = True
            outcome = execute_calendar_action(CalendarActionEnvelope(
                request=CreateCalendarAction.model_validate(payload), approved=True,
                attribution=attribution,
            ), calendar_provider)
        elif action_type.startswith("task."):
            provider_started = True
            request = _REQUEST_MODELS[action_type].model_validate(payload)
            outcome = execute_task_action(TaskActionEnvelope(
                request=request, approved=True, attribution=attribution,
            ), task_provider)
        elif action_type == "email.create_draft":
            provider_started = True
            outcome = execute_email_action(EmailActionEnvelope(
                request=CreateEmailDraftAction.model_validate(payload), approved=True,
                attribution=attribution,
            ), email_provider)
        else:
            raise ActionIntentError(
                "Governance execution requires its existing owner executor."
            )
        result = outcome.model_dump(mode="json", exclude_none=True)
        if outcome.status != "completed":
            # A provider that explicitly reports unavailable did not accept the
            # operation; that is a definite failure, not an ambiguous effect.
            if outcome.status == "approval_required":
                provider_started = False
            result = {
                "status": "uncertain" if provider_started else "failed",
                "action": action_type,
                "message": (
                    "The provider may have completed this action. Check its current state before retrying."
                    if provider_started else
                    "The provider did not accept this action; it is safe to retry after fixing availability."
                ),
            }
    except Exception:  # noqa: BLE001 - claimed intents must never remain stuck on bad data
        outcome = None
        result = {
            "status": "uncertain" if provider_started else "failed",
            "action": claim.get("action_type", "unknown"),
            "message": (
                "The provider may have completed this action. Check its current state before retrying."
                if provider_started else "The stored action could not be executed safely."
            ),
        }

    execution_status = (
        "succeeded" if outcome is not None and outcome.status == "completed"
        else "uncertain" if provider_started else "failed"
    )
    final = resolve_action_intent(
        intent_id=str(intent_id), decision="complete",
        execution_status=execution_status,
        result=result,
    )
    return ActionIntent.model_validate(final["intent"])
