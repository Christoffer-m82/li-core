import json

import pytest

from app.li_runtime import talk_to_li, talk_to_li_with_outcome


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


@pytest.mark.parametrize("message", ["What is the weather today?", "Vad är vädret idag?"])
def test_direct_current_question_fails_closed_when_evidence_is_unavailable(
    monkeypatch, message,
) -> None:
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: json.dumps({
            "final_response": "It is sunny and 22 degrees now.",
            "used_specialist_keys": [],
            "action_intents": [],
        }),
    )

    outcome = talk_to_li_with_outcome(message)

    assert "22" not in outcome.response
    assert not outcome.action_intents
    assert "verify" in outcome.response.lower() or "verifiera" in outcome.response.lower()


@pytest.mark.parametrize(
    "message", ["What is the weather today without Milo?", "Vad är vädret idag utan Milo?"],
)
def test_current_evidence_gate_survives_specialist_exclusion(monkeypatch, message) -> None:
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Blocked current facts must not reach an unverified direct model path")
        ),
    )

    outcome = talk_to_li_with_outcome(message)

    assert outcome.action_intents == []
    assert outcome.decision_trace["validation_path"] == "direct_evidence_blocked"
    assert "verify" in outcome.response.lower() or "verifiera" in outcome.response.lower()


@pytest.mark.parametrize(
    "message,response",
    [
        ("They moved the deadline again.", "Again? What changed this time?"),
        ("Nu har de flyttat deadline igen.", "Igen? Vad har ändrats?"),
    ],
)
def test_incidental_freshness_word_does_not_block_general_conversation(
    monkeypatch, message, response,
) -> None:
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: response)

    outcome = talk_to_li_with_outcome(message)

    assert outcome.response == response
    assert outcome.decision_trace["turn_evidence_required"] is False


def test_direct_response_cannot_invent_specialist_attribution_or_actions(monkeypatch) -> None:
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: json.dumps({
            "final_response": "Nora says to do it.",
            "used_specialist_keys": ["nora"],
            "action_intents": [{
                "action_type": "task.create",
                "summary": "Do it",
                "payload": {"title": "Synthetic task", "notes": "", "due_at": None},
            }],
        }),
    )

    outcome = talk_to_li_with_outcome("Hello")

    assert "Nora says" not in outcome.response
    assert outcome.action_intents == []


def test_nora_gets_bounded_context_and_li_synthesizes(monkeypatch) -> None:
    from app.governed_systems import ConversationContextMessage

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
        return json.dumps({
            "final_response": "I would choose the reversible option.",
            "used_specialist_keys": ["nora"],
        })

    monkeypatch.setattr("app.specialist_runtime.generate_claude_text", fake_generate)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    history = "x" * 5500
    response = talk_to_li(
        "Ask Nora to recommend the best option for my priorities.",
        conversation_context=history,
        conversation_messages=[ConversationContextMessage(
            role="user", content=history, allowed_specialists=("nora",),
        )],
    )

    specialist_packet = json.loads(str(calls[0]["user_message"]))
    assert len(specialist_packet["conversation_context"]) == 5506
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


def test_corrected_memory_is_disclosed_only_to_permitted_specialist(monkeypatch) -> None:
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    corrected = _memory()
    corrected["value_text"] = "I now prefer option B."
    monkeypatch.setattr(
        "app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [corrected],
    )
    observed = {}

    def consult(_specialists, request):
        observed["memory"] = request.canonical_memory
        return SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Use the current confirmed preference.", confidence=0.8,
                sources_needed=False,
            ),
        })

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "Use B.")
    talk_to_li("Ask Nora to compare these for my preferences.")
    assert [item.value for item in observed["memory"]] == ["I now prefer option B."]
    assert all(item.truth_status == "confirmed" for item in observed["memory"])


def test_private_or_undisclosed_conversation_is_never_shared_with_specialist(
    monkeypatch,
) -> None:
    """R5: privacy survives the history channel, not only canonical memory."""
    from app.governed_systems import ConversationContextMessage
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    observed = {}

    def consult(names, request):
        observed["request"] = request
        return SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Use the supplied task only.", confidence=0.7,
                sources_needed=False,
            ),
        })

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "Li answer")
    talk_to_li(
        "Ask Nora to compare these options.",
        conversation_context="user: PRIVATE-BUDGET\nuser: UNDICLOSED-RELATIONSHIP",
        conversation_messages=[
            ConversationContextMessage(
                role="user", content="PRIVATE-BUDGET", private_to_li=True,
                allowed_specialists=("nora",),
            ),
            ConversationContextMessage(
                role="user", content="UNDISCLOSED-RELATIONSHIP",
            ),
            ConversationContextMessage(
                role="user", content="OPTION-A-COST", allowed_specialists=("nora",),
            ),
        ],
    )

    packet = observed["request"]
    assert packet.conversation_context == "user: OPTION-A-COST"
    assert "PRIVATE-BUDGET" not in packet.conversation_context
    assert "UNDISCLOSED-RELATIONSHIP" not in packet.conversation_context


def test_current_message_recipient_scope_blocks_a_different_specialist(monkeypatch) -> None:
    from app.governed_systems import ConversationContextMessage

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("A specialist outside the current disclosure scope must not run")
        ),
    )
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: json.dumps({
            "final_response": "I kept this with Li.",
            "used_specialist_keys": [],
            "action_intents": [],
        }),
    )

    outcome = talk_to_li_with_outcome(
        "Ask Marco for a training plan.",
        current_message=ConversationContextMessage(
            role="user", content="Ask Marco for a training plan.",
            allowed_specialists=("nora",),
        ),
    )

    assert outcome.response == "I kept this with Li."
    assert outcome.response_allowed_specialists == []
    assert outcome.decision_trace["route_category"] == "li_only_disclosure_scope"


