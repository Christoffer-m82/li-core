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
        "app.li_runtime.consult_specialists",
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
        assert "INTERNAL SPECIALIST ANALYSES" in str(kwargs["system"])
        assert "Nora: Research, Intelligence & Decision Adviser" in str(kwargs["system"])
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

    def fake_consult(specialists, request):
        observed["request"] = request
        from app.specialist_runtime import NoraSpecialistResult, SpecialistConsultation

        return SpecialistConsultation(results={
            "nora": NoraSpecialistResult(
                recommendation="Use the available public criteria.", confidence=0.5,
                sources_needed=False,
            )
        })

    monkeypatch.setattr("app.li_runtime.consult_specialists", fake_consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "My answer.")
    talk_to_li("Ask Nora to recommend the best option for my priorities.")
    assert observed["request"].canonical_memory == []


def test_li_synthesizes_multiple_specialists(monkeypatch) -> None:
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    observed = {}

    def fake_consult(specialists, request):
        assert specialists == ["victor", "milo"]
        return SpecialistConsultation(results={
            name: SpecialistResult(
                recommendation=f"{name} view", confidence=0.7, sources_needed=True
            )
            for name in specialists
        })

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return "A synthesized answer."

    monkeypatch.setattr("app.li_runtime.consult_specialists", fake_consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    response = talk_to_li("Consult Victor and Milo about this business travel decision.")
    assert response == "A synthesized answer."
    assert "victor view" in observed["system"]
    assert "milo view" in observed["system"]
    assert "Synthesize them in Li's voice" in observed["system"]


def test_li_uses_valid_result_when_other_specialist_is_unavailable(monkeypatch) -> None:
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(
            results={
                "milo": SpecialistResult(
                    recommendation="Prefer Lisbon.", confidence=0.8, sources_needed=False
                )
            },
            unavailable=["victor"],
        ),
    )
    observed = {}

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return "Lisbon is the strongest available choice."

    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    response = talk_to_li("Consult Victor and Milo about this business travel decision.")
    assert response == "Lisbon is the strongest available choice."
    assert "Prefer Lisbon." in observed["system"]
    assert "Victor" in observed["system"]
    assert "validation details" in observed["system"]


def test_all_specialists_failure_falls_back_to_direct_li_reasoning(monkeypatch) -> None:
    from app.specialist_runtime import SpecialistConsultation

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(unavailable=["victor", "milo"]),
    )
    observed = {}

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return "Here is my direct assessment."

    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    response = talk_to_li("Consult Victor and Milo about this business travel decision.")
    assert response == "Here is my direct assessment."
    assert "INTERNAL SPECIALIST ANALYSES" not in observed["system"]
    assert "Answer using Li's own reasoning" in observed["system"]


def test_nora_research_request_total_failure_falls_back_transparently(monkeypatch) -> None:
    from app.specialist_runtime import (
        ResearchRequest,
        SpecialistConsultation,
        SpecialistResult,
    )

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Research first.",
                confidence=0.4,
                sources_needed=True,
                research_request=ResearchRequest(
                    query="Current vendor evidence",
                    freshness_requirement="Last 12 months",
                    source_types=["primary sources"],
                    rationale="The facts may have changed.",
                ),
            )
        }),
    )
    observed = {}

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return "I need current sources before making a firm recommendation."

    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    talk_to_li("Ask Nora to research and compare these vendors.")
    assert "Current vendor evidence" in observed["system"]
    assert "Live research was unavailable" in observed["system"]


def test_nora_research_is_executed_then_nora_is_reinvoked(monkeypatch) -> None:
    from app.specialist_runtime import ResearchRequest, SpecialistConsultation, SpecialistResult

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Research first.",
                confidence=0.4,
                sources_needed=True,
                research_request=ResearchRequest(
                    query="current vendor evidence",
                    freshness_requirement="last 30 days",
                    source_types=["primary"],
                    rationale="Facts change.",
                ),
            )
        }),
    )

    class Provider:
        def search(self, request):
            return [{
                "title": "Vendor release",
                "identifier": "https://example.test/release",
                "source": "Vendor",
                "publication_date": "2026-08-20",
                "excerpt": "The current price is 10.",
                "source_type": "primary",
            }]

    observed = {}

    def fake_nora(request, **kwargs):
        assert request.research_evidence[0]["title"] == "Vendor release"
        return SpecialistResult(
            recommendation="Choose A based on the current release.",
            findings=["Current price is 10."],
            confidence=0.8,
            sources_needed=False,
        )

    monkeypatch.setattr("app.li_runtime.delegate_to_nora", fake_nora)
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: observed.update(kwargs) or "Choose A.",
    )
    response = talk_to_li(
        "Ask Nora to research and compare these vendors.", research_provider=Provider()
    )
    assert response == "Choose A."
    assert "Choose A based on the current release." in observed["system"]


def test_specialist_prompt_explicitly_denies_direct_tool_access(monkeypatch) -> None:
    from app.specialist_runtime import SpecialistRequest, delegate_to_nora

    observed = {}
    payload = {
        "recommendation": "Use supplied evidence only.",
        "findings": [],
        "confidence": 0.5,
        "key_assumptions": [],
        "sources_needed": False,
        "follow_up_questions": [],
        "research_request": None,
    }

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return json.dumps(payload)

    monkeypatch.setattr("app.specialist_runtime.generate_claude_text", fake_generate)
    delegate_to_nora(SpecialistRequest(current_user_message="Analyze this."))
    assert "You have no tools and no database access" in observed["system"]
    assert "Li is the sole orchestrator" in observed["system"]
