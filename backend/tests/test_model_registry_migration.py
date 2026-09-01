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
    assert "model registry direct table boundary is broader than intended" in sql


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
    assert sql.index("insert into li_memory.schema_versions") < sql.rindex("commit;")
