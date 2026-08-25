from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.main import app
from app.memory_capture import (
    MemoryCaptureError,
    MemoryCaptureOutcome,
)


def test_li_chat_returns_automatic_memory_capture(
    monkeypatch,
) -> None:
    captured: dict[str, str | None] = {}

    def fake_talk_to_li(user_message: str) -> str:
        assert user_message == "I prefer silver pens."
        return "Noted."

    def fake_capture_memory_from_message(
        user_message: str,
        source_reference: str | None = None,
    ) -> list[MemoryCaptureOutcome]:
        captured["message"] = user_message
        captured["source_reference"] = source_reference

        return [
            MemoryCaptureOutcome(
                status="stored",
                memory_class="explicit_preference",
                domain="preferences",
                memory_id="110273b2-6941-4bc7-9a2c-c1ee60209763",
                proposal_id=None,
                reason="Synthetic test memory.",
            )
        ]

    monkeypatch.setattr(
        "app.main.talk_to_li",
        fake_talk_to_li,
    )
    monkeypatch.setattr(
        "app.main.capture_memory_from_message",
        fake_capture_memory_from_message,
    )

    app.dependency_overrides[require_api_token] = lambda: None

    try:
        with TestClient(app) as client:
            response = client.post(
                "/li/chat",
                json={
                    "message": "I prefer silver pens.",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["response"] == "Noted."
    assert body["memory_capture_error"] is None

    assert body["memory_capture_reference"].startswith(
        "li-chat:"
    )

    assert len(body["memory_capture"]) == 1

    memory = body["memory_capture"][0]

    assert memory["status"] == "stored"
    assert memory["memory_class"] == "explicit_preference"
    assert memory["domain"] == "preferences"
    assert (
        memory["memory_id"]
        == "110273b2-6941-4bc7-9a2c-c1ee60209763"
    )
    assert memory["proposal_id"] is None

    assert captured["message"] == "I prefer silver pens."
    assert (
        captured["source_reference"]
        == body["memory_capture_reference"]
    )


def test_li_chat_still_answers_when_memory_capture_fails(
    monkeypatch,
) -> None:
    def fake_talk_to_li(user_message: str) -> str:
        return "Here is your answer."

    def fake_capture_memory_from_message(
        user_message: str,
        source_reference: str | None = None,
    ) -> list[MemoryCaptureOutcome]:
        raise MemoryCaptureError(
            "Synthetic memory capture failure."
        )

    monkeypatch.setattr(
        "app.main.talk_to_li",
        fake_talk_to_li,
    )
    monkeypatch.setattr(
        "app.main.capture_memory_from_message",
        fake_capture_memory_from_message,
    )

    app.dependency_overrides[require_api_token] = lambda: None

    try:
        with TestClient(app) as client:
            response = client.post(
                "/li/chat",
                json={
                    "message": "What should I do today?",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["response"] == "Here is your answer."
    assert body["memory_capture"] == []

    assert body["memory_capture_reference"].startswith(
        "li-chat:"
    )

    assert (
        body["memory_capture_error"]
        == "Automatic memory capture failed."
    )