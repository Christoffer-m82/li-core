import json

import pytest
from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.li_runtime import talk_to_li
from app.main import app
from app.memory_capture import MemoryCaptureAnalysis
from app.specialist_runtime import SpecialistConsultation, SpecialistResult


@pytest.mark.parametrize("recipient", ["group", "specialist"])
def test_workspace_routes_followup_to_selected_specialist_and_keeps_li(monkeypatch, recipient):
    observed = {}
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])

    def consult(keys, request):
        observed["keys"] = keys
        observed["request"] = request
        return SpecialistConsultation(results={"nora": SpecialistResult(
            recommendation="Consider the alternatives.", confidence=.7, sources_needed=False,
        )})

    def generate(**kwargs):
        observed["system"] = kwargs["system"]
        return json.dumps({"final_response": "Li synthesis", "used_specialist_keys": ["nora"]})

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", generate)
    response = talk_to_li("Hello", workspace_specialist="nora", workspace_recipient=recipient,
                          conversation_context="user: Prior question", temporary_upload_context="File data")
    assert response == "Li synthesis"
    assert observed["keys"] == ["nora"]
    assert observed["request"].conversation_context == "user: Prior question"
    assert observed["request"].temporary_upload_context == "File data"
    assert "not a private thread" in observed["system"]
    assert "action-confirmation rules still apply" in observed["system"]


def test_workspace_chat_endpoint_forwards_selection_without_rewriting_owner_message(monkeypatch):
    observed = {}
    monkeypatch.setattr("app.main.create_conversation", lambda **k: "00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **k: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **k: "message-id")
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *a, **k: MemoryCaptureAnalysis())

    def talk(message, **kwargs):
        observed.update(kwargs)
        observed["message"] = message
        return "Reply"

    monkeypatch.setattr("app.main.talk_to_li", talk)
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/li/chat", json={"message": "Follow up", "workspace_specialist": "nora", "workspace_recipient": "specialist"})
            for invalid in ["li", "heimdall", "unknown"]:
                assert client.post("/li/chat", json={"message": "Hi", "workspace_specialist": invalid}).status_code == 422
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert observed["workspace_specialist"] == "nora"
    assert observed["workspace_recipient"] == "specialist"
    assert observed["message"] == "Follow up"
