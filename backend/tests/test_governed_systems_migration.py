from pathlib import Path


SQL = (Path(__file__).resolve().parents[2] / "memory" / "migrations" /
       "035_governed_li_native_systems.sql").read_text(encoding="utf-8")


def test_migration_is_immutable_ordered_and_migration_ready():
    assert "Migration 035 requires applied schema 0.34" in SQL
    assert "VALUES('0.35'" in SQL
    assert SQL.strip().endswith("COMMIT;")


def test_migration_covers_all_nine_durable_boundaries():
    for name in ("skills", "skill_outcomes", "context_selections", "conversation_compressions",
                 "watcher_events", "temporary_worker_runs", "model_registry", "tool_registry",
                 "delivery_adapters", "heavy_work_audit"):
        assert f"li_runtime_data.{name}" in SQL
    assert "search_conversation_history" in SQL
    assert "CHECK(NOT enabled)" in SQL
    assert "CHECK(NOT grants_authority)" in SQL


def test_historical_search_is_bounded_and_does_not_write_memory():
    function = SQL.split("CREATE FUNCTION li_api.search_conversation_history", 1)[1]
    assert "LIMIT LEAST(GREATEST(p_limit,1),25)" in function
    assert "INSERT INTO li_memory.memories" not in function
