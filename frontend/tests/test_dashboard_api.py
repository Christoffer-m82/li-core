from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import MAX_UPLOAD_BYTES, app
from app.profile_service import ProfileServiceResponse
from app.security import require_user


def signed_in_client() -> TestClient:
    app.dependency_overrides[require_user] = lambda: "owner@example.com"
    return TestClient(app)


def test_workspace_recipient_forwarding_and_validation(monkeypatch):
    calls = []

    async def backend(*args, **kwargs):
        calls.append((args, kwargs))
        return httpx.Response(200, json={"response": "Reply"})

    monkeypatch.setattr("app.main.request_backend", backend)
    client = signed_in_client()
    for recipient in ("group", "specialist"):
        assert client.post("/api/chat", json={"message": "Hi", "workspace_specialist": "nora", "workspace_recipient": recipient}).status_code == 200
        assert calls[-1][1]["json_body"]["workspace_specialist"] == "nora"
        assert calls[-1][1]["json_body"]["workspace_recipient"] == recipient
    assert client.post("/api/chat", json={"message": "Hi", "workspace_specialist": "heimdall"}).status_code == 422
    assert client.post("/api/chat", json={"message": "Hi", "workspace_recipient": "private"}).status_code == 422


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


@pytest.mark.parametrize("path", ["/api/specialists", "/api/specialists/nora/interactions"])
@pytest.mark.parametrize("failure", ["status", "transport", "malformed"])
def test_specialist_unavailability_is_not_empty_activity(monkeypatch, path, failure):
    async def backend(*args, **kwargs):
        if failure == "transport":
            raise httpx.ConnectError("internal detail must not leak")
        return httpx.Response(503 if failure == "status" else 200, json={"interactions": None})

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().get(path)
    assert response.status_code == 502
    assert response.json() == {"detail": "Specialist activity is temporarily unavailable."}


def test_specialist_deep_view_assets_and_controls():
    root = Path(__file__).parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    worker = (root / "static" / "sw.js").read_text(encoding="utf-8")
    for asset in ("/assets/specialists.js", "/assets/specialists.css", "/assets/workspace.js"):
        assert asset in html and asset in worker
    for control in ("specialist-refresh", "specialist-search", "specialist-filter", "specialist-record"):
        assert f'id="{control}"' in html
    assert html.index('src="/assets/specialists.js"') < html.index('src="/assets/app.js"')
    assert 'aria-pressed="true" data-specialist-tab="live">Workspace' in html


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


