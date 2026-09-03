from pathlib import Path
from uuid import uuid4

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
        headers={
            "content-type": "multipart/form-data",
            "content-length": str(MAX_UPLOAD_BYTES * 2),
        },
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


def test_chat_forwards_bounded_temporary_upload_context(monkeypatch):
    observed = {}

    async def backend(*args, **kwargs):
        observed.update(kwargs["json_body"])
        return httpx.Response(
            200, json={"response": "ok", "conversation_id": "00000000-0000-0000-0000-000000000001"}
        )

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().post(
        "/api/chat",
        json={"message": "Analyse it", "temporary_upload_context": "File: notes.txt\nhello"},
    )
    assert response.status_code == 200
    assert observed["temporary_upload_context"] == "File: notes.txt\nhello"


def test_artifact_library_is_proxied_from_governed_storage(monkeypatch):
    async def backend(*args, **kwargs):
        assert args[2] == "/artifacts"
        return httpx.Response(200, json={"artifacts": []})

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get("/api/artifacts")
    assert response.status_code == 200
    assert response.json() == {"artifacts": []}


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
    assert "temporaryUploadContext" in javascript
    assert "loadArtifacts" in javascript
    assert "coords.latitude" in javascript
    assert "localStorage.setItem('li-theme', choice)" in javascript
    assert "setInterval(loadSpecialists, 1200)" in javascript
    assert "item.active ? ' active' : ''" in javascript
    assert "renderActionIntent" in javascript
    assert "data.action_intents || []" in javascript
    assert "decision: value" in javascript
    assert "specialist_interaction_ids" not in javascript


def test_action_intent_decision_proxy_forwards_only_safe_decision(monkeypatch):
    observed = {}

    async def backend(*args, **kwargs):
        observed.update(path=args[2], body=kwargs["json_body"])
        return httpx.Response(200, json={"approval_state": "denied"})

    monkeypatch.setattr("app.main.request_backend", backend)
    intent_id = "d7d0fbbb-d650-4ec3-a053-f5e6022267da"
    response = signed_in_client().post(
        f"/api/action-intents/{intent_id}/decision", json={"decision": "deny"}
    )
    assert response.status_code == 200
    assert observed == {"path": f"/li/action-intents/{intent_id}/decision",
                        "body": {"decision": "deny"}}


def test_active_only_specialist_pulse_returns_to_idle_from_real_events():
    css = (Path(__file__).parents[1] / "static" / "assets" / "app.css").read_text(encoding="utf-8")
    javascript = (Path(__file__).parents[1] / "static" / "assets" / "app.js").read_text(
        encoding="utf-8"
    )
    assert ".specialist-card.active" in css and "animation:active-card" in css
    assert "clearInterval(specialistPoll); await loadSpecialists()" in javascript
    assert "const recommendation = entry.outcome?.recommendation" in javascript
    assert "Interaction completed." not in javascript


def test_responsive_breakpoints_are_present():
    css = (Path(__file__).parents[1] / "static" / "assets" / "app.css").read_text(encoding="utf-8")
    assert "@media(max-width:1050px)" in css
    assert "@media(max-width:680px)" in css


def test_phone_navigation_keeps_all_primary_views_reachable():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    css = (root / "static" / "assets" / "app.css").read_text(encoding="utf-8")
    bottom_navigation = html.split('<nav class="bottom-nav"', 1)[1].split("</nav>", 1)[0]

    assert bottom_navigation.count('class="nav-item') == 5
    assert 'data-view="history"' in bottom_navigation
    assert ".bottom-nav .nav-item:nth-child(4){display:none}" not in css


def test_productized_home_uses_only_real_backed_collections():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    for element_id in ("home-conversations", "home-open-loops", "home-briefs", "home-artifacts"):
        assert f'id="{element_id}"' in html
    for endpoint in ("/api/conversations", "/api/open-loops", "/api/proactive-briefs", "/api/artifacts"):
        assert endpoint in javascript
    assert "confidence" not in html.casefold()
    assert "fake" not in html.casefold()


