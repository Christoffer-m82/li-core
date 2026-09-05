from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.governed_systems import (
    ConversationContextMessage,
    ContextItem,
    DeliveryAdapter,
    HeavyWorkRequest,
    ModelDefinition,
    SkillManifest,
    TemporaryWorkerRequest,
    ToolDefinition,
    WatcherDefinition,
    assemble_context,
    authorize_heavy_work,
    conversation_context_message,
    compress_conversation,
    evaluate_watcher,
    governed_platform_overview,
    import_skill,
    route_model,
    specialist_conversation_context,
    transition_skill,
    validate_temporary_worker,
)


def skill(state="draft", **values):
    return SkillManifest(
        skill_id="sweden-trip", name="Sweden trip", domain="travel",
        description="Prepare a governed Sweden trip.", created_from="owner-request",
        trust_state=state, **values,
    )


def test_skill_lifecycle_versioning_and_trusted_validation():
    assert transition_skill(skill(), "trial").trust_state == "trial"
    with pytest.raises(ValueError):
        transition_skill(skill(), "trusted")
    with pytest.raises(ValidationError):
        skill("trusted")
    approved = skill("trusted", review_status="approved", validation_tests=("safe-output",))
    assert approved.version == 1


def test_imported_skill_is_always_untrusted_and_sanitized():
    imported = import_skill({**skill().model_dump(), "trust_state": "trusted",
                             "review_status": "approved", "unknown": "drop"})
    assert imported.owner_scope == "community"
    assert imported.trust_state == "untrusted"
    assert imported.review_status == "pending"


def test_context_loader_enforces_relevance_budget_and_private_to_li():
    items = [
        ContextItem(context_class="core", content="constitution", tokens=100,
                    mandatory=True, relevance=1, selection_reason="hard governance"),
        ContextItem(context_class="memory", content="private", tokens=100,
                    private_to_li=True, relevance=1, selection_reason="canonical match"),
        ContextItem(context_class="historical", content="old", tokens=500,
                    relevance=.2, selection_reason="weak historical match"),
    ]
    assembly = assemble_context(items, total_budget=250, caller="specialist")
    assert [item.content for item in assembly.selected] == ["constitution"]
    assert assembly.estimated_tokens == 100
    assert "historical" in assembly.omitted_classes


def test_specialist_context_requires_exact_disclosure_and_keeps_whole_messages():
    messages = [
        ConversationContextMessage(
            role="user", content="Li only", private_to_li=True,
            allowed_specialists=("nora",),
        ),
        ConversationContextMessage(role="assistant", content="No disclosure"),
        ConversationContextMessage(
            role="user", content="Shared with Nora", allowed_specialists=("nora",),
        ),
        ConversationContextMessage(
            role="assistant", content="Shared with James", allowed_specialists=("james",),
        ),
    ]
    assert specialist_conversation_context(messages, "nora") == "user: Shared with Nora"
    assert specialist_conversation_context(messages, "james") == "assistant: Shared with James"
    assert specialist_conversation_context(messages, "nora", character_budget=10) is None


def test_long_context_keeps_latest_shared_correction_as_whole_messages():
    messages = [ConversationContextMessage(
        role="user", content="old " + ("x" * 3000), allowed_specialists=("nora",),
    ) for _ in range(3)]
    messages.extend([
        ConversationContextMessage(
            role="user", content="Decision is option A", allowed_specialists=("nora",),
        ),
        ConversationContextMessage(
            role="user", content="Correction: decision is option B", allowed_specialists=("nora",),
        ),
    ])
    selected = specialist_conversation_context(messages, "nora", character_budget=120)
    assert "Decision is option A" in selected
    assert "Correction: decision is option B" in selected
    assert "old " not in selected


def test_malformed_history_privacy_metadata_fails_closed():
    message = conversation_context_message({
        "role": "user", "content": "Sensitive", "privacy_metadata": {
            "private_to_li": "no", "allowed_specialists": ["nora"],
        },
    })
    assert message.private_to_li
    assert message.allowed_specialists == ()


def test_watcher_is_no_llm_idempotent_and_disabled_by_default():
    watcher = WatcherDefinition(watcher_key="overdue-tasks", condition="overdue")
    assert evaluate_watcher(watcher, [{"id": "1"}], set(), lambda _: True) == []
    active = watcher.model_copy(update={"enabled": True})
    facts = [{"id": "1", "due_at": "2026-09-01"}]
    first = evaluate_watcher(active, facts, set(), lambda _: True)
    second = evaluate_watcher(active, facts, {first[0].occurrence_key}, lambda _: True)
    assert len(first) == 1 and first[0].llm_calls_avoided == 1
    assert second == []


