from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.location_settings import (
    ISO_COUNTRY_CODES,
    CurrentPlace,
    MobileLocationUpdateV1,
    MobileOvernightEvent,
    MostVisitedPreference,
    VisitEvent,
    location_is_relevant,
    minimal_location_context,
    promoted_countries,
    qualifying_visit_count,
    town_is_useful,
    device_update_may_replace,
    validate_mobile_freshness,
)


def visit(country: str, first: str, last: str, overnight: bool = True) -> VisitEvent:
    return VisitEvent(country_code=country, first_seen=date.fromisoformat(first),
                      last_seen=date.fromisoformat(last), overnight_confirmed=overnight)


def test_complete_iso_country_list_and_validation():
    assert len(ISO_COUNTRY_CODES) == 249
    assert len(set(ISO_COUNTRY_CODES)) == 249
    assert {"MT", "SE", "GB", "ES"} <= set(ISO_COUNTRY_CODES)
    assert CurrentPlace(country_code="mt").country_code == "MT"
    with pytest.raises(ValidationError):
        CurrentPlace(country_code="XX")


def test_two_distinct_overnight_visits_promote_but_continuous_trip_counts_once():
    events = [
        visit("MT", "2026-02-01", "2026-02-05"),
        visit("MT", "2026-02-05", "2026-02-08"),
        visit("MT", "2026-07-01", "2026-07-02"),
    ]
    assert qualifying_visit_count(events, today=date(2026, 8, 30))["MT"] == 2
    assert promoted_countries(events, []) == ["MT"]


def test_transit_old_visits_and_suppression_do_not_promote():
    events = [
        visit("SE", "2026-01-01", "2026-01-01", False),
        visit("SE", "2026-03-01", "2026-03-02"),
        visit("SE", "2026-05-01", "2026-05-02"),
        visit("ES", "2024-01-01", "2024-01-02"),
        visit("ES", "2024-03-01", "2024-03-02"),
    ]
    prefs = [MostVisitedPreference(country_code="SE", state="suppressed")]
    assert promoted_countries(events, prefs) == []


def test_same_day_claim_is_not_an_overnight_and_stale_automatic_entry_expires():
    with pytest.raises(ValidationError):
        visit("ES", "2026-04-01", "2026-04-01")
    events = [visit("ES", "2024-04-01", "2024-04-02")]
    prefs = [MostVisitedPreference(country_code="ES", state="automatic")]
    assert qualifying_visit_count(events, today=date(2026, 8, 30)) == {}
    assert promoted_countries(events, prefs) == []


def test_manual_pins_are_authoritative_and_ordered_first():
    prefs = [MostVisitedPreference(country_code="GB", state="pinned"),
             MostVisitedPreference(country_code="MT", state="pinned")]
    assert promoted_countries([], prefs) == ["GB", "MT"]


def test_location_context_is_minimal_and_relevance_gated():
    place = CurrentPlace(country_code="MT", town_city="Valletta")
    assert minimal_location_context("Summarize this paragraph", place) is None
    context = minimal_location_context("Find a nearby restaurant", place)
    assert "ISO MT" in context and "Valletta" in context
    assert "visit" in context and "coordinates" not in context
    assert location_is_relevant("What tax rules apply to me?")
    assert town_is_useful("What is the weather near me?")
    assert not town_is_useful("What national tax rules apply?")
    national = minimal_location_context("What national tax rules apply?", place)
    assert "ISO MT" in national and "Valletta" not in national


def test_provider_contract_has_no_coordinate_fields():
    fields = set(CurrentPlace.model_fields) | set(VisitEvent.model_fields)
    assert not {"latitude", "longitude", "coordinates", "gps"} & fields
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "032_private_place_settings.sql").read_text(encoding="utf-8").lower()
    assert " latitude " not in sql and " longitude " not in sql
    assert "precise_coordinates_persisted',false" in sql
    assert "provider_permission" in sql and "device_coarse" in sql
    with pytest.raises(ValidationError):
        CurrentPlace(country_code="MT", source="device_coarse", provider_permission="denied")
    assert CurrentPlace(country_code="MT", source="device_coarse",
                        provider_permission="granted").country_code == "MT"


def test_migration_is_immutable_private_and_suppression_aware():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "032_private_place_settings.sql").read_text(encoding="utf-8")
    assert "Migration 032 requires applied schema 0.31" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "TO li_memory_api" in sql
    assert "Backend runtime lost required Place execution" in sql
    assert "Temporary function-owner authority was not removed" in sql
    assert "state='suppressed'" in sql
    assert "CURRENT_DATE-365" in sql
    assert sql.index("schema_versions") < sql.rindex("COMMIT;")


