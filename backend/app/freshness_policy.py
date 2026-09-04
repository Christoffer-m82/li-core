"""Versioned per-specialist freshness and evidence policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.request_language import has_term


POLICY_VERSION = "1.1"


class FreshnessMode(str, Enum):
    stable_allowed = "stable_allowed"
    current_check_required = "current_check_required"
    high_stakes_current_required = "high_stakes_current_required"


class SourceClass(str, Enum):
    official = "official"
    primary = "primary"
    authoritative = "authoritative"
    provider = "provider"
    academic = "academic"
    professional = "professional"
    news = "news"
    secondary = "secondary"


class EvidenceAgeLimit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_type: str
    maximum_age_days: int = Field(gt=0)


class SpecialistFreshnessPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    policy_version: str = POLICY_VERSION
    specialist_key: str
    domain: str
    freshness_mode: FreshnessMode
    live_verification_triggers: tuple[str, ...]
    high_stakes_triggers: tuple[str, ...] = ()
    maximum_evidence_age: tuple[EvidenceAgeLimit, ...]
    preferred_source_classes: tuple[SourceClass, ...]
    primary_or_official_required: bool = False
    minimum_source_count: int = Field(default=1, ge=1, le=5)
    secondary_commentary_allowed: bool = True
    provider_failure_behavior: Literal["qualify", "decline"] = "qualify"
    user_memory_may_combine: bool = True

    def age_limit(self, evidence_type: str) -> int:
        exact = next((x.maximum_age_days for x in self.maximum_evidence_age
                      if x.evidence_type == evidence_type), None)
        default = next(x.maximum_age_days for x in self.maximum_evidence_age
                       if x.evidence_type == "default")
        return exact or default


class FreshnessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    specialist_key: str
    policy_version: str
    evidence_required: bool
    high_stakes: bool = False
    freshness_reason: str
    required_source_classes: tuple[SourceClass, ...]
    primary_or_official_required: bool
    minimum_source_count: int
    maximum_age_days: int


def _limits(default: int, **values: int) -> tuple[EvidenceAgeLimit, ...]:
    return (EvidenceAgeLimit(evidence_type="default", maximum_age_days=default), *(
        EvidenceAgeLimit(evidence_type=key, maximum_age_days=value)
        for key, value in values.items()
    ))


def _policy(key: str, domain: str, mode: FreshnessMode, triggers: tuple[str, ...], *,
            high: tuple[str, ...] = (), days: int = 365,
            sources: tuple[SourceClass, ...] = (SourceClass.official, SourceClass.primary,
                                               SourceClass.authoritative),
            primary: bool = False, count: int = 1, secondary: bool = True,
            failure: Literal["qualify", "decline"] = "qualify",
            memory: bool = True, **age_types: int) -> SpecialistFreshnessPolicy:
    return SpecialistFreshnessPolicy(
        specialist_key=key, domain=domain, freshness_mode=mode,
        live_verification_triggers=triggers, high_stakes_triggers=high,
        maximum_evidence_age=_limits(days, **age_types), preferred_source_classes=sources,
        primary_or_official_required=primary, minimum_source_count=count,
        secondary_commentary_allowed=secondary, provider_failure_behavior=failure,
        user_memory_may_combine=memory,
    )


COMMON_CURRENT = ("latest", "today", "current", "right now", "this week", "recent", "as of")
POLICIES: dict[str, SpecialistFreshnessPolicy] = {
    "sofia": _policy("sofia", "health and medicine", FreshnessMode.high_stakes_current_required,
        ("guideline", "safety alert", "recall", "medication", "clinical guidance"),
        high=("symptom", "diagnosis", "treatment", "dose", "pregnan", "emergency"), days=365,
        sources=(SourceClass.official, SourceClass.authoritative, SourceClass.academic),
        primary=True, count=2, failure="decline", safety_alert=30),
    "marco": _policy("marco", "fitness and training", FreshnessMode.stable_allowed,
        ("sports rule", "event schedule", "product recall", "current research"),
        high=("injury", "chest pain", "rehabilitation"), days=730,
        sources=(SourceClass.authoritative, SourceClass.academic, SourceClass.official)),
    "elena": _policy("elena", "nutrition and food", FreshnessMode.stable_allowed,
        ("food recall", "allergen alert", "current guideline", "product availability"),
        high=("allergy", "pregnan", "eating disorder"), days=730,
        sources=(SourceClass.official, SourceClass.authoritative, SourceClass.academic)),
    "amelia": _policy("amelia", "relationships and communication", FreshnessMode.stable_allowed,
        ("current service", "current local resource", "safety resource"), days=730,
        sources=(SourceClass.official, SourceClass.authoritative, SourceClass.professional)),
    "freja": _policy("freja", "parenting and family", FreshnessMode.stable_allowed,
        ("current guideline", "school rule", "benefit rule", "product recall", "safety alert"),
        high=("child safety", "medical", "custody"), days=365,
        sources=(SourceClass.official, SourceClass.authoritative, SourceClass.academic), primary=True),
    "oliver": _policy("oliver", "law and regulation", FreshnessMode.high_stakes_current_required,
        ("law", "regulation", "jurisdiction", "court", "filing", "deadline", "legal requirement"),
        high=("legal advice", "contract", "liability", "employment", "tax", "court"), days=90,
        sources=(SourceClass.official, SourceClass.primary, SourceClass.authoritative),
        primary=True, count=1, failure="decline", law=30),
    "james": _policy("james", "finance, markets and tax", FreshnessMode.high_stakes_current_required,
        ("rate", "market", "yield", "inflation", "price", "tax", "pension", "regulation"),
        high=("invest", "financial advice", "tax", "mortgage", "pension"), days=30,
        sources=(SourceClass.official, SourceClass.primary, SourceClass.provider),
        primary=True, count=2, failure="decline", market=1, rate=7, tax=30),
    "victor": _policy("victor", "business, commercial and iGaming", FreshnessMode.current_check_required,
        ("regulation", "market", "competitor", "company", "operator launch", "tax", "jurisdiction"),
        days=90, sources=(SourceClass.official, SourceClass.primary, SourceClass.news),
        primary=True, count=2),
    "nora": _policy("nora", "research and evidence", FreshnessMode.current_check_required,
        ("research", "verify", "fact-check", "source", "evidence", "claim"), days=365,
        sources=(SourceClass.official, SourceClass.primary, SourceClass.authoritative,
                 SourceClass.academic), primary=True, count=1, failure="decline", memory=False),
    "milo": _policy("milo", "travel and leisure", FreshnessMode.current_check_required,
        ("entry requirement", "visa", "schedule", "flight", "strike", "closure", "advisory",
         "weather", "event", "ticket", "restaurant"), days=14,
        sources=(SourceClass.official, SourceClass.provider, SourceClass.primary),
        primary=True, count=1, failure="decline", weather=1, schedule=1, advisory=7),
    "iris": _policy("iris", "home, design, plants and gardening", FreshnessMode.stable_allowed,
        ("plant season", "seasonal", "weather", "product availability", "recall", "safety"), days=90,
        sources=(SourceClass.official, SourceClass.authoritative, SourceClass.provider)),
    "clara": _policy("clara", "wellbeing, habits and performance", FreshnessMode.stable_allowed,
        ("current guideline", "current local resource", "workplace rule"),
        high=("self-harm", "suicide", "crisis", "medical"), days=730,
        sources=(SourceClass.official, SourceClass.authoritative, SourceClass.academic)),
}

if len(POLICIES) != 12 or any(key != policy.specialist_key for key, policy in POLICIES.items()):
    raise RuntimeError("Freshness policy registry must cover exactly all permanent specialists.")


def decide_freshness(specialist_key: str, message: str) -> FreshnessDecision:
    policy = POLICIES[specialist_key]
    def matches(term: str) -> bool:
        # A few registry entries are intentional stems (for example ``pregnan``).
        # Everything else must match whole words so ``rate`` does not match
        # ``separate`` and ``market`` does not match ``marketing``.
        return has_term(message, term)

    high = next((term for term in policy.high_stakes_triggers if matches(term)), None)
    explicit = next((term for term in COMMON_CURRENT if matches(term)), None)
    trigger = next((term for term in policy.live_verification_triggers if matches(term)), None)
    required = bool(high or explicit or trigger)
    reason = (f"High-stakes {policy.domain} request requires current verification." if high else
              f"Explicit time-sensitive term '{explicit}' requires current verification." if explicit else
              f"Policy trigger '{trigger}' requires current verification." if trigger else
              f"Stable {policy.domain} knowledge is allowed for this request.")
    evidence_type = trigger or "default"
    return FreshnessDecision(
        specialist_key=specialist_key, policy_version=policy.policy_version,
        evidence_required=required, high_stakes=bool(high), freshness_reason=reason,
        required_source_classes=policy.preferred_source_classes,
        primary_or_official_required=policy.primary_or_official_required,
        minimum_source_count=policy.minimum_source_count,
        maximum_age_days=policy.age_limit(evidence_type),
    )


def evidence_date_is_fresh(publication_date: str | None, maximum_age_days: int,
                           *, now: datetime | None = None) -> bool:
    if not publication_date:
        return False
    try:
        published = datetime.fromisoformat(publication_date.replace("Z", "+00:00"))
    except ValueError:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return published <= (now or datetime.now(UTC)) and published >= (
        (now or datetime.now(UTC)) - timedelta(days=maximum_age_days)
    )


def public_policy_registry() -> dict[str, object]:
    return {"schema_version": "1.0", "policy_version": POLICY_VERSION,
            "specialists": [policy.model_dump(mode="json") for policy in POLICIES.values()]}
