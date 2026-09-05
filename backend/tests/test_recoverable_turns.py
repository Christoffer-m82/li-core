from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.main import app
from app.memory_capture import MemoryCaptureAnalysis
from app.li_runtime import LiRuntimeError
from app.runtime_data import RuntimeDataCapabilityUnavailable, RuntimeDataError
from app.schemas import LiChatRequest, LiChatResponse


ROOT = Path(__file__).parents[2]


def test_chat_contract_accepts_stable_turn_identity_and_reports_durability():
    turn_id = uuid4()
    request = LiChatRequest(message="Hej", turn_id=turn_id)
    response = LiChatResponse(response="Hej", conversation_id=uuid4(), turn_id=turn_id,
                              turn_state="completed")
    assert request.turn_id == turn_id
    assert response.turn_state == "completed"


def test_recoverable_turn_migration_binds_owner_payload_and_truthful_states():
    sql = (ROOT / "memory" / "migrations" /
           "038_recoverable_turns_and_actions.sql").read_text(encoding="utf-8")
    assert "owner_user_id" in sql and "request_hash" in sql
    assert "FOR UPDATE" in sql
    assert "state IN ('accepted','completed','replay_expired','failed','uncertain')" in sql
    assert "execution_lease_expired_outcome_unknown" in sql
    assert "provider_outcome_unobserved" in sql
    assert "'outcome','conflict'" in sql
    assert "ON DELETE CASCADE" in sql
    assert "state<>'completed' OR conversation_id IS NOT NULL" in sql
    assert "INTERVAL '30 days'" in sql
    assert "replay_expired" in sql
    assert "expire_chat_replay_responses" in sql
    assert "ON CONFLICT(id) DO NOTHING" in sql
    assert "Schema version 0.38 is already claimed" in sql
    assert "ON CONFLICT(version) DO NOTHING" not in sql


def test_phase_2_recovery_migration_fences_attempts_and_enforces_truth_pairing():
    sql = (ROOT / "memory" / "migrations" /
           "039_phase_2_truth_and_turn_recovery.sql").read_text(encoding="utf-8")
    assert "attempt_token UUID" in sql
    assert "external_effect_started BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "external_effect_state TEXT NOT NULL DEFAULT 'none'" in sql
    assert "'action_prepared','provider_dispatched','provider_completed','provider_no_effect'" in sql
    assert "CREATE FUNCTION li_api.mark_chat_turn_progress" in sql
    assert "CREATE FUNCTION li_api.finish_chat_turn_attempt" in sql
    assert "t.attempt_token IS DISTINCT FROM p_attempt_token" in sql
    assert "t.response_expires_at<=v_now" in sql
    assert "t.external_effect_state IN ('none','prepared','no_effect')" in sql
    assert "Inference proposals must retain inferred truth status" in sql
    assert "li_api.correct_explicit_memory(UUID,TEXT,TEXT,TEXT,TEXT,BOOLEAN)" in sql
    assert "SET private_to_li=TRUE" in sql
    assert "Schema version 0.39 is already claimed" in sql
    assert "ON CONFLICT(version) DO NOTHING" not in sql


def test_web_and_native_clients_forward_turn_identity():
    frontend = (ROOT / "frontend" / "app" / "main.py").read_text(encoding="utf-8")
    browser = (ROOT / "frontend" / "static" / "assets" / "app.js").read_text(
        encoding="utf-8"
    )
    workspace = (ROOT / "frontend" / "static" / "assets" / "workspace.js").read_text(
        encoding="utf-8"
    )
    native = (ROOT / "native-gateway" / "app" / "contracts.py").read_text(encoding="utf-8")
    assert 'body["turn_id"] = str(payload.turn_id)' in frontend
    assert "turn_id: turn.turnId" in browser
    assert "turn_id: pendingTurnId" in workspace
    assert "turn_id: UUID | None = None" in native


def test_model_provider_has_bounded_timeout_and_no_hidden_retries():
    source = (ROOT / "backend" / "app" / "claude.py").read_text(encoding="utf-8")
    assert "timeout=settings.claude_timeout_seconds" in source
    assert "max_retries=0" in source


