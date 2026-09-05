from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from anthropic import APIError, Anthropic

from app.config import get_settings


class ClaudeError(RuntimeError):
    """Raised when Li OS cannot communicate with Claude."""


_telemetry: ContextVar[list[dict[str, object]] | None] = ContextVar(
    "claude_generation_telemetry", default=None
)


@contextmanager
def capture_generation_telemetry() -> Iterator[list[dict[str, object]]]:
    """Capture privacy-minimized call facts for one internal turn."""
    records: list[dict[str, object]] = []
    token = _telemetry.set(records)
    try:
        yield records
    finally:
        _telemetry.reset(token)


def _record(value: dict[str, object]) -> None:
    records = _telemetry.get()
    if records is not None:
        records.append(value)


def _claude_client() -> Anthropic:
    settings = get_settings()

    return Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.claude_timeout_seconds,
        # A model request is not known to be safe to replay after a transport
        # timeout. Turn-level recovery owns any deliberate retry.
        max_retries=0,
    )


def generate_claude_text(
    *,
    user_message: str,
    system: str | None = None,
    max_tokens: int | None = None,
    output_json_schema: dict[str, object] | None = None,
    stage: str = "unspecified",
) -> str:
    """
    Send a basic text request to Claude.

    Li identity, memory, tool use, and agent orchestration
    will be layered on top of this client separately.
    """

    started = time.monotonic()
    settings = get_settings()

    response_max_tokens = (
        max_tokens
        if max_tokens is not None
        else settings.claude_max_tokens
    )
    # Bound the complete provider request, including mandatory instructions and
    # reserved output. Refuse an oversized request instead of silently dropping
    # a safety rule or an arbitrary tail of conversation.
    estimated_input_tokens = (
        len(user_message) + len(system or "") + 3
    ) // 4
    if estimated_input_tokens + response_max_tokens > settings.claude_total_token_budget:
        _record({
            "stage": stage, "status": "budget_rejected", "elapsed_ms": 0,
            "estimated_input_tokens": estimated_input_tokens,
            "reserved_output_tokens": response_max_tokens,
        })
        raise ClaudeError("Li OS request exceeds its complete model-call budget.")
    client = _claude_client()

    try:
        request = {
            "model": settings.claude_model,
            "max_tokens": response_max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
        }

        if system is not None:
            request["system"] = system
        if output_json_schema is not None:
            request["output_config"] = {
                "format": {"type": "json_schema", "schema": output_json_schema}
            }

        response = client.messages.create(**request)

    except APIError as exc:
        _record({
            "stage": stage, "status": "provider_failed",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "estimated_input_tokens": estimated_input_tokens,
            "reserved_output_tokens": response_max_tokens,
        })
        raise ClaudeError(
            "Li OS could not communicate with Claude."
        ) from exc

    if getattr(response, "stop_reason", None) != "end_turn":
        _record({
            "stage": stage, "status": "incomplete_response",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "stop_reason": getattr(response, "stop_reason", None),
        })
        raise ClaudeError("Claude did not complete the response within the bounded request.")

    text_parts = [
        block.text
        for block in response.content
        if block.type == "text"
    ]

    if not text_parts:
        _record({
            "stage": stage, "status": "empty_response",
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "stop_reason": getattr(response, "stop_reason", None),
        })
        raise ClaudeError(
            "Claude returned no text response."
        )

    usage = getattr(response, "usage", None)
    _record({
        "stage": stage,
        "status": "completed",
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "stop_reason": getattr(response, "stop_reason", None),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "estimated_input_tokens": estimated_input_tokens,
        "reserved_output_tokens": response_max_tokens,
        "structured_output_requested": output_json_schema is not None,
    })
    return "\n".join(text_parts)
