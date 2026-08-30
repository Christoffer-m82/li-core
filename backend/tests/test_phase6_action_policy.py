from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.action_policy import (
    ActionCategoryPolicy, conservative_default_policy, execution_allowed,
    identity_policy_mismatches,
)
from app.action_policy_runtime import (
    PolicyChangeProposal, PolicyDecision, PolicyRollback, create_policy_proposal,
    decide_policy_proposal, read_policy_overview, rollback_policy,
)
from app.rhythms import DEFAULT_RHYTHMS, OpenLoopCreate, three_postponement_hook


def test_policy_defaults_match_current_effective_permissions():
    policy = conservative_default_policy()
    assert policy.policy_version == 1
    assert policy.specialist_action_authority == "none"
    assert all(item.approval_required for item in policy.categories)
    assert not any(item.auto_execution_permitted for item in policy.categories)
    assert policy.for_action("money.transact").amount_threshold_eur is None
    assert policy.for_action("governance.execute").owner_confirmation_required is True


@pytest.mark.parametrize("action_type", [
    "calendar.create", "task.create", "task.complete", "task.cancel", "email.create_draft",
])
def test_unauthorized_auto_execution_is_rejected(action_type):
    assert execution_allowed(action_type, approved=False, policy=conservative_default_policy()) is False
    assert execution_allowed(action_type, approved=True, policy=conservative_default_policy()) is True


def test_invalid_auto_execution_grant_is_not_representable():
    with pytest.raises(ValidationError):
        ActionCategoryPolicy(
            category="tasks", action_types=("task.create",), autonomy_level="auto_execute",
            approval_required=True, auto_execution_permitted=True,
        )


def test_identity_amount_preference_surfaces_warning_without_permission():
    mismatches = identity_policy_mismatches(
        "Li may act under €150 when enabled by system policy.", conservative_default_policy()
    )
    assert mismatches[0].code == "identity_amount_preference_not_enabled"
    assert "require approval" in mismatches[0].enforced_policy


def test_policy_upgrade_proposal_and_owner_decision_are_distinct(monkeypatch):
    observed = {}
    policy = conservative_default_policy().model_copy(update={"policy_version": 2})
    monkeypatch.setattr("app.action_policy_runtime.propose_action_policy_change", lambda **values: observed.update(values) or {"state": "proposed"})
    proposal = create_policy_proposal(PolicyChangeProposal(
        base_version=1, proposed_policy=policy, summary="Explicit governed upgrade",
    ))
    assert proposal["state"] == "proposed" and observed["base_version"] == 1
    monkeypatch.setattr("app.action_policy_runtime.decide_action_policy_change", lambda proposal_id, decision: {"proposal_id": proposal_id, "state": "approved", "effective_version": 2})
    result = decide_policy_proposal(uuid4(), PolicyDecision(decision="approve"))
    assert result["state"] == "approved" and result["effective_version"] == 2


def test_policy_rollback_requires_typed_owner_confirmation(monkeypatch):
    monkeypatch.setattr("app.action_policy_runtime.rollback_action_policy", lambda version, confirmation: {"state": "rolled_back", "restored_from_version": version, "confirmation": confirmation})
    result = rollback_policy(PolicyRollback(
        target_version=1, confirmation="confirm_action_policy_rollback"
    ))
    assert result["state"] == "rolled_back" and result["restored_from_version"] == 1


def test_overview_is_read_only_and_falls_back_safely_before_migration(monkeypatch):
    monkeypatch.setattr("app.action_policy_runtime.get_action_policy_overview", lambda: (_ for _ in ()).throw(RuntimeError()))
    overview = read_policy_overview()
    assert overview["read_only"] is True
    assert overview["identity_preference_is_authority"] is False
    assert overview["effective_policy"]["categories"]


def test_schedule_definitions_are_preview_only_and_never_mutate_providers():
    assert {item.key for item in DEFAULT_RHYTHMS} == {"morning", "friday", "monthly", "quarterly", "annual"}
    assert all(item.mode in {"preview_only", "disabled"} for item in DEFAULT_RHYTHMS)
    assert all(item.external_mutations_permitted is False for item in DEFAULT_RHYTHMS)


def test_open_loop_contract_minimizes_content_and_three_postponement_hook():
    loop = OpenLoopCreate(commitment_summary="Send the agreed summary", owed_to="Alex", next_action="Prepare concise draft")
    assert "raw_message" not in loop.model_dump()
    assert three_postponement_hook(2) is False
    assert three_postponement_hook(3) is True


def test_migration_has_durable_lifecycle_rollback_and_narrow_authority():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "030_governed_action_policy_and_rhythms.sql").read_text(encoding="utf-8")
    for value in ("action_policy_versions", "action_policy_proposals", "action_policy_events",
                  "rhythm_definitions", "open_loops", "rollback_action_policy"):
        assert value in sql
    assert "confirm_action_policy_rollback" in sql
    assert "preview_only" in sql and "external_mutations_permitted" in sql
    assert "Action policy privilege escalation boundary is broader than intended" in sql
    assert "Schema version 0.30 is already claimed" in sql
    assert "ON CONFLICT(version) DO NOTHING" not in sql
