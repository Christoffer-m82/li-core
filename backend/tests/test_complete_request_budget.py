import pytest
from types import SimpleNamespace

from app.claude import (
    ClaudeError,
    capture_generation_telemetry,
    estimate_complete_request_tokens,
    generate_claude_text,
)
from app.li_runtime import build_li_system_prompt


def test_complete_request_budget_rejects_before_provider(monkeypatch):
    class Settings:
        claude_max_tokens = 2048
        claude_total_token_budget = 4096
        claude_model = "test"

    monkeypatch.setattr("app.claude.get_settings", lambda: Settings())
    monkeypatch.setattr(
        "app.claude._claude_client",
        lambda: pytest.fail("oversized request must not reach provider"),
    )
    with pytest.raises(ClaudeError, match="complete model-call budget"):
        generate_claude_text(user_message="x" * 20_000, system="mandatory", max_tokens=2048)


def test_structured_schema_and_output_reserve_are_included_in_budget(monkeypatch):
    class Settings:
        claude_max_tokens = 512
        claude_total_token_budget = 4096
        claude_model = "test"

    monkeypatch.setattr("app.claude.get_settings", lambda: Settings())
    monkeypatch.setattr(
        "app.claude._claude_client",
        lambda: pytest.fail("schema-over-budget request must not reach provider"),
    )
    schema = {"type": "object", "description": "x" * 16_000}
    with pytest.raises(ClaudeError, match="complete model-call budget"):
        generate_claude_text(
            user_message="short", system="mandatory", max_tokens=512,
            output_json_schema=schema,
        )


def test_compact_authoritative_prompt_leaves_room_for_normal_continuity_and_output():
    estimated = estimate_complete_request_tokens(
        user_message="Please compare the two options and explain the main trade-off.",
        system=(build_li_system_prompt() + "\n" + ("Relevant authorized history. " * 600)
                + "\n" + ("Temporary attachment fact. " * 200)),
        output_json_schema={
            "type": "object", "properties": {"final_response": {"type": "string"}},
            "required": ["final_response"], "additionalProperties": False,
        },
    )
    assert estimated + 2048 < 30_000


def test_model_telemetry_contains_usage_and_timing_but_no_content(monkeypatch):
    class Settings:
        claude_max_tokens = 128
        claude_total_token_budget = 4096
        claude_model = "test-model"

    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="private synthetic answer")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=12, output_tokens=5),
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setattr("app.claude.get_settings", lambda: Settings())
    monkeypatch.setattr("app.claude._claude_client", lambda: client)
    with capture_generation_telemetry() as trace:
        assert generate_claude_text(user_message="private synthetic input", stage="test")
    assert trace[0]["stage"] == "test"
    assert trace[0]["input_tokens"] == 12 and trace[0]["output_tokens"] == 5
    assert "private synthetic" not in str(trace)


def test_incomplete_provider_response_is_rejected_and_traced(monkeypatch):
    class Settings:
        claude_max_tokens = 128
        claude_total_token_budget = 4096
        claude_model = "test-model"

    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="partial")],
                               stop_reason="max_tokens", usage=None)
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setattr("app.claude.get_settings", lambda: Settings())
    monkeypatch.setattr("app.claude._claude_client", lambda: client)
    with capture_generation_telemetry() as trace:
        with pytest.raises(ClaudeError, match="did not complete"):
            generate_claude_text(user_message="synthetic", stage="li_direct")
    assert trace == [{
        "stage": "li_direct", "status": "incomplete_response",
        "elapsed_ms": trace[0]["elapsed_ms"], "stop_reason": "max_tokens",
    }]