def test_rejected_specialist_attribution_cannot_propose_an_action(monkeypatch) -> None:
    """R1: a rejected synthesis is not an authority-bearing partial success."""
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Compare the options.", confidence=0.7, sources_needed=False,
            ),
        }),
    )
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return json.dumps({
                "final_response": "I used an agent that was never consulted.",
                "used_specialist_keys": ["unknown_agent"],
                "action_intents": [{
                    "action_type": "task.create", "summary": "Unsafe leftover proposal",
                    "payload": {"title": "Should not survive", "notes": "", "due_at": None},
                }],
            })
        return "I couldn't safely use that specialist response, so no action was proposed."

    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    outcome = talk_to_li_with_outcome("Ask Nora to compare these options.")

    assert outcome.action_intents == []
    assert outcome.used_interaction_ids == []
    assert "no action was proposed" in outcome.response
    assert "RECENT CONVERSATION HISTORY" not in calls[1]["system"]


def test_synthesis_fallback_preserves_task_context_and_evidence_limit(monkeypatch) -> None:
    """R2: recovery keeps current-world and conversation constraints."""
    from app.specialist_runtime import SpecialistConsultation

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(),
    )
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        return "A response generated without a specialist."

    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    # A configured specialist path whose current evidence cannot be obtained is constructed
    # by the runtime before synthesis. Force invalid structured output to exercise recovery.
    from app.specialist_runtime import SpecialistResult

    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda *a, **k: SpecialistConsultation(results={
            "james": SpecialistResult(
                recommendation="Cannot verify the current state. Do not guess.",
                confidence=0.0, sources_needed=True,
            ),
        }),
    )
    responses = iter([
        "{malformed structured response",
        "I couldn't verify the current mortgage rate, so I won't guess.",
    ])
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: calls.append(kwargs) or next(responses),
    )

    outcome = talk_to_li_with_outcome(
        "What is today's mortgage rate?", conversation_context="user: My budget is private."
    )

    assert "won't guess" in outcome.response
    assert "RECENT CONVERSATION HISTORY" in calls[-1]["system"]
    assert "My budget is private." in calls[-1]["system"]
    assert "REQUIRED EVIDENCE LIMIT" in calls[-1]["system"]


def test_malformed_direct_structured_output_is_not_returned_raw(monkeypatch) -> None:
    """R4: broken structured output never becomes user-facing prose."""
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text", lambda **kwargs: '{"final_response": "unfinished"'
    )

    response = talk_to_li("What is compound interest?")

    assert "final_response" not in response
    assert "couldn't safely complete" in response


def test_li_synthesizes_multiple_specialists(monkeypatch) -> None:
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    observed = {}

    def fake_consult(specialists, request):
        assert specialists == ["victor", "milo"]
        assert set(request) == {"victor", "milo"}
        assert request["victor"].specialist_question != request["milo"].specialist_question
        assert "Business, Commercial & CCO Adviser" in request["victor"].specialist_question
        assert "Travel, Leisure & Experiences Adviser" in request["milo"].specialist_question
        assert all(item.success_criteria for item in request.values())
        return SpecialistConsultation(results={
            name: SpecialistResult(
                recommendation=f"{name} view", confidence=0.7, sources_needed=True
            )
            for name in specialists
        })

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return json.dumps({
            "final_response": "A synthesized answer.",
            "used_specialist_keys": ["victor", "milo"],
        })

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
        return json.dumps({
            "final_response": "Lisbon is the strongest available choice.",
            "used_specialist_keys": ["milo"],
        })

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
        return json.dumps({
            "final_response": "I need current sources before making a firm recommendation.",
            "used_specialist_keys": ["nora"],
        })

    monkeypatch.setattr("app.li_runtime.generate_claude_text", fake_generate)
    talk_to_li("Ask Nora to research and compare these vendors.")
    assert "Current vendor evidence" in observed["system"]
    assert "Live research was unavailable" in observed["system"]
    assert "do not provide the requested changing facts from model memory" in observed["system"]


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
        assert kwargs["max_tokens"] == 4096
        evidence = request.research_evidence[0]
        assert evidence["title"] == "Vendor release"
        assert evidence["identifier"] == "https://example.test/release"
        assert evidence["source"] == "Vendor"
        assert evidence["publication_date"] == "2026-08-20"
        assert evidence["source_type"] == "primary"
        assert evidence["retrieved_at"]
        return SpecialistResult(
            recommendation=(
                "Choose A based on Vendor's current release "
                "(https://example.test/release)."
            ),
            findings=["Current price is 10."],
            confidence=0.8,
            sources_needed=False,
        )

    monkeypatch.setattr("app.li_runtime.delegate_to_nora", fake_nora)
    monkeypatch.setattr(
        "app.li_runtime.generate_claude_text",
        lambda **kwargs: observed.update(kwargs) or json.dumps({
            "final_response": "Choose A.", "used_specialist_keys": ["nora"],
        }),
    )
    response = talk_to_li(
        "Ask Nora to research and compare these vendors.", research_provider=Provider()
    )
    assert response == "Choose A."
    assert "https://example.test/release" in observed["system"]
    assert "Preserve exact citation metadata" in observed["system"]


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
    assert "include exact" in observed["system"]
    assert "identifiers/URLs" in observed["system"]
