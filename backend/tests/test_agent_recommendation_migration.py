from pathlib import Path


def test_recommendation_fix_qualifies_user_status_column():
    migration = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "019_fix_agent_recommendation_status_ambiguity.sql"
    ).read_text(encoding="utf-8")

    assert migration.count("u.status='active'") == 2
    assert "status='active' LIMIT 1" not in migration
    assert "r.status='pending_approval'" in migration
