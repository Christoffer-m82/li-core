import json

import pytest

from app.specialist_runtime import (
    NoraDelegationRequest,
    SpecialistRuntimeError,
    delegate_to_nora,
    nora_needs_canonical_memory,
    route_specialist,
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


def test_complex_research_decision_delegates() -> None:
    message = (
        "Research the evidence and compare the trade-offs between these two approaches "
        "so I can choose the more resilient option for next year."
    )
    assert route_specialist(message).route == "nora"


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

