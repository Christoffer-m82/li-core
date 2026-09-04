from uuid import UUID
import pytest

from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.main import app
from app.memory_capture import MemoryCaptureAnalysis


def test_chat_creates_persists_and_returns_conversation_id(monkeypatch) -> None:
    conversation_id = "ac8d03d3-0417-48e2-b603-a84f4432bdc1"
    writes: list[tuple[str, str]] = []
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: conversation_id)
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr(
        "app.main.append_conversation_message",
        lambda **kwargs: writes.append((kwargs["role"], kwargs["content"])) or "message-id",
    )
    monkeypatch.setattr(
        "app.main.analyze_memory_capture",
        lambda message, **kwargs: MemoryCaptureAnalysis(),
    )
    monkeypatch.setattr("app.main.talk_to_li", lambda message, **kwargs: "Hello back.")
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/li/chat", json={"message": "Hello"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert UUID(response.json()["conversation_id"]) == UUID(conversation_id)
    assert writes == [("user", "Hello"), ("assistant", "Hello back.")]


def test_static_conversation_search_route_precedes_uuid_detail_route(monkeypatch) -> None:
    monkeypatch.setattr("app.main.search_conversation_history", lambda query, limit: [])
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get("/conversations/search", params={"q": "migration", "limit": 3})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_chat_passes_bounded_history_to_runtime_and_change_resolver(monkeypatch) -> None:
    conversation_id = "4d9b7df2-9b69-4a62-bd7e-cef00bd4d82b"
    history = [
        {"role": "user", "content": "I prefer green notebooks."},
        {"role": "assistant", "content": "Got it."},
    ]
    observed: dict[str, str | None] = {}
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: history)
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message-id")

    def analyze(message, *, conversation_context=None):
        observed["capture"] = conversation_context
        return MemoryCaptureAnalysis()

    def talk(message, *, conversation_context=None, **kwargs):
        observed["runtime"] = conversation_context
        return "You told me you prefer green notebooks."

    monkeypatch.setattr("app.main.analyze_memory_capture", analyze)
    monkeypatch.setattr("app.main.talk_to_li", talk)
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post(
                "/li/chat",
                json={"message": "What did I just tell you?", "conversation_id": conversation_id},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert observed["capture"] == "user: I prefer green notebooks.\nassistant: Got it."
    assert observed["runtime"] == observed["capture"]


def test_chat_reuses_conversation_without_creating_another(monkeypatch) -> None:
    conversation_id = "67433621-7441-416e-ab1e-0067953272a8"
    monkeypatch.setattr(
        "app.main.create_conversation",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not create")),
    )
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **kwargs: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message-id")
    monkeypatch.setattr(
        "app.main.analyze_memory_capture",
        lambda message, **kwargs: MemoryCaptureAnalysis(),
    )
    monkeypatch.setattr("app.main.talk_to_li", lambda message, **kwargs: "Continued.")
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post(
                "/li/chat", json={"message": "Continue", "conversation_id": conversation_id}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id


@pytest.mark.parametrize("message", ["forget that", "glöm det"])
def test_unresolved_contextual_forget_is_blocked_even_with_history(monkeypatch, message) -> None:
    conversation_id = "d729b771-a656-470e-bf83-2f542f910154"
    monkeypatch.setattr(
        "app.main.get_recent_conversation_messages",
        lambda **kwargs: [{"role": "user", "content": "We discussed two preferences."}],
    )
    monkeypatch.setattr("app.main.append_conversation_message", lambda **kwargs: "message-id")
    monkeypatch.setattr(
        "app.main.analyze_memory_capture",
        lambda message, **kwargs: MemoryCaptureAnalysis(),
    )

    def talk(message, *, trusted_runtime_context=None, **kwargs):
        assert "blocked" in trusted_runtime_context
        return "Which specific memory should I forget?"

    monkeypatch.setattr("app.main.talk_to_li", talk)
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post(
                "/li/chat", json={"message": message, "conversation_id": conversation_id}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["memory_capture"] == []
