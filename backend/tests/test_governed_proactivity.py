from datetime import UTC, datetime, time, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.main as main_module
from app.proactivity import (
    BriefItem, ProactiveBrief, RhythmKey, RhythmState, build_brief,
    fixture_is_eligible, next_occurrence, should_surface, third_postponement_prompt_due,
)


def test_disabled_and_unapproved_rhythm_cannot_execute():
    state = RhythmState(key="morning", label="Morning", local_time=time(7, 30))
    assert state.runnable is False
    with pytest.raises(ValidationError):
        RhythmState(key="morning", label="Morning", local_time=time(7, 30), enabled=True)


def test_approved_activation_schedules_in_timezone():
    after = datetime(2026, 10, 23, 20, 0, tzinfo=UTC)
    run = next_occurrence(RhythmKey.morning, after=after, local_time=time(7, 30),
                          timezone="Europe/Berlin")
    assert run.astimezone().tzinfo is not None
    assert run > after
    assert run.astimezone(__import__("zoneinfo").ZoneInfo("Europe/Berlin")).hour == 7


def test_morning_omits_empty_categories_and_never_fills_content():
    assert build_brief(RhythmKey.morning, "morning:2026-08-30", []) is None
    item = BriefItem(category="commitment", title="Send summary", detail="Prepare draft",
                     why_now="Due today", source="open_loop:1")
    brief = build_brief(RhythmKey.morning, "morning:2026-08-30", [item])
    assert brief and [value.category for value in brief.items] == ["commitment"]


def test_current_world_items_fail_closed_without_freshness_and_provider_evidence():
    finance = BriefItem(category="finance", title="Market", detail="Current value",
                        why_now="Monthly review", source="provider")
    sports = BriefItem(category="sports", title="Fixture", detail="Tomorrow",
                       why_now="Upcoming", source="web", evidence={
                           "freshness_policy_compliant": True,
                           "provider_coverage_compliant": True,
                           "source_authority": "secondary", "verified": True,
                           "competitive": True,
                       })
    assert build_brief(RhythmKey.morning, "run", [finance, sports]) is None


def test_snooze_stand_down_and_same_day_raise_suppress_resurfacing():
    now = datetime(2026, 8, 30, 10, tzinfo=UTC)
    assert not should_surface(last_raised_at=None, suppressed_until=now + timedelta(hours=1),
                              category_stood_down=False, now=now)
    assert not should_surface(last_raised_at=None, suppressed_until=None,
                              category_stood_down=True, now=now)
    assert not should_surface(last_raised_at=now - timedelta(hours=1), suppressed_until=None,
                              category_stood_down=False, now=now)


def test_third_postponement_hook_fires_once():
    assert not third_postponement_prompt_due(2, None)
    assert third_postponement_prompt_due(3, None)
    assert not third_postponement_prompt_due(4, datetime.now(UTC))


def test_sensitive_brief_has_neutral_shoulder_visible_preview():
    brief = ProactiveBrief(
        rhythm="morning", run_key="morning:private", title="Medical appointment",
        items=(BriefItem(category="today", title="Medical appointment", detail="Private detail",
                         why_now="Today", source="calendar", sensitive=True),),
    )
    assert brief.neutral_preview == "A new private Li brief is ready."
    assert "Medical" not in brief.neutral_preview


@pytest.mark.parametrize(("authority", "verified", "competitive", "eligible"), [
    ("official_primary", True, True, True), ("official_primary", True, False, False),
    ("secondary", True, True, False), ("official_primary", False, True, False),
])
def test_sports_fixture_requires_official_verified_competitive(authority, verified, competitive,
                                                               eligible):
    assert fixture_is_eligible(source_authority=authority, verified=verified,
                               competitive=competitive) is eligible


def test_migration_has_idempotency_privacy_suppression_and_no_retention_grant():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "031_governed_proactivity.sql").read_text(encoding="utf-8")
    for value in ("UNIQUE(owner_user_id,rhythm_key,run_key)", "proactive_briefs",
                  "neutral_preview", "suppressed_until", "blocker_prompted_at",
                  "duplicate_prevented", "approved_before_enabled"):
        assert value in sql
    assert "Retention runtime gained proactivity execution" in sql


