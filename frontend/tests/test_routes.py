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
