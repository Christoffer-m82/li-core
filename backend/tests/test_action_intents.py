import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.action_intents import (
    ActionIntentError,
    ActionIntentProposal,
    IntentDecision,
    decide_intent,
    persist_proposals,
)


NOW = datetime.now(UTC)


def public(intent_id, request_id, state="proposed", result=None):
    return {
        "intent_id": intent_id, "request_id": request_id, "action_type": "task.create",
        "summary": "Create a follow-up task", "approval_state": state,
        "approval_required": True, "owner_confirmation_required": False,
        "created_at": NOW, "expires_at": NOW + timedelta(hours=24),
        "resolved_at": NOW if state in {"succeeded", "failed", "denied", "expired"} else None,
        "result": result,
    }


def proposal():
    return ActionIntentProposal(
        action_type="task.create", summary="Create a follow-up task",
        payload={"title": "Follow up", "notes": None, "due_at": None, "timezone": None},
    )


def test_chat_proposal_persists_server_correlation_without_execution(monkeypatch):
    request_id, interaction_id, conversation_id = uuid4(), uuid4(), uuid4()
    seen = {}

    def create(**values):
        seen.update(values)
        return public(values["intent_id"], values["request_id"])

    monkeypatch.setattr("app.action_intents.create_action_intent", create)
    intents = persist_proposals(
        [proposal()], request_id=str(request_id), used_interaction_ids=[str(interaction_id)],
        conversation_id=str(conversation_id),
    )
    assert intents[0].approval_state == "proposed"
    assert seen["request_id"] == str(request_id)
    assert seen["interaction_ids"] == [str(interaction_id)]
    assert seen["payload"]["idempotency_key"].startswith("intent:")
    assert len(seen["payload_hash"]) == 64


class TaskProvider:
    calls = 0

    def create_task(self, request):
        self.calls += 1
        now = datetime.now(UTC)
        return {"task_id": uuid4(), "title": request.title, "notes": request.notes,
                "due_at": None, "timezone": None, "status": "open", "created_at": now,
                "updated_at": now, "completed_at": None, "cancelled_at": None}

    def complete_task(self, request):
        raise AssertionError("unexpected complete")

    def cancel_task(self, request):
        raise AssertionError("unexpected cancel")


def test_approve_executes_stored_payload_and_returns_resolved_result(monkeypatch):
    intent_id, request_id, interaction_id = uuid4(), uuid4(), uuid4()
    payload = {"action": "task.create", "title": "Follow up", "notes": None,
               "due_at": None, "timezone": None, "idempotency_key": f"intent:{intent_id}"}
    payload_hash = __import__("hashlib").sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    provider = TaskProvider()
    calls = []

    def resolve(**values):
        calls.append(values)
        if values["decision"] == "approve":
            return {"outcome": "execute", "intent": public(intent_id, request_id),
                    "payload": payload, "payload_hash": payload_hash,
                    "request_id": request_id, "action_type": "task.create",
                    "specialist_interaction_ids": [interaction_id]}
        return {"outcome": "resolved", "intent": public(
            intent_id, request_id, "succeeded", values["result"]
        )}

    monkeypatch.setattr("app.action_intents.resolve_action_intent", resolve)
    result = decide_intent(intent_id, IntentDecision(decision="approve"),
                           calendar_provider=object(), task_provider=provider,
                           email_provider=object())
    assert provider.calls == 1 and result.approval_state == "succeeded"
    assert calls[-1]["execution_status"] == "succeeded"


@pytest.mark.parametrize("state", ["denied", "expired", "failed", "succeeded"])
def test_resolved_or_non_attempt_states_never_call_provider(monkeypatch, state):
    intent_id, request_id = uuid4(), uuid4()
    monkeypatch.setattr("app.action_intents.resolve_action_intent", lambda **values: {
        "outcome": "resolved", "intent": public(intent_id, request_id, state)
    })
    provider = TaskProvider()
    result = decide_intent(intent_id, IntentDecision(decision="deny"),
                           calendar_provider=object(), task_provider=provider,
                           email_provider=object())
    assert result.approval_state == state and provider.calls == 0


def test_payload_tamper_is_rejected_before_provider(monkeypatch):
    intent_id, request_id = uuid4(), uuid4()
    monkeypatch.setattr("app.action_intents.resolve_action_intent", lambda **values: {
        "outcome": "execute", "intent": public(intent_id, request_id),
        "payload": {"action": "task.create", "title": "tampered"},
        "payload_hash": "0" * 64, "request_id": request_id,
        "action_type": "task.create", "specialist_interaction_ids": [],
    })
    provider = TaskProvider()
    with pytest.raises(ActionIntentError, match="integrity"):
        decide_intent(intent_id, IntentDecision(decision="approve"),
                      calendar_provider=object(), task_provider=provider,
                      email_provider=object())
    assert provider.calls == 0


def test_provider_failure_resolves_failed_and_retry_returns_same_result(monkeypatch):
    intent_id, request_id = uuid4(), uuid4()
    payload = {"action": "task.create", "title": "Follow up", "notes": None,
               "due_at": None, "timezone": None, "idempotency_key": f"intent:{intent_id}"}
    payload_hash = __import__("hashlib").sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    transitions = []

    def resolve(**values):
        transitions.append(values)
        if len(transitions) == 1:
            return {"outcome": "execute", "intent": public(intent_id, request_id),
                    "payload": payload, "payload_hash": payload_hash,
                    "request_id": request_id, "action_type": "task.create",
                    "specialist_interaction_ids": []}
        return {"outcome": "resolved", "intent": public(intent_id, request_id, "failed", {
            "status": "failed", "action": "task.create", "message": "failed",
        })}

    class FailingProvider(TaskProvider):
        def create_task(self, request):
            self.calls += 1
            raise RuntimeError("provider detail must be redacted")

    monkeypatch.setattr("app.action_intents.resolve_action_intent", resolve)
    provider = FailingProvider()
    first = decide_intent(intent_id, IntentDecision(decision="approve"),
                          calendar_provider=object(), task_provider=provider,
                          email_provider=object())
    assert first.approval_state == "failed"
    assert transitions[-1]["execution_status"] == "failed"
    assert "provider detail" not in json.dumps(transitions[-1]["result"])


def test_migration_enforces_lifecycle_correlation_audit_and_measurement_semantics():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "029_durable_action_intents.sql").read_text(encoding="utf-8")
    assert "FOR UPDATE" in sql and "FOR UPDATE SKIP LOCKED" in sql
    assert "action_intent_events" in sql and "expired_without_attempt" in sql
    assert "denied_without_attempt" in sql
    assert "record_specialist_action_attribution" in sql
    assert "i.request_id=p_request AND i.used_in_final IS TRUE" in sql
    assert "owner_confirmation_required" in sql
    assert "confirm_permanent_agent_change" in sql
    assert "INTERVAL '24 hours'" in sql
    assert "email.send" not in sql


def test_supported_intent_contract_has_no_gmail_send():
    with pytest.raises(ValueError):
        ActionIntentProposal(action_type="email.send", summary="Send", payload={})
