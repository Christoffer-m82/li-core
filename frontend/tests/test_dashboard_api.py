from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import MAX_UPLOAD_BYTES, app
from app.security import require_user


def signed_in_client() -> TestClient:
    app.dependency_overrides[require_user] = lambda: "owner@example.com"
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_specialist_roster_is_single_and_inactive_without_real_events(monkeypatch):
    async def backend(*args, **kwargs):
        return httpx.Response(200, json={"interactions": []})
    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get("/api/specialists")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["specialists"]) == 12
    assert payload["live_events_available"] is True
    assert all(item["active"] is False for item in payload["specialists"])


def test_specialist_history_does_not_fabricate_transcripts(monkeypatch):
    async def backend(*args, **kwargs):
        return httpx.Response(200, json={"interactions": []})
    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get("/api/specialists/nora/interactions")
    assert response.status_code == 200
    assert response.json()["interactions"] == []
    assert response.json()["live_events_available"] is True


def test_conversation_delete_uses_owner_authority(monkeypatch):
    conversation_id = "00000000-0000-0000-0000-000000000001"
    observed = {}

    async def backend(settings, method, path, json_body=None, authority="li"):
        observed.update(method=method, path=path, body=json_body, authority=authority)
        return httpx.Response(200, json={"deleted": True, "specialist_interactions_deleted": 1})

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().post(
        f"/api/conversations/{conversation_id}/delete",
        json={"confirmation": "delete_private_conversation"},
    )
    assert response.status_code == 200
    assert observed["authority"] == "owner"
    assert observed["path"] == f"/owner/conversations/{conversation_id}/delete"


def test_upload_rejects_unsupported_type():
    response = signed_in_client().post(
        "/api/uploads", files={"file": ("unsafe.exe", b"MZ", "application/octet-stream")}
    )
    assert response.status_code == 415


def test_upload_rejects_oversized_file():
    response = signed_in_client().post(
        "/api/uploads", files={"file": ("large.txt", b"x" * (MAX_UPLOAD_BYTES + 1), "text/plain")}
    )
    assert response.status_code == 413


def test_upload_rejects_oversized_body_before_parsing():
    response = signed_in_client().post(
        "/api/uploads",
        content=b"x",
        headers={"content-type": "multipart/form-data", "content-length": str(MAX_UPLOAD_BYTES * 2)},
    )
    assert response.status_code == 413


def test_valid_upload_is_temporary_by_default(monkeypatch):
    async def backend(*args, **kwargs):
        assert kwargs["json_body"]["save"] is False
        return httpx.Response(200, json={"retained": False, "analysis_text": "hello"})
    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().post(
        "/api/uploads", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 200
    assert response.json()["retained"] is False


def test_artifact_ids_cannot_traverse_paths():
    response = signed_in_client().get("/api/artifacts/..%2Fsecret")
    assert response.status_code in {400, 404}


def test_dashboard_contains_one_roster_and_no_legacy_boxes():
    html = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert html.count('id="specialist-list"') == 1
    assert "How Li works" not in html
    assert "Ask Li Anything" not in html
    assert 'id="conversation-panel"' in html


def test_client_includes_activity_sorting_theme_fallback_and_real_artifact_guard():
    javascript = (Path(__file__).parents[1] / "static" / "assets" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "Number(b.active) - Number(a.active)" in javascript
    assert "prefers-color-scheme: light" in javascript
    assert "attachment.url ? 'a' : 'span'" in javascript
    assert "Save privately" in javascript
    assert "artifact-retention" in javascript
    assert "coords.latitude" in javascript
    assert "localStorage.setItem('li-theme', choice)" in javascript


def test_responsive_breakpoints_are_present():
    css = (Path(__file__).parents[1] / "static" / "assets" / "app.css").read_text(
        encoding="utf-8"
    )
    assert "@media(max-width:1050px)" in css
    assert "@media(max-width:680px)" in css


def test_agent_analytics_page_and_controls_are_rendered():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'data-view-panel="agents"' in html
    assert 'id="analytics-period"' in html
    assert 'id="relevance-cadence"' in html
    assert "approved · execution pending".casefold() in javascript.casefold()


def test_agent_analytics_bff_proxy(monkeypatch):
    async def backend(*args, **kwargs):
        assert args[2] == "/agents/analytics?period=90d"
        return httpx.Response(200, json={"period": "90d", "agents": []})
    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get("/api/agents/analytics?period=90d")
    assert response.status_code == 200
    assert response.json()["period"] == "90d"


def test_agent_execution_uses_owner_boundary(monkeypatch):
    observed = {}
    async def backend(*args, **kwargs):
        observed.update(path=args[2], authority=kwargs.get("authority"))
        return httpx.Response(200, json={"outcome": "no_op"})
    monkeypatch.setattr("app.main.request_backend", backend)
    rec_id, key = "d7d0fbbb-d650-4ec3-a053-f5e6022267da", "6e12f41d-c909-4353-9435-e0d4779cfa43"
    response = signed_in_client().post(f"/api/agents/recommendations/{rec_id}/execute", json={
        "confirmation": "confirm_permanent_agent_change", "idempotency_key": key})
    assert response.status_code == 200
    assert observed == {"path": f"/owner/agents/recommendations/{rec_id}/execute", "authority": "owner"}


def test_backend_overview_is_read_only_and_proxies_capability_inventory(monkeypatch):
    observed = {}

    async def backend(*args, **kwargs):
        observed.update(method=args[1], path=args[2])
        return httpx.Response(200, json={"read_only": True, "capabilities": []})

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get("/api/capabilities")
    assert response.status_code == 200
    assert response.json()["read_only"] is True
    assert observed == {"method": "GET", "path": "/capabilities"}


def test_backend_overview_page_has_filters_live_metadata_and_no_mutating_controls():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'data-view-panel="backend"' in html
    assert 'id="capability-search"' in html
    assert 'id="capability-status"' in html
    assert "Last refreshed" in javascript
    assert "fetch('/api/capabilities')" in javascript
    backend_section = html.split('data-view-panel="backend"', 1)[1].split('</section>', 1)[0]
    assert "type=\"submit\"" not in backend_section
