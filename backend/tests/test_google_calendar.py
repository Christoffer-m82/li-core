from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from app.calendar_runtime import (
    CalendarProviderError,
    CreateCalendarAction,
    SearchCalendarAction,
    UnavailableCalendarProvider,
    configured_calendar_provider,
)
from app.google_calendar import GOOGLE_CALENDAR_SCOPE, GoogleCalendarProvider

START = datetime(2030, 6, 3, 9, 0, tzinfo=UTC)
END = datetime(2030, 6, 3, 10, 0, tzinfo=UTC)


def _google_event(event_id: str = "event1") -> dict[str, object]:
    return {
        "id": event_id,
        "summary": "Planning",
        "start": {"dateTime": "2030-06-03T11:00:00+02:00", "timeZone": "Europe/Berlin"},
        "end": {"dateTime": "2030-06-03T12:00:00+02:00", "timeZone": "Europe/Berlin"},
        "location": "Office",
        "description": "Quarterly plan",
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/event?eid=event1",
    }


def _provider(handler) -> GoogleCalendarProvider:
    return GoogleCalendarProvider(
        client_id="client-id",
        client_secret="client-secret",
        refresh_token="refresh-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _token_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": "access-token", "scope": GOOGLE_CALENDAR_SCOPE},
        request=request,
    )


def test_search_maps_google_event_and_preserves_timezone() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        assert request.headers["Authorization"] == "Bearer access-token"
        assert request.url.params["timeMin"] == START.isoformat()
        return httpx.Response(200, json={"items": [_google_event()]}, request=request)

    events = _provider(handler).search_events(
        SearchCalendarAction(action="calendar.search", time_min=START, time_max=END)
    )
    assert events == [{
        "event_id": "event1",
        "title": "Planning",
        "start": "2030-06-03T11:00:00+02:00",
        "end": "2030-06-03T12:00:00+02:00",
        "start_date": None,
        "end_date": None,
        "all_day": False,
        "timezone": "Europe/Berlin",
        "location": "Office",
        "description": "Quarterly plan",
        "status": "confirmed",
        "html_link": "https://calendar.google.com/event?eid=event1",
    }]


def test_search_maps_all_day_dates_without_timezone_conversion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        return httpx.Response(200, json={"items": [{
            "id": "all-day", "summary": "Birthday",
            "start": {"date": "2030-06-03"}, "end": {"date": "2030-06-04"},
            "status": "confirmed",
        }]}, request=request)

    event = _provider(handler).search_events(
        SearchCalendarAction(action="calendar.search", time_min=START, time_max=END)
    )[0]
    assert event["all_day"] is True
    assert event["start_date"] == "2030-06-03"
    assert event["end_date"] == "2030-06-04"
    assert event["start"] is None and event["end"] is None


def test_create_sends_timezone_and_uses_stable_idempotency_id() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        body = __import__("json").loads(request.content)
        bodies.append(body)
        event = _google_event(str(body["id"]))
        return httpx.Response(200, json=event, request=request)

    provider = _provider(handler)
    action = CreateCalendarAction(
        action="calendar.create",
        title="Planning",
        start=START,
        end=END,
        timezone="Europe/Berlin",
    )
    first = provider.create_event(action)
    second = provider.create_event(action)
    assert bodies[0]["id"] == bodies[1]["id"]
    assert bodies[0]["start"] == {
        "dateTime": START.isoformat(),
        "timeZone": "Europe/Berlin",
    }
    assert first["event_id"] == bodies[0]["id"]
    assert second["event_id"] == bodies[0]["id"]


def test_duplicate_create_reads_existing_event_after_google_conflict() -> None:
    calls: list[str] = []
    event_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal event_id
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        calls.append(request.method)
        if request.method == "POST":
            event_id = __import__("json").loads(request.content)["id"]
            return httpx.Response(409, json={"error": "duplicate"}, request=request)
        return httpx.Response(200, json=_google_event(event_id), request=request)

    result = _provider(handler).create_event(CreateCalendarAction(
        action="calendar.create", title="Planning", start=START, end=END
    ))
    assert calls == ["POST", "GET"]
    assert result["event_id"] == event_id


