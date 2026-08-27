from datetime import datetime
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class CalendarProviderError(RuntimeError):
    """Raised when a calendar provider cannot complete an operation."""


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    start: datetime
    end: datetime
    timezone: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, max_length=100)
    html_link: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "CalendarEvent":
        if self.end <= self.start:
            raise ValueError("Calendar event end must be after start.")
        return self


class SearchCalendarAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["calendar.search"]
    time_min: datetime
    time_max: datetime
    query: str | None = Field(default=None, max_length=500)
    max_results: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def range_must_be_valid(self) -> "SearchCalendarAction":
        if self.time_max <= self.time_min:
            raise ValueError("Calendar search time_max must be after time_min.")
        return self


class CreateCalendarAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["calendar.create"]
    title: str = Field(min_length=1, max_length=500)
    start: datetime
    end: datetime
    timezone: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "CreateCalendarAction":
        if self.end <= self.start:
            raise ValueError("Calendar event end must be after start.")
        return self


CalendarActionRequest = Annotated[
    SearchCalendarAction | CreateCalendarAction,
    Field(discriminator="action"),
]


class CalendarActionEnvelope(BaseModel):
    """Li-owned execution envelope. Specialists never receive or produce it."""

    request: CalendarActionRequest
    approved: bool = False


class CalendarActionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "approval_required", "failed"]
    action: Literal["calendar.search", "calendar.create"]
    events: list[CalendarEvent] = Field(default_factory=list)
    event: CalendarEvent | None = None
    message: str
    failed_items: int = Field(default=0, ge=0)


class CalendarProvider(Protocol):
    """Least-privilege calendar adapter invoked only by Li's executor."""

    def search_events(self, request: SearchCalendarAction) -> list[object]: ...

    def create_event(self, request: CreateCalendarAction) -> object: ...


class UnavailableCalendarProvider:
    def search_events(self, request: SearchCalendarAction) -> list[object]:
        raise CalendarProviderError("No calendar provider is configured.")

    def create_event(self, request: CreateCalendarAction) -> object:
        raise CalendarProviderError("No calendar provider is configured.")


def execute_calendar_action(
    envelope: CalendarActionEnvelope,
    provider: CalendarProvider,
) -> CalendarActionOutcome:
    """Validate approval at the execution boundary and fail closed on bad provider data."""

    request = envelope.request
    if isinstance(request, CreateCalendarAction) and not envelope.approved:
        return CalendarActionOutcome(
            status="approval_required",
            action=request.action,
            message=(
                f'Approval required to create "{request.title}" from '
                f"{request.start.isoformat()} to {request.end.isoformat()}."
            ),
        )

    if isinstance(request, SearchCalendarAction):
        try:
            raw_events = provider.search_events(request)
        except Exception:  # noqa: BLE001 - provider adapters must fail closed
            return CalendarActionOutcome(
                status="failed",
                action=request.action,
                message="Calendar search failed; no calendar state was changed.",
                failed_items=1,
            )

        events: list[CalendarEvent] = []
        failed_items = 0
        if not isinstance(raw_events, list):
            raw_events = [raw_events]
        for candidate in raw_events[: request.max_results]:
            try:
                events.append(CalendarEvent.model_validate(candidate))
            except (ValidationError, ValueError, TypeError):
                failed_items += 1
        if not events and failed_items:
            return CalendarActionOutcome(
                status="failed",
                action=request.action,
                message="Calendar provider returned no valid events.",
                failed_items=failed_items,
            )
        return CalendarActionOutcome(
            status="completed",
            action=request.action,
            events=events,
            message=f"Found {len(events)} calendar event(s).",
            failed_items=failed_items,
        )

    try:
        raw_event = provider.create_event(request)
        event = CalendarEvent.model_validate(raw_event)
    except Exception:  # noqa: BLE001 - creation must never claim success on adapter failure
        return CalendarActionOutcome(
            status="failed",
            action=request.action,
            message="Calendar event creation failed; success was not confirmed.",
            failed_items=1,
        )
    return CalendarActionOutcome(
        status="completed",
        action=request.action,
        event=event,
        message=f'Created calendar event "{event.title}".',
    )
