import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


class DatabaseHealthError(RuntimeError):
    """Raised when the Li OS database health check fails."""


def database_health() -> dict[str, str | int]:
    """
    Verify connectivity to the Li OS memory database through the
    restricted li_backend_runtime account.

    This function calls only the approved li_api.health_check()
    database function. It does not access canonical memory tables
    directly.
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