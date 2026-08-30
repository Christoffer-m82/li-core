"""Narrow database boundary for artifacts, privacy, history, and specialist events."""

from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings


class RuntimeDataError(RuntimeError):
    pass


def _call(name: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    settings = get_settings()
    placeholders = ",".join(["%s"] * len(params))
    try:
        with psycopg.connect(**settings.database_connect_kwargs(), row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM li_api.{name}({placeholders});", params)
                return [dict(row) for row in cursor.fetchall()]
    except psycopg.Error as exc:
        raise RuntimeDataError(f"Runtime data operation {name} failed.") from exc


def _owner_call(name: str, params: tuple[object, ...]) -> list[dict[str, object]]:
    settings = get_settings()
    placeholders = ",".join(["%s"] * len(params))
    try:
        with psycopg.connect(**settings.owner_database_connect_kwargs(), row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM li_api.{name}({placeholders});", params)
                return [dict(row) for row in cursor.fetchall()]
    except psycopg.Error as exc:
        raise RuntimeDataError(f"Owner runtime operation {name} failed.") from exc


def get_privacy_settings() -> dict[str, object]:
    rows = _call("get_privacy_settings")
    if not rows:
        raise RuntimeDataError("Privacy settings were not returned.")
    return rows[0]


def set_retention(days: int) -> int:
    rows = _call("set_artifact_retention_days", (days,))
    return int(next(iter(rows[0].values())))


def reserve_artifact(**values: object) -> dict[str, object]:
    rows = _call("reserve_artifact", (
        values["filename"], values["content_type"], values["size_bytes"],
        values["source"], values.get("conversation_id"),
    ))
    if not rows:
        raise RuntimeDataError("Artifact reservation failed.")
    return rows[0]


def finalize_artifact(artifact_id: str, object_name: str, generation: int | None, keep: bool) -> bool:
    rows = _call("finalize_artifact", (UUID(artifact_id), object_name, generation, keep))
    return bool(next(iter(rows[0].values())))


def get_artifact(artifact_id: str) -> dict[str, object] | None:
    rows = _call("get_artifact", (UUID(artifact_id),))
    return rows[0] if rows else None


def list_artifacts(limit: int = 50) -> list[dict[str, object]]:
    return _call("list_artifacts", (limit,))


def change_artifact(artifact_id: str, action: str) -> dict[str, object] | None:
    rows = _call("change_artifact_retention", (UUID(artifact_id), action))
    return rows[0] if rows else None


def start_interaction(
    conversation_id: str, request_id: str, specialist: str, request: str,
    selection_mode: str, group_mode: str, route_category: str, route_reason: str,
) -> str:
    rows = _call("start_specialist_interaction", (
        UUID(conversation_id), UUID(request_id), specialist, request,
        selection_mode, group_mode, route_category, route_reason,
    ))
    return str(next(iter(rows[0].values())))


def finish_interaction(interaction_id: str, status: str, outcome: dict[str, object]) -> bool:
    rows = _call("finish_specialist_interaction", (
        UUID(interaction_id), status, Jsonb(outcome),
    ))
    return bool(next(iter(rows[0].values())))


def record_synthesis_attribution(
    request_id: str, used_interaction_ids: list[str], measured_interaction_ids: list[str]
) -> bool:
    rows = _call("record_specialist_synthesis_attribution", (
        UUID(request_id),
        [UUID(value) for value in used_interaction_ids],
        [UUID(value) for value in measured_interaction_ids],
    ))
    return bool(rows and next(iter(rows[0].values())))


def record_action_attribution(
    *, action_id: str, request_id: str, interaction_ids: list[str],
    action_type: str, status: str,
) -> bool:
    rows = _call("record_specialist_action_attribution", (
        UUID(action_id), UUID(request_id), [UUID(value) for value in interaction_ids],
        action_type, status,
    ))
    return bool(rows and next(iter(rows[0].values())))


def create_action_intent(**values: object) -> dict[str, object]:
    rows = _call("create_action_intent", (
        UUID(str(values["intent_id"])), UUID(str(values["request_id"])),
        [UUID(str(value)) for value in values["interaction_ids"]],
        UUID(str(values["conversation_id"])), values["action_type"], values["summary"],
        Jsonb(values["payload"]), values["payload_hash"],
        values["owner_confirmation_required"],
    ))
    if not rows:
        raise RuntimeDataError("Action intent was not persisted.")
    return rows[0]


def resolve_action_intent(
    *, intent_id: str, decision: str, owner_confirmation: str | None = None,
    execution_status: str | None = None, result: dict[str, object] | None = None,
) -> dict[str, object]:
    rows = _call("resolve_action_intent", (
        UUID(intent_id), decision, owner_confirmation, execution_status,
        Jsonb(result) if result is not None else None,
    ))
    if not rows:
        raise RuntimeDataError("Action intent transition returned no result.")
    return dict(next(iter(rows[0].values())))


def get_action_policy_overview() -> dict[str, object]:
    rows = _call("get_action_policy_overview")
    if not rows:
        raise RuntimeDataError("Action policy was not returned.")
    return dict(next(iter(rows[0].values())))


def propose_action_policy_change(*, proposal_id: str, base_version: int,
                                 proposed_policy: dict[str, object], summary: str) -> dict[str, object]:
    rows = _call("propose_action_policy_change", (
        UUID(proposal_id), base_version, Jsonb(proposed_policy), summary,
    ))
    return rows[0]


def decide_action_policy_change(proposal_id: str, decision: str) -> dict[str, object]:
    rows = _owner_call("decide_action_policy_change", (UUID(proposal_id), decision))
    if not rows:
        raise RuntimeDataError("Policy decision returned no result.")
    return dict(next(iter(rows[0].values())))


def rollback_action_policy(target_version: int, confirmation: str) -> dict[str, object]:
    rows = _owner_call("rollback_action_policy", (target_version, confirmation))
    if not rows:
        raise RuntimeDataError("Policy rollback returned no result.")
    return dict(next(iter(rows[0].values())))


def list_open_loops(limit: int = 100) -> list[dict[str, object]]:
    public = []
    for value in _call("list_open_loops", (limit,)):
        row = dict(value)
        row["open_loop_id"] = row.pop("id")
        row.pop("owner_user_id", None)
        row["three_postponements_reached"] = int(row.get("postponement_count", 0)) >= 3
        public.append(row)
    return public


def create_open_loop(**values: object) -> dict[str, object]:
    rows = _call("create_open_loop", (
        values["commitment_summary"], values.get("owed_to"), values.get("source_conversation_id"),
        values.get("source_request_id"), values["next_action"], values.get("due_at"),
        values["urgency"], values.get("approved", False), values.get("sensitive", False),
        values.get("commitment_kind", "self"),
    ))
    if not rows:
        raise RuntimeDataError("Open loop was not created.")
    row = dict(rows[0])
    row["open_loop_id"] = row.pop("id")
    row.pop("owner_user_id", None)
    row["three_postponements_reached"] = int(row.get("postponement_count", 0)) >= 3
    return row


def transition_open_loop(open_loop_id: str, transition: str) -> dict[str, object]:
    rows = _call("transition_open_loop", (UUID(open_loop_id), transition))
    if not rows:
        raise RuntimeDataError("Open-loop transition returned no result.")
    row = dict(rows[0])
    row["open_loop_id"] = row.pop("id")
    row.pop("owner_user_id", None)
    row["three_postponements_reached"] = int(row.get("postponement_count", 0)) >= 3
    return row


def list_rhythm_states() -> list[dict[str, object]]:
    return _call("list_rhythm_states")


def configure_rhythm(**values: object) -> dict[str, object]:
    rows = _call("configure_rhythm", (
        values["key"], values["enabled"], values["timezone"], values["local_time"],
        values.get("next_run"), values.get("approved", False),
    ))
    if not rows:
        raise RuntimeDataError("Rhythm configuration returned no state.")
    return rows[0]


def claim_rhythm_run(key: str, run_key: str, scheduled_for: object) -> dict[str, object]:
    rows = _call("claim_rhythm_run", (key, run_key, scheduled_for))
    return rows[0] if rows else {"run_id": None, "claimed": False, "state": "failed"}


def complete_rhythm_run(**values: object) -> str | None:
    rows = _call("complete_rhythm_run", (
        UUID(str(values["run_id"])), values["status"], values.get("title", ""),
        Jsonb(values.get("content", {})), values.get("sensitive", False), values.get("next_run"),
    ))
    value = next(iter(rows[0].values())) if rows else None
    return str(value) if value else None


def list_proactive_briefs(limit: int = 50) -> list[dict[str, object]]:
    return _call("list_proactive_briefs", (limit,))


def mark_proactive_brief_read(brief_id: str) -> bool:
    rows = _call("mark_proactive_brief_read", (UUID(brief_id),))
    return bool(rows and next(iter(rows[0].values())))


def suppress_open_loop(open_loop_id: str, action: str, until: object | None) -> dict[str, object]:
    rows = _call("suppress_open_loop", (UUID(open_loop_id), action, until))
    if not rows:
        raise RuntimeDataError("Open-loop suppression returned no result.")
    row = dict(rows[0])
    row["open_loop_id"] = row.pop("id")
    row.pop("owner_user_id", None)
    row["three_postponements_reached"] = int(row.get("postponement_count", 0)) >= 3
    return row


def set_category_suppression(category: str, action: str, until: object | None) -> dict[str, object]:
    rows = _call("set_proactivity_suppression", (category, action, until))
    if not rows:
        raise RuntimeDataError("Category suppression returned no state.")
    return rows[0]


def list_category_suppressions() -> list[dict[str, object]]:
    return _call("list_proactivity_suppressions")


def list_interactions(specialist: str | None = None, limit: int = 50) -> list[dict[str, object]]:
    return _call("list_specialist_interactions", (specialist, limit))


def analytics_events() -> list[dict[str, object]]:
    return _call("list_agent_analytics_events")


def get_agent_settings() -> dict[str, object]:
    rows = _call("get_agent_analytics_settings")
    return rows[0]


def agent_states() -> list[dict[str, object]]:
    return _call("list_agent_states")


def set_agent_cadence(months: int | None) -> dict[str, object]:
    return _call("set_agent_relevance_cadence", (months,))[0]


def create_agent_recommendations(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return _call("replace_agent_recommendations", (Jsonb(items),))


def review_agent_recommendation(recommendation_id: str, decision: str) -> dict[str, object]:
    rows = _call("review_agent_recommendation", (UUID(recommendation_id), decision))
    if not rows:
        raise RuntimeDataError("Recommendation was not found.")
    return rows[0]


def execute_agent_recommendation(recommendation_id: str, idempotency_key: str,
                                 confirmation: str, note: str | None) -> dict[str, object]:
    rows = _owner_call("execute_agent_recommendation", (
        UUID(recommendation_id), UUID(idempotency_key), confirmation, note,
    ))
    if not rows:
        raise RuntimeDataError("Agent recommendation execution returned no result.")
    return rows[0]


def list_conversations(limit: int = 30) -> list[dict[str, object]]:
    return _call("list_conversations", (limit,))


def conversation_messages(conversation_id: str, limit: int = 40) -> list[dict[str, object]]:
    return _call("get_recent_conversation_messages", (UUID(conversation_id), limit))


def delete_conversation(conversation_id: str) -> dict[str, object] | None:
    rows = _owner_call("delete_private_conversation", (UUID(conversation_id),))
    return rows[0] if rows else None
