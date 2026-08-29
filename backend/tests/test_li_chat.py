import pytest
from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.main import app
from app.memory_capture import (
    MemoryCandidate,
    MemoryCaptureAnalysis,
    MemoryCaptureError,
    MemoryCaptureOutcome,
)

CONVERSATION_ID = "9d55e6c7-9b99-4432-a09f-bbb597580e19"


@pytest.fixture(autouse=True)
def mock_conversation_storage(monkeypatch):
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: CONVERSATION_ID)
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message-id")


def _post(message: str):
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            return client.post("/li/chat", json={"message": message})
    finally:
        app.dependency_overrides.clear()


def test_temporary_upload_context_is_used_once_but_not_saved_in_history(monkeypatch) -> None:
    saved: list[dict] = []
    monkeypatch.setattr("app.main.append_conversation_message",
                        lambda **kwargs: saved.append(kwargs) or "message-id")
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *args, **kwargs: None)

    def fake_talk(user_message: str, *, temporary_upload_context=None, **kwargs) -> str:
        assert temporary_upload_context == "File: notes.txt\nuntrusted contents"
        return "Analysed without retaining the file."

    monkeypatch.setattr("app.main.talk_to_li", fake_talk)
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/li/chat", json={
                "message": "Analyse this file",
                "temporary_upload_context": "File: notes.txt\nuntrusted contents",
            })
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [item["content"] for item in saved] == [
        "Analyse this file", "Analysed without retaining the file."]
    assert all("untrusted contents" not in item["content"] for item in saved)


def test_li_chat_defers_ordinary_capture_until_after_answer(monkeypatch) -> None:
    events: list[str] = []
    candidate = MemoryCandidate(
        action="store_explicit",
        memory_class="explicit_preference",
        domain="preferences",
        value="I prefer silver pens.",
        sensitivity="low",
        reason="Synthetic test memory.",
    )
    monkeypatch.setattr(
        "app.main.analyze_memory_capture",
        lambda message, **kwargs: MemoryCaptureAnalysis(candidates=[candidate]),
    )

    def fake_talk(
        user_message: str, *, trusted_runtime_context=None, conversation_context=None,
        research_provider=None,
    ) -> str:
        events.append("talk")
        assert trusted_runtime_context is None
        return "Noted."

    def fake_apply(analysis, *, source_reference=None):
        events.append("apply")
        assert analysis.candidates == [candidate]
        return [MemoryCaptureOutcome(
            status="stored",
            memory_class="explicit_preference",
            domain="preferences",
            memory_id="110273b2-6941-4bc7-9a2c-c1ee60209763",
            reason="Synthetic test memory.",
        )]

    monkeypatch.setattr("app.main.talk_to_li", fake_talk)
    monkeypatch.setattr("app.main.apply_memory_capture", fake_apply)
    response = _post("I prefer silver pens.")
    body = response.json()

    assert response.status_code == 200
    assert events == ["talk", "apply"]
    assert body["response"] == "Noted."
    assert body["memory_capture"][0]["status"] == "stored"
    assert body["memory_capture_error"] is None


