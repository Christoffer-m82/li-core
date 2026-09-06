import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.main import app
from app.memory_capture import MemoryCandidate, MemoryCaptureAnalysis
from app.runtime_data import RuntimeDataError
from app.specialist_runtime import SpecialistConsultation, SpecialistResult


def _install_controlled_chat_fixture(monkeypatch) -> dict[str, object]:
    conversation_id = uuid4()
    interaction_id = uuid4()
    attempt_token = uuid4()
    messages: list[dict[str, object]] = []
    turns: dict[str, dict[str, object]] = {}
    observed: dict[str, object] = {
        "consultations": [],
        "syntheses": 0,
        "messages": messages,
    }

    def begin_chat_turn(*, turn_id: UUID, request_hash: str) -> dict[str, object]:
        existing = turns.get(str(turn_id))
        if existing and existing.get("state") == "completed":
            return {"outcome": "replay", "response": existing["response"]}
        turns[str(turn_id)] = {
            "request_hash": request_hash,
            "state": "accepted",
            "attempt_token": attempt_token,
            "progress_stage": "accepted",
        }
        return {
            "outcome": "accepted",
            "attempt_token": str(attempt_token),
            "progress_stage": "accepted",
        }

    def bind_chat_turn_conversation(**kwargs) -> dict[str, object]:
        turn = turns[str(kwargs["turn_id"])]
        turn["conversation_id"] = str(kwargs["conversation_id"])
        return turn

    def mark_chat_turn_progress(**kwargs) -> dict[str, object]:
        turn = turns[str(kwargs["turn_id"])]
        turn["progress_stage"] = kwargs["stage"]
        return turn

    def finish_chat_turn_attempt(**kwargs) -> dict[str, object]:
        turn = turns[str(kwargs["turn_id"])]
        turn.update({"state": kwargs["state"], "response": kwargs.get("response")})
        return turn

    def append_conversation_message(**kwargs) -> str:
        messages.append({
            "message_id": str(uuid4()),
            "role": kwargs["role"],
            "content": kwargs["content"],
            "privacy_metadata": kwargs["privacy_metadata"],
            "created_at": "2026-09-06T09:00:00Z",
        })
        return str(messages[-1]["message_id"])

    def consult_specialists(names, request) -> SpecialistConsultation:
        observed["consultations"].append(list(names))
        assert list(names) == ["nora"]
        assert request.current_user_message
        return SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Prefer the more reversible option.",
                findings=["It preserves the owner's ability to change course."],
                confidence=0.8,
                key_assumptions=["Both options are otherwise viable."],
                sources_needed=False,
            ),
        })

    def synthesize(**kwargs) -> str:
        observed["syntheses"] = int(observed["syntheses"]) + 1
        assert "Prefer the more reversible option." in str(kwargs["system"])
        return json.dumps({
            "final_response": "Nora's comparison favors the more reversible option.",
            "used_specialist_keys": ["nora"],
            "action_intents": [],
        })

    monkeypatch.setattr("app.main.begin_chat_turn", begin_chat_turn)
    monkeypatch.setattr("app.main.bind_chat_turn_conversation", bind_chat_turn_conversation)
    monkeypatch.setattr("app.main.mark_chat_turn_progress", mark_chat_turn_progress)
    monkeypatch.setattr("app.main.finish_chat_turn_attempt", finish_chat_turn_attempt)
    monkeypatch.setattr("app.main.create_conversation", lambda **kwargs: str(conversation_id))
    monkeypatch.setattr(
        "app.main.get_recent_conversation_messages", lambda **kwargs: list(messages)
    )
    monkeypatch.setattr("app.main.append_conversation_message", append_conversation_message)
    monkeypatch.setattr("app.main.conversation_messages", lambda value: list(messages))
    monkeypatch.setattr(
        "app.main.analyze_memory_capture", lambda *args, **kwargs: MemoryCaptureAnalysis()
    )
    monkeypatch.setattr(
        "app.main.get_place_settings",
        lambda: (_ for _ in ()).throw(RuntimeDataError("controlled unavailable fixture")),
    )
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.li_runtime.consult_specialists", consult_specialists)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", synthesize)
    monkeypatch.setattr(
        "app.li_runtime.start_interaction", lambda *args, **kwargs: str(interaction_id)
    )
    monkeypatch.setattr("app.li_runtime.finish_interaction", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.li_runtime.record_synthesis_attribution", lambda *args, **kwargs: None
    )
    observed.update({
        "conversation_id": conversation_id,
        "interaction_id": interaction_id,
        "turns": turns,
    })
    return observed


