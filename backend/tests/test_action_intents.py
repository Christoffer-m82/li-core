import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.action_intents import (
    ActionIntentProposal,
    IntentDecision,
    decide_intent,
    persist_proposals,
)
from app.li_runtime import build_li_system_prompt


NOW = datetime.now(UTC)


def public(intent_id, request_id, state="proposed", result=None):
    return {
        "intent_id": intent_id, "request_id": request_id, "action_type": "task.create",
        "summary": "Create a follow-up task", "approval_state": state,
        "approval_required": True, "owner_confirmation_required": False,
        "created_at": NOW, "expires_at": NOW + timedelta(hours=24),
        "resolved_at": NOW if state in {"succeeded", "failed", "uncertain", "denied", "expired"} else None,
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


def test_structured_output_null_placeholders_are_removed_before_validation(monkeypatch):
    request_id, conversation_id = uuid4(), uuid4()
    seen = {}

    def create(**values):
        seen.update(values)
        return public(values["intent_id"], values["request_id"])

    monkeypatch.setattr("app.action_intents.create_action_intent", create)
    candidate = proposal().model_copy(update={
        "payload": {
            **proposal().payload,
            "start": None,
            "recipients": None,
            "recommendation_id": None,
            "description": "irrelevant non-null placeholder",
        }
    })
    intents = persist_proposals(
        [candidate], request_id=str(request_id), used_interaction_ids=[],
        conversation_id=str(conversation_id),
    )
    assert intents[0].approval_state == "proposed"
    assert "start" not in seen["payload"]
    assert "recipients" not in seen["payload"]
    assert "recommendation_id" not in seen["payload"]
    assert "description" not in seen["payload"]


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


@pytest.mark.parametrize("state", ["denied", "expired", "failed", "uncertain", "succeeded"])
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


def test_payload_tamper_fails_intent_before_provider(monkeypatch):
    intent_id, request_id = uuid4(), uuid4()
    calls = []

    def resolve(**values):
        calls.append(values)
        if values["decision"] == "approve":
            return {
                "outcome": "execute", "intent": public(intent_id, request_id),
                "payload": {"action": "task.create", "title": "tampered"},
                "payload_hash": "0" * 64, "request_id": request_id,
                "action_type": "task.create", "specialist_interaction_ids": [],
            }
        return {"outcome": "resolved", "intent": public(
            intent_id, request_id, "failed", values["result"]
        )}

    monkeypatch.setattr("app.action_intents.resolve_action_intent", resolve)
    provider = TaskProvider()
    result = decide_intent(intent_id, IntentDecision(decision="approve"),
                           calendar_provider=object(), task_provider=provider,
                           email_provider=object())
    assert provider.calls == 0
    assert result.approval_state == "failed"
    assert calls[-1]["execution_status"] == "failed"
    assert "tampered" not in json.dumps(calls[-1]["result"])


def test_provider_failure_resolves_uncertain_and_requires_reconciliation(monkeypatch):
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
        return {"outcome": "resolved", "intent": public(intent_id, request_id, "uncertain", {
            "status": "uncertain", "action": "task.create", "message": "uncertain",
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
    assert first.approval_state == "uncertain"
    assert transitions[-1]["execution_status"] == "uncertain"
    assert "provider detail" not in json.dumps(transitions[-1]["result"])
    assert "Check its current state" in transitions[-1]["result"]["message"]


def test_policy_rejection_finishes_failed_before_provider_boundary(monkeypatch):
    intent_id, request_id = uuid4(), uuid4()
    payload = {"action": "task.create", "title": "Follow up", "notes": None,
               "due_at": None, "timezone": None, "idempotency_key": f"intent:{intent_id}"}
    transitions = []

    def resolve(**values):
        transitions.append(values)
        if values["decision"] == "approve":
            return {"outcome": "execute", "intent": public(intent_id, request_id),
                    "payload": payload, "payload_hash": "0" * 64,
                    "request_id": request_id, "action_type": "task.create",
                    "specialist_interaction_ids": []}
        return {"outcome": "resolved", "intent": public(intent_id, request_id, "failed")}

    monkeypatch.setattr("app.action_intents.resolve_action_intent", resolve)
    monkeypatch.setattr("app.action_intents.execution_allowed", lambda *args, **kwargs: False)
    provider = TaskProvider()
    result = decide_intent(intent_id, IntentDecision(decision="approve"),
                           calendar_provider=object(), task_provider=provider,
                           email_provider=object())
    assert result.approval_state == "failed"
    assert provider.calls == 0
    assert transitions[-1]["execution_status"] == "failed"


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
    assert "REFERENCES li_conversation.conversations(id) ON DELETE SET NULL" in sql
    assert "Schema version 0.29 is already claimed" in sql
    assert "ON CONFLICT(version) DO NOTHING" not in sql
    assert "Function % has unexpected owner" in sql
    assert "Temporary function-owner authority was not removed" in sql
    assert "Action-intent function privileges are broader than intended" in sql


def test_supported_intent_contract_has_no_gmail_send():
    with pytest.raises(ValueError):
        ActionIntentProposal(action_type="email.send", summary="Send", payload={})


def test_anthropic_structured_output_schema_avoids_unsupported_array_keywords():
    source = (Path(__file__).parents[1] / "app" / "li_runtime.py").read_text(
        encoding="utf-8"
    )
    assert '"maxItems"' not in source


def test_direct_li_runtime_requires_governed_action_intents():
    prompt = build_li_system_prompt()

    assert "For every concrete state-changing request" in prompt
    assert "return a matching action_intent" in prompt
    assert "Never say or imply that an action ran" in prompt
