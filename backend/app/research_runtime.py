import re
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.specialist_runtime import ResearchRequest
from app.freshness_policy import (
    FreshnessDecision,
    POLICIES,
    SourceClass,
    evidence_date_is_fresh,
)


class ResearchProviderError(RuntimeError):
    """Raised when a research provider is wholly unavailable."""


class RawEvidence(BaseModel):
    """Untrusted provider output before Li validates and sanitizes it."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    identifier: str = Field(min_length=1, max_length=2000)
    source: str | None = Field(default=None, max_length=300)
    publication_date: str | None = Field(default=None, max_length=100)
    excerpt: str = Field(min_length=1, max_length=4000)
    source_type: str = Field(min_length=1, max_length=100)


class EvidenceRecord(BaseModel):
    """Typed evidence safe to pass from Li back to a specialist."""

    model_config = ConfigDict(extra="forbid")

    title: str
    identifier: str
    source: str | None = None
    publisher_authority: str | None = None
    publication_date: str | None = None
    retrieved_at: datetime
    excerpt: str
    source_type: str
    source_class: SourceClass
    claim_mapping: str | None = None
    freshness_status: Literal["fresh", "stale", "unknown"]


class EvidenceValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    evidence: list[EvidenceRecord] = Field(default_factory=list, max_length=20)
    rejected_count: int = Field(default=0, ge=0)
    freshness_status: Literal["not_required", "passed", "failed"]
    source_class_summary: dict[str, int] = Field(default_factory=dict)
    failure_reason: str | None = None


class ResearchOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceRecord] = Field(default_factory=list, max_length=20)
    failed_sources: int = Field(default=0, ge=0)
    unavailable: bool = False


class ResearchProvider(Protocol):
    """Adapter boundary invoked only by Li.

    Providers must apply the request's freshness requirement and requested source types.
    Li passes both fields through unchanged and still validates every returned record.
    """

    def search(self, request: ResearchRequest) -> list[object]: ...


class UnavailableResearchProvider:
    """Safe default until a real web provider is configured."""

    def search(self, request: ResearchRequest) -> list[object]:
        raise ResearchProviderError("No live research provider is configured.")


def configured_research_provider(settings: object) -> ResearchProvider:
    """Build Li's provider without exposing credentials to specialists."""

    secret = getattr(settings, "brave_search_api_key", None)
    if secret is None:
        return UnavailableResearchProvider()
    api_key = secret.get_secret_value().strip()
    if not api_key:
        return UnavailableResearchProvider()

    from app.brave_research import BraveSearchProvider

    return BraveSearchProvider(
        api_key,
        timeout_seconds=getattr(settings, "brave_search_timeout_seconds", 10.0),
    )


def is_research_provider_available(provider: ResearchProvider) -> bool:
    return not isinstance(provider, UnavailableResearchProvider)


_INSTRUCTION_BLOCK = re.compile(
    r"(?im)^\s*(?:system|assistant|developer|tool|instruction|prompt)\s*:\s*.*$"
)
_INJECTION_PHRASE = re.compile(
    r"(?i)\b(?:ignore (?:all |any )?(?:previous|prior|system) instructions|"
    r"follow these instructions|you are now|call (?:the )?tool|execute (?:this|the following))\b"
)


def _sanitize(value: str, *, limit: int) -> str:
    value = _INSTRUCTION_BLOCK.sub("[external instruction removed]", value)
    value = _INJECTION_PHRASE.sub("[external instruction removed]", value)
    value = " ".join(value.split())
    return value[:limit]


def _source_class(value: str, identifier: str, source: str | None) -> SourceClass:
    normalized = value.casefold().strip()
    authority = f"{identifier} {source or ''}".casefold()
    if any(marker in authority for marker in (
        ".gov", "europa.eu", "who.int", "nhs.uk", "regulator", "central bank",
        "court", "ministry", "parliament", "official gazette",
    )):
        return SourceClass.official
    aliases = {
        "government": SourceClass.official, "regulator": SourceClass.official,
        "central_bank": SourceClass.official, "primary": SourceClass.primary,
        "official": SourceClass.official, "academic": SourceClass.academic,
        "medical": SourceClass.authoritative, "guideline": SourceClass.authoritative,
        "provider": SourceClass.provider, "news": SourceClass.news,
        "professional": SourceClass.professional, "secondary": SourceClass.secondary,
        "web": SourceClass.secondary,
    }
    return aliases.get(normalized, SourceClass.secondary)


def execute_research(
    request: ResearchRequest,
    provider: ResearchProvider,
) -> ResearchOutcome:
    """Execute Li-owned research and quarantine malformed or unsafe records."""

    try:
        candidates = provider.search(request)
    except Exception:  # noqa: BLE001 - adapters must fail closed regardless of exception type
        return ResearchOutcome(unavailable=True, failed_sources=1)

    evidence: list[EvidenceRecord] = []
    failed = 0
    retrieved_at = datetime.now(UTC)
    for candidate in candidates[:20]:
        try:
            raw = RawEvidence.model_validate(candidate)
            evidence.append(
                EvidenceRecord(
                    title=_sanitize(raw.title, limit=500),
                    identifier=_sanitize(raw.identifier, limit=2000),
                    source=_sanitize(raw.source, limit=300) if raw.source else None,
                    publisher_authority=_sanitize(raw.source, limit=300) if raw.source else None,
                    publication_date=raw.publication_date,
                    retrieved_at=retrieved_at,
                    excerpt=_sanitize(raw.excerpt, limit=1200),
                    source_type=_sanitize(raw.source_type, limit=100),
                    source_class=_source_class(raw.source_type, raw.identifier, raw.source),
                    claim_mapping=_sanitize(request.query, limit=500),
                    freshness_status="unknown",
                )
            )
        except (ValidationError, ValueError, TypeError):
            failed += 1
    return ResearchOutcome(
        evidence=evidence,
        failed_sources=failed,
        unavailable=not evidence,
    )


def validate_evidence_contract(
    specialist_key: str,
    decision: FreshnessDecision,
    evidence: list[EvidenceRecord],
    *,
    now: datetime | None = None,
) -> EvidenceValidation:
    """Enforce freshness, source hierarchy, and minimum-count rules after retrieval."""
    if not decision.evidence_required:
        return EvidenceValidation(passed=True, freshness_status="not_required")
    policy = POLICIES[specialist_key]
    accepted: list[EvidenceRecord] = []
    rejected = 0
    for record in evidence:
        fresh = evidence_date_is_fresh(record.publication_date, decision.maximum_age_days, now=now)
        allowed_secondary = policy.secondary_commentary_allowed
        if not fresh or (record.source_class == SourceClass.secondary and not allowed_secondary):
            rejected += 1
            continue
        accepted.append(record.model_copy(update={"freshness_status": "fresh"}))
    primary_classes = {SourceClass.official, SourceClass.primary, SourceClass.authoritative,
                       SourceClass.provider}
    primary_present = any(item.source_class in primary_classes for item in accepted)
    passed = len(accepted) >= decision.minimum_source_count and (
        not decision.primary_or_official_required or primary_present
    )
    summary: dict[str, int] = {}
    for item in accepted:
        summary[item.source_class.value] = summary.get(item.source_class.value, 0) + 1
    reason = None
    if not passed:
        reason = ("Required official/primary evidence was unavailable or stale."
                  if decision.primary_or_official_required and not primary_present
                  else "Not enough current evidence passed policy validation.")
    return EvidenceValidation(
        passed=passed, evidence=accepted if passed else [], rejected_count=rejected,
        freshness_status="passed" if passed else "failed", source_class_summary=summary,
        failure_reason=reason,
    )
