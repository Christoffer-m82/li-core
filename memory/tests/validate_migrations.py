"""Apply and audit the Li OS migration history in a disposable PostgreSQL database."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_ROOT = REPOSITORY_ROOT / "memory" / "migrations"

# Historical order is explicit because two files use the 021 prefix and claim
# version 0.21. Migration 025 restores the capability from the skipped file.
MIGRATION_ORDER = tuple(
    [
        f"{number:03d}_{name}.sql"
        for number, name in (
            (1, "initial_schema"),
            (2, "security_baseline"),
            (3, "memory_api_boundary"),
            (4, "core_memory_functions"),
            (5, "theo_review_workflow"),
            (6, "backend_runtime_role"),
            (7, "explicit_memory_deduplication"),
            (8, "theo_runtime_role"),
            (9, "owner_memory_confirmation"),
            (10, "owner_api_schema_usage"),
            (11, "memory_corrections_and_forgetting"),
            (12, "harden_forget_memory_policy"),
            (13, "automated_theo_review"),
            (14, "conversation_history"),
            (15, "conversation_history_rls_cleanup"),
            (16, "tasks_and_reminders"),
            (17, "governed_artifacts_and_specialist_history"),
            (18, "agent_analytics_and_relevance"),
            (19, "fix_agent_recommendation_status_ambiguity"),
            (20, "controlled_agent_governance_executor"),
            (21, "artifact_library"),
            (22, "retention_worker_role"),
            (23, "fix_artifact_reservation_ambiguity"),
            (24, "fix_specialist_history_status_ambiguity"),
            (25, "restore_private_conversation_deletion"),
            (26, "generalized_specialist_orchestration"),
            (27, "fix_generalized_specialist_history_status_ambiguity"),
            (28, "specialist_synthesis_action_instrumentation"),
            (29, "durable_action_intents"),
            (30, "governed_action_policy_and_rhythms"),
            (31, "governed_proactivity"),
            (32, "private_place_settings"),
            (33, "native_mobile_location_boundary"),
            (34, "authenticated_native_gateway"),
            (35, "governed_li_native_systems"),
            (36, "owner_model_registry_configuration"),
        )
    ]
)
INTENTIONALLY_SKIPPED = {"021_private_conversation_deletion.sql"}
EXPECTED_VERSIONS = {f"0.{number}" for number in range(1, 37)}


def psql(
    *arguments: str, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["psql", "-X", "--no-psqlrc", "--set", "ON_ERROR_STOP=1", *arguments],
        check=check,
        capture_output=capture,
        text=True,
    )


def scalar(sql: str) -> str:
    result = psql("--tuples-only", "--no-align", "--command", sql, capture=True)
    return result.stdout.strip()


def validate_inventory() -> None:
    actual = {path.name for path in MIGRATIONS_ROOT.glob("*.sql")}
    expected = set(MIGRATION_ORDER) | INTENTIONALLY_SKIPPED
    if actual != expected:
        missing = sorted(expected - actual)
        unlisted = sorted(actual - expected)
        raise RuntimeError(
            f"Migration manifest mismatch; missing={missing}, unlisted={unlisted}"
        )


def bootstrap_supabase_roles() -> None:
    psql(
        "--command",
        "CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; "
        "CREATE ROLE service_role NOLOGIN;",
    )


def apply_history() -> None:
    for filename in MIGRATION_ORDER:
        print(f"Applying {filename}", flush=True)
        psql("--quiet", "--file", str(MIGRATIONS_ROOT / filename))


def validate_result() -> None:
    versions = set(
        scalar(
            "SELECT version FROM li_memory.schema_versions ORDER BY version::numeric;"
        ).splitlines()
    )
    if versions != EXPECTED_VERSIONS:
        raise RuntimeError(
            "Unexpected schema versions; "
            f"missing={sorted(EXPECTED_VERSIONS - versions)}, "
            f"extra={sorted(versions - EXPECTED_VERSIONS)}"
        )

    checks = {
        "initial synthetic user survived": (
            "SELECT count(*) = 1 FROM li_memory.users WHERE user_key = 'christoffer';"
        ),
        "canonical memory RLS is forced": (
            "SELECT c.relrowsecurity AND c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'li_memory' AND c.relname = 'memory_records';"
        ),
        "runtime roles own no protected tables": (
            "SELECT count(*) = 0 FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_roles r ON r.oid = c.relowner "
            "WHERE n.nspname IN ('li_memory', 'li_runtime_data') "
            "AND r.rolname IN ('li_backend_runtime', 'li_theo_runtime', "
            "'li_owner_runtime', 'li_retention_runtime');"
        ),
        "private deletion capability was restored": (
            "SELECT to_regprocedure('li_api.delete_private_conversation(uuid)') IS NOT NULL;"
        ),
    }
    for label, sql in checks.items():
        if scalar(sql) != "t":
            raise RuntimeError(f"Database invariant failed: {label}")

    allowed = psql(
        "--command",
        "SET ROLE li_backend_runtime; SELECT count(*) FROM li_api.get_primary_user();",
        capture=True,
        check=False,
    )
    if allowed.returncode != 0:
        raise RuntimeError("Backend runtime could not call its approved API capability")

    denied = psql(
        "--command",
        "SET ROLE li_backend_runtime; SELECT count(*) FROM li_memory.memory_records;",
        capture=True,
        check=False,
    )
    if denied.returncode == 0:
        raise RuntimeError(
            "Backend runtime unexpectedly read the canonical table directly"
        )

    replay = psql(
        "--file",
        str(MIGRATIONS_ROOT / MIGRATION_ORDER[-1]),
        capture=True,
        check=False,
    )
    if (
        replay.returncode == 0
        or "schema version 0.36 is already claimed" not in replay.stderr.lower()
    ):
        raise RuntimeError("Latest migration did not fail closed on replay")

    if scalar("SELECT count(*) FROM li_memory.schema_versions;") != "36":
        raise RuntimeError("Replay attempt changed schema-version history")


def main() -> None:
    validate_inventory()
    bootstrap_supabase_roles()
    apply_history()
    validate_result()
    print("Disposable database migration validation passed.")


if __name__ == "__main__":
    main()
