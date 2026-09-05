import json

import pytest

from app.theo_runtime import (
    TheoRuntimeError,
    evaluate_memory_proposal,
    process_next_memory_proposal,
)


def _proposal(**overrides) -> dict[str, object]:
    proposal = {
        "proposal_id": "00000000-0000-0000-0000-000000000001",
        "proposed_by_agent": "li",
        "proposed_class": "explicit_preference",
        "proposed_domain": "preferences",
        "proposed_value_text": "Prefers blue notebooks",
        "proposed_truth_status": "confirmed",
        "proposed_temporal_status": "current",
        "proposed_sensitivity": "personal",
        "reason": "The user stated this directly.",
        "source_reference": "synthetic-test",
    }
    proposal.update(overrides)
    return proposal


def test_evaluate_approve_with_canonical_context(monkeypatch) -> None:
    recorded = {}
    monkeypatch.setattr(
        "app.theo_runtime.recall_memory_for_theo",
        lambda **kwargs: [{"memory_id": "memory-1", "value_text": "Uses notebooks"}],
    )

    def fake_claude(**kwargs):
        recorded.update(kwargs)
        return """{"decision":"approve","rationale":"Explicit and consistent.",
        "final_truth_status":"confirmed","final_temporal_status":"current",
        "final_confidence":0.95}"""

    monkeypatch.setattr("app.theo_runtime.generate_claude_text", fake_claude)
    decision = evaluate_memory_proposal(_proposal())

    assert decision.decision == "approve"
    assert decision.final_confidence == 0.95
    assert "Uses notebooks" in recorded["user_message"]


def test_theo_cannot_promote_unconfirmed_inference_to_confirmed_fact(monkeypatch) -> None:
    monkeypatch.setattr("app.theo_runtime.recall_memory_for_theo", lambda **kwargs: [])
    monkeypatch.setattr(
        "app.theo_runtime.generate_claude_text",
        lambda **kwargs: json.dumps({
            "decision": "approve",
            "rationale": "The inference seems plausible.",
            "final_truth_status": "confirmed",
            "final_temporal_status": "current",
            "final_confidence": 0.9,
        }),
    )

    with pytest.raises(TheoRuntimeError, match="inference|confirmed"):
        evaluate_memory_proposal(_proposal(
            proposed_class="inference",
            proposed_truth_status="inferred",
            proposed_by_agent="li",
        ))


def test_theo_may_approve_inference_without_changing_inferred_truth(monkeypatch) -> None:
    monkeypatch.setattr("app.theo_runtime.recall_memory_for_theo", lambda **kwargs: [])
    monkeypatch.setattr(
        "app.theo_runtime.generate_claude_text",
        lambda **kwargs: json.dumps({
            "decision": "approve",
            "rationale": "Retain this as an inference.",
            "final_truth_status": None,
            "final_temporal_status": "current",
            "final_confidence": 0.9,
        }),
    )

    decision = evaluate_memory_proposal(_proposal(
        proposed_class="inference", proposed_truth_status="inferred",
    ))

    assert decision.decision == "approve"
    assert decision.final_truth_status is None


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        '{"decision":"approve","rationale":"Unsure","final_confidence":0.4}',
        '{"decision":"maybe","rationale":"Unsure"}',
        '{"decision":"reject","rationale":"No","unexpected":true}',
    ],
)
def test_evaluate_fails_closed_on_invalid_model_output(monkeypatch, response) -> None:
    monkeypatch.setattr("app.theo_runtime.recall_memory_for_theo", lambda **kwargs: [])
    monkeypatch.setattr("app.theo_runtime.generate_claude_text", lambda **kwargs: response)

    with pytest.raises(TheoRuntimeError, match="invalid|no JSON"):
        evaluate_memory_proposal(_proposal())


def test_secret_is_rejected_without_model_or_memory_access(monkeypatch) -> None:
    def fail(**kwargs):
        raise AssertionError("Secrets must be rejected before external calls.")

    monkeypatch.setattr("app.theo_runtime.recall_memory_for_theo", fail)
    monkeypatch.setattr("app.theo_runtime.generate_claude_text", fail)
    decision = evaluate_memory_proposal(
        _proposal(proposed_value_text="My API key is sk_abcdefghijklmnop1234")
    )

    assert decision.decision == "reject"
    assert "secret" in decision.rationale


def test_processes_only_one_proposal(monkeypatch) -> None:
    proposals = [_proposal(), _proposal(proposal_id="second")]
    recorded = {}
    monkeypatch.setattr(
        "app.theo_runtime.get_pending_memory_proposals",
        lambda **kwargs: proposals[: kwargs["limit"]],
    )
    monkeypatch.setattr(
        "app.theo_runtime.evaluate_memory_proposal",
        lambda proposal: __import__("app.theo_runtime", fromlist=["TheoReviewDecision"])
        .TheoReviewDecision(
            decision="needs_user_confirmation",
            rationale="Sensitive and ambiguous; owner confirmation is required.",
        ),
    )

    def fake_review(**kwargs):
        recorded.update(kwargs)
        return {
            "proposal_status": "needs_user_confirmation",
            "memory_id": None,
            "outcome": "user_confirmation_required",
        }

    monkeypatch.setattr("app.theo_runtime.review_memory_proposal", fake_review)
    result = process_next_memory_proposal()

    assert result.status == "processed"
    assert recorded["proposal_id"] == proposals[0]["proposal_id"]
    assert recorded["decision"] == "needs_user_confirmation"


def test_empty_queue_does_not_review(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.theo_runtime.get_pending_memory_proposals", lambda **kwargs: []
    )
    result = process_next_memory_proposal()
    assert result.status == "no_pending_proposals"
