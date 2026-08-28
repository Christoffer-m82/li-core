"""Typed, Li-owned email action boundary."""

import re
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class EmailProviderError(RuntimeError):
    """Raised when an email provider cannot safely complete an operation."""


class EmailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1, max_length=500)
    thread_id: str = Field(min_length=1, max_length=500)
    sender: str | None = Field(default=None, max_length=1000)
    recipients: list[str] = Field(default_factory=list, max_length=100)
    cc: list[str] = Field(default_factory=list, max_length=100)
    subject: str = Field(default="(no subject)", max_length=1000)
    date: str | None = Field(default=None, max_length=500)
    labels: list[str] = Field(default_factory=list, max_length=100)
    snippet: str = Field(default="", max_length=2000)
    body: str = Field(default="", max_length=50000)
    content_warning: str | None = Field(default=None, max_length=500)


class EmailThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str = Field(min_length=1, max_length=500)
    messages: list[EmailMessage] = Field(min_length=1, max_length=100)


class EmailDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=1, max_length=500)
    message_id: str = Field(min_length=1, max_length=500)
    thread_id: str | None = Field(default=None, max_length=500)
    recipients: list[str] = Field(min_length=1, max_length=100)
    cc: list[str] = Field(default_factory=list, max_length=100)
    bcc: list[str] = Field(default_factory=list, max_length=100)
    subject: str = Field(min_length=1, max_length=1000)
    body: str = Field(min_length=1, max_length=50000)


class SearchEmailAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["email.search"]
    query: str | None = Field(default=None, max_length=1000)
    sender: str | None = Field(default=None, max_length=500)
    recipient: str | None = Field(default=None, max_length=500)
    after: str | None = Field(default=None, pattern=r"^\d{4}/\d{2}/\d{2}$")
    before: str | None = Field(default=None, pattern=r"^\d{4}/\d{2}/\d{2}$")
    label_ids: list[str] = Field(default_factory=list, max_length=50)
    max_results: int = Field(default=20, ge=1, le=100)


class GetEmailMessageAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["email.get_message"]
    message_id: str = Field(min_length=1, max_length=500)


class GetEmailThreadAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["email.get_thread"]
    thread_id: str = Field(min_length=1, max_length=500)


class CreateEmailDraftAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["email.create_draft"]
    recipients: list[str] = Field(min_length=1, max_length=100)
    cc: list[str] = Field(default_factory=list, max_length=100)
    bcc: list[str] = Field(default_factory=list, max_length=100)
    subject: str = Field(min_length=1, max_length=1000)
    body: str = Field(min_length=1, max_length=50000)
    thread_id: str | None = Field(default=None, max_length=500)
    in_reply_to: str | None = Field(default=None, max_length=1000)
    references: str | None = Field(default=None, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=200)

    @field_validator("recipients", "cc", "bcc")
    @classmethod
    def addresses_must_be_safe(cls, values: list[str]) -> list[str]:
        address = re.compile(r"^[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+$")
        cleaned = [value.strip() for value in values]
        if any(not address.fullmatch(value) for value in cleaned):
            raise ValueError("Email addresses must use a simple address@example.com form.")
        return cleaned


EmailActionRequest = Annotated[
    SearchEmailAction | GetEmailMessageAction | GetEmailThreadAction | CreateEmailDraftAction,
    Field(discriminator="action"),
]


class EmailActionEnvelope(BaseModel):
    """Only Li's authenticated executor can represent or execute this envelope."""

    request: EmailActionRequest
    approved: bool = False


class EmailActionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "approval_required", "failed"]
    action: Literal["email.search", "email.get_message", "email.get_thread", "email.create_draft"]
    messages: list[EmailMessage] = Field(default_factory=list)
    message: EmailMessage | None = None
    thread: EmailThread | None = None
    draft: EmailDraft | None = None
    confirmation: str
    failed_items: int = Field(default=0, ge=0)


