"""Typed, versioned provider coverage and policy-compliant selection."""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.freshness_policy import FreshnessDecision, SourceClass

COVERAGE_VERSION = "1.0"


class ProviderDomain(str, Enum):
    web = "web"
    finance_market = "finance_market"
    finance_macro = "finance_macro"
    legal = "legal"


class FreshnessClass(str, Enum):
    real_time = "real_time"
    delayed = "delayed"
    official_current = "official_current"
    static = "static"


class AuthorityLevel(str, Enum):
    official_primary = "official_primary"
    authoritative = "authoritative"
    commercial_provider = "commercial_provider"
    secondary = "secondary"


class CostMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: Literal["free", "free_tier", "paid", "unknown"]
    note: str | None = None


class ProviderDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    coverage_version: str = COVERAGE_VERSION
    provider_id: str
    public_name: str
    domains: tuple[ProviderDomain, ...]
    source_classes: tuple[SourceClass, ...]
    jurisdictions: tuple[str, ...]
    markets: tuple[str, ...]
    freshness_classes: tuple[FreshnessClass, ...]
    authority_level: AuthorityLevel
    authentication: Literal["none", "credential_required"]
    configured: bool
    strict_policy_eligible: bool
    status: Literal["available", "not_configured", "limited"]
    status_probe: Literal["configuration", "adapter"]
    cost: CostMetadata | None = None
    public_summary: str


class ProviderRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    specialist_key: str
    domain: ProviderDomain
    required_source_classes: tuple[SourceClass, ...]
    required_freshness: FreshnessClass
    jurisdiction: str | None = None
    market: str | None = None
    primary_required: bool = False


class ProviderSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    requirement: ProviderRequirement
    selected_provider_ids: tuple[str, ...] = ()
    selected_source_classes: tuple[SourceClass, ...] = ()
    compliant: bool
    provider_selection_reason: str
    decline_reason: str | None = None


JURISDICTIONS: dict[str, tuple[str, ...]] = {
    "MT": ("malta", "maltese", "mt"),
    "GB": ("united kingdom", "uk", "british", "england", "wales", "scotland"),
    "EU": ("european union", "eu"),
    "US": ("united states", "usa", "us", "american"),
    "DE": ("germany", "german", "deutschland"),
}

OFFICIAL_DOMAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "MT": ("gov.mt", "legislation.mt", "justice.gov.mt", "mga.org.mt"),
    "GB": ("gov.uk", "legislation.gov.uk", "judiciary.uk"),
    "EU": ("europa.eu", "eur-lex.europa.eu", "curia.europa.eu"),
    "US": (".gov",),
    "DE": ("bund.de", "bundesgerichtshof.de", "gesetze-im-internet.de"),
}


def resolve_jurisdiction(query: str) -> str | None:
    lowered = query.casefold()
    for code, names in JURISDICTIONS.items():
        if any(re.search(rf"\b{re.escape(name)}\b", lowered) for name in names):
            return code
    return None


def provider_registry(*, web_configured: bool, market_quote_configured: bool = False) -> tuple[ProviderDefinition, ...]:
    return (
        ProviderDefinition(
            provider_id="official-web-resolution", public_name="Official web resolution",
            domains=(ProviderDomain.web, ProviderDomain.finance_macro, ProviderDomain.legal),
            source_classes=(SourceClass.official, SourceClass.primary, SourceClass.authoritative),
            jurisdictions=tuple(JURISDICTIONS), markets=(),
            freshness_classes=(FreshnessClass.official_current, FreshnessClass.static),
            authority_level=AuthorityLevel.official_primary,
            authentication="credential_required", configured=web_configured,
            strict_policy_eligible=True,
            status="available" if web_configured else "not_configured",
            status_probe="configuration", cost=CostMetadata(model="free_tier"),
            public_summary="Official and primary web sources; jurisdiction coverage varies.",
        ),
        ProviderDefinition(
            provider_id="market-quote-adapter", public_name="Market quote adapter",
            domains=(ProviderDomain.finance_market,), source_classes=(SourceClass.provider,),
            jurisdictions=(), markets=("configurable",),
            freshness_classes=(FreshnessClass.real_time,),
            authority_level=AuthorityLevel.commercial_provider,
            authentication="credential_required", configured=market_quote_configured,
            strict_policy_eligible=True,
            status="available" if market_quote_configured else "not_configured",
            status_probe="adapter", cost=CostMetadata(model="unknown", note="Depends on configured adapter."),
            public_summary="Real-time or near-real-time quotes; no adapter is configured by default.",
        ),
    )


