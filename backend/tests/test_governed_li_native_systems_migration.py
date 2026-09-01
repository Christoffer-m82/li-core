from pathlib import Path


def test_migration_035_uses_one_relation_per_alter_table_and_preserves_boundaries():
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "035_governed_li_native_systems.sql"
    ).read_text(encoding="utf-8").lower()

    governed_tables = (
        "skills",
        "skill_outcomes",
        "context_selections",
        "conversation_compressions",
        "watcher_events",
        "temporary_worker_runs",
        "model_registry",
        "tool_registry",
        "delivery_adapters",
        "heavy_work_audit",
    )
    for table in governed_tables:
        assert (
            f"alter table li_runtime_data.{table} enable row level security;" in sql
        )

    assert sql.count("alter table ") == len(governed_tables)
    assert "temporary function-owner authority was not removed" in sql
    assert "governed-system direct table boundary is broader than intended" in sql
    assert "migration 035 requires exactly one active owner" in sql
    assert sql.index("insert into li_memory.schema_versions") < sql.rindex("commit;")
