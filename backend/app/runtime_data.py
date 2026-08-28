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


def change_artifact(artifact_id: str, action: str) -> dict[str, object] | None:
    rows = _call("change_artifact_retention", (UUID(artifact_id), action))
    return rows[0] if rows else None


def expired_artifacts(limit: int = 100) -> list[dict[str, object]]:
    return _call("list_expired_artifacts", (limit,))


def mark_expired(artifact_id: str) -> bool:
    rows = _call("mark_artifact_expired", (UUID(artifact_id),))
    return bool(next(iter(rows[0].values())))


def start_interaction(conversation_id: str, request_id: str, specialist: str, request: str) -> str:
    rows = _call("start_specialist_interaction", (
        UUID(conversation_id), UUID(request_id), specialist, request,
    ))
    return str(next(iter(rows[0].values())))


def finish_interaction(interaction_id: str, status: str, outcome: dict[str, object]) -> bool:
    rows = _call("finish_specialist_interaction", (
        UUID(interaction_id), status, Jsonb(outcome),
    ))
    return bool(next(iter(rows[0].values())))


def list_interactions(specialist: str | None = None, limit: int = 50) -> list[dict[str, object]]:
    return _call("list_specialist_interactions", (specialist, limit))


def list_conversations(limit: int = 30) -> list[dict[str, object]]:
    return _call("list_conversations", (limit,))


def conversation_messages(conversation_id: str, limit: int = 40) -> list[dict[str, object]]:
    return _call("get_recent_conversation_messages", (UUID(conversation_id), limit))
