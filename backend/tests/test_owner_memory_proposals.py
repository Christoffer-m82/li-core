from datetime import UTC, datetime
from pathlib import Path
from fastapi.testclient import TestClient

from app.auth import require_owner_api_token
from app.database import get_owner_memory_proposals
from app.main import app


def proposal() -> dict[str, object]:
    return {
        "proposed_by_agent": "li",
        "proposed_class": "inference",
        "proposed_domain": "preferences",
        "proposed_value_text": "Christoffer may prefer green notebooks.",
        "proposed_truth_status": "inferred",
        "proposed_temporal_status": "current",
        "proposed_sensitivity": "personal",
        "proposal_status": "needs_user_confirmation",
        "reason": "Repeated preference signal.",
        "review_note": "Please confirm before promotion.",
        "owner_confirmation_required": True,
        "created_at": datetime(2026, 9, 6, tzinfo=UTC),
        "reviewed_at": datetime(2026, 9, 6, 1, tzinfo=UTC),
    }


def test_owner_endpoint_is_authenticated_read_only_and_redacted(monkeypatch) -> None:
    item = proposal()
    observed: dict[str, object] = {}

    def list_proposals(*, limit: int) -> list[dict[str, object]]:
        observed["limit"] = limit
        return [{**item, "source_reference": "must-not-cross-owner-boundary"}]

    monkeypatch.setattr("app.main.get_owner_memory_proposals", list_proposals)
    assert TestClient(app).get("/owner/memory/proposals").status_code == 401

    app.dependency_overrides[require_owner_api_token] = lambda: None
    try:
        client = TestClient(app)
        response = client.get("/owner/memory/proposals", params={"limit": 7})
        invalid_limit = client.get("/owner/memory/proposals", params={"limit": 51})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert invalid_limit.status_code == 422
    assert observed == {"limit": 7}
    assert response.json()[0]["owner_confirmation_required"] is True
    assert "proposal_id" not in response.json()[0]
    assert "source_reference" not in response.json()[0]


def test_database_query_uses_owner_connection_and_bounded_function(monkeypatch) -> None:
    item = proposal()
    observed: dict[str, object] = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, parameters) -> None:
            observed["query"] = query
            observed["parameters"] = parameters

        def fetchall(self):
            return [item]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr("app.database._owner_connect", lambda: Connection())
    result = get_owner_memory_proposals(limit=12)

    assert "li_api.list_owner_memory_proposals(%s)" in str(observed["query"])
    assert observed["parameters"] == (12,)
    assert result == [item]


def test_migration_is_owner_only_read_only_and_excludes_private_source_fields() -> None:
    sql = (
        Path(__file__).parents[2]
        / "memory"
        / "migrations"
        / "040_owner_memory_proposal_inspection.sql"
    ).read_text(encoding="utf-8").lower()

    signature = "li_api.list_owner_memory_proposals(integer)"
    assert "migration 040 requires applied schema 0.39" in sql
    assert "schema version 0.40 is already claimed" in sql
    assert f"grant execute on function {signature}" in sql
    assert "to li_memory_owner_confirmation" in sql
    assert "has_function_privilege(\n      'li_memory_api'" in sql
    assert "has_function_privilege(\n      'li_memory_theo'" in sql
    assert "has_table_privilege(\n      'li_memory_owner_confirmation'" in sql
    returned_columns = sql.split("returns table (", 1)[1].split(")\nlanguage", 1)[0]
    assert "source_reference" not in returned_columns
    assert "metadata" not in returned_columns
    assert "source_reference" not in sql.split("return query", 1)[1]
    assert "insert into li_memory.schema_versions" in sql
