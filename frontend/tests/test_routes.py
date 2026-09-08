from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_is_public_and_minimal():
    assert client.get("/health").json() == {"status": "ok"}


def test_api_requires_session():
    response = client.get("/api/session")
    assert response.status_code == 401


def test_shell_has_security_headers():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(self), geolocation=(self)"
    )


def test_public_oauth_documents_are_anonymous_fixed_and_cross_linked():
    expected = {
        "/about": ("About Li OS", "Google Calendar", "/privacy", "/terms"),
        "/privacy": (
            "Li OS Privacy Policy",
            "https://www.googleapis.com/auth/calendar.events",
            "/about",
            "/terms",
        ),
        "/terms": ("Li OS Terms of Service", "Google Calendar", "/about", "/privacy"),
    }
    for path, fragments in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert all(fragment in response.text for fragment in fragments)
        assert "<script" not in response.text


def test_public_privacy_document_describes_google_data_controls():
    policy = client.get("/privacy").text
    for disclosure in (
        "Google Calendar remains the system of record",
        "does not use Google Calendar information for advertising",
        "explicit owner approval",
        "revoked from the Google Account",
        "OAuth credentials are stored as restricted server-side secrets",
        "configured AI provider",
    ):
        assert disclosure in policy
    assert client.get("/api/privacy/settings").status_code == 401


def test_sign_in_shell_links_to_public_oauth_documents():
    shell = client.get("/").text
    signed_out = shell.split('id="signed-out"', 1)[1].split('id="workspace"', 1)[0]
    for path in ("/about", "/privacy", "/terms"):
        assert f'href="{path}"' in signed_out


def test_public_documents_keep_valid_responsive_widths():
    css = (Path(__file__).parents[1] / "static/assets/public.css").read_text(encoding="utf-8")
    assert "width: calc(100% - 32px);" in css
    assert "max-width: 940px;" in css
    assert "width: calc(100% - 20px);" in css


def test_place_ui_and_authenticated_bff_routes_exist():
    root = Path(__file__).parents[1]
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    source = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert "COUNTRY_CODES" in javascript and "Intl.DisplayNames" in javascript
    assert "Most visited" in javascript and "Confirm this overnight visit" in javascript
    assert "Native access is enabled only after an authenticated app installation exists" in javascript
    assert "Li stores no GPS trail" in javascript
    assert "no GPS trail" in javascript and "explicit OS permission" in javascript
    assert "Connected native providers" in javascript and "revokeMobileProvider" in javascript
    assert '@app.get("/api/settings/place")' in source
    assert '@app.post("/api/settings/place")' in source
    assert '@app.post("/api/settings/place/mobile/revoke")' in source
