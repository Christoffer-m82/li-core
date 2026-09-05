from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings, get_settings
from app.main import app
from app.tokens import issue_access_token

OWNER = "owner@example.com"
SESSION = uuid4()
INSTALL = uuid4()


def settings() -> Settings:
    return Settings(
        allowed_email=OWNER, google_client_ids=["ios-client", "android-client"],
        token_signing_key="s" * 32, backend_api_token="b" * 32,
    )


class FakeBackend:
    calls: ClassVar[list[tuple[str, str, dict | None]]] = []

    def __init__(self, _: Settings): pass

    async def request(self, method: str, path: str, body: dict | None = None):
        self.calls.append((method, path, body))
        values = {
            "/internal/native/sessions/bootstrap": {
                "session_id": str(SESSION), "installation_id": str(INSTALL)
            },
            "/internal/native/sessions/refresh": {
                "session_id": str(SESSION), "installation_id": str(INSTALL)
            },
            "/internal/native/sessions/status": {"status": "active"},
            "/internal/native/sessions/revoke": {"status": "revoked"},
            "/internal/native/sessions/revoke-all": {"status": "revoked"},
            "/internal/native/place/updates": {"status": "accepted"},
            "/internal/native/place": {"provider": {"installations": []}},
            "/internal/native/chat": {"response": "ok", "action_intents": []},
        }
        return httpx.Response(200, json=values[path])


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    FakeBackend.calls = []
    app.dependency_overrides[get_settings] = settings
    monkeypatch.setattr(main, "BackendClient", FakeBackend)
    yield
    app.dependency_overrides.clear()


def auth(installation=INSTALL):
    token = issue_access_token(session_id=SESSION, installation_id=installation, owner=OWNER,
                               signing_key="s" * 32, lifetime=600)
    return {"Authorization": f"Bearer {token}"}


def update(installation=INSTALL):
    now = datetime.now(UTC).isoformat()
    return {
        "contract_version": "1.0", "installation_id": str(installation),
        "update_id": str(uuid4()), "country_code": "MT", "town_city": "Valletta",
        "source": "device_coarse", "observed_at": now,
        "permission": {"state": "granted", "checked_at": now},
    }


def test_valid_owner_bootstrap_and_unallowlisted_user_rejected(monkeypatch):
    monkeypatch.setattr(main.id_token, "verify_oauth2_token", lambda *_args, **_kwargs: {
        "aud": "ios-client", "email": OWNER, "email_verified": True,
    })
    client = TestClient(app)
    accepted = client.post("/v1/auth/bootstrap", json={
        "google_id_token": "x" * 40, "platform": "ios"
    })
    assert accepted.status_code == 200 and accepted.json()["installation_id"] == str(INSTALL)
    assert "refresh_token_hash" in FakeBackend.calls[-1][2]
    assert accepted.json()["refresh_token"] not in str(FakeBackend.calls[-1][2])

    monkeypatch.setattr(main.id_token, "verify_oauth2_token", lambda *_args, **_kwargs: {
        "aud": "ios-client", "email": "intruder@example.com", "email_verified": True,
    })
    assert client.post("/v1/auth/bootstrap", json={
        "google_id_token": "x" * 40, "platform": "ios"
    }).status_code == 403


def test_refresh_rotation_logout_and_revoke_all():
    client = TestClient(app)
    refreshed = client.post("/v1/auth/refresh", json={"refresh_token": "r" * 48})
    assert refreshed.status_code == 200
    body = next(call[2] for call in FakeBackend.calls if call[1].endswith("/refresh"))
    assert body["refresh_token_hash"] != body["replacement_hash"]
    assert client.post("/v1/auth/logout", headers=auth()).status_code == 204
    assert client.post("/v1/auth/revoke-all", headers=auth()).status_code == 204


def test_wrong_install_rejected_and_valid_coarse_payload_forwarded():
    client = TestClient(app)
    assert client.post("/v1/place/updates", headers=auth(), json=update(uuid4())).status_code == 403
    accepted = client.post("/v1/place/updates", headers=auth(), json=update())
    assert accepted.status_code == 200 and accepted.json() == {"status": "accepted"}
    forwarded = next(call[2] for call in FakeBackend.calls
                     if call[1] == "/internal/native/place/updates")
    assert forwarded["update"]["country_code"] == "MT"


@pytest.mark.parametrize("field", ["latitude", "longitude", "coordinates", "hardware_id"])
def test_coordinate_and_fingerprint_fields_rejected_before_backend(field):
    payload = update()
    payload[field] = 1
    response = TestClient(app).post("/v1/place/updates", headers=auth(), json=payload)
    assert response.status_code == 422
    assert not any(call[1] == "/internal/native/place/updates" for call in FakeBackend.calls)


def test_denied_permission_makes_no_update_and_capabilities_leak_nothing():
    payload = update()
    payload["permission"]["state"] = "denied"
    client = TestClient(app)
    assert client.post("/v1/place/updates", headers=auth(), json=payload).status_code == 422
    capabilities = client.get("/v1/capabilities").json()
    encoded = str(capabilities).lower()
    assert capabilities["raw_coordinate_retention"] == "none"
    assert "backend_url" not in encoded and "secret" not in encoded and "token" not in encoded


def test_native_chat_forwards_stable_turn_identity_and_drops_input_mode():
    turn_id = uuid4()
    response = TestClient(app).post("/v1/chat", headers=auth(), json={
        "message": "Hej", "turn_id": str(turn_id), "input_mode": "voice_transcript",
    })
    assert response.status_code == 200
    forwarded = next(call[2] for call in FakeBackend.calls if call[1] == "/internal/native/chat")
    assert forwarded["turn_id"] == str(turn_id)
    assert "input_mode" not in forwarded


def test_revoked_session_fails_closed(monkeypatch):
    async def rejected(_self, method, path, body=None):
        if path.endswith("/status"):
            return httpx.Response(401, json={"detail": "revoked"})
        return await FakeBackend(None).request(method, path, body)
    monkeypatch.setattr(FakeBackend, "request", rejected)
    assert TestClient(app).get("/v1/place/status", headers=auth()).status_code == 401
