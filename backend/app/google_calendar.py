import hashlib
from collections.abc import Mapping
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.calendar_runtime import (
    CalendarProviderError,
    CreateCalendarAction,
    SearchCalendarAction,
)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _validated_datetime(value: datetime, timezone: str | None) -> dict[str, str]:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarProviderError("Google Calendar requires timezone-aware datetimes.")
    result = {"dateTime": value.isoformat()}
    if timezone:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise CalendarProviderError("The calendar timezone is invalid.") from exc
        result["timeZone"] = timezone
    return result


def _map_google_event(candidate: object) -> object:
    if not isinstance(candidate, Mapping):
        return candidate
    start = candidate.get("start")
    end = candidate.get("end")
    if not isinstance(start, Mapping) or not isinstance(end, Mapping):
        return {"malformed": True}
    return {
        "event_id": candidate.get("id"),
        "title": candidate.get("summary") or "(untitled)",
        "start": start.get("dateTime"),
        "end": end.get("dateTime"),
        "timezone": start.get("timeZone") or end.get("timeZone"),
        "location": candidate.get("location"),
        "description": candidate.get("description"),
        "status": candidate.get("status"),
        "html_link": candidate.get("htmlLink"),
    }


def _event_id(request: CreateCalendarAction) -> str:
    """Stable Google-compatible ID prevents duplicate inserts after retries."""

    material = "\x1f".join(
        (
            request.title,
            request.start.isoformat(),
            request.end.isoformat(),
            request.timezone or "",
            request.location or "",
            request.description or "",
        )
    )
    return "li" + hashlib.sha256(material.encode("utf-8")).hexdigest()


class GoogleCalendarProvider:
    """Li-owned OAuth adapter using Google's least-privilege event scope."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        calendar_id: str = "primary",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._calendar_id = calendar_id
        self._timeout_seconds = timeout_seconds
        self._client = client

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        client = self._client or httpx
        try:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=self._timeout_seconds,
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            access_token = token_payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise CalendarProviderError("Google OAuth returned no access token.")
            granted_scope = token_payload.get("scope")
            if isinstance(granted_scope, str) and GOOGLE_CALENDAR_SCOPE not in granted_scope.split():
                raise CalendarProviderError("Google OAuth did not grant the calendar event scope.")
            response = client.request(
                method,
                f"{GOOGLE_CALENDAR_API}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except CalendarProviderError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise CalendarProviderError("Google Calendar request failed.") from exc

    def search_events(self, request: SearchCalendarAction) -> list[object]:
        params: dict[str, str | int] = {
            "timeMin": _validated_datetime(request.time_min, None)["dateTime"],
            "timeMax": _validated_datetime(request.time_max, None)["dateTime"],
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": request.max_results,
        }
        if request.query:
            params["q"] = request.query
        response = self._request(
            "GET", f"/calendars/{quote(self._calendar_id, safe='')}/events", params=params
        )
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise CalendarProviderError("Google Calendar returned invalid JSON.") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("items"), list):
            raise CalendarProviderError("Google Calendar returned an invalid event list.")
        return [_map_google_event(item) for item in payload["items"]]

    def create_event(self, request: CreateCalendarAction) -> object:
        body = {
            "id": _event_id(request),
            "summary": request.title,
            "start": _validated_datetime(request.start, request.timezone),
            "end": _validated_datetime(request.end, request.timezone),
        }
        if request.location:
            body["location"] = request.location
        if request.description:
            body["description"] = request.description
        path = f"/calendars/{quote(self._calendar_id, safe='')}/events"
        try:
            response = self._request("POST", path, json=body)
        except CalendarProviderError as exc:
            cause = exc.__cause__
            if isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code == 409:
                response = self._request("GET", f"{path}/{body['id']}")
            else:
                raise
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise CalendarProviderError("Google Calendar returned invalid JSON.") from exc
        mapped = _map_google_event(payload)
        if not isinstance(mapped, Mapping) or mapped.get("event_id") != body["id"]:
            raise CalendarProviderError("Google Calendar did not confirm the requested event.")
        return mapped
