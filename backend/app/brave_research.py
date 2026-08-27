import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx

from app.research_runtime import ResearchProviderError
from app.specialist_runtime import ResearchRequest

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

_CUSTOM_RANGE = re.compile(
    r"(?P<start>\d{4}-\d{2}-\d{2})\s*(?:to|through|until|-)\s*"
    r"(?P<end>\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_LAST_NUMBERED_PERIOD = re.compile(
    r"\b(?:last|past|within)\s+(?P<count>\d+)\s+"
    r"(?P<unit>hours?|days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)


def brave_freshness_filter(requirement: str, *, now: datetime | None = None) -> str | None:
    """Translate common typed freshness requirements to Brave's supported filters."""

    normalized = " ".join(requirement.lower().split())
    custom = _CUSTOM_RANGE.search(normalized)
    if custom:
        return f"{custom.group('start')}to{custom.group('end')}"

    if any(phrase in normalized for phrase in ("24 hours", "one day", "today")):
        return "pd"
    if any(phrase in normalized for phrase in ("7 days", "one week", "this week")):
        return "pw"
    if any(phrase in normalized for phrase in ("30 days", "31 days", "one month")):
        return "pm"
    if any(phrase in normalized for phrase in ("12 months", "one year", "365 days")):
        return "py"

    numbered = _LAST_NUMBERED_PERIOD.search(normalized)
    if not numbered:
        return None

    count = int(numbered.group("count"))
    unit = numbered.group("unit")
    if count == 1 and unit.startswith("hour"):
        return "pd"
    if count <= 1 and unit.startswith("day"):
        return "pd"
    if count <= 7 and unit.startswith("day"):
        return "pw"
    if count <= 31 and unit.startswith("day"):
        return "pm"
    if count <= 1 and unit.startswith("week"):
        return "pw"
    if count <= 4 and unit.startswith("week"):
        return "pm"
    if count <= 1 and unit.startswith("month"):
        return "pm"
    if count <= 12 and unit.startswith("month"):
        return "py"
    if count <= 1 and unit.startswith("year"):
        return "py"

    end = (now or datetime.now(UTC)).date()
    if unit.startswith("hour"):
        days = max(1, (count + 23) // 24)
    elif unit.startswith("day"):
        days = count
    elif unit.startswith("week"):
        days = count * 7
    elif unit.startswith("month"):
        days = count * 31
    else:
        days = count * 365
    start = end - timedelta(days=days)
    return f"{start.isoformat()}to{end.isoformat()}"


def _result_filters(source_types: list[str]) -> str:
    normalized = " ".join(source_types).lower()
    wants_news = any(word in normalized for word in ("news", "journalism", "media"))
    wants_web = any(word in normalized for word in (
        "web", "primary", "regulator", "official", "filing", "report", "paper",
    ))
    if wants_news and not wants_web:
        return "news"
    if wants_news:
        return "web,news"
    return "web"


def _publisher(result: Mapping[str, object], identifier: str) -> str | None:
    profile = result.get("profile")
    if isinstance(profile, Mapping):
        long_name = profile.get("long_name")
        if isinstance(long_name, str) and long_name.strip():
            return long_name
    hostname = urlparse(identifier).hostname
    return hostname.removeprefix("www.") if hostname else None


def _map_result(result: object, source_type: str) -> object:
    if not isinstance(result, Mapping):
        return result
    identifier = result.get("url")
    if not isinstance(identifier, str):
        identifier = ""
    return {
        "title": result.get("title"),
        "identifier": identifier,
        "source": _publisher(result, identifier),
        "publication_date": result.get("page_age") or result.get("age"),
        "excerpt": result.get("description"),
        "source_type": source_type,
    }


class BraveSearchProvider:
    """Li-owned adapter for Brave Web Search API results."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client = client

    def search(self, request: ResearchRequest) -> list[object]:
        params: dict[str, str | int] = {
            "q": request.query,
            "count": 20,
            "result_filter": _result_filters(request.source_types),
            "safesearch": "strict",
            "text_decorations": "false",
        }
        freshness = brave_freshness_filter(request.freshness_requirement)
        if freshness:
            params["freshness"] = freshness

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key,
        }
        try:
            if self._client is None:
                response = httpx.get(
                    BRAVE_WEB_SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            else:
                response = self._client.get(
                    BRAVE_WEB_SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ResearchProviderError("Brave Search is unavailable.") from exc

        if not isinstance(payload, Mapping):
            raise ResearchProviderError("Brave Search returned an invalid response.")

        candidates: list[object] = []
        for section_name, source_type in (("web", "web"), ("news", "news")):
            section = payload.get(section_name)
            if section is None:
                continue
            if not isinstance(section, Mapping):
                candidates.append(section)
                continue
            results = section.get("results", [])
            if not isinstance(results, list):
                candidates.append(results)
                continue
            candidates.extend(_map_result(result, source_type) for result in results)
        return candidates
