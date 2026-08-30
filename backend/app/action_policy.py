"""Typed, versioned action policy. Identity expresses preferences; policy grants authority."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AutonomyLevel = Literal["advice_only", "propose_only", "execute_after_approval", "auto_execute"]


class ActionCategoryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str
    action_types: tuple[str, ...]
    autonomy_level: AutonomyLevel = "execute_after_approval"
    approval_required: bool = True
    owner_confirmation_required: bool = False
    auto_execution_permitted: bool = False
    amount_threshold_eur: int | None = None
    irreversibility: Literal["reversible", "limited", "high"] = "limited"
    known_vendor_required: bool = False
    third_party_or_family_involvement: Literal["none", "approval_required"] = "approval_required"
    sensitivity: tuple[Literal["legal", "tax", "employment"], ...] = ()

    @model_validator(mode="after")
    def prevent_implicit_authority(self) -> "ActionCategoryPolicy":
        if self.auto_execution_permitted and self.approval_required:
            raise ValueError("Auto-execution cannot coexist with required approval.")
        if self.autonomy_level == "auto_execute" and not self.auto_execution_permitted:
            raise ValueError("Auto-execution level requires an explicit permission grant.")
        return self


class FreshnessEvidencePolicyExtension(BaseModel):
    """Reserved contract for a future per-specialist policy milestone."""
    enabled: Literal[False] = False
    schema_version: str = "future-1"
    specialist_overrides: dict[str, dict[str, object]] = Field(default_factory=dict)


class ActionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = "1.0"
    policy_version: int = 1
    effective_at: datetime | None = None
    categories: tuple[ActionCategoryPolicy, ...]
    specialist_action_authority: Literal["none"] = "none"
    freshness_evidence: FreshnessEvidencePolicyExtension = Field(
        default_factory=FreshnessEvidencePolicyExtension
    )

    def for_action(self, action_type: str) -> ActionCategoryPolicy:
        for item in self.categories:
            if action_type in item.action_types:
                return item
        raise KeyError(f"No governed policy for {action_type}.")


def conservative_default_policy() -> ActionPolicy:
    common = dict(approval_required=True, auto_execution_permitted=False)
    return ActionPolicy(categories=(
        ActionCategoryPolicy(category="calendar", action_types=("calendar.create",), **common),
        ActionCategoryPolicy(category="tasks", action_types=("task.create", "task.complete", "task.cancel"), **common),
        ActionCategoryPolicy(category="email_drafts", action_types=("email.create_draft",), irreversibility="reversible", **common),
        ActionCategoryPolicy(category="registry_governance", action_types=("governance.execute",), autonomy_level="propose_only", owner_confirmation_required=True, irreversibility="high", sensitivity=("employment",), **common),
        ActionCategoryPolicy(category="money", action_types=("money.transact",), autonomy_level="propose_only", amount_threshold_eur=None, known_vendor_required=True, irreversibility="high", **common),
        ActionCategoryPolicy(category="legal_tax_employment", action_types=("legal.submit", "tax.submit", "employment.change"), autonomy_level="propose_only", owner_confirmation_required=True, irreversibility="high", sensitivity=("legal", "tax", "employment"), **common),
        ActionCategoryPolicy(category="third_party_family", action_types=("third_party.commit",), autonomy_level="propose_only", owner_confirmation_required=True, irreversibility="high", **common),
    ))


class PolicyMismatch(BaseModel):
    code: str
    identity_claim: str
    enforced_policy: str
    severity: Literal["warning"] = "warning"


def identity_policy_mismatches(identity_text: str, policy: ActionPolicy) -> list[PolicyMismatch]:
    mismatches: list[PolicyMismatch] = []
    euro_claim = re.search(r"(?:€|EUR\s*)(\d+)", identity_text, re.IGNORECASE)
    money = policy.for_action("money.transact")
    if euro_claim and (money.amount_threshold_eur is None or money.approval_required):
        mismatches.append(PolicyMismatch(
            code="identity_amount_preference_not_enabled",
            identity_claim=f"Identity describes an autonomy preference around €{euro_claim.group(1)}.",
            enforced_policy="Money actions are proposal-only and require approval; no amount grants auto-execution.",
        ))
    return mismatches


def repository_identity_mismatches(policy: ActionPolicy) -> list[PolicyMismatch]:
    identity = Path(__file__).parents[2] / "li" / "identity.md"
    return identity_policy_mismatches(identity.read_text(encoding="utf-8"), policy)


def execution_allowed(action_type: str, *, approved: bool, policy: ActionPolicy) -> bool:
    rule = policy.for_action(action_type)
    if rule.approval_required and not approved:
        return False
    return approved or rule.auto_execution_permitted
