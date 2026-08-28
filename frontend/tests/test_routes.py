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
