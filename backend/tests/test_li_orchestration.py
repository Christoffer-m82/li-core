import json

from app.li_runtime import talk_to_li


def _memory(*, private_to_li: bool = False) -> dict[str, object]:
    return {
        "memory_id": "110273b2-6941-4bc7-9a2c-c1ee60209763",
        "memory_class": "explicit_preference",
        "domain": "preferences",
        "title": "Decision preference",
        "value_text": "I prefer reversible decisions.",
        "truth_status": "confirmed",
        "temporal_status": "current",
        "sensitivity": "personal",
        "private_to_li": private_to_li,
        "confidence": 1.0,
        "confirmed_by_user": True,
    }


def test_direct_route_does_not_call_specialist(monkeypatch) -> None:
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.delegate_to_nora",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must stay with Li")),
    )
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text", lambda **kwargs: "A direct answer."
    )
    assert talk_to_li("What is compound interest?") == "A direct answer."


def test_nora_gets_bounded_context_and_li_synthesizes(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [_memory()]
    )

    def fake_generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return json.dumps({
                "recommendation": "Prefer the reversible option.",
                "findings": ["It better matches the stated preference."],
                "confidence": 0.8,
                "key_assumptions": ["Both options are viable."],
                "sources_needed": False,
                "follow_up_questions": [],
            })
        assert "NORA SPECIALIST ANALYSIS" in str(kwargs["system"])
        assert "Prefer the reversible option." in str(kwargs["system"])
        return "I would choose the reversible option."

    monkeypatch.setattr("app.specialist_runtime.generate_claude_text", fake_generate)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    history = "x" * 7000
    response = talk_to_li(
        "Ask Nora to recommend the best option for my priorities.",
        conversation_context=history,
    )

    specialist_packet = json.loads(str(calls[0]["user_message"]))
    assert len(specialist_packet["conversation_context"]) == 6000
    assert specialist_packet["canonical_memory"][0]["value"] == "I prefer reversible decisions."
    assert response == "I would choose the reversible option."


def test_private_memory_is_never_shared_with_nora(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.li_runtime._retrieve_relevant_memories",
        lambda *a, **k: [_memory(private_to_li=True)],
    )
    observed = {}

    def fake_delegate(request):
        observed["request"] = request
        from app.specialist_runtime import NoraSpecialistResult
        return NoraSpecialistResult(
            recommendation="Use the available public criteria.",
            confidence=0.5,
            sources_needed=False,
        )

    monkeypatch.setattr("app.li_runtime.delegate_to_nora", fake_delegate)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "My answer.")
    talk_to_li("Ask Nora to recommend the best option for my priorities.")
    assert observed["request"].canonical_memory == []

