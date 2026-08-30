import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.action_instrumentation import ActionAttribution
from app.li_runtime import specialist_recording_context, talk_to_li_with_outcome
from app.main import _measure_action
from app.specialist_runtime import RoutingDecision, SpecialistConsultation, SpecialistResult


CONVERSATION_ID = "00000000-0000-0000-0000-000000000001"


def _result(name: str) -> SpecialistResult:
    return SpecialistResult(recommendation=f"{name} finding", confidence=0.8, sources_needed=False)


def _run_synthesis(monkeypatch, specialists, results, used, *, unavailable=None):
    ids = {key: str(uuid4()) for key in specialists}
    recorded = []
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr("app.li_runtime.route_specialists", lambda message: RoutingDecision(
        specialists=specialists, selection_mode="li_selected",
        group_mode="multi" if len(specialists) > 1 else "solo",
        route_category="test", route_reason="test route",
    ))
    monkeypatch.setattr("app.li_runtime.start_interaction", lambda *a: ids[a[2]])
    monkeypatch.setattr("app.li_runtime.finish_interaction", lambda *a: True)
    monkeypatch.setattr("app.li_runtime.consult_specialists", lambda *a: SpecialistConsultation(
        results=results, unavailable=unavailable or [],
    ))
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **k: json.dumps({
        "final_response": "Li synthesis", "used_specialist_keys": used,
    }))
    monkeypatch.setattr(
        "app.li_runtime.record_synthesis_attribution",
        lambda request, used_ids, measured_ids: recorded.append((used_ids, measured_ids)) or True,
    )
    with specialist_recording_context(CONVERSATION_ID):
        outcome = talk_to_li_with_outcome("test request")
    return outcome, ids, recorded


def test_one_used_specialist_is_explicitly_attributed(monkeypatch):
    outcome, ids, recorded = _run_synthesis(monkeypatch, ["sofia"], {"sofia": _result("sofia")}, ["sofia"])
    assert outcome.used_interaction_ids == [ids["sofia"]]
    assert recorded[0][0] == [ids["sofia"]]


def test_consulted_but_unused_specialist_is_measured_false(monkeypatch):
    outcome, ids, recorded = _run_synthesis(monkeypatch, ["sofia"], {"sofia": _result("sofia")}, [])
    assert outcome.used_interaction_ids == []
    assert recorded[0] == ([], [ids["sofia"]])


def test_multi_agent_mixed_attribution(monkeypatch):
    outcome, ids, recorded = _run_synthesis(
        monkeypatch, ["sofia", "james"],
        {"sofia": _result("sofia"), "james": _result("james")}, ["james"],
    )
    assert outcome.used_interaction_ids == [ids["james"]]
    assert set(recorded[0][1]) == set(ids.values())


def test_failed_specialist_cannot_be_attributed(monkeypatch):
    outcome, ids, recorded = _run_synthesis(
        monkeypatch, ["sofia", "elena"], {"sofia": _result("sofia")}, ["sofia"],
        unavailable=["elena"],
    )
    assert ids["elena"] not in recorded[0][1]
    assert outcome.used_interaction_ids == [ids["sofia"]]


def test_li_only_response_has_no_attribution(monkeypatch):
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    monkeypatch.setattr("app.li_runtime.route_specialists", lambda message: RoutingDecision(
        specialists=[], route_category="direct", route_reason="Li only",
    ))
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **k: "Li only")
    outcome = talk_to_li_with_outcome("simple request")
    assert outcome.request_id is None and outcome.used_interaction_ids == []


@pytest.mark.parametrize(
    "provider_status,expected",
    [("completed", "succeeded"), ("approval_required", "blocked"), ("failed", "failed")],
)
def test_mutating_action_outcomes_are_measured(monkeypatch, provider_status, expected):
    calls = []
    monkeypatch.setattr("app.main.record_action_attribution", lambda **values: calls.append(values) or True)
    attribution = ActionAttribution(
        action_id=uuid4(), request_id=uuid4(), specialist_interaction_ids=[uuid4()]
    )
    _measure_action(SimpleNamespace(attribution=attribution), provider_status, "task.create", mutation=True)
    assert calls[0]["status"] == expected


def test_action_retry_uses_same_stable_correlation_id(monkeypatch):
    calls = []
    monkeypatch.setattr("app.main.record_action_attribution", lambda **values: calls.append(values) or True)
    attribution = ActionAttribution(
        action_id=uuid4(), request_id=uuid4(), specialist_interaction_ids=[uuid4()]
    )
    payload = SimpleNamespace(attribution=attribution)
    _measure_action(payload, "failed", "calendar.create", mutation=True)
    _measure_action(payload, "completed", "calendar.create", mutation=True)
    assert calls[0]["action_id"] == calls[1]["action_id"]


def test_read_action_never_counts_as_action_taken(monkeypatch):
    calls = []
    monkeypatch.setattr("app.main.record_action_attribution", lambda **values: calls.append(values))
    payload = SimpleNamespace(attribution=ActionAttribution(
        action_id=uuid4(), request_id=uuid4(), specialist_interaction_ids=[uuid4()]
    ))
    _measure_action(payload, "completed", "calendar.search", mutation=False)
    assert calls == []


def test_migration_rejects_unrelated_later_action_and_is_idempotent():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "028_specialist_synthesis_action_instrumentation.sql").read_text(encoding="utf-8")
    assert "i.request_id=p_request AND i.used_in_final IS TRUE" in sql
    assert "PRIMARY KEY(action_id, interaction_id)" in sql
    assert "ON CONFLICT(action_id,interaction_id) DO UPDATE" in sql
    assert "p_status='succeeded' THEN TRUE" in sql
    assert "VALUES('0.28','Measured specialist synthesis and Li-owned action attribution')" in sql