class EmailProvider(Protocol):
    def search_messages(self, request: SearchEmailAction) -> list[object]: ...
    def get_message(self, request: GetEmailMessageAction) -> object: ...
    def get_thread(self, request: GetEmailThreadAction) -> object: ...
    def create_draft(self, request: CreateEmailDraftAction) -> object: ...


class UnavailableEmailProvider:
    def search_messages(self, request: SearchEmailAction) -> list[object]:
        raise EmailProviderError("No email provider is configured.")

    def get_message(self, request: GetEmailMessageAction) -> object:
        raise EmailProviderError("No email provider is configured.")

    def get_thread(self, request: GetEmailThreadAction) -> object:
        raise EmailProviderError("No email provider is configured.")

    def create_draft(self, request: CreateEmailDraftAction) -> object:
        raise EmailProviderError("No email provider is configured.")


def configured_email_provider(settings: object) -> EmailProvider:
    secret_names = (
        "google_gmail_client_id",
        "google_gmail_client_secret",
        "google_gmail_refresh_token",
    )
    secrets: list[str] = []
    for name in secret_names:
        secret = getattr(settings, name, None)
        if secret is None or not secret.get_secret_value().strip():
            return UnavailableEmailProvider()
        secrets.append(secret.get_secret_value().strip())

    from app.google_gmail import GoogleGmailProvider

    return GoogleGmailProvider(
        client_id=secrets[0],
        client_secret=secrets[1],
        refresh_token=secrets[2],
        user_id=getattr(settings, "google_gmail_user_id", "me"),
        timeout_seconds=getattr(settings, "google_gmail_timeout_seconds", 10.0),
    )


def execute_email_action(
    envelope: EmailActionEnvelope, provider: EmailProvider
) -> EmailActionOutcome:
    request = envelope.request
    if isinstance(request, CreateEmailDraftAction) and not envelope.approved:
        return EmailActionOutcome(
            status="approval_required",
            action=request.action,
            confirmation=(
                f"Approval required to create a draft to {', '.join(map(str, request.recipients))} "
                f'with subject "{request.subject}". The draft body must also be confirmed.'
            ),
        )

    if isinstance(request, SearchEmailAction):
        try:
            raw = provider.search_messages(request)
        except Exception:  # noqa: BLE001 - adapters must fail closed
            return EmailActionOutcome(
                status="failed",
                action=request.action,
                confirmation="Email search failed; no mailbox state was changed.",
                failed_items=1,
            )
        candidates = raw if isinstance(raw, list) else [raw]
        messages: list[EmailMessage] = []
        failed = 0
        for candidate in candidates[: request.max_results]:
            try:
                messages.append(EmailMessage.model_validate(candidate))
            except (ValidationError, ValueError, TypeError):
                failed += 1
        if not messages and failed:
            return EmailActionOutcome(
                status="failed",
                action=request.action,
                confirmation="Email provider returned no valid messages.",
                failed_items=failed,
            )
        return EmailActionOutcome(
            status="completed",
            action=request.action,
            messages=messages,
            confirmation=f"Found {len(messages)} email message(s).",
            failed_items=failed,
        )

    model, method, field = (
        (EmailMessage, provider.get_message, "message")
        if isinstance(request, GetEmailMessageAction)
        else (EmailThread, provider.get_thread, "thread")
        if isinstance(request, GetEmailThreadAction)
        else (EmailDraft, provider.create_draft, "draft")
    )
    try:
        result = model.model_validate(method(request))
    except Exception:  # noqa: BLE001 - provider results are untrusted
        return EmailActionOutcome(
            status="failed",
            action=request.action,
            confirmation="Email provider did not return a valid confirmed result.",
            failed_items=1,
        )
    confirmation = (
        "Created email draft. It has not been sent."
        if field == "draft"
        else f"Retrieved email {field}."
    )
    return EmailActionOutcome(
        status="completed", action=request.action, confirmation=confirmation, **{field: result}
    )
