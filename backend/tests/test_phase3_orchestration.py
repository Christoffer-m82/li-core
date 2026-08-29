from pathlib import Path

from app.li_runtime import specialist_recording_context, talk_to_li
from app.specialist_runtime import SpecialistConsultation, SpecialistResult


def _memory(domain: str, *, private: bool = False) -> dict[str, object]:
    return {
        "memory_id": domain,
        "memory_class": "explicit_preference",
        "domain": domain,
        "title": domain,
        "value_text": f"private {domain}",
        "truth_status": "confirmed",
        "temporal_status": "current",
        "sensitivity": "personal",
        "private_to_li": private,
        "confidence": 1.0,
        "confirmed_by_user": True,
    }


def test_context_and_temporary_upload_are_scoped_to_routed_specialists(monkeypatch):
    monkeypatch.setattr(
        "app.li_runtime._retrieve_relevant_memories",
        lambda *a, **k: [_memory("health"), _memory("finance"), _memory("health", private=True)],
    )
    observed = {}

    def consult(names, requests):
        observed.update(requests)
        return SpecialistConsultation(
            results={
                name: SpecialistResult(
                    recommendation=f"{name} advice", confidence=0.6, sources_needed=False
                )
                for name in names
            }
        )

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "Li synthesis")
    talk_to_li(
        "Compare my health and finance options and recommend a plan.",
        temporary_upload_context="one-request file",
    )
    assert set(observed) == {"sofia", "james"}
    assert [m.domain for m in observed["sofia"].canonical_memory] == ["health"]
    assert [m.domain for m in observed["james"].canonical_memory] == ["finance"]
    assert all(req.temporary_upload_context == "one-request file" for req in observed.values())


def test_real_lifecycle_metadata_is_recorded_without_fabricated_analytics(monkeypatch):
    monkeypatch.setattr("app.li_runtime._retrieve_relevant_memories", lambda *a, **k: [])
    started, finished = [], []
    monkeypatch.setattr(
        "app.li_runtime.start_interaction",
        lambda *args: started.append(args) or f"event-{len(started)}",
    )
    monkeypatch.setattr(
        "app.li_runtime.finish_interaction", lambda *args: finished.append(args) or True
    )
    monkeypatch.setattr(
        "app.li_runtime.consult_specialists",
        lambda names, request: SpecialistConsultation(
            results={
                "sofia": SpecialistResult(
                    recommendation="Validated advice", confidence=0.7, sources_needed=False
                )
            }
        ),
    )
    monkeypatch.setattr("app.li_runtime.generate_claude_text", lambda **kwargs: "Li answer")
    with specialist_recording_context("00000000-0000-0000-0000-000000000001"):
        talk_to_li("Ask Sofia for medical advice.")
    assert started[0][2:] == (
        "sofia",
        "Ask Sofia for medical advice.",
        "explicit",
        "solo",
        "explicit_specialist",
        "User explicitly named the selected registered specialist(s).",
    )
    outcome = finished[0][2]
    assert outcome["validation"]["validated"] is True
    assert outcome["validation"]["used_in_final"] is None
    assert outcome["validation"]["action_converted"] is None
    assert "transcript" not in outcome


def test_migration_026_expands_registry_and_adds_lifecycle_fields():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "026_generalized_specialist_orchestration.sql"
    ).read_text(encoding="utf-8")
    for key in (
        "sofia",
        "marco",
        "elena",
        "amelia",
        "freja",
        "oliver",
        "james",
        "victor",
        "nora",
        "milo",
        "iris",
        "clara",
    ):
        assert f"'{key}'" in sql
    for field in ("selection_mode", "group_mode", "route_category", "route_reason", "elapsed_ms"):
        assert field in sql
    assert (
        "VALUES('0.26','Generalized permanent specialist orchestration lifecycle metadata')" in sql
    )


