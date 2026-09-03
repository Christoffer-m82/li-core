from datetime import UTC, datetime, timedelta

import pytest

from app.calendar_runtime import CalendarEvent
from app.email_runtime import EmailMessage
from app.proactive_watchers import (
    unread_important_email_candidates,
    upcoming_calendar_candidates,
)


NOW = datetime(2026, 9, 3, 7, 30, tzinfo=UTC)


def event(
    *, event_id: str = "provider-secret-id", title: str = "Dentist",
    start: datetime = NOW + timedelta(hours=4), end: datetime | None = None,
    status: str | None = "confirmed",
) -> CalendarEvent:
    return CalendarEvent(
        event_id=event_id, title=title, start=start, end=end or start + timedelta(hours=1),
        timezone="Europe/Berlin", location="Private address",
        description="Private provider description", status=status,
        html_link="https://calendar.example/private-event",
    )


def message(*, labels: list[str] | None = None) -> EmailMessage:
    return EmailMessage(
        message_id="provider-message-id",
        thread_id="provider-thread-id",
        sender="Alex Example <alex@example.com>",
        recipients=["owner@example.com"],
        cc=["private-copy@example.com"],
        subject="Important follow-up",
        date="Thu, 03 Sep 2026 09:00:00 +0200",
        labels=labels or ["INBOX", "IMPORTANT", "UNREAD"],
        snippet="Sensitive snippet",
        body="Private message body",
    )


def test_calendar_watcher_emits_private_minimised_read_only_candidate():
    candidate = upcoming_calendar_candidates([event()], now=NOW)[0]

    assert candidate.category == "today"
    assert candidate.kind == "commitment"
    assert candidate.urgency == "high"
    assert candidate.sensitive is True
    assert candidate.confidence == 1.0
    assert candidate.why_now == "This calendar commitment starts within six hours"
    assert candidate.detail == "Starts Thursday 03 September at 13:30"
    serialized = candidate.model_dump_json()
    assert "provider-secret-id" not in serialized
    assert "Private address" not in serialized
    assert "Private provider description" not in serialized
    assert "calendar.example" not in serialized
    assert candidate.source.startswith("calendar_event:")


def test_calendar_watcher_filters_cancelled_past_and_out_of_horizon_events():
    values = [
        event(event_id="cancelled", status="cancelled"),
        event(event_id="past", start=NOW - timedelta(hours=2)),
        event(event_id="later", start=NOW + timedelta(days=3)),
    ]

    assert upcoming_calendar_candidates(values, now=NOW) == []


def test_calendar_watcher_rejects_unbounded_or_naive_evaluation_windows():
    with pytest.raises(ValueError, match="timezone-aware"):
        upcoming_calendar_candidates([], now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="seven days"):
        upcoming_calendar_candidates([], now=NOW, horizon=timedelta(days=8))
    with pytest.raises(ValueError, match="display timezone"):
        upcoming_calendar_candidates([], now=NOW, display_timezone="Not/A-Timezone")


def test_calendar_watcher_detects_and_prioritises_private_conflicts():
    candidates = upcoming_calendar_candidates([
        event(event_id="first-private-id", title="Dentist", start=NOW + timedelta(hours=4)),
        event(
            event_id="second-private-id", title="Train",
            start=NOW + timedelta(hours=4, minutes=30),
        ),
    ], now=NOW)

    conflicts = [candidate for candidate in candidates if candidate.kind == "risk"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.title == "Calendar conflict: Dentist and Train"
    assert conflict.detail == "Overlap Thursday 03 September, 14:00 to 14:30"
    assert conflict.urgency == "high"
    assert conflict.sensitive is True
    assert conflict.attention_score > candidates[0].attention_score
    serialized = conflict.model_dump_json()
    assert "first-private-id" not in serialized
    assert "second-private-id" not in serialized
    assert conflict.source.startswith("calendar_conflict:")


def test_calendar_watcher_does_not_flag_adjacent_or_duplicate_events_as_conflicts():
    first = event(event_id="same-id", start=NOW + timedelta(hours=4))
    values = [
        first,
        event(event_id="next-id", start=first.end),
        event(event_id="same-id", start=NOW + timedelta(hours=4)),
    ]

    assert not any(
        candidate.kind == "risk"
        for candidate in upcoming_calendar_candidates(values, now=NOW)
    )


def test_calendar_conflict_names_both_dates_when_overlap_crosses_midnight():
    candidates = upcoming_calendar_candidates([
        event(
            event_id="late-one", start=NOW + timedelta(hours=12, minutes=30),
            end=NOW + timedelta(hours=15, minutes=30),
        ),
        event(
            event_id="late-two", start=NOW + timedelta(hours=14),
            end=NOW + timedelta(hours=15),
        ),
    ], now=NOW)

    conflict = next(candidate for candidate in candidates if candidate.kind == "risk")
    assert conflict.detail == (
        "Overlap Thursday 03 September, 23:30 to Friday 04 September, 00:30"
    )


def test_email_watcher_emits_private_metadata_only_candidate():
    candidate = unread_important_email_candidates([message()])[0]

    assert candidate.category == "private_mail"
    assert candidate.title == "Important follow-up"
    assert candidate.detail == "From Alex Example <alex@example.com>"
    assert candidate.sensitive is True
    assert candidate.why_now == "Gmail marked this unread message as important"
    serialized = candidate.model_dump_json()
    assert "provider-message-id" not in serialized
    assert "provider-thread-id" not in serialized
    assert "owner@example.com" not in serialized
    assert "private-copy@example.com" not in serialized
    assert "Sensitive snippet" not in serialized
    assert "Private message body" not in serialized
    assert candidate.source.startswith("email_message:")


def test_email_watcher_requires_both_unread_and_important_labels():
    assert unread_important_email_candidates([
        message(labels=["INBOX", "UNREAD"]),
        message(labels=["INBOX", "IMPORTANT"]),
    ]) == []
