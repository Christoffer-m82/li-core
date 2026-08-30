import re
from datetime import UTC, datetime
from enum import Enum
from typing import Literal, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.freshness_policy import (
    POLICIES,
    FreshnessDecision,
    SourceClass,
    evidence_date_is_fresh,
)
from app.provider_coverage import OFFICIAL_DOMAIN_PATTERNS
from app.specialist_runtime import ResearchRequest


class SourceAuthority(str, Enum):
    statute = "statute"
    official_gazette = "official_gazette"
    regulator = "regulator"
    court = "court"
    government_portal = "government_portal"
    official_guidance = "official_guidance"
    secondary_commentary = "secondary_commentary"


AUTHORITY_RANK = {
    SourceAuthority.statute: 100, SourceAuthority.official_gazette: 95,
    SourceAuthority.regulator: 90, SourceAuthority.court: 90,
    SourceAuthority.government_portal: 80, SourceAuthority.official_guidance: 70,
    SourceAuthority.secondary_commentary: 10,
}


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
    source_authority: SourceAuthority = SourceAuthority.secondary_commentary
    authority_rank: int = 10
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
_CLAIM_WORD = re.compile(r"[a-z0-9][a-z0-9-]{2,}")
_CLAIM_STOPWORDS = {
    "about", "ask", "citizen", "claim", "current", "evidence", "given", "latest",
    "official", "only", "policy", "research", "right", "source", "specialist",
    "this", "today", "travelling", "use", "verify", "week", "what", "when", "which",
    "with",
}


def _sanitize(value: str, *, limit: int) -> str:
    value = _INSTRUCTION_BLOCK.sub("[external instruction removed]", value)
    value = _INJECTION_PHRASE.sub("[external instruction removed]", value)
    value = " ".join(value.split())
    return value[:limit]


def _contains_external_instruction(value: str) -> bool:
    return bool(_INSTRUCTION_BLOCK.search(value) or _INJECTION_PHRASE.search(value))


def _claim_mapping(query: str, *record_values: str) -> str | None:
    query_words = {
        word for word in _CLAIM_WORD.findall(query.casefold()) if word not in _CLAIM_STOPWORDS
    }
    record_words = set(_CLAIM_WORD.findall(" ".join(record_values).casefold()))
    required_overlap = 1 if len(query_words) <= 2 else 2
    return _sanitize(query, limit=500) if len(query_words & record_words) >= required_overlap else None


def _source_class(value: str, identifier: str, source: str | None) -> SourceClass:
    normalized = value.casefold().strip()
    try:
        hostname = (urlparse(identifier).hostname or "").casefold().rstrip(".")
    except ValueError:
        hostname = ""
    official_hosts = ("europa.eu", "who.int", "nhs.uk", *(
        pattern for patterns in OFFICIAL_DOMAIN_PATTERNS.values() for pattern in patterns
        if not pattern.startswith(".")
    ))
    government_cc_domain = bool(re.search(r"(?:^|\.)gov\.[a-z]{2,3}$", hostname))
    if (hostname.endswith(".gov") or government_cc_domain or
            any(hostname == host or hostname.endswith(f".{host}") for host in official_hosts)):
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


def _source_authority(value: str, identifier: str, source_class: SourceClass) -> SourceAuthority:
    normalized = value.casefold().strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "statute": SourceAuthority.statute, "legislation": SourceAuthority.statute,
        "official_gazette": SourceAuthority.official_gazette, "gazette": SourceAuthority.official_gazette,
        "regulator": SourceAuthority.regulator, "central_bank": SourceAuthority.regulator,
        "court": SourceAuthority.court, "judgment": SourceAuthority.court,
        "government": SourceAuthority.government_portal,
        "government_portal": SourceAuthority.government_portal,
        "official_guidance": SourceAuthority.official_guidance,
    }
    if normalized in aliases and source_class in {SourceClass.official, SourceClass.primary}:
        return aliases[normalized]
    if source_class == SourceClass.official:
        path = urlparse(identifier).path.casefold()
        if "legislation" in path or "statute" in path or "act/" in path:
            return SourceAuthority.statute
        return SourceAuthority.government_portal
    return SourceAuthority.secondary_commentary


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
            if any(_contains_external_instruction(value) for value in (
                raw.title, raw.identifier, raw.source or "", raw.excerpt, raw.source_type
            )):
                failed += 1
                continue
            source_class = _source_class(raw.source_type, raw.identifier, raw.source)
            source_authority = _source_authority(raw.source_type, raw.identifier, source_class)
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
                    source_class=source_class, source_authority=source_authority,
                    authority_rank=AUTHORITY_RANK[source_authority],
                    claim_mapping=_claim_mapping(
                        request.query, raw.title, raw.source or "", raw.excerpt
                    ),
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
        if (not fresh or not record.claim_mapping or
                (record.source_class == SourceClass.secondary and not allowed_secondary)):
            rejected += 1
            continue
        accepted.append(record.model_copy(update={"freshness_status": "fresh"}))
    primary_classes = {SourceClass.official, SourceClass.primary, SourceClass.authoritative,
                       SourceClass.provider}
    primary_present = any(
        item.source_class in primary_classes
        and item.source_class in decision.required_source_classes
        for item in accepted
    )
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
