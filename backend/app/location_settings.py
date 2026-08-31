"""Private, minimal Place settings and relevance-gated context contracts."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ISO 3166-1 alpha-2 codes. Names are localized by the web client with Intl.DisplayNames.
ISO_COUNTRY_CODES = tuple("""AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW""".split())  # noqa: SIM905
ISO_COUNTRY_CODE_SET = frozenset(ISO_COUNTRY_CODES)


class CurrentPlace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country_code: str | None = None
    town_city: str | None = Field(default=None, max_length=120)
    source: Literal["manual_web", "manual_mobile", "device_coarse"] = "manual_web"
    provider_permission: Literal["not_applicable", "not_requested", "denied", "granted"] = "not_applicable"

    @field_validator("country_code")
    @classmethod
    def valid_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.upper()
        if value not in ISO_COUNTRY_CODE_SET:
            raise ValueError("country_code must be ISO 3166-1 alpha-2")
        return value

    @field_validator("town_city")
    @classmethod
    def clean_town(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def consistent_provider_state(self) -> CurrentPlace:
        if self.source == "device_coarse" and self.provider_permission != "granted":
            raise ValueError("device_coarse requires granted permission")
        if self.source != "device_coarse" and self.provider_permission == "granted":
            raise ValueError("granted permission is reserved for device_coarse")
        return self


class MostVisitedPreference(BaseModel):
    country_code: str
    state: Literal["automatic", "pinned", "suppressed"]

    @field_validator("country_code")
    @classmethod
    def valid_country(cls, value: str) -> str:
        value = value.upper()
        if value not in ISO_COUNTRY_CODE_SET:
            raise ValueError("invalid country")
        return value


class VisitEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country_code: str
    first_seen: date
    last_seen: date
    overnight_confirmed: bool = False
    source: Literal["manual", "device_coarse"] = "manual"

    @field_validator("country_code")
    @classmethod
    def valid_country(cls, value: str) -> str:
        value = value.upper()
        if value not in ISO_COUNTRY_CODE_SET:
            raise ValueError("invalid country")
        return value

    @field_validator("last_seen")
    @classmethod
    def ordered_dates(cls, value: date, info) -> date:
        first = info.data.get("first_seen")
        if first and value < first:
            raise ValueError("last_seen cannot precede first_seen")
        return value

    @model_validator(mode="after")
    def confirmed_overnight_spans_a_night(self) -> VisitEvent:
        if self.overnight_confirmed and self.last_seen <= self.first_seen:
            raise ValueError("confirmed overnight visit must span at least one night")
        return self


class LocationProvider(Protocol):
    """Future native boundary; implementations must return derived coarse state only."""

    permission_state: Literal["not_requested", "denied", "granted"]

    def current_place(self) -> CurrentPlace | None: ...


PermissionState = Literal["unknown", "not_requested", "denied", "granted", "restricted"]


class MobilePermissionProof(BaseModel):
    """Minimal client assertion; never contains an OS token or location payload."""

    model_config = ConfigDict(extra="forbid")
    state: PermissionState
    platform: Literal["ios", "android"]
    checked_at: datetime


class MobileOvernightEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    first_observed_at: datetime
    last_observed_at: datetime
    classification: Literal["overnight", "transit"]

    @model_validator(mode="after")
    def valid_range(self) -> MobileOvernightEvent:
        if self.first_observed_at.utcoffset() is None or self.last_observed_at.utcoffset() is None:
            raise ValueError("visit timestamps must include a timezone")
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("last_observed_at cannot precede first_observed_at")
        if (self.classification == "overnight" and
                self.last_observed_at.date() <= self.first_observed_at.date()):
            raise ValueError("overnight event must span at least one night")
        return self


class MobileLocationUpdateV1(BaseModel):
    """Stable privacy-minimal contract for a future authenticated native gateway."""

    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["1.0"] = "1.0"
    installation_id: UUID
    update_id: UUID
    country_code: str
    town_city: str | None = Field(default=None, max_length=120)
    source: Literal["device_coarse"] = "device_coarse"
    permission: MobilePermissionProof
    observed_at: datetime
    overnight_event: MobileOvernightEvent | None = None

    @field_validator("country_code")
    @classmethod
    def valid_country(cls, value: str) -> str:
        value = value.upper()
        if value not in ISO_COUNTRY_CODE_SET:
            raise ValueError("country_code must be ISO 3166-1 alpha-2")
        return value

    @field_validator("town_city")
    @classmethod
    def clean_town(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @model_validator(mode="after")
    def granted_and_consistent(self) -> MobileLocationUpdateV1:
        if self.observed_at.utcoffset() is None or self.permission.checked_at.utcoffset() is None:
            raise ValueError("mobile timestamps must include a timezone")
        if self.permission.state != "granted":
            raise ValueError("device_coarse update requires granted OS permission")
        if self.permission.checked_at < self.observed_at - timedelta(hours=24):
            raise ValueError("permission proof is stale")
        if self.permission.checked_at > self.observed_at + timedelta(minutes=5):
            raise ValueError("permission proof cannot post-date the observation")
        if self.overnight_event and self.overnight_event.last_observed_at > self.observed_at:
            raise ValueError("overnight event cannot extend beyond the observation")
        return self


def validate_mobile_freshness(observed_at: datetime, *, now: datetime | None = None,
                              max_age: timedelta = timedelta(hours=24),
                              future_skew: timedelta = timedelta(minutes=5)) -> None:
    current = now or datetime.now(UTC)
    observed = observed_at.astimezone(UTC)
    if observed < current - max_age:
        raise ValueError("location observation is stale")
    if observed > current + future_skew:
        raise ValueError("location observation is in the future")


def device_update_may_replace(*, current_source: str | None, current_updated_at: datetime | None,
                              observed_at: datetime,
                              manual_hold: timedelta = timedelta(hours=24)) -> bool:
    """A device observation must post-date a manual correction and its hold window."""
    if current_source not in {"manual_web", "manual_mobile"} or current_updated_at is None:
        return True
    return observed_at >= current_updated_at + manual_hold


_LOCATION_RELEVANT = re.compile(
    r"\b(?:near me|nearby|local|weather|restaurant|shop|service|law|legal|tax|health|doctor|"
    r"insurance|visa|residen|travel|trip|hotel|flight|garden|plant|delivery|currency|"
    r"jurisdiction|licen[cs]e|permit|government|bank)\b", re.IGNORECASE
)
_TOWN_RELEVANT = re.compile(
    r"\b(?:near me|nearby|restaurant|cafe|shop|local service|weather|doctor|hospital|"
    r"hotel|airport|delivery|garden cent(?:er|re))\b", re.IGNORECASE
)


def location_is_relevant(message: str) -> bool:
    return bool(_LOCATION_RELEVANT.search(message))


def town_is_useful(message: str) -> bool:
    return bool(_TOWN_RELEVANT.search(message))


def minimal_location_context(message: str, place: CurrentPlace | None) -> str | None:
    if not place or not place.country_code or not location_is_relevant(message):
        return None
    town_relevant = town_is_useful(message)
    town = f"; town/city: {place.town_city}" if place.town_city and town_relevant else ""
    prompt = " Ask for town/city only if materially needed." if not place.town_city and town_relevant else ""
    return (
        f"Private current place (relevant to this request): country ISO {place.country_code}{town}."
        f"{prompt} This context does not replace freshness, evidence, provider coverage, or "
        "jurisdiction-specific verification. Do not mention visit history."
    )


def qualifying_visit_count(events: list[VisitEvent], *, today: date | None = None) -> dict[str, int]:
    cutoff = (today or datetime.now(UTC).date()) - timedelta(days=365)
    trips: dict[str, list[tuple[date, date]]] = {}
    for event in events:
        if event.overnight_confirmed and event.last_seen > event.first_seen:
            trips.setdefault(event.country_code, []).append((event.first_seen, event.last_seen))
    counts: dict[str, int] = {}
    for country, ranges in trips.items():
        merged: list[list[date]] = []
        for first_seen, last_seen in sorted(ranges):
            if merged and first_seen <= merged[-1][1] + timedelta(days=1):
                merged[-1][1] = max(merged[-1][1], last_seen)
            else:
                merged.append([first_seen, last_seen])
        count = sum(last_seen >= cutoff for _, last_seen in merged)
        if count:
            counts[country] = count
    return counts


def promoted_countries(events: list[VisitEvent], preferences: list[MostVisitedPreference]) -> list[str]:
    states = {item.country_code: item.state for item in preferences}
    pinned = [item.country_code for item in preferences if item.state == "pinned"]
    automatic = sorted(
        country for country, count in qualifying_visit_count(events).items()
        if count >= 2 and states.get(country) != "suppressed" and country not in pinned
    )
    return list(dict.fromkeys([*pinned, *automatic]))
