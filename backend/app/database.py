import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class DatabaseError(RuntimeError):
    """Base error for Li OS database operations."""


class DatabaseHealthError(DatabaseError):
    """Raised when the Li OS database health check fails."""


class MemoryReadError(DatabaseError):
    """Raised when Li OS cannot retrieve memory information."""


class MemoryWriteError(DatabaseError):
    """Raised when Li OS cannot write permitted memory information."""


def _connect() -> psycopg.Connection:
    settings = get_settings()

    return psycopg.connect(
        **settings.database_connect_kwargs(),
        row_factory=dict_row,
        connect_timeout=10,
    )


def database_health() -> dict[str, str | int]:
    """
    Verify connectivity through the restricted Li OS database role.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        status,
                        schema_version,
                        canonical_tables
                    FROM li_api.health_check();
                    """
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise DatabaseHealthError(
            "Li OS database health check failed."
        ) from exc

    if row is None:
        raise DatabaseHealthError(
            "Li OS database health check returned no result."
        )

    return {
        "status": str(row["status"]),
        "schema_version": str(row["schema_version"]),
        "canonical_tables": int(row["canonical_tables"]),
    }


def get_primary_user() -> dict[str, str]:
    """
    Retrieve the active primary Li OS user through the controlled API.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        user_id,
                        user_key,
                        full_name,
                        display_name,
                        memory_namespace
                    FROM li_api.get_primary_user();
                    """
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise MemoryReadError(
            "Li OS could not retrieve the primary user."
        ) from exc

    if row is None:
        raise MemoryReadError(
            "Li OS primary user was not found."
        )

    return {
        "user_id": str(row["user_id"]),
        "user_key": str(row["user_key"]),
        "full_name": str(row["full_name"]),
        "display_name": str(row["display_name"]),
        "memory_namespace": str(row["memory_namespace"]),
    }


def store_explicit_memory(
    *,
    memory_class: str,
    domain: str,
    value: str,
    title: str | None,
    sensitivity: str,
    private_to_li: bool,
    source_reference: str | None,
) -> str:
    """
    Store an explicit low-risk memory through the controlled
    li_api.store_explicit_memory() database function.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT li_api.store_explicit_memory(
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    ) AS memory_id;
                    """,
                    (
                        memory_class,
                        domain,
                        value,
                        title,
                        sensitivity,
                        private_to_li,
                        source_reference,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise MemoryWriteError(
            "Li OS could not store explicit memory."
        ) from exc

    if row is None or row["memory_id"] is None:
        raise MemoryWriteError(
            "Li OS memory write returned no memory ID."
        )

    return str(row["memory_id"])


def recall_memory(
    *,
    query: str,
    domains: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, object]]:
    """
    Retrieve relevant canonical memories through the controlled
    li_api.recall_memory() function.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        memory_id,
                        memory_class,
                        domain,
                        title,
                        value_text,
                        truth_status,
                        temporal_status,
                        sensitivity,
                        private_to_li,
                        confidence,
                        source_type,
                        source_reference,
                        confirmed_by_user,
                        valid_from,
                        valid_until,
                        created_at,
                        relevance
                    FROM li_api.recall_memory(
                        %s,
                        %s,
                        %s
                    );
                    """,
                    (
                        query,
                        domains,
                        limit,
                    ),
                )

                rows = cursor.fetchall()

    except psycopg.Error as exc:
        raise MemoryReadError(
            "Li OS could not recall memory."
        ) from exc

    return [
        {
            "memory_id": str(row["memory_id"]),
            "memory_class": str(row["memory_class"]),
            "domain": str(row["domain"]),
            "title": row["title"],
            "value_text": row["value_text"],
            "truth_status": str(row["truth_status"]),
            "temporal_status": str(row["temporal_status"]),
            "sensitivity": str(row["sensitivity"]),
            "private_to_li": bool(row["private_to_li"]),
            "confidence": float(row["confidence"]),
            "source_type": str(row["source_type"]),
            "source_reference": row["source_reference"],
            "confirmed_by_user": bool(row["confirmed_by_user"]),
            "valid_from": row["valid_from"],
            "valid_until": row["valid_until"],
            "created_at": row["created_at"],
            "relevance": float(row["relevance"]),
        }
        for row in rows
    ]