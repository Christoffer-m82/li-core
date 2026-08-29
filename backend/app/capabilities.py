from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CapabilityStatus = Literal["available", "degraded", "unavailable", "configured"]


class Capability(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    category: str
    name: str
    purpose: str
    operations: tuple[str, ...]
    access: tuple[str, ...]
    approval: str
    persisted: bool
    retention: str
    web_exposure: Literal["available", "partial", "not_exposed"]
    web_path: str | None = None
    sensitivity: Literal["standard", "personal", "restricted"] = "standard"
    boundary: Literal["li", "theo", "owner", "runtime"] = "li"
    status_source: Literal["runtime", "configuration", "policy"] = "policy"
    status: CapabilityStatus = "available"
    status_detail: str
    covered_routes: tuple[str, ...] = Field(default=(), exclude=True)


class CapabilityInventory(BaseModel):
    schema_version: str
    system_version: str
    last_refreshed: datetime
    read_only: Literal[True] = True
    source_of_truth: str
    architecture_flow: tuple[str, ...]
    privacy_posture: tuple[str, ...]
    permissions: tuple[dict[str, str], ...]
    capabilities: tuple[Capability, ...]


def _status(available: bool, configured: bool = True) -> CapabilityStatus:
    if available:
        return "available"
    return "degraded" if configured else "unavailable"


def build_capability_inventory(
    *,
    system_version: str,
    database_available: bool,
    research_available: bool,
    calendar_available: bool,
    gmail_available: bool,
    artifact_storage_configured: bool,
) -> CapabilityInventory:
    database_status = _status(database_available)
    database_detail = "Live database readiness check passed." if database_available else "Database readiness check failed."
    capabilities = (
        Capability(id="ai-runtime", category="AI & orchestration", name="Li / Claude runtime", purpose="Answers through Li and routes work to governed tools and specialists.", operations=("chat", "reason", "orchestrate"), access=("read", "execute"), approval="Consequential actions are checked at their execution boundary.", persisted=True, retention="Conversation messages remain until owner deletion.", web_exposure="available", web_path="/", boundary="li", status_source="runtime", status="available", status_detail="The running backend is serving the inventory.", covered_routes=("POST /li/chat",)),
        Capability(id="memory", category="Memory & history", name="Personal memory", purpose="Recalls explicit memory and stages proposed memory changes for review.", operations=("recall", "store explicit", "propose", "review"), access=("read", "write", "owner-only"), approval="Theo reviews proposals; canonical changes require the governed confirmation boundary.", persisted=True, retention="Persistent; governed correction and forgetting rules apply.", web_exposure="partial", sensitivity="restricted", boundary="theo", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /memory/primary-user", "POST /memory/explicit", "GET /memory/recall", "POST /memory/proposals", "GET /theo/memory/proposals", "POST /theo/memory/proposals/{proposal_id}/review", "POST /theo/memory/proposals/process-next", "POST /owner/memory/proposals/{proposal_id}/confirm")),
        Capability(id="conversation-history", category="Memory & history", name="Conversation history", purpose="Stores and retrieves Li conversations without displaying sensitive contents in this overview.", operations=("list", "read", "owner delete"), access=("read", "owner-only"), approval="Permanent deletion requires separate owner confirmation.", persisted=True, retention="Retained until owner deletion; encrypted backups age out on the provider schedule.", web_exposure="available", web_path="/history", sensitivity="restricted", boundary="owner", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /conversations", "GET /conversations/{conversation_id}", "POST /owner/conversations/{conversation_id}/delete")),
        Capability(id="specialists", category="Agents & governance", name="Specialists and system agents", purpose="Routes suitable work to registered advisers and records real interactions.", operations=("discover", "consult", "record activity"), access=("read", "execute"), approval="Advice is automatic; consequential downstream actions retain their own approval checks.", persisted=True, retention="Interaction history remains until linked conversation deletion.", web_exposure="available", web_path="/agents", boundary="li", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /specialists/interactions",)),
        Capability(id="agent-analytics", category="Agents & governance", name="Agent analytics and registry governance", purpose="Measures real agent activity and manages permanent registry recommendations.", operations=("read analytics", "recommend", "review", "owner execute"), access=("read", "write", "owner-only"), approval="Li approval → approved_pending_execution → separate owner confirmation for permanent registry changes.", persisted=True, retention="Analytics and audited governance records are persisted.", web_exposure="available", web_path="/agents", boundary="owner", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /agents/analytics", "POST /agents/relevance-review", "POST /agents/settings", "POST /agents/recommendations/{recommendation_id}/review", "POST /owner/agents/recommendations/{recommendation_id}/execute")),
        Capability(id="research", category="Research & web", name="Live web research", purpose="Retrieves current public information through the configured research provider.", operations=("search", "read results"), access=("read",), approval="No approval for research; consequential use remains governed separately.", persisted=False, retention="Provider results are not a separate permanent knowledge store.", web_exposure="partial", boundary="li", status_source="configuration", status=_status(research_available, research_available), status_detail="Research provider is configured." if research_available else "No research provider is configured.", covered_routes=()),
        Capability(id="calendar", category="Productivity", name="Google Calendar", purpose="Reads calendar events and creates events only after explicit approval.", operations=("search events", "create approved event"), access=("read", "write with approval"), approval="Reads do not require approval; every write requires explicit approval.", persisted=False, retention="Calendar data remains with Google; Li stores only normal conversation/audit context.", web_exposure="partial", boundary="li", status_source="configuration", status=_status(calendar_available, calendar_available), status_detail="Calendar provider is configured." if calendar_available else "Calendar provider is not configured.", covered_routes=("POST /li/actions/calendar",)),
        Capability(id="gmail", category="Productivity", name="Gmail", purpose="Reads, searches, and opens threads; creates drafts only after approval.", operations=("read", "search", "thread", "create approved draft"), access=("read", "draft with approval", "sending unavailable"), approval="Draft creation requires explicit approval. Sending is unavailable by design.", persisted=False, retention="Email remains with Gmail; no refresh tokens or message contents are exposed here.", web_exposure="not_exposed", sensitivity="restricted", boundary="li", status_source="configuration", status=_status(gmail_available, gmail_available), status_detail="Gmail read/draft provider is configured; sending remains disabled." if gmail_available else "Gmail provider is not configured; sending remains disabled.", covered_routes=("POST /li/actions/email",)),
        Capability(id="tasks", category="Productivity", name="Tasks and reminders", purpose="Reads commitments and applies approved task/reminder changes.", operations=("list", "create", "update", "complete", "delete"), access=("read", "write with approval"), approval="All mutations are approval-gated at execution.", persisted=True, retention="Stored in the private database until completed or deleted under task rules.", web_exposure="partial", boundary="li", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("POST /li/actions/tasks",)),
        Capability(id="artifacts", category="Files & artifacts", name="Private artifacts and uploads", purpose="Temporarily analyses uploads and privately stores explicitly saved or Li-generated files.", operations=("temporary analyse", "save", "list", "download", "keep", "delete"), access=("read", "write"), approval="Uploads persist only when explicitly saved; retention changes are user-directed.", persisted=True, retention="Uploads are temporary unless saved; generated files expire on the configured policy unless kept; expiry cleanup runs as an isolated worker.", web_exposure="available", sensitivity="restricted", boundary="li", status_source="configuration", status=_status(artifact_storage_configured, artifact_storage_configured), status_detail="Private object storage is configured." if artifact_storage_configured else "Private object storage is not configured.", covered_routes=("POST /artifacts/uploads", "POST /artifacts/generated", "GET /artifacts", "GET /artifacts/{artifact_id}", "POST /artifacts/{artifact_id}/retention", "GET /privacy/settings", "POST /privacy/settings")),
        Capability(id="authentication", category="Security & platform", name="Authentication and API security", purpose="Restricts Li Web to the approved account and separates Li, Theo, and Owner authorities.", operations=("authenticate", "authorize", "rate limit"), access=("owner-only",), approval="Owner-only endpoints require the separate owner authority.", persisted=False, retention="Signed sessions expire; credential values are never returned.", web_exposure="partial", sensitivity="restricted", boundary="runtime", status_source="policy", status="configured", status_detail="Authenticated BFF and separated backend authorities are active.", covered_routes=()),
        Capability(id="database", category="Security & platform", name="Database and private storage", purpose="Persists memory, conversations, tasks, governance records, and metadata.", operations=("read", "write", "health check"), access=("service-scoped", "owner-only"), approval="Database roles enforce Li, Theo, and Owner boundaries.", persisted=True, retention="Varies by record type; summaries are shown on the relevant capability.", web_exposure="not_exposed", sensitivity="restricted", boundary="runtime", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /health/database",)),
        Capability(id="deployment", category="Security & platform", name="Private deployment runtime", purpose="Runs the BFF and backend with private service-to-service authentication.", operations=("serve", "read readiness"), access=("service-only",), approval="Infrastructure changes occur outside this read-only page.", persisted=False, retention="Runtime logs follow the platform logging policy.", web_exposure="partial", boundary="runtime", status_source="runtime", status="available", status_detail="Backend runtime is online.", covered_routes=("GET /", "GET /health", "GET /ready", "GET /capabilities")),
    )
    return CapabilityInventory(
        schema_version="1.0",
        system_version=system_version,
        last_refreshed=datetime.now(UTC),
        source_of_truth="Generated from the backend capability manifest and live readiness/configuration state.",
        architecture_flow=("Li Web", "authenticated BFF", "IAM-private backend", "providers and private data stores"),
        privacy_posture=("Backend Cloud Run is IAM-private; no public allUsers access.", "Secrets remain server-side and are supplied through Secret Manager/runtime configuration.", "Secret values, credentials, raw secret identifiers, and personal-memory contents are never included."),
        permissions=(
            {"actor": "Li", "summary": "Reads and reasons; approved reversible actions execute only at governed boundaries."},
            {"actor": "Theo", "summary": "Curates memory proposals; cannot bypass canonical-memory confirmation rules."},
            {"actor": "Owner", "summary": "Separately confirms permanent registry changes and destructive private-data actions."},
        ),
        capabilities=capabilities,
    )


def documented_routes(inventory: CapabilityInventory) -> set[str]:
    return {route for capability in inventory.capabilities for route in capability.covered_routes}
