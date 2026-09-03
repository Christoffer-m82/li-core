"""Deterministic, privacy-minimised inputs for governed proactive briefs."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.calendar_runtime import CalendarEvent
from app.email_runtime import EmailMessage
from app.proactivity import BriefItem


def upcoming_calendar_candidates(
    events: list[CalendarEvent], *, now: datetime, horizon: timedelta = timedelta(days=2),
    display_timezone: str = "Europe/Berlin",
) -> list[BriefItem]:
    """Turn upcoming authorized calendar reads into private, non-mutating brief candidates."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Calendar watcher requires a timezone-aware current time.")
    if horizon <= timedelta(0) or horizon > timedelta(days=7):
        raise ValueError("Calendar watcher horizon must be between zero and seven days.")
    try:
        display_zone = ZoneInfo(display_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Calendar watcher display timezone is invalid.") from exc

    candidates: list[BriefItem] = []
    for event in events:
        if event.status == "cancelled" or event.end <= now or event.start > now + horizon:
            continue
        starts_in = event.start - now
        if event.start <= now:
            why_now = "This calendar commitment is in progress"
            urgency = "high"
            importance = 0.9
        elif starts_in <= timedelta(hours=6):
            why_now = "This calendar commitment starts within six hours"
            urgency = "high"
            importance = 0.9
        elif starts_in <= timedelta(days=1):
            why_now = "This calendar commitment starts within one day"
            urgency = "normal"
            importance = 0.85
        else:
            why_now = "This calendar commitment starts within two days"
            urgency = "normal"
            importance = 0.7

        local_start = event.start.astimezone(display_zone)
        fingerprint = hashlib.sha256(
            f"{event.event_id}\x1f{event.start.isoformat()}".encode()
        ).hexdigest()[:32]
        candidates.append(BriefItem(
            category="today",
            title=event.title,
            detail=f"Starts {local_start.strftime('%A %d %B at %H:%M')}",
            why_now=why_now,
            source=f"calendar_event:{fingerprint}",
            urgency=urgency,
            kind="commitment",
            importance=importance,
            relevance=0.95,
            confidence=1.0,
            sensitive=True,
        ))
    return candidates


def unread_important_email_candidates(messages: list[EmailMessage]) -> list[BriefItem]:
    """Turn important unread email metadata into private, non-mutating brief candidates."""
    candidates: list[BriefItem] = []
    for message in messages:
        labels = {label.upper() for label in message.labels}
        if not {"IMPORTANT", "UNREAD"}.issubset(labels):
            continue
        subject = " ".join(message.subject.split())[:200] or "(no subject)"
        sender = " ".join((message.sender or "Unknown sender").split())
        fingerprint = hashlib.sha256(message.message_id.encode()).hexdigest()[:32]
        candidates.append(BriefItem(
            category="private_mail",
            title=subject,
            detail=f"From {sender}"[:1000],
            why_now="Gmail marked this unread message as important",
            source=f"email_message:{fingerprint}",
            urgency="normal",
            kind="commitment",
            importance=0.8,
            relevance=0.9,
            confidence=0.85,
            sensitive=True,
        ))
    return candidates