@pytest.mark.parametrize(
    "message",
    [
        "Ask Nora to compare these options.",
        "Be Nora jämföra de här alternativen.",
    ],
)
def test_bilingual_specialist_chat_persists_reloads_and_replays_once(
    monkeypatch, message,
) -> None:
    fixture = _install_controlled_chat_fixture(monkeypatch)
    turn_id = uuid4()
    payload = {"message": message, "turn_id": str(turn_id)}
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            completed = client.post("/li/chat", json=payload)
            history = client.get(f"/conversations/{fixture['conversation_id']}")
            replay = client.post("/li/chat", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert completed.status_code == 200
    assert completed.json()["turn_state"] == "completed"
    attribution = completed.json()["specialist_attribution"]
    assert UUID(attribution["request_id"])
    assert attribution["used_interaction_ids"] == [str(fixture["interaction_id"])]
    assert history.status_code == 200
    assert [item["role"] for item in history.json()["messages"]] == ["user", "assistant"]
    assert history.json()["messages"][0]["content"] == message
    assert history.json()["messages"][1]["content"] == completed.json()["response"]

    assert replay.status_code == 200
    assert replay.json()["turn_state"] == "completed_replay"
    assert replay.json()["response"] == completed.json()["response"]
    assert fixture["consultations"] == [["nora"]]
    assert fixture["syntheses"] == 1
    assert len(fixture["messages"]) == 2


@pytest.mark.parametrize("message", [
    "Ask Nora to compare these options from our previous conversation.",
    "Be Nora jämföra de här alternativen från vårt tidigare samtal.",
])
@pytest.mark.parametrize("existing_history", [False, True])
def test_historical_recall_stays_private_in_workspace_and_derived_outputs(
    monkeypatch, message, existing_history,
):
    fixture = _install_controlled_chat_fixture(monkeypatch)
    if existing_history:
        fixture["messages"].append({
            "role": "user", "content": "Compare reversible options.",
            "privacy_metadata": {"private_to_li": False, "allowed_specialists": ["nora"]},
        })
    private_history = "Synthetic private notebook preference: amber covers."
    packets, captures = [], []
    monkeypatch.setattr("app.main.search_conversation_history", lambda *args: [{
        "created_at": "2026-09-01T09:00:00Z", "conversation_id": str(uuid4()),
        "role": "user", "snippet": private_history,
    }])
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *args, **kwargs:
                        MemoryCaptureAnalysis(candidates=[MemoryCandidate(
                            action="store_explicit", memory_class="explicit_preference",
                            domain="preferences", value="Synthetic preference", sensitivity="low",
                        )]))
    monkeypatch.setattr("app.main.apply_memory_capture",
                        lambda *args, **kwargs: captures.append(kwargs) or [])

    def consult(names, request):
        packets.append(request)
        return SpecialistConsultation(results={"nora": SpecialistResult(
            recommendation="Compare reversibility.", confidence=0.8, sources_needed=False,
        )})

    def synthesize(**kwargs):
        assert private_history in str(kwargs["system"])
        return json.dumps({"final_response": private_history,
                           "used_specialist_keys": ["nora"], "action_intents": []})

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", synthesize)
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/li/chat", json={
                "message": message, "turn_id": str(uuid4()), "workspace_specialist": "nora",
            })
            metadata = fixture["messages"][-1]["privacy_metadata"]
            # A later Workspace turn must not launder Li's private recalled answer.
            followup = client.post("/li/chat", json={
                "message": "Ask Nora to compare these options.", "turn_id": str(uuid4()),
                "conversation_id": str(fixture["conversation_id"]),
                "workspace_specialist": "nora",
            })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert followup.status_code == 200
    assert len(packets) == 2
    assert all(private_history not in packet.model_dump_json() for packet in packets)
    assert metadata["private_to_li"] is True
    assert metadata["allowed_specialists"] == []
    assert captures and captures[0]["source_private_to_li"] is True
