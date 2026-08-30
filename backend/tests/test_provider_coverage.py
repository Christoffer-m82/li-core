from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.freshness_policy import SourceClass, decide_freshness
from app.main import app
from app.provider_coverage import (
    AuthorityLevel,
    CostMetadata,
    FreshnessClass,
    ProviderDefinition,
    ProviderDomain,
    provider_registry,
    public_provider_coverage,
    requirement_for,
    resolve_jurisdiction,
    select_providers,
)
from app.research_runtime import SourceAuthority, execute_research, validate_evidence_contract
from app.specialist_runtime import ResearchRequest


def _selection(specialist: str, query: str, *, web=True, quote=False):
    decision = decide_freshness(specialist, query)
    return select_providers(requirement_for(specialist, query, decision), provider_registry(
        web_configured=web, market_quote_configured=quote))


def test_registry_is_typed_versioned_queryable_and_secret_free():
    payload = public_provider_coverage(web_configured=True)
    assert payload["coverage_version"] == "1.0" and payload["read_only"] is True
    assert all(item["schema_version"] == "1.0" for item in payload["providers"])
    serialized = str(payload).casefold()
    assert "api_key" not in serialized and "secret_value" not in serialized
    assert all("provider_id" not in item for item in payload["providers"])


def test_james_live_quote_declines_without_realtime_adapter():
    selection = _selection("james", "What is the live Bitcoin spot price right now?")
    assert not selection.compliant
    assert "real-time market quote" in selection.decline_reason


def test_james_official_macro_can_use_configured_official_web_resolution():
    selection = _selection("james", "What is the current Malta inflation rate?")
    assert selection.compliant
    assert selection.selected_source_classes == (SourceClass.official, SourceClass.primary)


def test_delayed_market_data_cannot_satisfy_realtime_requirement():
    delayed = ProviderDefinition(
        provider_id="delayed", public_name="Delayed", domains=(ProviderDomain.finance_market,),
        source_classes=(SourceClass.provider,), jurisdictions=(), markets=("US",),
        freshness_classes=(FreshnessClass.delayed,), authority_level=AuthorityLevel.commercial_provider,
        authentication="none", configured=True, strict_policy_eligible=True, status="available",
        status_probe="adapter", cost=CostMetadata(model="free"), public_summary="Delayed data.")
    requirement = requirement_for("james", "live stock quote", decide_freshness("james", "live stock quote"))
    assert not select_providers(requirement, (delayed,)).compliant


def test_oliver_resolves_supported_jurisdiction_and_unsupported_fails_closed():
    assert resolve_jurisdiction("current Malta employment law") == "MT"
    assert _selection("oliver", "current Malta employment law").compliant
    unsupported = _selection("oliver", "current employment law in Atlantis")
    assert not unsupported.compliant and "jurisdiction" in unsupported.decline_reason


def test_official_domains_fake_paths_and_authority_hierarchy():
    class Provider:
        def search(self, request):
            return [
                {"title": "Malta statute", "identifier": "https://legislation.gov.mt/legislation/act/1",
                 "source": "Legislation Malta", "publication_date": "2026-08-30",
                 "excerpt": "Malta employment statute current text", "source_type": "statute"},
                {"title": "Court judgment", "identifier": "https://judiciary.uk/judgment/employment",
                 "source": "Judiciary", "publication_date": "2026-08-30",
                 "excerpt": "Employment judgment", "source_type": "court"},
                {"title": "Fake", "identifier": "https://example.test/path/gov.mt/employment",
                 "source": "Blog", "publication_date": "2026-08-30",
                 "excerpt": "Employment commentary", "source_type": "web"},
            ]
    outcome = execute_research(ResearchRequest(query="Malta employment law", freshness_requirement="30 days",
        source_types=["official", "primary"], rationale="current law"), Provider())
    assert outcome.evidence[0].source_class == SourceClass.official
    assert outcome.evidence[0].source_authority == SourceAuthority.statute
    assert outcome.evidence[1].source_authority == SourceAuthority.court
    assert outcome.evidence[0].authority_rank > outcome.evidence[1].authority_rank
    assert outcome.evidence[2].source_class == SourceClass.secondary


def test_secondary_never_replaces_required_primary():
    class Provider:
        def search(self, request):
            return [{"title": "Malta law commentary", "identifier": "https://example.test/malta-law",
                     "source": "Blog", "publication_date": "2026-08-30",
                     "excerpt": "Malta law commentary", "source_type": "secondary"}]
    decision = decide_freshness("oliver", "What law currently applies in Malta?")
    outcome = execute_research(ResearchRequest(query="What law currently applies in Malta?",
        freshness_requirement="30 days", source_types=["official"], rationale="law"), Provider())
    validated = validate_evidence_contract("oliver", decision, outcome.evidence,
                                           now=datetime(2026, 8, 30, tzinfo=UTC))
    assert not validated.passed and validated.evidence == []


def test_generic_provider_class_never_replaces_oliver_official_source():
    class Provider:
        def search(self, request):
            return [{"title": "Malta legal database", "identifier": "https://vendor.test/malta-law",
                     "source": "Vendor", "publication_date": "2026-08-30",
                     "excerpt": "Malta law database", "source_type": "provider"}]

    decision = decide_freshness("oliver", "What law currently applies in Malta?")
    outcome = execute_research(ResearchRequest(query="What law currently applies in Malta?",
        freshness_requirement="30 days", source_types=["official"], rationale="law"), Provider())
    validated = validate_evidence_contract("oliver", decision, outcome.evidence,
                                           now=datetime(2026, 8, 30, tzinfo=UTC))
    assert not validated.passed


def test_backend_provider_coverage_endpoint_is_read_only_and_safe():
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).get("/providers/coverage")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200 and response.json()["read_only"] is True
    assert "real-time market quote provider is not configured" in str(response.json())