def mobile_payload(now: datetime, **overrides) -> dict:
    value = {
        "installation_id": uuid4(), "update_id": uuid4(), "country_code": "MT",
        "source": "device_coarse", "observed_at": now,
        "permission": {"state": "granted", "platform": "ios", "checked_at": now},
    }
    value.update(overrides)
    return value


def test_granted_typed_mobile_contract_accepts_only_coarse_fields():
    now = datetime(2026, 8, 31, 10, tzinfo=UTC)
    update = MobileLocationUpdateV1.model_validate(mobile_payload(now, town_city=" Valletta "))
    assert update.country_code == "MT" and update.town_city == "Valletta"
    assert update.contract_version == "1.0" and update.permission.state == "granted"
    for precise in ("lat", "lng", "latitude", "longitude", "gps", "coordinates"):
        with pytest.raises(ValidationError):
            MobileLocationUpdateV1.model_validate(mobile_payload(now, **{precise: 1}))
    for fingerprint in ("imei", "serial_number", "advertising_id", "hardware_id"):
        with pytest.raises(ValidationError):
            MobileLocationUpdateV1.model_validate(mobile_payload(now, **{fingerprint: "x"}))
    with pytest.raises(ValidationError):
        MobileLocationUpdateV1.model_validate(mobile_payload(
            now, permission={"state": "granted", "platform": "ios",
                             "checked_at": now + timedelta(minutes=6)}))


@pytest.mark.parametrize("state", ["unknown", "not_requested", "denied", "restricted"])
def test_non_granted_mobile_permission_is_rejected_before_mutation(state: str):
    now = datetime(2026, 8, 31, 10, tzinfo=UTC)
    with pytest.raises(ValidationError):
        MobileLocationUpdateV1.model_validate(mobile_payload(
            now, permission={"state": state, "platform": "android", "checked_at": now}))


def test_mobile_freshness_and_manual_precedence_rules():
    now = datetime(2026, 8, 31, 10, tzinfo=UTC)
    validate_mobile_freshness(now - timedelta(hours=23), now=now)
    with pytest.raises(ValueError, match="stale"):
        validate_mobile_freshness(now - timedelta(hours=25), now=now)
    manual_at = now - timedelta(hours=25)
    assert not device_update_may_replace(current_source="manual_web", current_updated_at=manual_at,
                                         observed_at=manual_at + timedelta(hours=23))
    assert device_update_may_replace(current_source="manual_web", current_updated_at=manual_at,
                                     observed_at=now)
    assert device_update_may_replace(current_source="device_coarse", current_updated_at=now,
                                     observed_at=now)


def test_mobile_overnight_and_transit_are_minimal_events():
    now = datetime(2026, 8, 31, 10, tzinfo=UTC)
    event = MobileOvernightEvent(event_id=uuid4(), first_observed_at=now-timedelta(days=1),
                                 last_observed_at=now, classification="overnight")
    update = MobileLocationUpdateV1.model_validate(mobile_payload(now, overnight_event=event))
    assert update.overnight_event.classification == "overnight"
    transit = MobileOvernightEvent(event_id=uuid4(), first_observed_at=now,
                                   last_observed_at=now, classification="transit")
    assert transit.classification == "transit"


def test_migration_033_has_replay_revocation_correction_and_no_identifiers_or_coordinates():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "033_native_mobile_location_boundary.sql").read_text(encoding="utf-8").lower()
    assert "migration 033 requires applied schema 0.32" in sql
    assert "update_id uuid primary key" in sql and "status','idempotent'" in sql
    assert "revoked_at is null" in sql and "revoke_mobile_location_installation" in sql
    assert "migration 033 requires exactly one active owner" in sql
    assert "visit event fields must be supplied together" in sql
    assert "out-of-order coarse observation" in sql
    assert "migration role cannot assume li_memory_function_owner" in sql
    assert "correct_mobile_location_visit" in sql and "classification in ('overnight','transit')" in sql
    assert "interval '24 hours'" in sql and "mobile location update limit exceeded" in sql
    assert "installation_id uuid primary key default gen_random_uuid()" in sql
    forbidden = (" latitude ", " longitude ", " imei ", " serial_number ",
                 " advertising_id ", " hardware_id ", " gps_payload ")
    assert not any(value in sql for value in forbidden)
    assert "li_retention_runtime" in sql and "backend runtime lost required mobile place execution" in sql
    assert sql.index("schema_versions") < sql.rindex("commit;")
