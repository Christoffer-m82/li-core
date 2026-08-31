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
        Capability(id="ai-runtime", category="AI & orchestration", name="Li-directed specialist orchestration", purpose="Keeps Li as the single front door and final synthesizer while routing bounded work across the permanent typed specialist registry.", operations=("chat", "reason", "route", "consult concurrently", "validate", "synthesize"), access=("read", "execute"), approval="Specialists are stateless advisers; Li alone owns tools and consequential actions remain checked at execution.", persisted=True, retention="Conversation messages and genuine linked interaction events remain until owner deletion.", web_exposure="available", web_path="/", boundary="li", status_source="runtime", status="available", status_detail="Registry-driven Li-only, solo, and bounded multi-specialist routes are available.", covered_routes=("POST /li/chat",)),
        Capability(id="voice-interaction", category="AI & orchestration", name="Voice interaction foundation", purpose="Adds push-to-talk transcription and optional spoken final responses to Li Web while preserving the normal chat, memory, orchestration, identity, and approval boundaries.", operations=("browser-native transcription", "browser-native synthesis", "stop playback", "fall back to text"), access=("read", "execute"), approval="Voice transcripts use POST /li/chat. Voice cannot call an approval endpoint; action cards still require an explicit tactile UI decision.", persisted=False, retention="Raw audio retention: none. Li stores only the resulting transcript and normal final response as conversation history.", web_exposure="available", web_path="/", sensitivity="personal", boundary="li", status_source="configuration", status="configured", status_detail="STT mode: browser-native when supported; TTS mode: browser-native when supported; server provider: not configured; raw-audio retention: none. Browser support is detected locally.", covered_routes=()),
        Capability(id="memory", category="Memory & history", name="Personal memory", purpose="Recalls explicit memory and stages proposed memory changes for review.", operations=("recall", "store explicit", "propose", "review"), access=("read", "write", "owner-only"), approval="Theo reviews proposals; canonical changes require the governed confirmation boundary.", persisted=True, retention="Persistent; governed correction and forgetting rules apply.", web_exposure="partial", sensitivity="restricted", boundary="theo", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /memory/primary-user", "POST /memory/explicit", "GET /memory/recall", "POST /memory/proposals", "GET /theo/memory/proposals", "POST /theo/memory/proposals/{proposal_id}/review", "POST /theo/memory/proposals/process-next", "POST /owner/memory/proposals/{proposal_id}/confirm")),
        Capability(id="place-settings", category="Memory & history", name="Private current place", purpose="Stores an explicitly selected or permission-gated coarse current country and optional town, plus minimal overnight visit events for user-controlled Most visited ordering.", operations=("read current place", "set current place", "pin or suppress country", "confirm or correct overnight visit", "register or revoke opaque mobile provider"), access=("read", "write"), approval="Web updates are explicit user actions; future device updates require granted OS location permission, a private authenticated gateway, and an active opaque installation.", persisted=True, retention="Stores country, optional town, provider permission and opaque replay/revocation state, and minimal trip boundaries only; no coordinates, hardware identifiers, or continuous trail.", web_exposure="available", web_path="/settings", sensitivity="restricted", boundary="li", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /settings/place", "POST /settings/place", "POST /settings/place/most-visited", "POST /settings/place/visits", "POST /settings/place/mobile/installations", "POST /settings/place/mobile/updates", "POST /settings/place/mobile/visits/correction", "POST /settings/place/mobile/revoke")),
        Capability(id="conversation-history", category="Memory & history", name="Conversation history", purpose="Stores and retrieves Li conversations without displaying sensitive contents in this overview.", operations=("list", "read", "owner delete"), access=("read", "owner-only"), approval="Permanent deletion requires separate owner confirmation.", persisted=True, retention="Retained until owner deletion; encrypted backups age out on the provider schedule.", web_exposure="available", web_path="/history", sensitivity="restricted", boundary="owner", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /conversations", "GET /conversations/{conversation_id}", "POST /owner/conversations/{conversation_id}/delete")),
        Capability(id="specialists", category="Agents & governance", name="Specialists and system agents", purpose="Routes suitable work to registered advisers and records real interactions.", operations=("discover", "consult", "record activity"), access=("read", "execute"), approval="Advice is automatic; consequential downstream actions retain their own approval checks.", persisted=True, retention="Interaction history remains until linked conversation deletion.", web_exposure="available", web_path="/agents", boundary="li", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /specialists/interactions",)),
        Capability(id="agent-analytics", category="Agents & governance", name="Agent analytics and registry governance", purpose="Measures real agent activity, explicit final-answer contribution, and correlated successful Li-owned action conversion; manages permanent registry recommendations.", operations=("read analytics", "measure synthesis contribution", "measure correlated action conversion", "recommend", "review", "owner execute"), access=("read", "write", "owner-only"), approval="Li approval → approved_pending_execution → separate owner confirmation for permanent registry changes. Measurement never bypasses an action executor's approval boundary.", persisted=True, retention="Analytics, correlation metadata, and audited governance records are persisted; unknown evidence remains null.", web_exposure="available", web_path="/agents", boundary="owner", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("GET /agents/analytics", "POST /agents/relevance-review", "POST /agents/settings", "POST /agents/recommendations/{recommendation_id}/review", "POST /owner/agents/recommendations/{recommendation_id}/execute")),
        Capability(id="action-intents", category="Agents & governance", name="Durable action approvals", purpose="Carries Li request and measured specialist correlation from a chat proposal through explicit approval and idempotent execution.", operations=("propose", "approve", "deny", "execute", "expire", "audit"), access=("write with approval", "owner-only"), approval="Only Li creates intents. Clients approve or deny by intent ID; governance retains separate owner confirmation.", persisted=True, retention="Pending intents expire after 24 hours; lifecycle events are append-only and payloads are minimized.", web_exposure="available", web_path="/", sensitivity="restricted", boundary="li", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("POST /li/chat", "POST /li/action-intents/{intent_id}/decision")),
        Capability(id="action-policy", category="Agents & governance", name="Governed action policy", purpose="Makes effective autonomy and approval thresholds explicit, versioned, auditable, and separate from identity preferences.", operations=("read effective policy", "warn on identity mismatch", "propose", "owner approve or reject", "owner rollback"), access=("read", "write with approval", "owner-only"), approval="Raising autonomy requires a durable proposal and separate owner decision. Policy never overrides harder executor boundaries or registry governance.", persisted=True, retention="Every effective version, proposal, and transition is retained as governance history.", web_exposure="available", web_path="/backend", sensitivity="restricted", boundary="owner", status_source="runtime", status=database_status, status_detail="Conservative baseline remains effective; identity preferences grant no authority.", covered_routes=("GET /action-policy", "POST /li/action-policy/proposals", "POST /owner/action-policy/proposals/{proposal_id}/decision", "POST /owner/action-policy/rollback")),
        Capability(id="research", category="Research & web", name="Live web research", purpose="Retrieves current public information through configured providers and enforces versioned specialist freshness, provider coverage, and source-authority rules.", operations=("search", "select compliant provider", "validate evidence", "read policy and coverage"), access=("read",), approval="No approval for research; consequential use remains governed separately.", persisted=False, retention="Provider results are not a separate permanent knowledge store; compact verification and provider-selection metadata may remain in specialist history.", web_exposure="partial", web_path="/backend", boundary="li", status_source="configuration", status=_status(research_available, research_available), status_detail="Official web resolution is configured; real-time market quotes remain unavailable until a compliant adapter is configured." if research_available else "No research provider is configured; strict current requests decline safely.", covered_routes=("GET /specialists/freshness-evidence", "GET /providers/coverage")),
        Capability(id="calendar", category="Productivity", name="Google Calendar", purpose="Reads calendar events and creates events only after explicit approval.", operations=("search events", "create approved event"), access=("read", "write with approval"), approval="Reads do not require approval; every write requires explicit approval.", persisted=False, retention="Calendar data remains with Google; Li stores only normal conversation/audit context.", web_exposure="partial", boundary="li", status_source="configuration", status=_status(calendar_available, calendar_available), status_detail="Calendar provider is configured." if calendar_available else "Calendar provider is not configured.", covered_routes=("POST /li/actions/calendar",)),
        Capability(id="gmail", category="Productivity", name="Gmail", purpose="Reads, searches, and opens threads; creates drafts only after approval.", operations=("read", "search", "thread", "create approved draft"), access=("read", "draft with approval", "sending unavailable"), approval="Draft creation requires explicit approval. Sending is unavailable by design.", persisted=False, retention="Email remains with Gmail; no refresh tokens or message contents are exposed here.", web_exposure="not_exposed", sensitivity="restricted", boundary="li", status_source="configuration", status=_status(gmail_available, gmail_available), status_detail="Gmail read/draft provider is configured; sending remains disabled." if gmail_available else "Gmail provider is not configured; sending remains disabled.", covered_routes=("POST /li/actions/email",)),
        Capability(id="tasks", category="Productivity", name="Tasks and reminders", purpose="Reads commitments and applies approved task/reminder changes.", operations=("list", "create", "update", "complete", "delete"), access=("read", "write with approval"), approval="All mutations are approval-gated at execution.", persisted=True, retention="Stored in the private database until completed or deleted under task rules.", web_exposure="partial", boundary="li", status_source="runtime", status=database_status, status_detail=database_detail, covered_routes=("POST /li/actions/tasks",)),
        Capability(id="rhythms-open-loops", category="Productivity", name="Governed rhythms, briefs, and open loops", purpose="Runs explicitly activated recurring reviews through an idempotent private scheduler and turns grounded commitments into quiet follow-up.", operations=("read rhythm state", "approve activation", "claim idempotent run", "read private briefs", "snooze", "stand down", "postpone", "close"), access=("read", "write with approval", "service-only"), approval="Every rhythm starts preview-only and needs explicit activation. Provider mutations remain behind ActionIntents.", persisted=True, retention="Briefs, minimal loop summaries, lifecycle and duplicate-prevention metadata persist under private task policy; raw provider payloads and conversation text are not copied.", web_exposure="available", web_path="/inbox", sensitivity="personal", boundary="li", status_source="runtime", status=database_status, status_detail="Scheduler state reports enabled, preview-only, disabled, and stood-down rhythms without claiming activation.", covered_routes=("GET /rhythms", "POST /li/rhythms/{rhythm_key}/configuration", "POST /internal/rhythms/{rhythm_key}/run", "GET /proactive-briefs", "POST /li/proactive-briefs/{brief_id}/read", "POST /li/proactivity/categories/{category}/suppression", "GET /open-loops", "POST /li/open-loops", "POST /li/open-loops/{open_loop_id}/{transition}", "POST /li/open-loops/{open_loop_id}/suppression")),
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
        privacy_posture=("Backend Cloud Run is IAM-private; no public allUsers access.", "Secrets remain server-side and are supplied through Secret Manager/runtime configuration.", "Voice audio is ephemeral and is not uploaded, logged, retained, or added to conversation history by Li.", "Secret values, credentials, raw secret identifiers, and personal-memory contents are never included."),
        permissions=(
            {"actor": "Li", "summary": "Reads and reasons; approved reversible actions execute only at governed boundaries."},
            {"actor": "Theo", "summary": "Curates memory proposals; cannot bypass canonical-memory confirmation rules."},
            {"actor": "Owner", "summary": "Separately confirms permanent registry changes and destructive private-data actions."},
        ),
        capabilities=capabilities,
    )


def documented_routes(inventory: CapabilityInventory) -> set[str]:
    return {route for capability in inventory.capabilities for route in capability.covered_routes}