def test_migration_026_safely_recreates_all_changed_table_return_types():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "026_generalized_specialist_orchestration.sql"
    ).read_text(encoding="utf-8")
    old_shape = (
        "request_text TEXT,outcome JSONB,started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,"
        "updated_at TIMESTAMPTZ"
    )
    new_shape = (
        f"{old_shape},\n explicit_request BOOLEAN,selection_mode TEXT,group_mode TEXT,"
        "route_category TEXT,route_reason TEXT,\n elapsed_ms BIGINT"
    )
    assert new_shape in sql
    assert "CREATE OR REPLACE FUNCTION li_api.list_specialist_interactions" not in sql
    assert "DROP FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER)" in sql
    assert "DROP FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER) CASCADE" not in sql
    assert "pg_catalog.pg_depend" in sql
    assert "dependent objects exist" in sql
    assert "migration 026 never uses CASCADE" in sql

    old_analytics_shape = (
        "explicit_request BOOLEAN,used_in_final BOOLEAN,\n action_taken BOOLEAN,"
        "topic_keys TEXT[]"
    )
    new_analytics_shape = (
        f"{old_analytics_shape},selection_mode TEXT,group_mode TEXT,"
        "route_category TEXT"
    )
    assert new_analytics_shape in sql
    assert "CREATE OR REPLACE FUNCTION li_api.list_agent_analytics_events" not in sql
    assert "DROP FUNCTION li_api.list_agent_analytics_events()" in sql
    assert "DROP FUNCTION li_api.list_agent_analytics_events() CASCADE" not in sql
    assert "Cannot safely replace list_agent_analytics_events" in sql

    dependency_check = sql.index("pg_catalog.pg_depend")
    owner_grant = sql.index("GRANT li_memory_function_owner TO postgres")
    set_role = sql.index("SET LOCAL ROLE li_memory_function_owner")
    function_drop = sql.index("DROP FUNCTION li_api.list_specialist_interactions")
    function_create = sql.index("CREATE FUNCTION li_api.list_specialist_interactions")
    function_revoke = sql.index(
        "REVOKE ALL ON FUNCTION li_api.list_specialist_interactions"
    )
    function_grant = sql.index(
        "GRANT EXECUTE ON FUNCTION li_api.list_specialist_interactions"
    )
    assert (
        dependency_check < owner_grant < set_role < function_drop < function_create
        < function_revoke < function_grant
    )
    analytics_dependency_check = sql.index(
        "Cannot safely replace list_agent_analytics_events"
    )
    analytics_drop = sql.index("DROP FUNCTION li_api.list_agent_analytics_events()")
    analytics_create = sql.index("CREATE FUNCTION li_api.list_agent_analytics_events()")
    analytics_revoke = sql.index(
        "REVOKE ALL ON FUNCTION li_api.start_specialist_interaction"
    )
    analytics_grant = sql.index(
        "GRANT EXECUTE ON FUNCTION li_api.start_specialist_interaction"
    )
    assert (
        analytics_dependency_check < owner_grant < set_role < analytics_drop
        < analytics_create < analytics_revoke < analytics_grant
    )


def test_migration_026_preserves_owner_acl_and_temporary_authority_boundaries():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "026_generalized_specialist_orchestration.sql"
    ).read_text(encoding="utf-8")
    assert "function_owner IS DISTINCT FROM 'li_memory_function_owner'" in sql
    assert "added_owner_membership BOOLEAN NOT NULL" in sql
    assert "added_schema_create BOOLEAN NOT NULL" in sql
    assert "TO li_memory_api" in sql
    assert "li_backend_runtime" in sql
    assert "li_retention_runtime" in sql
    assert "list_specialist_interactions owner changed unexpectedly" in sql
    assert "list_agent_analytics_events owner changed unexpectedly" in sql
    assert "Backend runtime lost analytics event execution" in sql
    assert "Retention runtime gained analytics event execution" in sql
    assert "Temporary li_api CREATE authority was not removed" in sql
    assert "Temporary function-owner authority was not removed" in sql


def test_migration_026_is_single_transaction_and_failed_attempt_is_rerunnable():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "026_generalized_specialist_orchestration.sql"
    ).read_text(encoding="utf-8")
    statements = [line.strip() for line in sql.splitlines()]
    assert statements.count("BEGIN;") == 1
    assert statements.count("COMMIT;") == 1
    assert statements[0] == "BEGIN;"
    assert statements[-1] == "COMMIT;"
    assert sql.index("INSERT INTO li_memory.schema_versions") < sql.rindex("COMMIT;")


def test_migration_027_qualifies_status_and_preserves_function_boundary():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "027_fix_generalized_specialist_history_status_ambiguity.sql"
    ).read_text(encoding="utf-8")
    assert "WHERE u.user_key='christoffer' AND u.status='active'" in sql
    assert "CREATE OR REPLACE FUNCTION li_api.list_specialist_interactions" in sql
    assert "li_memory_function_owner" in sql
    assert "TO li_memory_api" in sql
    assert "li_retention_runtime" in sql
    assert sql.splitlines()[0] == "BEGIN;"
    assert sql.splitlines()[-1] == "COMMIT;"
