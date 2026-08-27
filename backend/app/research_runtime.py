import re
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.specialist_runtime import ResearchRequest


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
    publication_date: str | None = None
    retrieved_at: datetime
    excerpt: str
    source_type: str


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
                    publication_date=raw.publication_date,
                    retrieved_at=retrieved_at,
                    excerpt=_sanitize(raw.excerpt, limit=1200),
                    source_type=_sanitize(raw.source_type, limit=100),
                )
            )
        except (ValidationError, ValueError, TypeError):
            failed += 1
    return ResearchOutcome(
        evidence=evidence,
        failed_sources=failed,
        unavailable=not evidence,
    )