def test_temporary_worker_has_hard_isolation_and_limits():
    request = TemporaryWorkerRequest(role="translator", task="Translate", output_schema={})
    validate_temporary_worker(request, parallel_count=2)
    assert request.canonical_memory_write is False
    assert request.direct_database_access is False
    assert request.autonomous_actions is False
    with pytest.raises(ValueError):
        validate_temporary_worker(request, parallel_count=3)


def test_compression_preserves_recent_unresolved_and_action_records():
    turns = [{"message_id": str(uuid4()), "content": str(i)} for i in range(14)]
    turns[0]["action_intent"] = {"status": "pending"}
    turns[1].update(commitment="call mum", resolved=False)
    compressed = compress_conversation(turns, "Structured summary", keep_recent=12)
    assert len(compressed.recent_turns) == 12
    assert len(compressed.action_records) == 1
    assert compressed.unresolved_commitments == ("call mum",)
    assert all(compressed.quality_checks.values())


def test_model_router_keeps_primary_for_high_stakes_and_respects_health():
    registry = (
        ModelDefinition(key="claude", provider="anthropic", model="claude-primary",
                        capabilities=frozenset({"reasoning", "classification"}),
                        cost_tier="standard", latency_tier="standard", context_limit=200000,
                        health="healthy", primary=True),
        ModelDefinition(key="cheap", provider="optional", model="classifier",
                        capabilities=frozenset({"classification"}), cost_tier="low",
                        latency_tier="fast", context_limit=32000, health="healthy"),
    )
    assert route_model(registry, "classification", high_stakes=True).key == "claude"
    assert route_model(registry, "classification", high_stakes=False,
                       allow_specialized=True).key == "cheap"
    unhealthy = (registry[0].model_copy(update={"health": "unavailable"}), registry[1])
    with pytest.raises(ValueError):
        route_model(unhealthy, "classification", high_stakes=True)


def test_tools_and_delivery_never_bypass_li_or_approval():
    with pytest.raises(ValidationError):
        ToolDefinition(key="payment", mode="write", action_class=3,
                       approval_required=False, sensitivity="restricted", provider="bank",
                       availability="not_configured", rate_limit="1/minute")
    with pytest.raises(ValidationError):
        ToolDefinition(key="worker-write", mode="write", action_class=2,
                       approval_required=True, sensitivity="personal", provider="local",
                       availability="available", rate_limit="10/minute",
                       allowed_callers=frozenset({"temporary"}))
    adapter = DeliveryAdapter(key="sms", status="not_configured", can_carry_approvals=True)
    assert adapter.grants_authority is False


def test_heavy_worker_is_disabled_and_cannot_receive_governed_tools():
    request = HeavyWorkRequest(task="Compile a public report")
    with pytest.raises(PermissionError, match="disabled"):
        authorize_heavy_work(request, feature_flag=False)
    enabled = request.model_copy(update={"enabled": True, "allowed_tools": ("gmail.send",)})
    with pytest.raises(PermissionError, match="governed"):
        authorize_heavy_work(enabled, feature_flag=True)
    assert request.owner_database_credentials is False
    assert request.canonical_memory_access is False


def test_gmail_send_and_rhythm_activation_are_absent_from_platform_contracts():
    source = __import__("app.governed_systems", fromlist=["x"])
    assert not hasattr(source, "send_gmail")
    assert WatcherDefinition(watcher_key="known-dates", condition="known_date").enabled is False


def test_deployed_platform_statuses_do_not_claim_migration_is_pending():
    overview = governed_platform_overview([{
        "model_key": "claude-primary", "provider": "anthropic",
        "model_name": "claude-sonnet-5", "configuration_state": "configured",
        "health": "healthy", "capabilities": ["reasoning", "structured_output", "coding"],
        "context_limit": 200000, "cost_metadata": {}, "is_primary": True,
        "configuration_version": 1,
    }])
    statuses = {system["id"]: system["status"] for system in overview["systems"]}

    assert statuses[1] == "available"
    assert statuses[3] == "available"
    assert statuses[4] == "available_disabled"
    assert statuses[7] == "claude_healthy_primary"
    assert overview["model_registry"][0]["model_name"] == "claude-sonnet-5"


def test_registry_status_does_not_infer_configuration_from_runtime_defaults():
    overview = governed_platform_overview()
    statuses = {system["id"]: system["status"] for system in overview["systems"]}
    assert statuses[7] == "not_configured"