def test_duplicate_completed_turn_replays_without_model_or_new_effect(monkeypatch):
    turn_id, conversation_id = uuid4(), uuid4()
    stored = LiChatResponse(
        response="Already completed.", conversation_id=conversation_id,
        turn_id=turn_id, turn_state="completed",
    ).model_dump(mode="json")
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "replay", "response": stored,
    })
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model must not rerun")),
    )
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Do this once", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["response"] == "Already completed."
    assert response.json()["turn_state"] == "completed_replay"


def test_uncertain_turn_blocks_blind_retry(monkeypatch):
    turn_id = uuid4()
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "uncertain", "response": None,
    })
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Do this once", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "turn_outcome_uncertain"


def test_turn_identity_conflict_stops_before_model_or_effect(monkeypatch):
    turn_id = uuid4()
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "conflict", "response": None,
    })
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model must not run")),
    )
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Different request", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "turn_identity_conflict"


def test_expired_replay_tombstone_prevents_duplicate_execution(monkeypatch):
    turn_id = uuid4()
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "replay_expired", "response": None,
    })
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model must not run")),
    )
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Do this once", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "turn_replay_expired"


def test_turn_claim_failure_never_degrades_into_unprotected_execution(monkeypatch):
    turn_id = uuid4()
    monkeypatch.setattr(
        "app.main.begin_chat_turn",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeDataError("database unavailable")),
    )
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("model must not run")),
    )
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Do this once", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "turn_claim_unavailable"


def test_missing_turn_capability_preserves_rolling_upgrade_compatibility(monkeypatch):
    turn_id, conversation_id = uuid4(), uuid4()
    monkeypatch.setattr(
        "app.main.begin_chat_turn",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeDataCapabilityUnavailable("not installed")),
    )
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: str(conversation_id))
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message")
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *args, **kwargs: MemoryCaptureAnalysis())
    monkeypatch.setattr("app.main.talk_to_li", lambda *args, **kwargs: "Legacy safe reply.")
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Synthetic request", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["turn_state"] == "durability_unavailable"


def test_completed_turn_is_bound_and_recorded_once(monkeypatch):
    turn_id, conversation_id = uuid4(), uuid4()
    finished = []
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {"outcome": "accepted"})
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: str(conversation_id))
    monkeypatch.setattr("app.main.bind_chat_turn_conversation", lambda **kwargs: kwargs)
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message")
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *args, **kwargs: MemoryCaptureAnalysis())
    monkeypatch.setattr("app.main.talk_to_li", lambda *args, **kwargs: "Completed safely.")
    monkeypatch.setattr("app.main.finish_chat_turn", lambda **kwargs: finished.append(kwargs) or {})
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Synthetic request", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["turn_state"] == "completed"
    assert len(finished) == 1 and finished[0]["state"] == "completed"


def test_model_failure_after_message_save_is_failed_not_effect_uncertain(monkeypatch):
    turn_id, conversation_id = uuid4(), uuid4()
    finished = []
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {"outcome": "accepted"})
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: str(conversation_id))
    monkeypatch.setattr("app.main.bind_chat_turn_conversation", lambda **kwargs: kwargs)
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message")
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *args, **kwargs: MemoryCaptureAnalysis())
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(LiRuntimeError("synthetic model failure")),
    )
    monkeypatch.setattr("app.main.finish_chat_turn", lambda **kwargs: finished.append(kwargs) or {})
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Synthetic request", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert len(finished) == 1 and finished[0]["state"] == "failed"


def test_retry_after_saved_message_reuses_conversation_without_duplicate_user_write(monkeypatch):
    turn_id, conversation_id, attempt_token = uuid4(), uuid4(), uuid4()
    appended = []
    progress = []
    finished = []
    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "accepted", "conversation_id": str(conversation_id),
        "attempt_token": str(attempt_token), "progress_stage": "message_saved",
    })
    monkeypatch.setattr("app.main.bind_chat_turn_conversation", lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("an already-bound retry must not rebind")
    ))
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: appended.append(kwargs))
    monkeypatch.setattr("app.main.mark_chat_turn_progress", lambda **kwargs: progress.append(kwargs) or {})
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *args, **kwargs: MemoryCaptureAnalysis())
    monkeypatch.setattr("app.main.talk_to_li", lambda *args, **kwargs: "Recovered safely.")
    monkeypatch.setattr("app.main.finish_chat_turn_attempt", lambda **kwargs: finished.append(kwargs) or {})
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Synthetic request", "turn_id": str(turn_id),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert not [item for item in appended if item["role"] == "user"]
    assert len([item for item in appended if item["role"] == "assistant"]) == 1
    assert [item["stage"] for item in progress] == ["model_started", "response_ready"]
    assert len(finished) == 1 and finished[0]["attempt_token"] == attempt_token
    diagnostics = response.json()["diagnostics"]
    assert diagnostics["recovery"]["resumed_stage"] == "response_ready"
    assert "Synthetic request" not in str(diagnostics)


