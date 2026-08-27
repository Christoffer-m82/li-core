import json

import pytest

from app.specialist_runtime import (
    SPECIALIST_PROFILES,
    NoraDelegationRequest,
    SpecialistRequest,
    SpecialistRuntimeError,
    consult_specialists,
    delegate_to_nora,
    delegate_to_specialist,
    nora_needs_canonical_memory,
    route_specialist,
    route_specialists,
)


@pytest.mark.parametrize(
    "message",
    [
        "Hello",
        "What is compound interest?",
        "Translate this sentence into German.",
        "Should I take an umbrella?",
    ],
)
def test_simple_requests_stay_with_li(message: str) -> None:
    assert route_specialist(message).route == "direct"


def test_explicit_nora_request_delegates() -> None:
    assert route_specialist("Ask Nora to analyze these options.").route == "nora"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Ask Victor for his advice on this proposal.", ["victor"]),
        ("Get Milo's recommendation for this trip.", ["milo"]),
        ("Consult Victor and Milo about this business travel decision.", ["victor", "milo"]),
    ],
)
def test_named_specialists_route_exactly(message: str, expected: list[str]) -> None:
    assert route_specialists(message).specialists == expected


def test_complex_research_decision_delegates() -> None:
    message = (
        "Research the evidence and compare the trade-offs between these two approaches "
        "so I can choose the more resilient option for next year."
    )
    assert route_specialist(message).route == "nora"


def test_complex_cross_domain_request_routes_multiple_specialists() -> None:
    message = (
        "Compare the commercial trade-offs and travel experience of three cities for our "
        "next executive offsite, including hotel options and partnership opportunities."
    )
    assert route_specialists(message).specialists == ["victor", "milo"]


def test_fixed_registry_drives_profiles() -> None:
    assert SPECIALIST_PROFILES["victor"].role == "Business, Commercial & CCO Adviser"
    assert SPECIALIST_PROFILES["milo"].role == "Travel, Leisure & Experiences Adviser"


def test_memory_is_only_needed_for_personalized_task() -> None:
    assert not nora_needs_canonical_memory("Research and compare these vendors.")
    assert nora_needs_canonical_memory("Recommend the best option for my priorities.")


def test_delegate_to_nora_validates_structured_output(monkeypatch) -> None:
    payload = {
        "recommendation": "Prefer option A pending source verification.",
        "findings": ["A has the clearer trade-off."],
        "confidence": 0.7,
        "key_assumptions": ["The stated constraints are complete."],
        "sources_needed": True,
        "follow_up_questions": ["What is the budget ceiling?"],
    }
    monkeypatch.setattr(
        "app.specialist_runtime.generate_claude_text",
        lambda **kwargs: json.dumps(payload),
    )

    result = delegate_to_nora(
        NoraDelegationRequest(current_user_message="Compare A and B.")
    )

    assert result.confidence == 0.7
    assert result.sources_needed is True


def test_delegate_to_nora_rejects_untyped_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.specialist_runtime.generate_claude_text",
        lambda **kwargs: "I think A is best.",
    )
    with pytest.raises(SpecialistRuntimeError):
        delegate_to_nora(NoraDelegationRequest(current_user_message="Compare A and B."))


def test_shared_contract_and_specialist_profile_are_used(monkeypatch) -> None:
    observed = {}
    payload = {
        "recommendation": "Use a phased commercial rollout.",
        "findings": [],
        "confidence": 0.75,
        "key_assumptions": [],
        "sources_needed": False,
        "follow_up_questions": [],
    }

    def fake_generate(**kwargs):
        observed.update(kwargs)
        return json.dumps(payload)

    monkeypatch.setattr("app.specialist_runtime.generate_claude_text", fake_generate)
    result = delegate_to_specialist(
        "victor", SpecialistRequest(current_user_message="Assess this strategy.")
    )
    assert result.confidence == 0.75
    assert "Business, Commercial & CCO Adviser" in observed["system"]
    assert "no tools and no database access" in observed["system"]


def test_multiple_specialists_are_collected_in_requested_order(monkeypatch) -> None:
    def fake_delegate(name, request, *, max_tokens=None):
        from app.specialist_runtime import SpecialistResult

        return SpecialistResult(
            recommendation=f"{name} recommendation",
            confidence=0.5,
            sources_needed=False,
        )

    monkeypatch.setattr("app.specialist_runtime.delegate_to_specialist", fake_delegate)
    results = consult_specialists(
        ["victor", "milo"], SpecialistRequest(current_user_message="Plan the offsite.")
    )
    assert list(results) == ["victor", "milo"]
