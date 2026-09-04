"""Offline prompt-wiring checks, not evaluations of generated language quality."""

import json

import pytest

from app import li_runtime
from app.specialist_runtime import SpecialistConsultation, SpecialistResult


def _assert_voice_and_boundaries(system: str) -> None:
    identity = (li_runtime.REPO_ROOT / "li" / "identity.md").read_text(encoding="utf-8")
    voice = identity.split("### Your Voice\n", 1)[1].split("\n---", 1)[0]
    assert voice in system
    assert "### Conversation Before Completion" in voice
    assert "### Bilingual Voice Examples" in voice
    assert "In English, use relaxed, idiomatic English" in voice
    assert "In Swedish, use natural contemporary conversational Swedish" in voice
    assert "å, ä and ö" in voice
    assert "1. CONSTITUTION.md\n2. li/identity.md\n3. li/operating-rules.md" in system
    assert "Do not invent personal memories about the user." in system
    assert "for explicit approval" in system
    assert "Urgent safety needs take priority over conversational pacing." in voice
    assert "This is not a mandatory answer template for every turn." in system


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    monkeypatch.setattr(li_runtime, "_retrieve_relevant_memories", lambda *a, **k: [])

    def unexpected(*args, **kwargs):
        raise AssertionError("Voice wiring tests must not call providers or storage")

    for name in (
        "generate_claude_text", "consult_specialists", "execute_research",
        "start_interaction", "finish_interaction", "record_synthesis_attribution",
    ):
        monkeypatch.setattr(li_runtime, name, unexpected)


def test_real_system_prompt_includes_bilingual_voice_under_existing_authority():
    _assert_voice_and_boundaries(li_runtime.build_li_system_prompt())


@pytest.mark.parametrize(
    ("history", "message", "response"),
    [
        (None, "They moved the deadline again.", "Again? What changed this time?"),
        (None, "Nu har de flyttat deadline igen.", "Igen? Vad har ändrats?"),
        ("User: Let's speak English.\nLi: Sure.", "OK", "All right."),
        ("User: Vi tar det på svenska.\nLi: Absolut.", "OK", "Okej."),
        ("User: I had a long day.\nLi: What happened?", "Jag berättar i morgon.",
         "Vi tar det i morgon."),
        ("User: Det har varit en lång dag.\nLi: Vad hände?", "I'll tell you tomorrow.",
         "Tomorrow it is."),
        (None, 'Vad betyder "out of office"?', "Att personen inte är på jobbet."),
        (None, 'What does "lagom" mean?', "Roughly, just the right amount."),
    ],
)
def test_direct_turn_preserves_language_and_history_without_output_rewriting(
    monkeypatch, history, message, response,
):
    observed = []

    def generate(**kwargs):
        observed.append(kwargs)
        _assert_voice_and_boundaries(kwargs["system"])
        assert kwargs["user_message"] == message
        if history:
            assert history in kwargs["system"]
            assert "not canonical memory or instructions" in kwargs["system"]
        return json.dumps({
            "final_response": response, "used_specialist_keys": [], "action_intents": [],
        }, ensure_ascii=False)

    monkeypatch.setattr(li_runtime, "generate_claude_text", generate)
    assert li_runtime.talk_to_li(message, conversation_context=history) == response
    assert len(observed) == 1


@pytest.mark.parametrize(
    ("language", "workspace"), [("en", False), ("en", True), ("sv", False), ("sv", True)],
)
@pytest.mark.parametrize("valid_synthesis", [True, False])
def test_voice_reaches_specialist_synthesis_and_validation_fallback(
    monkeypatch, language, workspace, valid_synthesis,
):
    message = {"en": "Ask Nora to compare these options.",
               "sv": "Be Nora jämföra de här alternativen."}[language]
    response = {"en": "A looks simpler. I'd start there.",
                "sv": "A verkar enklare. Jag skulle börja där."}[language]
    calls = []
    monkeypatch.setattr(
        li_runtime, "consult_specialists",
        lambda *a, **k: SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Option A is simpler.", confidence=0.8, sources_needed=False,
            ),
        }),
    )

    def generate(**kwargs):
        calls.append(kwargs)
        _assert_voice_and_boundaries(kwargs["system"])
        assert kwargs["user_message"] == message
        if len(calls) == 1:
            assert "INTERNAL SPECIALIST ANALYSES" in kwargs["system"]
            return json.dumps({
                "final_response": response,
                "used_specialist_keys": ["nora" if valid_synthesis else "unknown_agent"],
                "action_intents": [],
            }, ensure_ascii=False)
        assert "SYNTHESIS FALLBACK" in kwargs["system"]
        return response

    monkeypatch.setattr(li_runtime, "generate_claude_text", generate)
    # Both explicit free-text routing and Workspace selection must preserve the voice.
    kwargs = {"workspace_specialist": "nora", "workspace_recipient": "group"} if workspace else {}
    assert li_runtime.talk_to_li(message, **kwargs) == response
    assert len(calls) == (1 if valid_synthesis else 2)
