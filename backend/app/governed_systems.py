"""Governed Li-native contracts for skills, context, recall, automation and workers.

The module is deliberately provider-neutral.  It defines policy-enforcing domain
objects; persistence and provider adapters sit behind the existing private API.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Callable, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrustState = Literal["draft", "untrusted", "trial", "trusted", "retired"]
Sensitivity = Literal["standard", "personal", "restricted"]


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    skill_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    name: str = Field(min_length=1, max_length=100)
    domain: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    owner_scope: Literal["li", "owner", "community"] = "li"
    trust_state: TrustState = "draft"
    version: int = Field(default=1, ge=1)
    created_from: str = Field(min_length=1, max_length=300)
    dependencies: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    required_providers: tuple[str, ...] = ()
    specialist_compatibility: tuple[str, ...] = ()
    sensitivity: Sensitivity = "standard"
    validation_tests: tuple[str, ...] = ()
    review_status: Literal["pending", "approved", "rejected"] = "pending"

    @model_validator(mode="after")
    def trusted_requires_review(self) -> "SkillManifest":
        if self.trust_state == "trusted" and (
            self.review_status != "approved" or not self.validation_tests
        ):
            raise ValueError("trusted skills require approved review and validation tests")
        if self.owner_scope == "community" and self.trust_state not in {"untrusted", "retired"}:
            raise ValueError("community imports must enter as untrusted")
        return self


class SkillOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    skill_id: str
    version: int = Field(ge=1)
    used_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_succeeded: bool | None = None
    user_corrected: bool | None = None
    action_followed: bool | None = None
    evidence: str | None = Field(default=None, max_length=500)


SKILL_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"untrusted", "trial", "retired"},
    "untrusted": {"trial", "retired"},
    "trial": {"trusted", "retired"},
    "trusted": {"retired"},
    "retired": set(),
}


def transition_skill(skill: SkillManifest, target: TrustState) -> SkillManifest:
    if target not in SKILL_TRANSITIONS[skill.trust_state]:
        raise ValueError(f"invalid skill transition {skill.trust_state} -> {target}")
    return skill.model_copy(update={"trust_state": target})


def import_skill(manifest: dict[str, Any]) -> SkillManifest:
    clean = {key: value for key, value in manifest.items() if key in SkillManifest.model_fields}
    clean.update(owner_scope="community", trust_state="untrusted", review_status="pending")
    return SkillManifest.model_validate(clean)


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    context_class: Literal[
        "core", "policy", "skill", "specialist", "freshness", "provider",
        "place", "memory", "historical", "task", "conversation",
    ]
    content: str
    tokens: int = Field(ge=0)
    mandatory: bool = False
    private_to_li: bool = False
    relevance: float = Field(default=0.0, ge=0, le=1)
    selection_reason: str = Field(min_length=1, max_length=240)


class ContextAssembly(BaseModel):
    selected: tuple[ContextItem, ...]
    omitted_classes: tuple[str, ...]
    estimated_tokens: int
    budget: int


DEFAULT_CONTEXT_BUDGETS = {
    "core": 12_000, "policy": 4_000, "skill": 4_000, "specialist": 2_500,
    "freshness": 1_000, "provider": 1_000, "place": 300, "memory": 3_000,
    "historical": 2_500, "task": 1_500, "conversation": 8_000,
}


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def assemble_context(
    items: list[ContextItem], *, total_budget: int = 30_000,
    caller: Literal["li", "specialist", "temporary", "heavy"] = "li",
) -> ContextAssembly:
    selected: list[ContextItem] = []
    class_use: dict[str, int] = {}
    candidates = sorted(items, key=lambda item: (not item.mandatory, -item.relevance))
    for item in candidates:
        if caller != "li" and item.private_to_li:
            continue
        class_budget = DEFAULT_CONTEXT_BUDGETS[item.context_class]
        used = class_use.get(item.context_class, 0)
        total = sum(value.tokens for value in selected)
        if item.mandatory or (used + item.tokens <= class_budget and total + item.tokens <= total_budget):
            selected.append(item)
            class_use[item.context_class] = used + item.tokens
    omitted = tuple(sorted({item.context_class for item in items} - {i.context_class for i in selected}))
    return ContextAssembly(
        selected=tuple(selected), omitted_classes=omitted,
        estimated_tokens=sum(item.tokens for item in selected), budget=total_budget,
    )


class HistoricalSnippet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    conversation_id: UUID
    message_id: UUID
    role: Literal["user", "assistant", "system"]
    snippet: str = Field(max_length=1200)
    created_at: datetime
    rank: float = Field(ge=0)
    retrieval: Literal["full_text", "semantic"] = "full_text"
    canonical_memory_candidate: Literal[False] = False


def bounded_snippet(text: str, query: str, limit: int = 480) -> str:
    match = re.search(re.escape(query), text, re.IGNORECASE)
    center = match.start() if match else 0
    start = max(0, center - limit // 3)
    return text[start:start + limit]


class WatcherDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    watcher_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    condition: Literal[
        "overdue", "approaching_deadline", "known_date", "payment_due",
        "scheduler_state", "provider_readiness",
    ]
    enabled: bool = False
    wake_li: bool = True
    threshold_seconds: int = Field(default=0, ge=0)


class WatcherEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: UUID = Field(default_factory=uuid4)
    watcher_key: str
    occurrence_key: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    wake_li: bool
    llm_calls_avoided: Literal[1] = 1


def evaluate_watcher(
    watcher: WatcherDefinition, facts: list[dict[str, Any]], seen: set[str],
    predicate: Callable[[dict[str, Any]], bool],
) -> list[WatcherEvent]:
    if not watcher.enabled:
        return []
    events = []
    for fact in facts:
        occurrence = f"{watcher.watcher_key}:{fact.get('id')}:{fact.get('due_at', fact.get('state'))}"
        if occurrence not in seen and predicate(fact):
            events.append(WatcherEvent(
                watcher_key=watcher.watcher_key, occurrence_key=occurrence,
                payload=fact, wake_li=watcher.wake_li,
            ))
    return events


class TemporaryWorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    worker_id: UUID = Field(default_factory=uuid4)
    role: str = Field(min_length=1, max_length=120)
    task: str = Field(min_length=1, max_length=6000)
    output_schema: dict[str, Any]
    context: tuple[ContextItem, ...] = ()
    max_seconds: int = Field(default=90, ge=1, le=300)
    max_cost_usd: float = Field(default=0.25, ge=0, le=5)
    allowed_tools: tuple[str, ...] = ()
    canonical_memory_write: Literal[False] = False
    direct_database_access: Literal[False] = False
    autonomous_actions: Literal[False] = False
    permanent_registry_mutation: Literal[False] = False


def validate_temporary_worker(request: TemporaryWorkerRequest, *, parallel_count: int) -> None:
    if parallel_count > 3:
        raise ValueError("temporary worker parallelism exceeds governed limit")
    if any(item.private_to_li for item in request.context):
        raise ValueError("temporary workers cannot receive private_to_li context")


class CompressedConversation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: int = Field(default=1, ge=1)
    summary: str
    recent_turns: tuple[dict[str, Any], ...]
    unresolved_commitments: tuple[str, ...] = ()
    action_records: tuple[dict[str, Any], ...] = ()
    source_message_ids: tuple[UUID, ...] = ()
    quality_checks: dict[str, bool]

    @model_validator(mode="after")
    def quality_passes(self) -> "CompressedConversation":
        if not all(self.quality_checks.get(key, False) for key in (
            "recent_preserved", "actions_preserved", "unresolved_preserved",
        )):
            raise ValueError("conversation compression quality checks failed")
        return self


def compress_conversation(
    turns: list[dict[str, Any]], summary: str, *, keep_recent: int = 12,
) -> CompressedConversation:
    recent = tuple(turns[-keep_recent:])
    older = turns[:-keep_recent]
    actions = tuple(t for t in older if t.get("action_intent") or t.get("tool_result"))
    unresolved = tuple(str(t["commitment"]) for t in turns if t.get("commitment") and not t.get("resolved"))
    ids = tuple(UUID(str(t["message_id"])) for t in older if t.get("message_id"))
    return CompressedConversation(
        summary=summary, recent_turns=recent, unresolved_commitments=unresolved,
        action_records=actions, source_message_ids=ids,
        quality_checks={"recent_preserved": len(recent) == min(len(turns), keep_recent),
                        "actions_preserved": True, "unresolved_preserved": True},
    )


class ModelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    provider: str
    model: str
    capabilities: frozenset[str]
    cost_tier: Literal["low", "standard", "high"]
    latency_tier: Literal["fast", "standard", "slow"]
    context_limit: int = Field(gt=0)
    health: Literal["healthy", "degraded", "unavailable", "not_configured"]
    privacy: Literal["private_allowed", "public_only"] = "private_allowed"
    primary: bool = False


def route_model(
    registry: tuple[ModelDefinition, ...], capability: str, *, high_stakes: bool,
    private_data: bool = True, allow_specialized: bool = False,
) -> ModelDefinition:
    primary = next((model for model in registry if model.primary), None)
    if primary is None:
        raise ValueError("model registry has no primary")
    if high_stakes or not allow_specialized:
        if primary.health != "healthy":
            raise ValueError("primary model unavailable; high-stakes downgrade prohibited")
        return primary
    candidates = [model for model in registry if model.health == "healthy"
                  and capability in model.capabilities
                  and (not private_data or model.privacy == "private_allowed")]
    return sorted(candidates, key=lambda model: (model.cost_tier != "low", not model.primary))[0] if candidates else primary


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str
    mode: Literal["read", "write"]
    action_class: Literal[0, 1, 2, 3]
    approval_required: bool
    sensitivity: Sensitivity
    provider: str
    availability: Literal["available", "degraded", "not_configured"]
    cost: str = "none"
    rate_limit: str
    allowed_callers: frozenset[str] = frozenset({"li"})
    evidence_required: bool = False

    @model_validator(mode="after")
    def authority_is_safe(self) -> "ToolDefinition":
        if self.mode == "write" and "li" not in self.allowed_callers:
            raise ValueError("write tools must remain Li-owned")
        if self.action_class >= 3 and not self.approval_required:
            raise ValueError("consequential tools require approval")
        return self


class DeliveryAdapter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: Literal["web", "native", "push", "email", "sms"]
    status: Literal["available", "ready", "not_configured"]
    can_carry_approvals: bool
    grants_authority: Literal[False] = False


class HeavyWorkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: UUID = Field(default_factory=uuid4)
    task: str = Field(min_length=1, max_length=6000)
    enabled: bool = False
    allowed_tools: tuple[str, ...] = ()
    network_allowlist: tuple[str, ...] = ()
    max_seconds: int = Field(default=300, ge=1, le=1800)
    max_cost_usd: float = Field(default=1, ge=0, le=10)
    temporary_credential_refs: tuple[str, ...] = ()
    owner_database_credentials: Literal[False] = False
    canonical_memory_access: Literal[False] = False
    unrestricted_secrets: Literal[False] = False
    autonomous_actions: Literal[False] = False


def authorize_heavy_work(request: HeavyWorkRequest, feature_flag: bool) -> None:
    if not feature_flag or not request.enabled:
        raise PermissionError("experimental heavy-work runtime is disabled")
    forbidden = {"gmail.send", "calendar.write", "owner.db", "canonical.memory"}
    if forbidden.intersection(request.allowed_tools):
        raise PermissionError("heavy worker requested a governed or private capability")


def governed_platform_overview() -> dict[str, Any]:
    return {
        "read_only": True,
        "systems": (
            {"id": 1, "name": "Governed Skills Platform", "status": "migration_ready"},
            {"id": 2, "name": "Progressive Context Loader", "status": "available"},
            {"id": 3, "name": "Historical Recall", "status": "migration_ready"},
            {"id": 4, "name": "Deterministic Watchers", "status": "migration_ready_disabled"},
            {"id": 5, "name": "Temporary Specialists", "status": "available_bounded"},
            {"id": 6, "name": "Long-context Compression", "status": "available"},
            {"id": 7, "name": "Model Capability Router", "status": "claude_primary"},
            {"id": 8, "name": "Tool & Delivery Platform", "status": "available"},
            {"id": 9, "name": "Isolated Heavy-work Runtime", "status": "experimental_disabled"},
        ),
        "invariants": ("canonical memory remains authoritative", "Gmail send unavailable",
                       "paused rhythms remain paused", "specialists inherit no tools",
                       "heavy work disabled by default"),
    }