@pytest.mark.parametrize(
    ("action", "status"),
    [("correct_explicit", "corrected"), ("forget", "forgotten")],
)
def test_li_chat_applies_change_before_answer_with_actual_outcome(
    monkeypatch, action, status
) -> None:
    events: list[str] = []
    candidate_data = {
        "action": action,
        "target_query": "notebook preference",
        "reason": "Explicit user request.",
    }
    if action == "correct_explicit":
        candidate_data.update(
            memory_class="explicit_preference",
            domain="preferences",
            value="I prefer blue notebooks.",
            sensitivity="low",
        )
    candidate = MemoryCandidate(**candidate_data)
    monkeypatch.setattr(
        "app.main.analyze_memory_capture",
        lambda message, **kwargs: MemoryCaptureAnalysis(candidates=[candidate]),
    )

    def fake_apply(analysis, *, source_reference=None):
        events.append("apply")
        return [MemoryCaptureOutcome(
            status=status,
            memory_class="explicit_preference",
            domain="preferences",
            memory_id="110273b2-6941-4bc7-9a2c-c1ee60209763",
        )]

    def fake_talk(
        user_message: str, *, trusted_runtime_context=None, conversation_context=None,
        research_provider=None,
    ) -> str:
        events.append("talk")
        assert f"success ({status})" in trusted_runtime_context
        return f"Memory {status}."

    monkeypatch.setattr("app.main.apply_memory_capture", fake_apply)
    monkeypatch.setattr("app.main.talk_to_li", fake_talk)
    response = _post("Change my notebook preference.")
    body = response.json()

    assert response.status_code == 200
    assert events == ["apply", "talk"]
    assert body["memory_capture"][0]["status"] == status
    assert body["memory_capture_error"] is None


def test_li_chat_blocks_ambiguous_forget_and_tells_li(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.analyze_memory_capture", lambda message, **kwargs: MemoryCaptureAnalysis()
    )

    def fail_apply(*args, **kwargs):
        raise AssertionError("Blocked request must not mutate memory.")

    def fake_talk(
        user_message: str, *, trusted_runtime_context=None, conversation_context=None,
        research_provider=None,
    ) -> str:
        assert "blocked" in trusted_runtime_context
        assert "did not resolve to one safe, specific memory change" in trusted_runtime_context
        return "What would you like me to forget?"

    monkeypatch.setattr("app.main.apply_memory_capture", fail_apply)
    monkeypatch.setattr("app.main.talk_to_li", fake_talk)
    response = _post("forget that")
    body = response.json()

    assert response.status_code == 200
    assert body["memory_capture"] == []
    assert body["memory_capture_error"] is None


def test_li_chat_answers_with_failed_change_context_without_retry(monkeypatch) -> None:
    calls = 0
    candidate = MemoryCandidate(
        action="forget",
        target_query="sensitive target",
        reason="Synthetic blocked request.",
    )
    monkeypatch.setattr(
        "app.main.analyze_memory_capture",
        lambda message, **kwargs: MemoryCaptureAnalysis(candidates=[candidate]),
    )

    def fake_apply(analysis, *, source_reference=None):
        nonlocal calls
        calls += 1
        raise MemoryCaptureError("Synthetic policy failure.")

    def fake_talk(
        user_message: str, *, trusted_runtime_context=None, conversation_context=None,
        research_provider=None,
    ) -> str:
        assert "failed or blocked" in trusted_runtime_context
        assert "No success may be claimed" in trusted_runtime_context
        return "I could not make that memory change."

    monkeypatch.setattr("app.main.apply_memory_capture", fake_apply)
    monkeypatch.setattr("app.main.talk_to_li", fake_talk)
    response = _post("Forget the sensitive target.")
    body = response.json()

    assert response.status_code == 200
    assert calls == 1
    assert body["memory_capture"] == []
    assert body["memory_capture_error"] == "Automatic memory capture failed."


def test_li_chat_still_answers_when_memory_analysis_fails(monkeypatch) -> None:
    def fail_analysis(message, **kwargs):
        raise MemoryCaptureError("Synthetic classifier failure.")

    def fake_talk(
        user_message: str, *, trusted_runtime_context=None, conversation_context=None,
        research_provider=None,
    ) -> str:
        assert trusted_runtime_context is None
        return "Here is your answer."

    monkeypatch.setattr("app.main.analyze_memory_capture", fail_analysis)
    monkeypatch.setattr("app.main.talk_to_li", fake_talk)
    response = _post("What should I do today?")
    body = response.json()

    assert response.status_code == 200
    assert body["response"] == "Here is your answer."
    assert body["memory_capture"] == []
    assert body["memory_capture_error"] == "Automatic memory capture failed."
