import pytest

from app.memory_capture import (
    MemoryCandidate,
    MemoryCaptureAnalysis,
    MemoryCaptureError,
    apply_memory_capture,
)


def _memory(memory_id: str = "old-id") -> dict[str, object]:
    return {
        "memory_id": memory_id,
        "memory_class": "explicit_preference",
        "domain": "preferences",
    }


def test_apply_memory_correction(monkeypatch) -> None:
    monkeypatch.setattr("app.memory_capture.recall_memory", lambda **kwargs: [_memory()])
    recorded = {}

    def fake_correct(**kwargs):
        recorded.update(kwargs)
        return {"memory_id": "new-id", "outcome": "created_replacement"}

    monkeypatch.setattr("app.memory_capture.correct_explicit_memory", fake_correct)
    analysis = MemoryCaptureAnalysis(
        candidates=[
            MemoryCandidate(
                action="correct_explicit",
                memory_class="explicit_preference",
                domain="preferences",
                value="Prefers purple notebooks",
                title="Notebook preference",
                sensitivity="low",
                target_query="orange notebook preference",
            )
        ]
    )

    outcomes = apply_memory_capture(analysis, source_reference="chat-1")

    assert outcomes[0].status == "corrected"
    assert outcomes[0].memory_id == "new-id"
    assert recorded["memory_id"] == "old-id"
    assert recorded["new_value"] == "Prefers purple notebooks"


def test_apply_memory_forget(monkeypatch) -> None:
    monkeypatch.setattr("app.memory_capture.recall_memory", lambda **kwargs: [_memory()])
    monkeypatch.setattr(
        "app.memory_capture.forget_memory",
        lambda **kwargs: {"memory_id": kwargs["memory_id"], "outcome": "forgotten"},
    )
    analysis = MemoryCaptureAnalysis(
        candidates=[
            MemoryCandidate(
                action="forget",
                domain="preferences",
                target_query="notebook preference",
                reason="The user explicitly asked to forget it.",
            )
        ]
    )

    outcomes = apply_memory_capture(analysis, source_reference="chat-2")

    assert outcomes[0].status == "forgotten"
    assert outcomes[0].memory_id == "old-id"


@pytest.mark.parametrize("matches", [[], [_memory("one"), _memory("two")]])
def test_memory_change_rejects_missing_or_ambiguous_target(monkeypatch, matches) -> None:
    monkeypatch.setattr("app.memory_capture.recall_memory", lambda **kwargs: matches)
    analysis = MemoryCaptureAnalysis(
        candidates=[
            MemoryCandidate(
                action="forget",
                target_query="notebook preference",
            )
        ]
    )

    with pytest.raises(MemoryCaptureError, match="missing or ambiguous"):
        apply_memory_capture(analysis)


def test_forget_requires_specific_target() -> None:
    with pytest.raises(ValueError, match="target_query"):
        MemoryCandidate(action="forget")
