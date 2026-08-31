from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import require_api_token
from app.main import app
import app.main as main


def payload(now: datetime, *, permission: str = "granted") -> dict:
    return {"update": {
        "contract_version": "1.0", "installation_id": str(uuid4()),
        "update_id": str(uuid4()), "country_code": "MT", "town_city": "Valletta",
        "source": "device_coarse", "observed_at": now.isoformat(),
        "permission": {"state": permission, "platform": "ios", "checked_at": now.isoformat()},
    }}


def test_granted_mobile_update_reaches_private_provider_boundary(monkeypatch):
    now = datetime.now(UTC)
    seen = []
    monkeypatch.setattr(main, "submit_mobile_location_update",
                        lambda update: seen.append(update) or {"status": "accepted"})
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/settings/place/mobile/updates", json=payload(now))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200 and response.json()["status"] == "accepted"
    assert len(seen) == 1 and seen[0].country_code == "MT"


def test_denied_and_stale_mobile_updates_never_reach_persistence(monkeypatch):
    called = []
    monkeypatch.setattr(main, "submit_mobile_location_update", lambda update: called.append(update))
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        client = TestClient(app)
        assert client.post("/settings/place/mobile/updates",
                           json=payload(datetime.now(UTC), permission="denied")).status_code == 422
        assert client.post("/settings/place/mobile/updates",
                           json=payload(datetime.now(UTC)-timedelta(hours=25))).status_code == 422
    finally:
        app.dependency_overrides.clear()
    assert called == []


def test_precise_location_payload_fails_closed(monkeypatch):
    called = []
    monkeypatch.setattr(main, "submit_mobile_location_update", lambda update: called.append(update))
    value = payload(datetime.now(UTC))
    value["update"]["latitude"] = 35.9
    value["update"]["longitude"] = 14.5
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app).post("/settings/place/mobile/updates", json=value)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422 and called == []
