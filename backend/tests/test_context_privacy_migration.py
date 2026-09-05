from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_migration_037_returns_privacy_metadata_without_broadening_authority():
    sql = (ROOT / "memory" / "migrations" / "037_conversation_context_privacy.sql").read_text(
        encoding="utf-8"
    )
    assert "privacy_metadata JSONB" in sql
    assert "recent.privacy_metadata" in sql
    assert "never uses CASCADE" in sql
    assert "DROP FUNCTION li_api.get_recent_conversation_messages(UUID,INTEGER);" in sql
    assert "TO li_memory_api" in sql
    assert "li_retention_runtime" in sql
    assert "Temporary li_api CREATE authority was not removed" in sql
    assert sql.splitlines()[0] == "BEGIN;"
    assert sql.splitlines()[-1] == "COMMIT;"


def test_database_query_requests_message_privacy_metadata():
    source = (ROOT / "backend" / "app" / "database.py").read_text(encoding="utf-8")
    query = source.split("def get_recent_conversation_messages", 1)[1].split(
        "def delete_conversation_for_owner", 1
    )[0]
    assert "message_id, role, content, privacy_metadata, created_at" in query
