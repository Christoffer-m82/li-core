import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class DatabaseError(RuntimeError):
    """Base error for Li OS database operations."""


class DatabaseHealthError(DatabaseError):
    """Raised when the Li OS database health check fails."""


class MemoryReadError(DatabaseError):
    """Raised when Li OS cannot retrieve memory information."""


def database_health() -> dict[str, str | int]:
    """
    Verify connectivity to the Li OS memory database through the
    restricted li_backend_runtime account.

    This function calls only the approved li_api.health_check()
    database function.
    """

    settings = get_settings()

    try:
        with psycopg.connect(
            **settings.database_connect_kwargs(),
            row_factory=dict_row,
            connect_timeout=10,
        ) as connection:
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
    Retrieve the active primary Li OS user through the controlled
    li_api.get_primary_user() database function.

    No direct canonical-table access is used.
    """

    settings = get_settings()

    try:
        with psycopg.connect(
            **settings.database_connect_kwargs(),
            row_factory=dict_row,
            connect_timeout=10,
        ) as connection:
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