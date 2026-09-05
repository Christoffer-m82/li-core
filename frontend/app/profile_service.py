"""Private owner-profile service client for the browser BFF.

Configuration is disabled by default. This module does not choose IAM, storage or deployment state.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from app.backend import BackendUnavailable, cloud_run_identity_token
from app.config import Settings

MAX_PROFILE_SERVICE_RESPONSE_BYTES = 520 * 1024
_REQUESTS = {
    ("GET", "/v1/profile"): frozenset({200, 401, 403, 503}),
    ("GET", "/v1/profile/image"): frozenset({200, 401, 403, 404, 503}),
    ("PUT", "/v1/profile"): frozenset({200, 401, 403, 409, 413, 415, 422, 503}),
    ("DELETE", "/v1/profile"): frozenset({200, 401, 403, 409, 503}),
}


class ProfileServiceUnavailable(Exception):
    """The private service is disabled, unreachable or returned an invalid response."""


@dataclass(frozen=True)
class ProfileServiceResponse:
    status: int
    body: bytes = field(repr=False)
    content_type: str

    def __post_init__(self) -> None:
        if type(self.status) is not int or not 100 <= self.status <= 599 or not isinstance(self.body, bytes):
            raise TypeError("Invalid profile service response.")
        if self.content_type not in {"application/json", "image/jpeg"}:
            raise ValueError("Invalid profile service response.")


def profile_service_configured(settings: Settings) -> bool:
    return bool(settings.profile_service_url.strip() and settings.profile_service_audience.strip())


def _configuration(settings: Settings) -> tuple[str, str]:
    url = settings.profile_service_url.strip().rstrip("/")
    audience = settings.profile_service_audience.strip()
    if (
        not url
        or not audience
        or len(url) > 2048
        or len(audience) > 512
        or not url.isascii()
        or not audience.isascii()
        or any(ord(character) < 33 or ord(character) == 127 for character in url + audience)
    ):
        raise ProfileServiceUnavailable("Private profile service is not configured.")
    try:
        parsed = urlsplit(url)
        parsed.port
    except ValueError:
        raise ProfileServiceUnavailable("Private profile service configuration is invalid.") from None
    if (
        parsed.scheme not in ({"https"} if settings.production else {"http", "https"})
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ProfileServiceUnavailable("Private profile service configuration is invalid.")
    return url, audience


async def request_profile_service(
    settings: Settings,
    method: str,
    path: str,
    *,
    revision: str | None = None,
    content_type: str | None = None,
    content_length: int | None = None,
    body: AsyncIterable[bytes] | bytes | None = None,
) -> ProfileServiceResponse:
    allowed_statuses = _REQUESTS.get((method, path))
    if allowed_statuses is None:
        raise ValueError("Unsupported profile service operation.")
    url, audience = _configuration(settings)
    if method != "PUT" and (content_type is not None or content_length is not None or body is not None):
        raise ValueError("Profile body is valid only for replacement.")
    if method == "PUT" and (
        content_type not in {"image/jpeg", "image/png", "image/webp"}
        or type(content_length) is not int
        or not 1 <= content_length <= 5 * 1024 * 1024
        or body is None
    ):
        raise ValueError("Invalid profile replacement request.")
    if method in {"PUT", "DELETE"} and (
        not isinstance(revision, str)
        or not 1 <= len(revision) <= 64
        or not revision.isascii()
        or any(character.isspace() for character in revision)
    ):
        raise ValueError("Profile mutation requires a revision.")

    try:
        token = cloud_run_identity_token(audience)
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 8192
            or not token.isascii()
            or any(character.isspace() for character in token)
        ):
            raise ProfileServiceUnavailable("Private profile identity is unavailable.")
        headers = {"Authorization": f"Bearer {token}"}
        if revision is not None:
            headers["If-Match"] = revision
        if content_type is not None:
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(content_length)
        async with httpx.AsyncClient(
            timeout=settings.profile_request_timeout_seconds,
            follow_redirects=False,
        ) as client:
            async with client.stream(
                method, f"{url}{path}", headers=headers, content=body,
            ) as response:
                response_status = response.status_code
                if response_status not in allowed_statuses:
                    raise ProfileServiceUnavailable("Private profile service returned an invalid status.")
                result = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(result) + len(chunk) > MAX_PROFILE_SERVICE_RESPONSE_BYTES:
                        raise ProfileServiceUnavailable("Private profile service response is too large.")
                    result.extend(chunk)
                response_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    except ProfileServiceUnavailable:
        raise
    except (BackendUnavailable, httpx.HTTPError, OSError, ValueError):
        raise ProfileServiceUnavailable("Private profile service is unavailable.") from None

    expected_type = "image/jpeg" if path.endswith("/image") and response_status == 200 else "application/json"
    if response_type != expected_type:
        raise ProfileServiceUnavailable("Private profile service returned an invalid response.")
    return ProfileServiceResponse(response_status, bytes(result), response_type)