def _claimed_run(monkeypatch):
    monkeypatch.setattr(main_module, "list_rhythm_states", lambda: [])
    monkeypatch.setattr(main_module, "claim_rhythm_run", lambda *_: {
        "run_id": "0f6e8934-8920-4d85-a54d-02fa2c19f8a2", "claimed": True, "state": "claimed",
    })
    monkeypatch.setattr(main_module, "list_category_suppressions", lambda: [])
    monkeypatch.setattr(main_module, "list_open_loops", lambda: [])
    return main_module.RhythmJobRequest(
        run_key="morning:2026-08-30", scheduled_for=datetime(2026, 8, 30, 7, 30, tzinfo=UTC),
    )


def test_generation_failure_after_claim_is_durably_failed(monkeypatch):
    payload = _claimed_run(monkeypatch)
    failures = []
    monkeypatch.setattr(main_module, "build_brief", lambda *_: (_ for _ in ()).throw(ValueError("bad")))
    monkeypatch.setattr(main_module, "fail_rhythm_run", lambda *args: failures.append(args) or True)
    with pytest.raises(HTTPException) as exc:
        main_module.run_rhythm_endpoint(RhythmKey.morning, payload)
    assert exc.value.status_code == 503
    assert failures == [("0f6e8934-8920-4d85-a54d-02fa2c19f8a2", "ValueError")]


def test_persistence_failure_after_claim_is_durably_failed(monkeypatch):
    payload = _claimed_run(monkeypatch)
    failures = []
    monkeypatch.setattr(main_module, "build_brief", lambda *_: None)
    monkeypatch.setattr(main_module, "complete_rhythm_run",
                        lambda **_: (_ for _ in ()).throw(main_module.RuntimeDataError("db")))
    monkeypatch.setattr(main_module, "fail_rhythm_run", lambda *args: failures.append(args) or True)
    with pytest.raises(HTTPException):
        main_module.run_rhythm_endpoint(RhythmKey.morning, payload)
    assert failures[0][1] == "RuntimeDataError"


def test_failure_marker_outage_still_returns_retriable_failure(monkeypatch):
    payload = _claimed_run(monkeypatch)
    monkeypatch.setattr(main_module, "build_brief", lambda *_: (_ for _ in ()).throw(ValueError("bad")))
    monkeypatch.setattr(main_module, "fail_rhythm_run",
                        lambda *_: (_ for _ in ()).throw(main_module.RuntimeDataError("db")))
    with pytest.raises(HTTPException, match="may be retried"):
        main_module.run_rhythm_endpoint(RhythmKey.morning, payload)


def test_claim_retry_and_terminal_duplicate_semantics_are_atomic():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "031_governed_proactivity.sql").read_text(encoding="utf-8")
    assert "v_status='failed' OR (v_status='claimed' AND v_expires<=NOW())" in sql
    assert "attempt_count=rr.attempt_count+1" in sql
    assert "FOR UPDATE" in sql
    assert "WHEN v_status='claimed' THEN 'in_progress' ELSE 'duplicate'" in sql
    assert "WHERE rr.id=p_id AND rr.status='claimed' FOR UPDATE" in sql
    assert "UNIQUE(owner_user_id,rhythm_key,run_key)" in sql


def test_migration_reasserts_security_ownership_and_owner_invariant():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "031_governed_proactivity.sql").read_text(encoding="utf-8")
    assert sql.count("requires exactly one active owner") == 2
    assert "Function % has unexpected owner" in sql
    assert "Temporary function-owner authority was not removed" in sql
    assert "Temporary li_api CREATE authority was not removed" in sql
    assert "REVOKE ALL PRIVILEGES ON SEQUENCE li_runtime_data.proactivity_events_id_seq" in sql
    assert "retained direct sequence privileges" in sql
    assert "retained direct privileges" in sql
    assert "gained unexpected execution" in sql


def test_no_gmail_send_or_direct_provider_mutation_added():
    source = (Path(__file__).parents[1] / "app" / "proactivity.py").read_text(encoding="utf-8")
    assert "gmail" not in source.casefold()
    assert "execute_" not in source
    assert "action_intent_id" in source