@pytest.mark.parametrize(
    "token_payload",
    [
        {},
        {"access_token": "token", "scope": "https://www.googleapis.com/auth/calendar.readonly"},
    ],
)
def test_auth_failure_fails_closed(token_payload) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=token_payload, request=request)

    with pytest.raises(CalendarProviderError):
        _provider(handler).search_events(
            SearchCalendarAction(action="calendar.search", time_min=START, time_max=END)
        )


def test_provider_http_failure_fails_closed_without_leaking_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        return httpx.Response(503, text="secret upstream detail", request=request)

    with pytest.raises(CalendarProviderError, match="Google Calendar request failed"):
        _provider(handler).search_events(
            SearchCalendarAction(action="calendar.search", time_min=START, time_max=END)
        )


@pytest.mark.parametrize("payload", [{}, {"items": {}}, "invalid"])
def test_malformed_google_event_list_fails_closed(payload) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        return httpx.Response(200, json=payload, request=request)

    with pytest.raises(CalendarProviderError):
        _provider(handler).search_events(
            SearchCalendarAction(action="calendar.search", time_min=START, time_max=END)
        )


def test_malformed_item_is_returned_for_executor_quarantine() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        return httpx.Response(200, json={"items": [_google_event(), {"id": "bad"}]}, request=request)

    result = _provider(handler).search_events(
        SearchCalendarAction(action="calendar.search", time_min=START, time_max=END)
    )
    assert result[0]["event_id"] == "event1"
    assert result[1] == {"malformed": True}


def test_naive_datetime_and_invalid_timezone_are_rejected_before_api_call() -> None:
    provider = _provider(lambda request: _token_response(request))
    with pytest.raises(CalendarProviderError):
        provider.create_event(CreateCalendarAction(
            action="calendar.create",
            title="Planning",
            start=datetime(2030, 6, 3, 9),  # noqa: DTZ001 - intentionally invalid input
            end=datetime(2030, 6, 3, 10),  # noqa: DTZ001 - intentionally invalid input
        ))
    with pytest.raises(CalendarProviderError):
        provider.create_event(CreateCalendarAction(
            action="calendar.create",
            title="Planning",
            start=START,
            end=END,
            timezone="Not/A_Timezone",
        ))


def test_configuration_requires_all_oauth_secrets() -> None:
    incomplete = SimpleNamespace(
        google_calendar_client_id=SecretStr("id"),
        google_calendar_client_secret=None,
        google_calendar_refresh_token=SecretStr("token"),
    )
    assert isinstance(configured_calendar_provider(incomplete), UnavailableCalendarProvider)

    complete = SimpleNamespace(
        google_calendar_client_id=SecretStr("id"),
        google_calendar_client_secret=SecretStr("secret"),
        google_calendar_refresh_token=SecretStr("token"),
        google_calendar_id="primary",
        google_calendar_timeout_seconds=5.0,
    )
    assert isinstance(configured_calendar_provider(complete), GoogleCalendarProvider)


@pytest.mark.parametrize("stage,status,body,category", [
    ("oauth", 400, {"error": "invalid_grant"}, "authentication"),
    ("oauth", 401, {"error": "invalid_client"}, "configuration"),
    ("api", 401, {}, "authentication"),
    ("api", 403, {"error": {"errors": [{"reason": "insufficientPermissions"}]}}, "scope"),
    ("api", 403, {"error": {"details": [{"reason": "SERVICE_DISABLED"}]}}, "api_disabled"),
    ("api", 403, {"error": {"errors": [{"reason": "userRateLimitExceeded"}]}}, "rate_limited"),
    ("api", 403, {}, "access_denied"),
    ("api", 404, {}, "not_found_or_inaccessible"),
    ("api", 400, {}, "invalid_request"),
    ("api", 429, {}, "rate_limited"),
    ("api", 503, {}, "unavailable"),
    ("oauth", 400, {"error": ["untrusted"]}, "unknown"),
])
@pytest.mark.parametrize("query", ["PRIVATE_QUERY meeting", "PRIVATE_QUERY möte"])
def test_sanitized_failure_categories(stage, status, body, category, query, caplog) -> None:
    from app.calendar_runtime import CalendarActionEnvelope, execute_calendar_action

    calls = []

    def handler(request):
        calls.append(request.method)
        if stage == "api" and request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        return httpx.Response(status, json={**body, "message": "PRIVATE_SENTINEL"})

    outcome = execute_calendar_action(CalendarActionEnvelope(request=SearchCalendarAction(
        action="calendar.search", time_min=START, time_max=END, query=query,
    )), _provider(handler))
    assert outcome.status == "failed"
    assert outcome.events == []
    assert f"category={category}" in caplog.text
    assert f"stage={stage}" in caplog.text
    assert f"http_status={status}" in caplog.text
    assert "PRIVATE" not in caplog.text + outcome.model_dump_json()
    assert len(calls) == (1 if stage == "oauth" else 2)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("payload", [[], None, {}, {"access_token": "token", "scope": []}])
