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
def test_place_ui_and_authenticated_bff_routes_exist():
    root = Path(__file__).parents[1]
    javascript = (root / "static" / "assets" / "app.js").read_text(encoding="utf-8")
    source = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert "COUNTRY_CODES" in javascript and "Intl.DisplayNames" in javascript
    assert "Most visited" in javascript and "Confirm this overnight visit" in javascript
    assert "On iPhone/Android" in javascript and "no precise coordinates" in javascript
    assert '@app.get("/api/settings/place")' in source
    assert '@app.post("/api/settings/place")' in source
