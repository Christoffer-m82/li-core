from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import require_owner_api_token
from app.main import app


def test_owner_execution_endpoint_is_separate_and_typed(monkeypatch):
    app.dependency_overrides[require_owner_api_token] = lambda: None
    observed = {}
    monkeypatch.setattr("app.main.execute_agent_recommendation",
                        lambda *args: observed.update(args=args) or {"outcome": "no_op", "status": "executed"})
    rec_id, key = uuid4(), uuid4()
    response = TestClient(app).post(f"/owner/agents/recommendations/{rec_id}/execute", json={
        "confirmation": "confirm_permanent_agent_change", "idempotency_key": str(key)})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert observed["args"][:3] == (str(rec_id), str(key), "confirm_permanent_agent_change")


def test_owner_execution_rejects_ordinary_approval_payload():
    app.dependency_overrides[require_owner_api_token] = lambda: None
    response = TestClient(app).post(f"/owner/agents/recommendations/{uuid4()}/execute",
                                    json={"decision": "approve"})
    app.dependency_overrides.clear()
    assert response.status_code == 422


def test_migration_has_atomic_idempotent_immutable_safe_semantics():
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "020_controlled_agent_governance_executor.sql").read_text(encoding="utf-8")
    assert "UNIQUE(recommendation_id,idempotency_key)" in sql
    assert "one_successful_agent_execution" in sql
    assert "immutable_agent_execution_audit" in sql
    assert "Explicit owner confirmation is required" in sql
    assert "WHEN 'remove'" in sql and "v_outcome := 'executed_as_archive'" in sql
    assert "WHEN 'keep' THEN v_outcome := 'no_op'" in sql
    assert "Subject agent is not in registry" in sql
    assert "Agent key already exists" in sql
    assert "EXCEPTION WHEN OTHERS" in sql
    assert "TO li_memory_owner_confirmation" in sql
    assert "FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo" in sql
