from anthropic import APIError, Anthropic

from app.config import get_settings


class ClaudeError(RuntimeError):
    """Raised when Li OS cannot communicate with Claude."""


def _claude_client() -> Anthropic:
    settings = get_settings()

    return Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
    )


def generate_claude_text(
    *,
    user_message: str,
    system: str | None = None,
    max_tokens: int | None = None,
    output_json_schema: dict[str, object] | None = None,
) -> str:
    """
    Send a basic text request to Claude.

    Li identity, memory, tool use, and agent orchestration
    will be layered on top of this client separately.
    """

    settings = get_settings()
    client = _claude_client()

    response_max_tokens = (
        max_tokens
        if max_tokens is not None
        else settings.claude_max_tokens
    )

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
        raise ClaudeError(
            "Li OS could not communicate with Claude."
        ) from exc

    text_parts = [
        block.text
        for block in response.content
        if block.type == "text"
    ]

    if not text_parts:
        raise ClaudeError(
            "Claude returned no text response."
        )

    return "\n".join(text_parts)