def test_read_only_provider_failure_does_not_make_turn_effect_uncertain(monkeypatch):
    turn_id, conversation_id, attempt_token = uuid4(), uuid4(), uuid4()
    stages, finished = [], []

    class Provider:
        def search_messages(self, request):
            raise RuntimeError("synthetic read failure")

    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "accepted", "attempt_token": str(attempt_token),
        "progress_stage": "accepted",
    })
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: str(conversation_id))
    monkeypatch.setattr("app.main.bind_chat_turn_conversation", lambda **kwargs: kwargs)
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message")
    monkeypatch.setattr("app.main.mark_chat_turn_progress",
                        lambda **kwargs: stages.append(kwargs["stage"]) or {})
    monkeypatch.setattr("app.main.analyze_memory_capture",
                        lambda *args, **kwargs: MemoryCaptureAnalysis())
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(LiRuntimeError("synthetic model failure")),
    )
    monkeypatch.setattr("app.main.finish_chat_turn_attempt",
                        lambda **kwargs: finished.append(kwargs) or {})
    previous = app.state.email_provider
    app.state.email_provider = Provider()
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Find a message", "turn_id": str(turn_id),
            "email_action": {"request": {"action": "email.search", "query": "synthetic"}},
        })
    finally:
        app.state.email_provider = previous
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert stages == ["conversation_bound", "message_saved", "model_started"]
    assert finished[-1]["state"] == "failed"


def test_known_provider_completion_is_persisted_before_later_model_failure(monkeypatch):
    turn_id, conversation_id, attempt_token = uuid4(), uuid4(), uuid4()
    stages, finished = [], []

    class Provider:
        def create_draft(self, request):
            return {
                "draft_id": "draft-1", "message_id": "message-1", "thread_id": None,
                "recipients": request.recipients, "cc": [], "bcc": [],
                "subject": request.subject, "body": request.body,
            }

    monkeypatch.setattr("app.main.begin_chat_turn", lambda **kwargs: {
        "outcome": "accepted", "attempt_token": str(attempt_token),
        "progress_stage": "accepted",
    })
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: str(conversation_id))
    monkeypatch.setattr("app.main.bind_chat_turn_conversation", lambda **kwargs: kwargs)
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message")
    monkeypatch.setattr("app.main.mark_chat_turn_progress",
                        lambda **kwargs: stages.append(kwargs["stage"]) or {})
    monkeypatch.setattr("app.main.analyze_memory_capture",
                        lambda *args, **kwargs: MemoryCaptureAnalysis())
    monkeypatch.setattr(
        "app.main.talk_to_li",
        lambda *args, **kwargs: (_ for _ in ()).throw(LiRuntimeError("synthetic model failure")),
    )
    monkeypatch.setattr("app.main.finish_chat_turn_attempt",
                        lambda **kwargs: finished.append(kwargs) or {})
    previous = app.state.email_provider
    app.state.email_provider = Provider()
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/li/chat", json={
            "message": "Create the approved draft", "turn_id": str(turn_id),
            "email_action": {
                "approved": True,
                "request": {
                    "action": "email.create_draft", "recipients": ["owner@example.com"],
                    "subject": "Synthetic", "body": "Synthetic body",
                    "idempotency_key": "synthetic-draft",
                },
            },
        })
    finally:
        app.state.email_provider = previous
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert stages == [
        "conversation_bound", "message_saved", "action_prepared", "provider_dispatched",
        "provider_completed", "model_started",
    ]
    assert finished[-1]["state"] == "uncertain"
