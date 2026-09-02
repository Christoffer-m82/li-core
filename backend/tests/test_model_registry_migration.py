from pathlib import Path


def migration_sql() -> str:
    return (Path(__file__).parents[2] / "memory" / "migrations" /
            "036_owner_model_registry_configuration.sql").read_text(encoding="utf-8").lower()


def test_owner_only_function_boundary_and_no_direct_dml():
    sql = migration_sql()
    signature = ("li_api.configure_model_registry(uuid,text,text,text,text,text,text,jsonb,"
                 "integer,jsonb,text,integer)")
    assert f"grant execute on function {signature} to li_memory_owner_confirmation" in sql
    for role in ("li_backend_runtime", "li_memory_theo", "li_retention_runtime"):
        assert f"has_function_privilege('{role}','{signature}','execute')" in sql
    assert "revoke all privileges on li_runtime_data.model_registry,li_runtime_data.model_registry_audit" in sql
    assert "role % retained direct privileges on %" in sql


def test_known_claude_only_and_secret_fields_rejected():
    sql = migration_sql()
    assert "('claude-primary','anthropic','claude-sonnet-5')" in sql
    assert "model is not present in the approved code/config registry" in sql
    for field in ("api_key", "secret", "credential", "password", "authorization"):
        assert field in sql
    assert "cost metadata contains an unsupported or secret-like field" in sql


def test_audit_idempotency_versioning_and_primary_invariants():
    sql = migration_sql()
    assert "unique(owner_user_id,request_id)" in sql
    assert "idempotent',true" in sql
    assert "model registry version conflict" in sql
    assert "configuration_version=configuration_version+1" in sql
    assert "is_primary=true" in sql
    assert "insert into li_runtime_data.model_registry_audit" in sql
    assert "before update or delete on li_runtime_data.model_registry_audit" in sql
    assert "model registry audit is append-only" in sql
    assert "previous_metadata" in sql and "new_metadata" in sql
    assert "update li_runtime_data.model_registry_audit" not in sql
    assert "delete from li_runtime_data.model_registry_audit" not in sql


def test_read_only_status_boundary_and_transactional_schema_gate():
    sql = migration_sql()
    assert "create function li_api.list_model_registry_overview()" in sql
    assert "grant execute on function li_api.list_model_registry_overview() to li_memory_api" in sql
    assert "migration 036 requires applied schema 0.35" in sql
    assert sql.strip().startswith("begin;")
    assert "schema version 0.36 is already claimed" in sql
    assert sql.index("insert into li_memory.schema_versions") < sql.rindex("commit;")


def test_table_and_function_owner_contexts_cover_trigger_and_acls():
    sql = migration_sql()
    owner_check = "model_registry has unexpected owner"
    set_function_owner = "set local role li_memory_function_owner"
    function_acl = "revoke all on function li_api.configure_model_registry"
    reset_role = "reset role;"
    trigger = "create trigger model_registry_audit_append_only"
    table_acl = ("revoke all privileges on li_runtime_data.model_registry,"
                 "li_runtime_data.model_registry_audit")
    assert "join pg_catalog.pg_roles r on r.oid=c.relowner" in sql
    assert sql.index(owner_check) < sql.index("alter table li_runtime_data.model_registry")
    first_set = sql.index(set_function_owner)
    first_reset = sql.index(reset_role)
    trigger_index = sql.index(trigger)
    second_set = sql.index(set_function_owner, first_set + 1)
    second_reset = sql.index(reset_role, first_reset + 1)
    assert first_set < first_reset < trigger_index < second_set
    assert second_set < sql.index(function_acl) < second_reset < sql.index(table_acl)
    assert "function % has unexpected owner" in sql
    assert "model registry table has unexpected owner" in sql


def test_append_only_audit_and_acl_cleanup_are_asserted_for_every_runtime_role():
    sql = migration_sql()
    assert "model_registry_function_select" in sql
    assert "model_registry_function_update" in sql
    assert "for all to li_memory_function_owner" not in sql
    assert "function owner table boundary is incorrect" in sql
    assert "role % retained direct privileges on %" in sql
    assert "temporary li_api create authority was not removed" in sql
    assert "temporary function-owner authority was not removed" in sql
    assert "tgrelid='li_runtime_data.model_registry_audit'::regclass" in sql
    assert "tgfoid='li_api.reject_model_registry_audit_mutation()'::regprocedure" in sql
    assert "model registry unexpectedly owns a sequence" in sql
