import psycopg
import pytest

from app.database import MemoryForgetError, forget_memory


def test_forget_memory_surfaces_database_policy_failure(monkeypatch) -> None:
    class RejectingCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, parameters) -> None:
            raise psycopg.ProgrammingError(
                "Sensitivity sensitive requires Theo review for forgetting"
            )

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return RejectingCursor()

    monkeypatch.setattr("app.database._connect", lambda: FakeConnection())

    with pytest.raises(MemoryForgetError, match="could not forget") as exc_info:
        forget_memory(memory_id="00000000-0000-0000-0000-000000000001")

    assert isinstance(exc_info.value.__cause__, psycopg.ProgrammingError)