def requirement_for(specialist_key: str, query: str, decision: FreshnessDecision) -> ProviderRequirement:
    lowered = query.casefold()
    if specialist_key == "james":
        live_quote = any(re.search(rf"\b{term}\b", lowered) for term in (
            "price", "quote", "spot", "trading", "ticker", "bitcoin", "stock"
        ))
        return ProviderRequirement(
            specialist_key=specialist_key,
            domain=ProviderDomain.finance_market if live_quote else ProviderDomain.finance_macro,
            required_source_classes=(SourceClass.provider,) if live_quote else (SourceClass.official, SourceClass.primary),
            required_freshness=FreshnessClass.real_time if live_quote else FreshnessClass.official_current,
            primary_required=True,
        )
    if specialist_key == "oliver":
        return ProviderRequirement(
            specialist_key=specialist_key, domain=ProviderDomain.legal,
            required_source_classes=(SourceClass.official, SourceClass.primary),
            required_freshness=FreshnessClass.official_current,
            jurisdiction=resolve_jurisdiction(query), primary_required=True,
        )
    return ProviderRequirement(
        specialist_key=specialist_key, domain=ProviderDomain.web,
        required_source_classes=decision.required_source_classes,
        required_freshness=FreshnessClass.official_current,
        primary_required=decision.primary_or_official_required,
    )


def select_providers(requirement: ProviderRequirement, registry: tuple[ProviderDefinition, ...]) -> ProviderSelection:
    if requirement.specialist_key == "oliver" and not requirement.jurisdiction:
        return ProviderSelection(
            requirement=requirement, compliant=False,
            provider_selection_reason="No supported jurisdiction could be resolved before research.",
            decline_reason="A named supported jurisdiction is required for current legal verification.",
        )
    candidates = [provider for provider in registry
                  if provider.configured and provider.strict_policy_eligible
                  and requirement.domain in provider.domains
                  and requirement.required_freshness in provider.freshness_classes
                  and any(source in provider.source_classes for source in requirement.required_source_classes)
                  and (not requirement.jurisdiction or requirement.jurisdiction in provider.jurisdictions)]
    if not candidates:
        label = ("real-time market quote" if requirement.required_freshness == FreshnessClass.real_time
                 else "required official/primary")
        return ProviderSelection(
            requirement=requirement, compliant=False,
            provider_selection_reason=f"No configured provider satisfies the {label} requirement.",
            decline_reason=f"No compliant {label} provider is configured for this request.",
        )
    chosen = candidates[0]
    selected_classes = tuple(source for source in requirement.required_source_classes
                             if source in chosen.source_classes)
    return ProviderSelection(
        requirement=requirement, selected_provider_ids=(chosen.provider_id,),
        selected_source_classes=selected_classes, compliant=True,
        provider_selection_reason=(f"Selected {chosen.public_name} because its configured coverage "
                                   "matches the required domain, freshness, and source authority."),
    )


def public_provider_coverage(*, web_configured: bool, market_quote_configured: bool = False) -> dict[str, object]:
    providers = provider_registry(web_configured=web_configured,
                                  market_quote_configured=market_quote_configured)
    return {
        "schema_version": "1.0", "coverage_version": COVERAGE_VERSION, "read_only": True,
        "providers": [provider.model_dump(mode="json", exclude={"provider_id"}) for provider in providers],
        "specialist_status": [
            {"specialist": "James", "summary": (
                "Official macro data is available; real-time market quote provider is "
                + ("configured." if market_quote_configured else "not configured."))},
            {"specialist": "Oliver", "summary": (
                "Official web resolution is available for supported jurisdictions; connector coverage varies."
                if web_configured else "Official web resolution is not configured; legal verification declines safely.")},
        ],
        "notes": ["Credentials and secret identifiers are never exposed.",
                  "Coverage is declared configuration, not a fabricated reliability metric."],
    }
