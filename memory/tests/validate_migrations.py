"""Apply and audit the Li OS migration history in a disposable PostgreSQL database."""

from __future__ import annotations

import json
import os
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
            (37, "conversation_context_privacy"),
            (38, "recoverable_turns_and_actions"),
            (39, "phase_2_truth_and_turn_recovery"),
        )
    ]
)
INTENTIONALLY_SKIPPED = {"021_private_conversation_deletion.sql"}
# PostgreSQL 16+ retains grantor-specific role-membership rows. Run the role-
# managing migration tail through Supabase's delegated migration executor so a
# migration's own GRANT/REVOKE pair has one grantor and its removal assertions
# test the real final authority state.
PRIVILEGED_ROLE_MIGRATIONS = set(MIGRATION_ORDER[7:])
EXPECTED_VERSIONS = {f"0.{number}" for number in range(1, 40)}


def psql(
    *arguments: str,
    capture: bool = False,
    check: bool = True,
    user: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = None if user is None else {**os.environ, "PGUSER": user}
    return subprocess.run(
        ["psql", "-X", "--no-psqlrc", "--set", "ON_ERROR_STOP=1", *arguments],
        check=check,
        capture_output=capture,
        env=environment,
        text=True,
    )


def scalar(sql: str) -> str:
    # Administrative inspection only; runtime allow/deny checks below always
    # set the exact session authorization being tested.
    result = psql(
        "--tuples-only", "--no-align", "--command", sql,
        capture=True, user="supabase_admin",
    )
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
    # The pinned Supabase image supplies its delegated postgres migration role.
    # Add only client roles that are absent when the image runs without the full
    # self-hosted stack's mounted initialization scripts.
    psql(
        "--command",
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN "
        "CREATE ROLE anon NOLOGIN; END IF; "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN "
        "CREATE ROLE authenticated NOLOGIN; END IF; "
        "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN "
        "CREATE ROLE service_role NOLOGIN; END IF; END $$;",
    )
    os.environ["PGUSER"] = "postgres"


def apply_history() -> None:
    for filename in MIGRATION_ORDER:
        print(f"Applying {filename}", flush=True)
        executor = "supabase_admin" if filename in PRIVILEGED_ROLE_MIGRATIONS else None
        psql(
            "--quiet",
            "--file",
            str(MIGRATIONS_ROOT / filename),
            user=executor,
        )


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
        "migration executor cannot assume delegated capability roles": (
            "SELECT bool_and(NOT pg_has_role('postgres', role_name, 'SET')) "
            "FROM unnest(ARRAY['li_memory_function_owner', "
            "'li_memory_owner_confirmation']) AS role_name;"
        ),
        "private deletion capability was restored": (
            "SELECT to_regprocedure('li_api.delete_private_conversation(uuid)') IS NOT NULL;"
        ),
        "conversation context returns privacy metadata": (
            "SELECT pg_get_function_result("
            "'li_api.get_recent_conversation_messages(uuid,integer)'::regprocedure) "
            "LIKE '%privacy_metadata jsonb%';"
        ),
        "chat turn lifecycle is installed": (
            "SELECT to_regprocedure('li_api.begin_chat_turn(uuid,text)') IS NOT NULL "
            "AND to_regprocedure('li_api.finish_chat_turn(uuid,text,text,jsonb)') IS NOT NULL "
            "AND to_regprocedure('li_api.expire_chat_replay_responses(integer)') IS NOT NULL;"
        ),
        "fenced chat attempt lifecycle is installed": (
            "SELECT to_regprocedure('li_api.mark_chat_turn_progress(uuid,text,uuid,text)') IS NOT NULL "
            "AND to_regprocedure('li_api.finish_chat_turn_attempt(uuid,text,uuid,text,jsonb)') IS NOT NULL;"
        ),
        "private-source correction boundary is installed": (
            "SELECT to_regprocedure('li_api.correct_explicit_memory(uuid,text,text,text,text,boolean)') "
            "IS NOT NULL;"
        ),
        "chat turns record progress and external-effect uncertainty": (
            "SELECT count(*)=3 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='li_runtime_data' "
            "AND c.relname='chat_turns' AND NOT a.attisdropped "
            "AND a.attname IN ('progress_stage','external_effect_started','external_effect_state');"
        ),
        "uncertain action state is enforced": (
            "SELECT pg_get_constraintdef(oid) LIKE '%uncertain%' FROM pg_constraint "
            "WHERE conname='action_intents_state_check_v038';"
        ),
    }
    for label, sql in checks.items():
        if scalar(sql) != "t":
            raise RuntimeError(f"Database invariant failed: {label}")

    synthetic_conversation = "00000000-0000-0000-0000-000000000038"
    synthetic_turn = "00000000-0000-0000-0000-000000000039"
    psql(
        "--command",
        "INSERT INTO li_conversation.conversations(id,owner_user_id) "
        f"SELECT '{synthetic_conversation}',id FROM li_memory.users "
        "WHERE user_key='christoffer'; "
        "INSERT INTO li_runtime_data.chat_turns("
        "id,owner_user_id,conversation_id,request_hash,state,response,finished_at,"
        "response_expires_at) "
        f"SELECT '{synthetic_turn}',id,'{synthetic_conversation}',repeat('a',64),"
        "'completed','{}',NOW(),NOW()-INTERVAL '1 second' FROM li_memory.users "
        "WHERE user_key='christoffer';",
        user="supabase_admin",
    )
    # Access-time retention must fail closed even before the periodic worker runs.
    expired_replay = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{synthetic_turn}',repeat('a',64))->>'outcome';",
        capture=True, user="supabase_admin",
    )
    if expired_replay.stdout.strip().splitlines()[-1] != "replay_expired":
        raise RuntimeError("Access-time replay expiry did not fail closed")
    if scalar(
        "SELECT state='replay_expired' AND response IS NULL "
        f"FROM li_runtime_data.chat_turns WHERE id='{synthetic_turn}';"
    ) != "t":
        raise RuntimeError("Expired replay did not retain a content-free idempotency tombstone")

    worker_expiry_turn = "00000000-0000-0000-0000-000000000044"
    psql(
        "--command",
        "INSERT INTO li_runtime_data.chat_turns("
        "id,owner_user_id,conversation_id,request_hash,state,response,finished_at,"
        "response_expires_at) "
        f"SELECT '{worker_expiry_turn}',id,'{synthetic_conversation}',repeat('9',64),"
        "'completed','{}',NOW(),NOW()-INTERVAL '1 second' FROM li_memory.users "
        "WHERE user_key='christoffer';",
        user="supabase_admin",
    )
    worker_expiry = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_retention_runtime; "
        "SELECT li_api.expire_chat_replay_responses(10);",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1]
    if worker_expiry != "1" or scalar(
        "SELECT state='replay_expired' AND response IS NULL "
        f"FROM li_runtime_data.chat_turns WHERE id='{worker_expiry_turn}';"
    ) != "t":
        raise RuntimeError("Retention worker replay cleanup did not preserve its tombstone")

    retry_turn = "00000000-0000-0000-0000-000000000040"
    first_claim = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{retry_turn}',repeat('b',64));",
        capture=True, user="supabase_admin",
    )
    first = json.loads(first_claim.stdout.strip().splitlines()[-1])
    if first.get("outcome") != "accepted" or not first.get("attempt_token"):
        raise RuntimeError("Initial chat attempt was not durably fenced")
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.bind_chat_turn_conversation('{retry_turn}',repeat('b',64),'{synthetic_conversation}'); "
        f"SELECT li_api.mark_chat_turn_progress('{retry_turn}',repeat('b',64),"
        f"'{first['attempt_token']}','message_saved'); "
        f"SELECT li_api.finish_chat_turn_attempt('{retry_turn}',repeat('b',64),"
        f"'{first['attempt_token']}','failed',NULL);",
        user="supabase_admin",
    )
    second_claim = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{retry_turn}',repeat('b',64));",
        capture=True, user="supabase_admin",
    )
    second = json.loads(second_claim.stdout.strip().splitlines()[-1])
    if (second.get("outcome") != "accepted"
            or second.get("attempt_token") == first.get("attempt_token")
            or second.get("progress_stage") != "message_saved"):
        raise RuntimeError("Safe retry did not preserve progress with a new attempt fence")
    stale_finish = psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.finish_chat_turn_attempt('{retry_turn}',repeat('b',64),"
        f"'{first['attempt_token']}','failed',NULL);",
        capture=True, check=False, user="supabase_admin",
    )
    if stale_finish.returncode == 0:
        raise RuntimeError("A stale chat worker could finish a newer attempt")
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.finish_chat_turn_attempt('{retry_turn}',repeat('b',64),"
        f"'{second['attempt_token']}','completed','{{}}'::jsonb);",
        user="supabase_admin",
    )

    prepared_turn = "00000000-0000-0000-0000-000000000041"
    prepared_claim = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{prepared_turn}',repeat('c',64));",
        capture=True, user="supabase_admin",
    )
    prepared = json.loads(prepared_claim.stdout.strip().splitlines()[-1])
    duplicate_claim = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{prepared_turn}',repeat('c',64))->>'outcome';",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1]
    conflict_claim = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{prepared_turn}',repeat('d',64))->>'outcome';",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1]
    if duplicate_claim != "in_progress" or conflict_claim != "conflict":
        raise RuntimeError("Duplicate start or payload mismatch did not stop safely")
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.mark_chat_turn_progress('{prepared_turn}',repeat('c',64),"
        f"'{prepared['attempt_token']}','message_saved'); "
        f"SELECT li_api.mark_chat_turn_progress('{prepared_turn}',repeat('c',64),"
        f"'{prepared['attempt_token']}','action_prepared');",
        user="supabase_admin",
    )
    psql(
        "--command",
        f"UPDATE li_runtime_data.chat_turns SET lease_expires_at=NOW()-INTERVAL '1 second' "
        f"WHERE id='{prepared_turn}';",
        user="supabase_admin",
    )
    prepared_retry = json.loads(psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{prepared_turn}',repeat('c',64));",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1])
    if (prepared_retry.get("outcome") != "accepted"
            or prepared_retry.get("progress_stage") != "message_saved"
            or prepared_retry.get("external_effect_state") != "prepared"):
        raise RuntimeError("An expired prepared-but-undispatched turn did not resume safely")

    dispatched_turn = "00000000-0000-0000-0000-000000000042"
    dispatched = json.loads(psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{dispatched_turn}',repeat('e',64));",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1])
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.mark_chat_turn_progress('{dispatched_turn}',repeat('e',64),"
        f"'{dispatched['attempt_token']}','provider_dispatched');",
        user="supabase_admin",
    )
    psql(
        "--command",
        f"UPDATE li_runtime_data.chat_turns SET lease_expires_at=NOW()-INTERVAL '1 second' "
        f"WHERE id='{dispatched_turn}';",
        user="supabase_admin",
    )
    dispatched_retry = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{dispatched_turn}',repeat('e',64))->>'outcome';",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1]
    if dispatched_retry != "uncertain":
        raise RuntimeError("An expired dispatched turn was eligible for blind replay")

    completed_effect_turn = "00000000-0000-0000-0000-000000000043"
    completed_effect = json.loads(psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.begin_chat_turn('{completed_effect_turn}',repeat('f',64));",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1])
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.mark_chat_turn_progress('{completed_effect_turn}',repeat('f',64),"
        f"'{completed_effect['attempt_token']}','provider_completed');",
        user="supabase_admin",
    )
    if scalar(
        "SELECT external_effect_started AND external_effect_state='completed' "
        f"FROM li_runtime_data.chat_turns WHERE id='{completed_effect_turn}';"
    ) != "t":
        raise RuntimeError("Known provider completion was not distinguished from dispatch")
    contradictory_effect = psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT li_api.mark_chat_turn_progress('{completed_effect_turn}',repeat('f',64),"
        f"'{completed_effect['attempt_token']}','provider_no_effect');",
        capture=True, check=False, user="supabase_admin",
    )
    if contradictory_effect.returncode == 0:
        raise RuntimeError("A completed provider effect could be downgraded to no effect")

    proposal_id = scalar(
        "INSERT INTO li_memory.memory_write_proposals(owner_user_id,proposed_by_agent,"
        "proposed_class,proposed_domain,proposed_value_text,proposed_truth_status,status) "
        "SELECT id,'synthetic-test','inference','testing','synthetic','inferred','pending' "
        "FROM li_memory.users WHERE user_key='christoffer' RETURNING id;"
    ).splitlines()[0]
    promoted_inference = psql(
        "--command",
        "SET SESSION AUTHORIZATION li_theo_runtime; "
        f"SELECT * FROM li_api.review_memory_proposal('{proposal_id}','approve',NULL,'confirmed',NULL,NULL);",
        capture=True, check=False, user="supabase_admin",
    )
    if promoted_inference.returncode == 0:
        raise RuntimeError("Database boundary allowed an inference to become confirmed")
    psql(
        "--command",
        f"UPDATE li_memory.memory_write_proposals SET status='needs_user_confirmation' "
        f"WHERE id='{proposal_id}';",
        user="supabase_admin",
    )
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_owner_runtime; "
        f"SELECT * FROM li_api.confirm_memory_proposal('{proposal_id}','confirm','synthetic');",
        user="supabase_admin",
    )
    psql(
        "--command",
        "SET SESSION AUTHORIZATION li_theo_runtime; "
        f"SELECT * FROM li_api.review_memory_proposal('{proposal_id}','approve',"
        "'retain as inference','inferred','current',0.9);",
        user="supabase_admin",
    )
    if scalar(
        "SELECT m.memory_class='inference' AND m.truth_status='inferred' "
        "AND m.confirmed_by_user IS FALSE FROM li_memory.memory_write_proposals p "
        "JOIN li_memory.memory_records m ON m.id=p.resulting_memory_id "
        f"WHERE p.id='{proposal_id}';"
    ) != "t":
        raise RuntimeError("Owner-confirmed inference acquired inconsistent truth metadata")

    original_memory = psql(
        "--tuples-only", "--no-align", "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        "SELECT li_api.store_explicit_memory('explicit_preference','testing',"
        "'shareable original','Synthetic correction','low',FALSE,'synthetic-test');",
        capture=True, user="supabase_admin",
    ).stdout.strip().splitlines()[-1]
    corrected = psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        f"SELECT * FROM li_api.correct_explicit_memory('{original_memory}',"
        "'private correction','testing','Synthetic correction','synthetic-private',TRUE);",
        capture=True, check=False, user="supabase_admin",
    )
    if corrected.returncode != 0 or scalar(
        "SELECT private_to_li FROM li_memory.memory_records "
        "WHERE value_text='private correction' AND deleted_at IS NULL;"
    ) != "t":
        raise RuntimeError("Private correction source did not restrict the replacement memory")
    psql(
        "--command",
        f"DELETE FROM li_conversation.conversations WHERE id='{synthetic_conversation}';",
        user="supabase_admin",
    )
    if scalar(
        f"SELECT count(*) FROM li_runtime_data.chat_turns WHERE id='{synthetic_turn}';"
    ) != "0":
        raise RuntimeError("Conversation deletion did not cascade to its chat turns")

    allowed = psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        "SELECT count(*) FROM li_api.get_primary_user();",
        capture=True,
        check=False,
        user="supabase_admin",
    )
    if allowed.returncode != 0:
        raise RuntimeError(
            "Backend runtime could not call its approved API capability: "
            + allowed.stderr.strip()
        )

    denied = psql(
        "--command",
        "SET SESSION AUTHORIZATION li_backend_runtime; "
        "SELECT count(*) FROM li_memory.memory_records;",
        capture=True,
        check=False,
        user="supabase_admin",
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
        or "schema version 0.39 is already claimed" not in replay.stderr.lower()
    ):
        raise RuntimeError("Latest migration did not fail closed on replay")

    if scalar("SELECT count(*) FROM li_memory.schema_versions;") != "39":
        raise RuntimeError("Replay attempt changed schema-version history")


def main() -> None:
    validate_inventory()
    bootstrap_supabase_roles()
    apply_history()
    validate_result()
    print("Disposable database migration validation passed.")


if __name__ == "__main__":
    main()
