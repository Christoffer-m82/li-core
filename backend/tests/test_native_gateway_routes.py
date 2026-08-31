from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app import main
from app.auth import require_native_gateway_api_token
from app.main import app


def test_private_native_session_lifecycle_routes(monkeypatch):
    session, installation = uuid4(), uuid4()
    monkeypatch.setattr(main, "bootstrap_native_session", lambda payload: {
        "session_id": str(session), "installation_id": str(installation)
    })
    monkeypatch.setattr(main, "refresh_native_session", lambda payload: {
        "session_id": str(session), "installation_id": str(installation)
    })
    monkeypatch.setattr(main, "validate_native_session", lambda sid, iid: {
        "status": "active", "session_id": str(sid), "installation_id": str(iid)
    })
    monkeypatch.setattr(main, "revoke_native_session", lambda sid, remove: {
        "status": "revoked", "installation_revoked": remove
    })
    monkeypatch.setattr(main, "revoke_all_native_sessions", lambda: {
        "status": "revoked", "session_count": 2
    })
    app.dependency_overrides[require_native_gateway_api_token] = lambda: None
    try:
        client = TestClient(app)
        expires = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        bootstrap = client.post("/internal/native/sessions/bootstrap", json={
            "platform": "ios", "owner_email": "owner@example.com",
            "refresh_token_hash": "a" * 64, "refresh_expires_at": expires,
            "attestation_provider": None, "attestation_status": "not_configured",
        })
        assert bootstrap.status_code == 200
        assert client.post("/internal/native/sessions/refresh", json={
            "refresh_token_hash": "a" * 64, "replacement_hash": "b" * 64,
            "refresh_expires_at": expires,
        }).status_code == 200
        assert client.post("/internal/native/sessions/status", json={
            "session_id": str(session), "installation_id": str(installation)
        }).status_code == 200
        assert client.post("/internal/native/sessions/revoke", json={
            "session_id": str(session), "revoke_installation": True
        }).json()["installation_revoked"] is True
        assert client.post("/internal/native/sessions/revoke-all", json={}).status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_session_contract_rejects_plaintext_and_unknown_fields():
    app.dependency_overrides[require_native_gateway_api_token] = lambda: None
    try:
        response = TestClient(app).post("/internal/native/sessions/refresh", json={
            "refresh_token": "plaintext", "refresh_token_hash": "short",
            "replacement_hash": "b" * 64,
            "refresh_expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        })
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_migration_034_has_hashed_rotation_revocation_rate_limit_and_no_coordinates():
    from pathlib import Path

    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "034_authenticated_native_gateway.sql").read_text(encoding="utf-8").lower()
    assert "migration 034 requires applied schema 0.33" in sql
    assert "refresh_token_hash char(64)" in sql and "refresh_token text" not in sql
    assert "for update" in sql and "refresh_token_hash=p_replacement_hash" in sql
    assert "revoke_all_native_sessions" in sql and "request_count" in sql
    assert "latitude" not in sql and "longitude" not in sql and "coordinate" not in sql
    assert "grant execute" in sql and "to li_memory_api" in sql
    assert "schema_versions" in sql and sql.index("schema_versions") < sql.rindex("commit;")


def test_deployment_keeps_backend_private_and_gateway_database_free():
    from pathlib import Path

    root = Path(__file__).parents[2]
    script = (root / "deployment" / "cloud-run" /
              "provision-native-gateway.ps1").read_text(encoding="utf-8").lower()
    manifest = (root / "deployment" / "cloud-run" /
                "native-gateway-service.template.yaml").read_text(encoding="utf-8").lower()
    assert "services add-iam-policy-binding $backendservice" in script
    assert 'serviceaccount:$gatewayaccount' in script
    assert "--allow-unauthenticated" in script  # Gateway network boundary only.
    assert "allusers" not in script and "cloud sql" not in manifest
    assert "li_native_db" not in manifest and "li_os_db_" not in manifest
    assert "pinned_native_api_token_version" in manifest
    assert "pinned_signing_key_version" in manifest
