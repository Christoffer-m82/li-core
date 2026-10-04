from datetime import UTC, datetime

import psycopg
from fastapi.testclient import TestClient

from app import runtime_data
from app.auth import require_api_token
from app.main import app


def teardown_function():
    app.dependency_overrides.clear()


def test_activity_requires_authentication():
    assert TestClient(app).get("/specialists/activity").status_code == 401


def test_activity_endpoint_is_metadata_only_and_uses_roster(monkeypatch):
    calls = []

    def activity(keys):
        calls.append(keys)
        return [{"specialist_key": "nora", "active": True,
                 "last_activity_at": datetime(2026, 9, 1, tzinfo=UTC)}]

    monkeypatch.setattr("app.main.specialist_activity", activity)
    app.dependency_overrides[require_api_token] = lambda: None
    response = TestClient(app).get("/specialists/activity")
    assert response.status_code == 200
    assert response.json()["scope"] == "retained_interactions"
    assert len(calls[0]) == 12
    assert "heimdall" not in calls[0]
    assert set(response.json()["activity"][0]) == {
        "specialist_key", "active", "last_activity_at"}


def test_activity_outage_is_sanitized(monkeypatch):
    def unavailable(keys):
        raise runtime_data.RuntimeDataError("synthetic private detail")

    monkeypatch.setattr("app.main.specialist_activity", unavailable)
    app.dependency_overrides[require_api_token] = lambda: None
    response = TestClient(app).get("/specialists/activity")
    assert response.status_code == 503
    assert "synthetic private" not in response.text


def test_database_aggregate_does_not_fetch_history_contents(monkeypatch):
    calls = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params):
            calls.append((sql, params))

        def fetchall(self):
            return [{"specialist_key": "nora", "active": False, "last_activity_at": None}]

    class Connection(Cursor):
        def cursor(self):
            return Cursor()

    monkeypatch.setattr(runtime_data.psycopg, "connect", lambda **kwargs: Connection())
    assert runtime_data.specialist_activity(["nora"])[0]["last_activity_at"] is None
    sql, params = calls[0]
    assert params == (["nora"],)
    assert "li_api.list_agent_analytics_events()" in sql
    assert "GROUP BY specialist_key" in sql
    assert "CURRENT_TIMESTAMP" in sql
    assert all(word not in sql for word in ("request_text", "outcome", "LIMIT", "li_runtime_data."))


def test_database_failure_is_sanitized(monkeypatch):
    def fail(**kwargs):
        raise psycopg.OperationalError("synthetic credential detail")

    monkeypatch.setattr(runtime_data.psycopg, "connect", fail)
    try:
        runtime_data.specialist_activity(["nora"])
    except runtime_data.RuntimeDataError as exc:
        assert str(exc) == "Specialist activity unavailable."
    else:
        raise AssertionError("Database failure must not become empty activity")
