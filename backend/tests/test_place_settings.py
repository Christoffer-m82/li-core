from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.location_settings import (
    ISO_COUNTRY_CODES,
    CurrentPlace,
    MostVisitedPreference,
    VisitEvent,
    location_is_relevant,
    minimal_location_context,
    promoted_countries,
    qualifying_visit_count,
    town_is_useful,
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
        visit("MT", "2026-02-01", "2026-02-05"),
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


def test_provider_contract_has_no_coordinate_fields():
    fields = set(CurrentPlace.model_fields) | set(VisitEvent.model_fields)
    assert not {"latitude", "longitude", "coordinates", "gps"} & fields
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "032_private_place_settings.sql").read_text(encoding="utf-8").lower()
    assert " latitude " not in sql and " longitude " not in sql
    assert "precise_coordinates_persisted',false" in sql
    assert "provider_permission" in sql and "device_coarse" in sql


def test_migration_is_immutable_private_and_suppression_aware():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "032_private_place_settings.sql").read_text(encoding="utf-8")
    assert "Migration 032 requires applied schema 0.31" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "TO li_backend_runtime" in sql
    assert "state='suppressed'" in sql
    assert "CURRENT_DATE-365" in sql
    assert sql.index("schema_versions") < sql.rindex("COMMIT;")