def test_profile_routes_are_authenticated_disabled_and_no_store():
    anonymous = TestClient(app)
    assert anonymous.get("/api/profile/photo").status_code == 401
    client = signed_in_client()
    for path in ("/api/profile/photo", "/api/profile/photo/image"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method", ["put", "delete"])
def test_disabled_profile_mutations_still_enforce_origin_header_and_revision(method):
    client = signed_in_client()
    call = getattr(client, method)
    path = "/api/profile/photo"
    assert call(path).status_code == 403
    base = {"Origin": "http://localhost:8080", "X-Li-Profile-Mutation": "1"}
    assert call(path, headers={**base, "If-Match": "untrusted"}).status_code == 409
    response = call(path, headers={**base, "If-Match": "absent"})
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


def test_enabled_profile_metadata_and_image_validate_private_service(monkeypatch):
    async def profile(_settings, method, path, **_kwargs):
        if path.endswith("/image"):
            return ProfileServiceResponse(200, b"synthetic-jpeg", "image/jpeg")
        return ProfileServiceResponse(200, b'{"revision":"absent","state":"empty"}', "application/json")

    monkeypatch.setattr("app.main.profile_service_configured", lambda _settings: True)
    monkeypatch.setattr("app.main.request_profile_service", profile)
    client = signed_in_client()
    metadata = client.get("/api/profile/photo")
    assert metadata.status_code == 200
    assert metadata.json() == {"revision": "absent", "state": "empty"}
    image = client.get("/api/profile/photo/image")
    assert image.status_code == 200
    assert image.content == b"synthetic-jpeg"
    assert image.headers["content-type"] == "image/jpeg"


def test_profile_replacement_extracts_one_bounded_file_and_forwards_no_filename(monkeypatch):
    observed = {}

    async def profile(_settings, method, path, **kwargs):
        observed.update(method=method, path=path, **kwargs)
        contents = bytearray()
        async for chunk in kwargs["body"]:
            contents.extend(chunk)
        observed["contents"] = bytes(contents)
        return ProfileServiceResponse(
            200,
            b'{"revision":"00000000-0000-0000-0000-000000000001","state":"available"}',
            "application/json",
        )

    monkeypatch.setattr("app.main.profile_service_configured", lambda _settings: True)
    monkeypatch.setattr("app.main.request_profile_service", profile)
    response = signed_in_client().put(
        "/api/profile/photo",
        headers={
            "Origin": "http://localhost:8080", "X-Li-Profile-Mutation": "1",
            "If-Match": "absent",
        },
        files={"file": ("private-name.png", b"synthetic-png", "image/png")},
    )
    assert response.status_code == 200
    assert observed == {
        "method": "PUT", "path": "/v1/profile", "revision": "absent",
        "content_type": "image/png", "content_length": 13,
        "body": observed["body"], "contents": b"synthetic-png",
    }
    assert "private-name" not in repr(observed)


def test_profile_replacement_rejects_extra_parts_and_unsupported_file(monkeypatch):
    calls = 0

    async def profile(*_args, **_kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr("app.main.profile_service_configured", lambda _settings: True)
    monkeypatch.setattr("app.main.request_profile_service", profile)
    headers = {
        "Origin": "http://localhost:8080", "X-Li-Profile-Mutation": "1", "If-Match": "absent",
    }
    client = signed_in_client()
    extra = client.put(
        "/api/profile/photo", headers=headers, data={"note": "no"},
        files={"file": ("photo.png", b"png", "image/png")},
    )
    assert extra.status_code == 400
    unsupported = client.put(
        "/api/profile/photo", headers=headers,
        files={"file": ("photo.gif", b"gif", "image/gif")},
    )
    assert unsupported.status_code == 415
    assert calls == 0


def test_profile_service_authority_failure_is_not_browser_auth_failure(monkeypatch):
    async def profile(*_args, **_kwargs):
        return ProfileServiceResponse(403, b'{"detail":"internal"}', "application/json")

    monkeypatch.setattr("app.main.profile_service_configured", lambda _settings: True)
    monkeypatch.setattr("app.main.request_profile_service", profile)
    response = signed_in_client().get("/api/profile/photo")
    assert response.status_code == 503
    assert response.json() == {"detail": "Private profile storage is unavailable."}
    assert b"internal" not in response.content


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


def test_chat_forwards_stable_turn_identity(monkeypatch):
    observed = {}
    turn_id = uuid4()

    async def backend(*args, **kwargs):
        observed.update(kwargs["json_body"])
        return httpx.Response(200, json={"response": "ok"})

    monkeypatch.setattr("app.main.request_backend", backend)
    response = signed_in_client().post(
        "/api/chat", json={"message": "Retry-safe", "turn_id": str(turn_id)},
    )
    assert response.status_code == 200
    assert observed["turn_id"] == str(turn_id)


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
    assert "savePreference('li-theme', choice)" in javascript
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
    assert "clearInterval(specialistPoll)" in javascript
    assert "await loadSpecialists()" in javascript
    specialist_js = (Path(__file__).parents[1] / "static" / "assets" / "specialists.js").read_text(
        encoding="utf-8"
    )
    assert "text(outcome.recommendation, missing)" in specialist_js
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
    specialist_js = (root / "static" / "assets" / "specialists.js").read_text(encoding="utf-8")
    assert "No live specialist interaction" in specialist_js
    assert "freshness_evidence" in javascript
    assert "Not measured" in javascript
    assert "confidence" not in javascript[javascript.index("function evidencePanel"):javascript.index("let specialistView")]


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
