import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.artifacts import StoredObject, safe_filename
from app.auth import require_api_token, require_owner_api_token
from app.main import _requested_text_artifact, app


class FakeStore:
    def __init__(self):
        self.deleted = []

    def put(self, **kwargs):
        return StoredObject("owners/o/artifacts/a/notes.txt", len(kwargs["contents"]), 1)

    def get(self, object_name):
        return b"synthetic"

    def delete(self, object_name):
        self.deleted.append(object_name)


def client():
    app.dependency_overrides[require_api_token] = lambda: None
    app.dependency_overrides[require_owner_api_token] = lambda: None
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def payload(save=False):
    return {"filename": "notes.txt", "content_type": "text/plain",
            "data_base64": base64.b64encode(b"synthetic notes").decode(), "save": save}


def test_temporary_upload_is_analyzed_without_metadata_or_storage(monkeypatch):
    monkeypatch.setattr("app.main.reserve_artifact",
                        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not persist")))
    response = client().post("/artifacts/uploads", json=payload())
    assert response.status_code == 200
    assert response.json()["retained"] is False
    assert response.json()["analysis_text"] == "synthetic notes"


def test_explicit_save_persists_upload_as_kept(monkeypatch):
    artifact_id = uuid4()
    store = FakeStore()
    monkeypatch.setattr("app.main._artifact_store", lambda: store)
    monkeypatch.setattr("app.main.reserve_artifact", lambda **kwargs: {
        "artifact_id": artifact_id, "owner_user_id": uuid4(), "expires_at": None})
    observed = {}
    monkeypatch.setattr("app.main.finalize_artifact",
                        lambda artifact_id, obj, generation, keep: observed.update(keep=keep) or True)
    response = client().post("/artifacts/uploads", json=payload(save=True))
    assert response.status_code == 200
    assert response.json()["retained"] is True
    assert observed["keep"] is True


def test_generated_artifact_uses_default_expiry_and_can_be_deleted(monkeypatch):
    artifact_id = uuid4()
    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    store = FakeStore()
    monkeypatch.setattr("app.main._artifact_store", lambda: store)
    monkeypatch.setattr("app.main.reserve_artifact", lambda **kwargs: {
        "artifact_id": artifact_id, "owner_user_id": uuid4(), "expires_at": expiry})
    monkeypatch.setattr("app.main.finalize_artifact", lambda *args: True)
    response = client().post("/artifacts/generated", json={**payload(), "source": "li_generated"})
    assert response.status_code == 200
    assert response.json()["kept"] is False
    assert response.json()["expires_at"] is not None
    monkeypatch.setattr("app.main.get_artifact", lambda *args: {
        "storage_object": "owners/o/artifacts/a/notes.txt", "retention_state": "expiring"})
    monkeypatch.setattr("app.main.change_artifact", lambda *args: {
        "storage_object": "owners/o/artifacts/a/notes.txt", "retention_state": "deleted"})
    deleted = client().post(f"/artifacts/{artifact_id}/retention", json={"action": "delete"})
    assert deleted.status_code == 200
    assert store.deleted


def test_cleanup_is_idempotent(monkeypatch):
    artifact_id = uuid4()
    store = FakeStore()
    monkeypatch.setattr("app.main._artifact_store", lambda: store)
    monkeypatch.setattr("app.main.expired_artifacts", lambda: [
        {"artifact_id": artifact_id, "storage_object": "owners/o/artifacts/a/notes.txt"}])
    calls = []
    monkeypatch.setattr("app.main.mark_expired", lambda value: not calls and not calls.append(value))
    first = client().post("/internal/retention/cleanup").json()
    assert first == {"deleted": 1}


def test_safe_filename_prevents_traversal():
    assert safe_filename("../../secret.txt") == "secret.txt"
    assert safe_filename("folder\\notes.txt") == "notes.txt"


def test_explicit_file_request_is_detected_without_matching_ordinary_chat():
    assert _requested_text_artifact("Please create a text file with your answer")
    assert not _requested_text_artifact("Please answer this normally")


def test_conversation_delete_requires_exact_confirmation_and_owner_operation(monkeypatch):
    conversation_id = uuid4()
    monkeypatch.setattr("app.main.delete_conversation", lambda value: {
        "deleted": True, "specialist_interactions_deleted": 2,
    })
    rejected = client().post(
        f"/owner/conversations/{conversation_id}/delete", json={"confirmation": "delete"}
    )
    assert rejected.status_code == 422
    deleted = client().post(
        f"/owner/conversations/{conversation_id}/delete",
        json={"confirmation": "delete_private_conversation"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["specialist_interactions_deleted"] == 2