def test_specialist_detail_is_truthful_and_has_live_history_tabs():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'data-specialist-tab="live"' in html
    assert 'data-specialist-tab="history"' in html
    assert 'id="handoff-to-li"' in html
    assert "No live specialist interaction" in javascript
    assert "freshness_evidence" in javascript
    assert "Not measured" in javascript
    assert "confidence" not in javascript[javascript.index("function evidencePanel"):javascript.index("function renderLiveInteraction")]


def test_voice_state_drives_all_visible_li_orbs_and_respects_reduced_motion():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    css = (root / "static" / "assets" / "app.css").read_text(encoding="utf-8")
    assert html.count('class="li-orb') >= 2
    assert "$$('.li-orb').forEach" in javascript
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert "@media(max-width:760px)" in css


def test_session_exposes_optional_authenticated_display_name(monkeypatch):
    from app.main import SESSION_COOKIE, settings
    from app.security import new_session

    client = signed_in_client()
    client.cookies.set(SESSION_COOKIE, new_session("owner@example.com", settings, "Chris Example"))
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {"email": "owner@example.com", "display_name": "Chris Example"}


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
    response = signed_in_client().post(
        f"/api/agents/recommendations/{rec_id}/execute",
        json={"confirmation": "confirm_permanent_agent_change", "idempotency_key": key},
    )
    assert response.status_code == 200
    assert observed == {
        "path": f"/owner/agents/recommendations/{rec_id}/execute",
        "authority": "owner",
    }


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
    backend_section = html.split('data-view-panel="backend"', 1)[1].split("</section>", 1)[0]
    assert 'type="submit"' not in backend_section


def test_phase6_read_only_policy_rhythm_and_open_loop_proxies(monkeypatch):
    observed = []

    async def backend(*args, **kwargs):
        observed.append((args[1], args[2]))
        return httpx.Response(200, json={"read_only": True})

    monkeypatch.setattr("app.main.request_backend", backend)
    client = signed_in_client()
    for route in ("action-policy", "rhythms", "open-loops"):
        assert client.get(f"/api/{route}").status_code == 200
    assert observed == [("GET", "/action-policy"), ("GET", "/rhythms"), ("GET", "/open-loops")]


def test_phase6_backend_overview_renders_read_only_governed_status():
    javascript = (Path(__file__).parents[1] / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    assert "loadGovernedWorkStatus" in javascript
    assert "Identity expresses preferences; this policy grants authority. Read-only." in javascript
    assert "fetch('/api/action-policy')" in javascript
    assert "fetch('/api/rhythms')" in javascript
    assert "fetch('/api/open-loops')" in javascript


def test_proactive_inbox_is_authenticated_private_and_marks_read(monkeypatch):
    observed = []

    async def fake_request(settings, method, path, **kwargs):
        observed.append((method, path))
        return httpx.Response(200, json={"briefs": []})

    monkeypatch.setattr("app.main.request_backend", fake_request)
    client = signed_in_client()
    assert client.get("/api/proactive-briefs").status_code == 200
    brief_id = uuid4()
    assert client.post(f"/api/proactive-briefs/{brief_id}/read").status_code == 200
    assert observed == [("GET", "/proactive-briefs"),
                        ("POST", f"/li/proactive-briefs/{brief_id}/read")]
    javascript = (Path(__file__).parents[1] / "static" / "assets" / "app.js").read_text()
    assert "A new private Li brief" not in javascript
    assert "loadProactiveBriefs" in javascript
    assert "Why now: ${item.why_now}" in javascript
    assert "item.kind || 'commitment'" in javascript
    assert "/api/action-policy', { method: 'POST'" not in javascript


def test_provider_coverage_is_read_only_proxied_and_rendered(monkeypatch):
    async def backend(*args, **kwargs):
        assert args[1:3] == ("GET", "/providers/coverage")
        return httpx.Response(
            200, json={"read_only": True, "providers": [], "specialist_status": []}
        )

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get("/api/providers/coverage")
    assert response.status_code == 200 and response.json()["read_only"] is True
    javascript = (Path(__file__).parents[1] / "static" / "assets" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "loadProviderCoverage" in javascript
    assert "fetch('/api/providers/coverage')" in javascript
    assert "secret identifiers" in javascript
    assert "/api/providers/coverage', { method: 'POST'" not in javascript
