from app.database import delete_conversation_for_owner


def test_delete_conversation_uses_owner_cleanup_function(monkeypatch) -> None:
    observed = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, query, params):
            observed["query"] = query
            observed["params"] = params

        def fetchone(self):
            return {"deleted": True}

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def cursor(self):
            return Cursor()

    monkeypatch.setattr("app.database._owner_connect", lambda: Connection())
    conversation_id = "f6dc5f9b-5b32-4a94-b457-589dbb15d56f"
    assert delete_conversation_for_owner(conversation_id=conversation_id) is True
    assert "li_api.delete_conversation" in observed["query"]
    assert observed["params"] == (conversation_id,)