def test_malformed_token_is_classified_without_api_call(payload, caplog) -> None:
    from app.calendar_runtime import CalendarActionEnvelope, execute_calendar_action

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    outcome = execute_calendar_action(CalendarActionEnvelope(request=SearchCalendarAction(
        action="calendar.search", time_min=START, time_max=END,
    )), _provider(handler))
    assert outcome.status == "failed"
    assert "category=malformed_response" in caplog.text
    assert len(calls) == 1


@pytest.mark.parametrize("stage", ["oauth", "api"])
@pytest.mark.parametrize("error,category", [
    (httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "network"),
])
def test_transport_diagnostics_never_log_exception(stage, error, category, caplog) -> None:
    from app.calendar_runtime import CalendarActionEnvelope, execute_calendar_action

    def handler(request):
        if stage == "api" and request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        raise error("PRIVATE_SENTINEL", request=request)

    outcome = execute_calendar_action(CalendarActionEnvelope(request=SearchCalendarAction(
        action="calendar.search", time_min=START, time_max=END,
    )), _provider(handler))
    assert outcome.status == "failed"
    assert f"category={category}" in caplog.text
    assert f"stage={stage}" in caplog.text
    assert "PRIVATE_SENTINEL" not in caplog.text


@pytest.mark.parametrize("body", [
    {"error": {"errors": [{"reason": ["PRIVATE_SENTINEL"]}]}},
    {"error": {"errors": [{"reason": "PRIVATE_SENTINEL"}]}},
    {"error": {"details": "PRIVATE_SENTINEL"}},
    {"error": {"errors": [{"reason": "SERVICE_DISABLED"}], "message": "x" * 17_000}},
])
def test_untrusted_or_oversized_error_uses_status_only(body, caplog) -> None:
    from app.calendar_runtime import CalendarActionEnvelope, execute_calendar_action

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            return _token_response(request)
        return httpx.Response(403, json=body)

    execute_calendar_action(CalendarActionEnvelope(request=SearchCalendarAction(
        action="calendar.search", time_min=START, time_max=END,
    )), _provider(handler))
    assert "category=access_denied" in caplog.text
    assert "PRIVATE_SENTINEL" not in caplog.text


def test_oauth_conflict_never_triggers_create_reconciliation() -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(409, text="PRIVATE_SENTINEL")

    with pytest.raises(CalendarProviderError):
        _provider(handler).create_event(CreateCalendarAction(
            action="calendar.create", title="Synthetic", start=START, end=END,
        ))
    assert len(calls) == 1


def test_missing_required_scope_is_diagnostic_not_permission_expansion(caplog) -> None:
    from app.calendar_runtime import CalendarActionEnvelope, execute_calendar_action

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={
            "access_token": "synthetic", "scope": "https://www.googleapis.com/auth/calendar",
        })

    result = execute_calendar_action(CalendarActionEnvelope(request=SearchCalendarAction(
        action="calendar.search", time_min=START, time_max=END,
    )), _provider(handler))
    assert result.status == "failed"
    assert "category=scope stage=oauth" in caplog.text
    assert len(calls) == 1
