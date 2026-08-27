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


class MemoryProposalError(DatabaseError):
    """Raised when Li OS cannot create or process a memory proposal."""


class MemoryCorrectionError(DatabaseError):
    """Raised when Li OS cannot correct an explicit memory."""


class MemoryForgetError(DatabaseError):
    """Raised when Li OS cannot forget a memory."""


class OwnerConfirmationError(DatabaseError):
    """Raised when the owner confirmation workflow fails."""


def _connect() -> psycopg.Connection:
    settings = get_settings()

    return psycopg.connect(
        **settings.database_connect_kwargs(),
        row_factory=dict_row,
        connect_timeout=10,
    )


def _theo_connect() -> psycopg.Connection:
    settings = get_settings()

    return psycopg.connect(
        **settings.theo_database_connect_kwargs(),
        row_factory=dict_row,
        connect_timeout=10,
    )


def _owner_connect() -> psycopg.Connection:
    settings = get_settings()

    return psycopg.connect(
        **settings.owner_database_connect_kwargs(),
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


def recall_memory_for_theo(
    *,
    query: str,
    domains: list[str] | None = None,
    limit: int = 8,
) -> list[dict[str, object]]:
    """Retrieve review context through Theo's approved database function."""

    try:
        with _theo_connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM li_api.recall_memory_for_theo(%s, %s, %s);
                    """,
                    (query, domains, limit),
                )
                rows = cursor.fetchall()
    except psycopg.Error as exc:
        raise MemoryReadError(
            "Theo could not retrieve canonical memory context."
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
            "confidence": float(row["confidence"]),
            "confirmed_by_user": bool(row["confirmed_by_user"]),
        }
        for row in rows
    ]


def correct_explicit_memory(
    *,
    memory_id: str,
    new_value: str,
    new_domain: str | None = None,
    new_title: str | None = None,
    source_reference: str | None = None,
) -> dict[str, object]:
    """
    Correct an existing low-risk explicit canonical memory.

    The old memory is preserved as historical/outdated and the
    replacement becomes the current canonical memory.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        previous_memory_id,
                        memory_id,
                        outcome
                    FROM li_api.correct_explicit_memory(
                        CAST(%s AS UUID),
                        CAST(%s AS TEXT),
                        CAST(%s AS TEXT),
                        CAST(%s AS TEXT),
                        CAST(%s AS TEXT)
                    );
                    """,
                    (
                        memory_id,
                        new_value,
                        new_domain,
                        new_title,
                        source_reference,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise MemoryCorrectionError(
            "Li OS could not correct the memory."
        ) from exc

    if row is None:
        raise MemoryCorrectionError(
            "Li OS memory correction returned no result."
        )

    return {
        "previous_memory_id": str(row["previous_memory_id"]),
        "memory_id": str(row["memory_id"]),
        "outcome": str(row["outcome"]),
    }


def forget_memory(
    *,
    memory_id: str,
    source_reference: str | None = None,
) -> dict[str, object]:
    """
    Forget a canonical memory through the controlled
    li_api.forget_memory() function.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        memory_id,
                        outcome
                    FROM li_api.forget_memory(
                        CAST(%s AS UUID),
                        CAST(%s AS TEXT)
                    );
                    """,
                    (
                        memory_id,
                        source_reference,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise MemoryForgetError(
            "Li OS could not forget the memory."
        ) from exc

    if row is None:
        raise MemoryForgetError(
            "Li OS memory forget operation returned no result."
        )

    return {
        "memory_id": str(row["memory_id"]),
        "outcome": str(row["outcome"]),
    }


def propose_memory(
    *,
    proposed_by_agent: str,
    memory_class: str,
    domain: str,
    value_text: str,
    reason: str | None = None,
    truth_status: str | None = None,
    temporal_status: str | None = None,
    sensitivity: str = "personal",
    source_reference: str | None = None,
) -> str:
    """
    Submit a proposed memory for Theo review using Li's normal
    restricted runtime database role.
    """

    try:
        with _connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT li_api.propose_memory(
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    ) AS proposal_id;
                    """,
                    (
                        proposed_by_agent,
                        memory_class,
                        domain,
                        value_text,
                        reason,
                        truth_status,
                        temporal_status,
                        sensitivity,
                        source_reference,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise MemoryProposalError(
            "Li OS could not create the memory proposal."
        ) from exc

    if row is None or row["proposal_id"] is None:
        raise MemoryProposalError(
            "Li OS memory proposal returned no proposal ID."
        )

    return str(row["proposal_id"])


def get_pending_memory_proposals(
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    """
    Retrieve pending memory proposals using Theo's dedicated
    restricted database role.
    """

    try:
        with _theo_connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        proposal_id,
                        proposed_by_agent,
                        proposed_class,
                        proposed_domain,
                        proposed_value_text,
                        proposed_truth_status,
                        proposed_temporal_status,
                        proposed_sensitivity,
                        reason,
                        source_reference,
                        created_at
                    FROM li_api.get_pending_memory_proposals(%s);
                    """,
                    (limit,),
                )

                rows = cursor.fetchall()

    except psycopg.Error as exc:
        raise MemoryProposalError(
            "Theo could not retrieve pending memory proposals."
        ) from exc

    return [
        {
            "proposal_id": str(row["proposal_id"]),
            "proposed_by_agent": str(row["proposed_by_agent"]),
            "proposed_class": str(row["proposed_class"]),
            "proposed_domain": str(row["proposed_domain"]),
            "proposed_value_text": str(row["proposed_value_text"]),
            "proposed_truth_status": (
                str(row["proposed_truth_status"])
                if row["proposed_truth_status"] is not None
                else None
            ),
            "proposed_temporal_status": (
                str(row["proposed_temporal_status"])
                if row["proposed_temporal_status"] is not None
                else None
            ),
            "proposed_sensitivity": str(
                row["proposed_sensitivity"]
            ),
            "reason": row["reason"],
            "source_reference": row["source_reference"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def review_memory_proposal(
    *,
    proposal_id: str,
    decision: str,
    review_note: str | None = None,
    final_truth_status: str | None = None,
    final_temporal_status: str | None = None,
    final_confidence: float | None = None,
) -> dict[str, object]:
    """
    Review a memory proposal using Theo's dedicated restricted
    database role.
    """

    try:
        with _theo_connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        proposal_id,
                        proposal_status,
                        memory_id,
                        outcome
                    FROM li_api.review_memory_proposal(
                        CAST(%s AS UUID),
                        CAST(%s AS TEXT),
                        CAST(%s AS TEXT),
                        CAST(%s AS TEXT),
                        CAST(%s AS TEXT),
                        CAST(%s AS NUMERIC)
                    );
                    """,
                    (
                        proposal_id,
                        decision,
                        review_note,
                        final_truth_status,
                        final_temporal_status,
                        final_confidence,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise MemoryProposalError(
            "Theo could not review the memory proposal."
        ) from exc

    if row is None:
        raise MemoryProposalError(
            "Theo memory review returned no result."
        )

    return {
        "proposal_id": str(row["proposal_id"]),
        "proposal_status": str(row["proposal_status"]),
        "memory_id": (
            str(row["memory_id"])
            if row["memory_id"] is not None
            else None
        ),
        "outcome": str(row["outcome"]),
    }


def confirm_memory_proposal(
    *,
    proposal_id: str,
    decision: str,
    note: str | None = None,
) -> dict[str, object]:
    """
    Confirm or reject a proposal using the owner's dedicated
    restricted database role.
    """

    try:
        with _owner_connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        proposal_id,
                        proposal_status,
                        outcome
                    FROM li_api.confirm_memory_proposal(
                        %s,
                        %s,
                        %s
                    );
                    """,
                    (
                        proposal_id,
                        decision,
                        note,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise OwnerConfirmationError(
            "Li OS owner confirmation failed."
        ) from exc

    if row is None:
        raise OwnerConfirmationError(
            "Li OS owner confirmation returned no result."
        )

    return {
        "proposal_id": str(row["proposal_id"]),
        "proposal_status": str(row["proposal_status"]),
        "outcome": str(row["outcome"]),
    }
