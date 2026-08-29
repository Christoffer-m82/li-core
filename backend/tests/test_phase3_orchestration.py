from pathlib import Path

from app.li_runtime import specialist_recording_context, talk_to_li
from app.specialist_runtime import SpecialistConsultation, SpecialistResult


def _memory(domain: str, *, private: bool = False) -> dict[str, object]:
    return {
        "memory_id": domain,
        "memory_class": "explicit_preference",
        "domain": domain,
        "title": domain,
        "value_text": f"private {domain}",
        "truth_status": "confirmed",
        "temporal_status": "current",
        "sensitivity": "personal",
        "private_to_li": private,
        "confidence": 1.0,
        "confirmed_by_user": True,
    }


def test_context_and_temporary_upload_are_scoped_to_routed_specialists(monkeypatch):
    monkeypatch.setattr(
        "app.li_runtime._retrieve_relevant_memories",
        lambda *a, **k: [_memory("health"), _memory("finance"), _memory("health", private=True)],
    )
    observed = {}

    def consult(names, requests):
        observed.update(requests)
        return SpecialistConsultation(
            results={
                name: SpecialistResult(
                    recommendation=f"{name} advice", confidence=0.6, sources_needed=False
                )
                for name in names
            }
        )

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "Li synthesis")
    talk_to_li(
        "Compare my health and finance options and recommend a plan.",
        temporary_upload_context="one-request file",
    )
    assert set(observed) == {"sofia", "james"}
    assert [m.domain for m in observed["sofia"].canonical_memory] == ["health"]
    assert [m.domain for m in observed["james"].canonical_memory] == ["finance"]
    assert all(req.temporary_upload_context == "one-request file" for req in observed.values())


def test_real_lifecycle_metadata_is_recorded_without_fabricated_analytics(monkeypatch):
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    started, finished = [], []
    monkeypatch.setattr(
        "app.li_runtime.start_interaction",
        lambda *args: started.append(args) or f"event-{len(started)}",
    )
    monkeypatch.setattr(
        "app.li_runtime.finish_interaction", lambda *args: finished.append(args) or True
    )
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda names, request: SpecialistConsultation(
            results={
                "sofia": SpecialistResult(
                    recommendation="Validated advice", confidence=0.7, sources_needed=False
                )
            }
        ),
    )
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "Li answer")
    with specialist_recording_context("00000000-0000-0000-0000-000000000001"):
        talk_to_li("Ask Sofia for medical advice.")
    assert started[0][2:] == (
        "sofia",
        "Ask Sofia for medical advice.",
        "explicit",
        "solo",
        "explicit_specialist",
        "User explicitly named the selected registered specialist(s).",
    )
    outcome = finished[0][2]
    assert outcome["validation"]["validated"] is True
    assert outcome["validation"]["used_in_final"] is None
    assert outcome["validation"]["action_converted"] is None
    assert "transcript" not in outcome


def test_migration_026_expands_registry_and_adds_lifecycle_fields():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "026_generalized_specialist_orchestration.sql"
    ).read_text(encoding="utf-8")
    for key in (
        "sofia",
        "marco",
        "elena",
        "amelia",
        "freja",
        "oliver",
        "james",
        "victor",
        "nora",
        "milo",
        "iris",
        "clara",
    ):
        assert f"'{key}'" in sql
    for field in ("selection_mode", "group_mode", "route_category", "route_reason", "elapsed_ms"):
        assert field in sql
    assert (
        "VALUES('0.26','Generalized permanent specialist orchestration lifecycle metadata')" in sql
    )
