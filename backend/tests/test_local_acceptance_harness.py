"""Synthetic-only application/database acceptance for KR-011.

These tests are deliberately opt-in. The normal backend suite collects them but
does not connect to a database. CI enables them only after the complete migration
manifest has been applied to its disposable, localhost-only PostgreSQL service.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql


pytestmark = pytest.mark.skipif(
    os.getenv("LI_OS_SYNTHETIC_ACCEPTANCE") != "1",
    reason="requires the explicitly isolated synthetic acceptance database",
)


def _is_blank_optional_setting(value: object) -> bool:
    if value is None:
        return True
    reveal = getattr(value, "get_secret_value", None)
    if callable(reveal):
        value = reveal()
    return value == ""


def _assert_isolated_configuration() -> None:
    assert os.environ["LI_OS_SYNTHETIC_ACCEPTANCE"] == "1"
    assert os.environ["LI_OS_ENVIRONMENT"] == "development"
    assert os.environ["LI_OS_DB_HOST"] in {"localhost", "127.0.0.1"}
    assert os.environ["PGHOST"] in {"localhost", "127.0.0.1"}
    assert (
        os.environ["LI_OS_DB_NAME"]
        == os.environ["PGDATABASE"]
        == "li_os_kr011_acceptance"
    )
    assert os.environ["LI_OS_DB_SSLMODE"] == "disable"
    assert not any(
        os.getenv(name)
        for name in (
            "LI_OS_BRAVE_SEARCH_API_KEY",
            "LI_OS_GOOGLE_CALENDAR_CLIENT_ID",
            "LI_OS_GOOGLE_CALENDAR_CLIENT_SECRET",
            "LI_OS_GOOGLE_CALENDAR_REFRESH_TOKEN",
            "LI_OS_GOOGLE_GMAIL_CLIENT_ID",
            "LI_OS_GOOGLE_GMAIL_CLIENT_SECRET",
            "LI_OS_GOOGLE_GMAIL_REFRESH_TOKEN",
        )
    )


@pytest.fixture(scope="module", autouse=True)
def isolated_synthetic_database() -> Iterator[None]:
    """Enable only the three runtime logins in the disposable CI cluster."""

    _assert_isolated_configuration()
    runtime_passwords = {
        "li_backend_runtime": os.environ["LI_OS_DB_PASSWORD"],
        "li_theo_runtime": os.environ["LI_OS_THEO_DB_PASSWORD"],
        "li_owner_runtime": os.environ["LI_OS_OWNER_DB_PASSWORD"],
    }
    assert len(set(runtime_passwords.values())) == len(runtime_passwords)
    assert all(password.startswith("ci-synthetic-") for password in runtime_passwords.values())

    from app.config import get_settings

    settings = get_settings()
    assert settings.anthropic_api_key.get_secret_value() == "ci-synthetic-provider-disabled"
    assert all(_is_blank_optional_setting(value) for value in (
        settings.brave_search_api_key,
        settings.google_calendar_client_id,
        settings.google_calendar_client_secret,
        settings.google_calendar_refresh_token,
        settings.google_gmail_client_id,
        settings.google_gmail_client_secret,
        settings.google_gmail_refresh_token,
    ))

    with psycopg.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ["PGPORT"]),
        dbname=os.environ["PGDATABASE"],
        user="postgres",
        password=os.environ["PGPASSWORD"],
        sslmode="disable",
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            for role, password in runtime_passwords.items():
                cursor.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )

    from app.database import database_health

    assert database_health()["schema_version"] == "0.42"
    yield


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['LI_OS_API_TOKEN']}"}


def _canonical_memory_fingerprint() -> str:
    """Hash every synthetic canonical-memory row without exposing its contents."""

    digest = hashlib.sha256()
    with psycopg.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ["PGPORT"]),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        sslmode="disable",
    ) as connection:
        tables = connection.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'li_memory' ORDER BY tablename"
        ).fetchall()
        for (table,) in tables:
            digest.update(table.encode())
            digest.update(b"\0")
            rows = connection.execute(
                sql.SQL(
                    "SELECT row_to_json(t)::text FROM {}.{} t "
                    "ORDER BY row_to_json(t)::text"
                ).format(sql.Identifier("li_memory"), sql.Identifier(table))
            ).fetchall()
            for (row,) in rows:
                digest.update(row.encode())
                digest.update(b"\0")
    return digest.hexdigest()


@pytest.mark.parametrize(
    "language,query,followup",
    [
        (
            "en",
            "Ask Nora to compare amber covers from our previous conversation.",
            "Ask Nora to refine that comparison using the notebook preference already discussed.",
        ),
        (
            "sv",
            "Be Nora jämföra bärnstensomslag från vårt tidigare samtal.",
            "Be Nora förfina jämförelsen utifrån anteckningsbokspreferensen vi redan diskuterade.",
        ),
    ],
)
def test_chained_historical_privacy_and_capture_cross_real_database_safely(
    monkeypatch: pytest.MonkeyPatch, language: str, query: str, followup: str,
) -> None:
    from app.database import (
        append_conversation_message,
        create_conversation,
        get_recent_conversation_messages,
        recall_memory,
    )
    from app.main import app
    from app.memory_capture import MemoryCandidate, MemoryCaptureAnalysis
    from app.specialist_runtime import SpecialistConsultation, SpecialistResult

    run_id = uuid4().hex
    private_marker = f"synthetic-private-{language}-{run_id}"
    capture_values = [
        f"Synthetic private notebook preference {language} first {run_id}",
        f"Synthetic private notebook preference {language} follow-up {run_id}",
    ]
    historical_conversation = create_conversation(
        privacy_metadata={"private_to_li": True, "allowed_specialists": []}
    )
    append_conversation_message(
        conversation_id=historical_conversation,
        role="user",
        content=f"{query} {private_marker}",
        privacy_metadata={"private_to_li": True, "allowed_specialists": []},
    )

    packets = []
    model_calls: list[str] = []
    li_responses: list[str] = []
    analysis_calls = 0

    def consult(names, request):
        model_calls.append("specialist")
        assert names == ["nora"]
        packets.append(request)
        return SpecialistConsultation(results={
            "nora": SpecialistResult(
                recommendation="Compare reversible options.",
                confidence=0.8,
                sources_needed=False,
            )
        })

    def synthesize(**kwargs):
        model_calls.append("synthesis")
        assert private_marker in str(kwargs["system"])
        if li_responses:
            assert li_responses[0] in str(kwargs["system"])
        response = f"Li retained {private_marker} privately in turn {len(li_responses) + 1}."
        li_responses.append(response)
        return json.dumps({
            "final_response": response,
            "used_specialist_keys": ["nora"],
            "action_intents": [],
        })

    def analyze(*args, **kwargs):
        nonlocal analysis_calls
        value = capture_values[analysis_calls]
        analysis_calls += 1
        return MemoryCaptureAnalysis(candidates=[MemoryCandidate(
            action="store_explicit",
            memory_class="explicit_preference",
            domain="preferences",
            value=value,
            sensitivity="low",
        )])

    monkeypatch.setattr("app.li_runtime.consult_specialists", consult)
    monkeypatch.setattr("app.li_runtime.generate_claude_text", synthesize)
    monkeypatch.setattr(
        "app.main.analyze_memory_capture", analyze,
    )

    first_turn_id = uuid4()
    first_payload = {
        "message": query,
        "turn_id": str(first_turn_id),
        "workspace_specialist": "nora",
    }
    with TestClient(app) as client:
        first = client.post("/li/chat", headers=_headers(), json=first_payload)
        assert first.status_code == 200
        assert first.json()["turn_state"] == "completed"

        conversation_id = first.json()["conversation_id"]
        second_turn_id = uuid4()
        second_payload = {
            "message": followup,
            "turn_id": str(second_turn_id),
            "conversation_id": conversation_id,
            "workspace_specialist": "nora",
        }
        second = client.post("/li/chat", headers=_headers(), json=second_payload)
        calls_before_replay = list(model_calls)
        messages_before_replay = get_recent_conversation_messages(
            conversation_id=conversation_id, limit=12
        )
        memory_before_replay = _canonical_memory_fingerprint()
        replay = client.post("/li/chat", headers=_headers(), json=second_payload)
        memory_after_replay = _canonical_memory_fingerprint()
        messages_after_replay = get_recent_conversation_messages(
            conversation_id=conversation_id, limit=12
        )

    assert second.status_code == 200
    assert second.json()["turn_state"] == "completed"
    assert replay.status_code == 200
    assert replay.json()["turn_state"] == "completed_replay"
    assert replay.json()["response"] == second.json()["response"]
    assert model_calls == calls_before_replay == [
        "specialist", "synthesis", "specialist", "synthesis"
    ]
    assert analysis_calls == 2
    assert len(li_responses) == 2
    assert len(packets) == 2
    assert all(
        private_marker not in packet.model_dump_json()
        and all(value not in packet.model_dump_json() for value in capture_values)
        for packet in packets
    )
    assert memory_after_replay == memory_before_replay
    assert messages_after_replay == messages_before_replay

    messages = get_recent_conversation_messages(
        conversation_id=conversation_id, limit=12
    )
    assistants = [row for row in messages if row["role"] == "assistant"]
    assert len(assistants) == 2
    for assistant in assistants:
        assert private_marker in assistant["content"]
        assert assistant["privacy_metadata"]["private_to_li"] is True
        assert assistant["privacy_metadata"]["allowed_specialists"] == []
        assert assistant["privacy_metadata"]["sharing_basis"] == "derived_from_runtime_sources"

    for value, turn_id in zip(capture_values, (first_turn_id, second_turn_id), strict=True):
        captured = [
            row for row in recall_memory(query=value, domains=["preferences"], limit=10)
            if row["value_text"] == value
        ]
        assert len(captured) == 1
        assert captured[0]["private_to_li"] is True
        assert captured[0]["source_reference"] == (
            f"li-chat:{conversation_id}:{turn_id}"
        )


@pytest.mark.parametrize(
    "language,message",
    [
        ("en", "Actually, correct my synthetic notebook preference."),
        ("sv", "Rätta min syntetiska anteckningsbokspreferens."),
    ],
)
def test_post_write_failure_is_uncertain_and_replay_has_no_more_effects(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str,
) -> None:
    from app.database import recall_memory, store_explicit_memory
    from app.li_runtime import LiRuntimeError
    from app.main import app
    from app.memory_capture import MemoryCandidate, MemoryCaptureAnalysis

    run_id = uuid4().hex
    old_value = f"synthetic-old-{language}-{run_id}"
    new_value = f"synthetic-new-{language}-{run_id}"
    store_explicit_memory(
        memory_class="explicit_preference",
        domain="preferences",
        value=old_value,
        title=None,
        sensitivity="low",
        private_to_li=False,
        source_reference=f"local-acceptance-seed:{run_id}",
    )

    analysis_calls = 0
    provider_calls = 0

    def analyze(*args, **kwargs):
        nonlocal analysis_calls
        analysis_calls += 1
        return MemoryCaptureAnalysis(candidates=[MemoryCandidate(
            action="correct_explicit",
            target_query=old_value,
            memory_class="explicit_preference",
            domain="preferences",
            value=new_value,
            sensitivity="low",
        )])

    def fail_after_write(*args, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        raise LiRuntimeError("synthetic post-write model failure")

    monkeypatch.setattr("app.main.analyze_memory_capture", analyze)
    monkeypatch.setattr("app.main.talk_to_li", fail_after_write)

    turn_id = uuid4()
    payload = {"message": message, "turn_id": str(turn_id)}
    with TestClient(app) as client:
        first = client.post("/li/chat", headers=_headers(), json=payload)
        after_first = [
            row for row in recall_memory(query=new_value, domains=["preferences"], limit=10)
            if row["value_text"] == new_value
        ]
        retry = client.post("/li/chat", headers=_headers(), json=payload)
        after_retry = [
            row for row in recall_memory(query=new_value, domains=["preferences"], limit=10)
            if row["value_text"] == new_value
        ]

    assert first.status_code == 503
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "turn_outcome_uncertain"
    assert analysis_calls == 1
    assert provider_calls == 1
    assert len(after_first) == len(after_retry) == 1
    assert after_first[0]["memory_id"] == after_retry[0]["memory_id"]
    assert after_first[0]["source_reference"].endswith(str(turn_id))
