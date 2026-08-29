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


def test_artifact_library_returns_only_governed_database_results(monkeypatch):
    artifact_id = uuid4()
    monkeypatch.setattr("app.main.list_artifacts", lambda: [{
        "artifact_id": artifact_id, "safe_filename": "notes.txt",
        "retention_state": "expiring", "storage_object": None,
    }])
    response = client().get("/artifacts")
    assert response.status_code == 200
    assert response.json()["artifacts"][0]["artifact_id"] == str(artifact_id)


def test_artifact_library_migration_is_owner_scoped_and_excludes_deleted():
    from pathlib import Path
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "021_artifact_library.sql").read_text(encoding="utf-8")
    assert "version='0.20'" in sql
    assert "a.owner_user_id=v_user" in sql
    assert "a.retention_state IN ('expiring','kept')" in sql
    assert "GRANT EXECUTE ON FUNCTION li_api.list_artifacts(INTEGER) TO li_memory_api" in sql
    assert "li_memory_theo" in sql


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


def test_cleanup_job_is_idempotent(monkeypatch):
    from app import retention_job

    artifact_id = uuid4()
    store = FakeStore()

    class Cursor:
        def __init__(self):
            self.statement = ""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement, _parameters):
            self.statement = statement

        def fetchall(self):
            return [{"artifact_id": artifact_id,
                     "storage_object": "owners/o/artifacts/a/notes.txt"}]

        def fetchone(self):
            return {"marked": True}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def cursor(self):
            return Cursor()

    class Settings:
        artifact_bucket = "private"

        def connect_kwargs(self):
            return {}

    monkeypatch.setattr(retention_job, "RetentionSettings", Settings)
    monkeypatch.setattr(retention_job, "PrivateArtifactStore", lambda _bucket: store)
    monkeypatch.setattr(retention_job.psycopg, "connect", lambda **_kwargs: Connection())

    assert retention_job.run() == 1
    assert store.deleted == ["owners/o/artifacts/a/notes.txt"]


def test_retention_worker_migration_is_least_privilege():
    from pathlib import Path
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "022_retention_worker_role.sql").read_text(encoding="utf-8")
    assert "CREATE ROLE li_artifact_retention" in sql
    assert "CREATE ROLE li_retention_runtime" in sql
    assert "NOLOGIN INHERIT" in sql
    assert "LOGIN INHERIT" in sql
    assert "GRANT li_artifact_retention TO li_retention_runtime" in sql
    assert "li_api.list_expired_artifacts(INTEGER)" in sql
    assert "li_api.mark_artifact_expired(UUID)" in sql
    assert "FROM PUBLIC, anon, authenticated, service_role, li_memory_api" in sql
    assert "ALL TABLES IN SCHEMA li_memory, li_runtime_data" in sql
    assert "has_function_privilege" in sql
    assert "has_table_privilege" in sql
    assert "VALUES ('0.22'" in sql


def test_expiry_selection_preserves_keep_and_delete_early_semantics():
    from pathlib import Path
    sql = (Path(__file__).parents[2] / "memory" / "migrations" /
           "017_governed_artifacts_and_specialist_history.sql").read_text(encoding="utf-8")
    selection = sql.split("CREATE FUNCTION li_api.list_expired_artifacts", 1)[1].split(
        "CREATE FUNCTION li_api.mark_artifact_expired", 1
    )[0]
    assert "retention_state='expiring'" in selection
    assert "expires_at<=NOW()" in selection
    assert "retention_state='kept'" not in selection
    assert "retention_state='deleted'" not in selection


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
