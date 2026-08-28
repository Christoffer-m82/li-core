import base64
import hashlib
import re
from collections.abc import Mapping
from email.message import EmailMessage as MimeMessage
from urllib.parse import quote

import httpx

from app.email_runtime import (
    CreateEmailDraftAction,
    EmailProviderError,
    GetEmailMessageAction,
    GetEmailThreadAction,
    SearchEmailAction,
)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_DRAFT_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
REQUIRED_GMAIL_SCOPES = frozenset({GMAIL_READ_SCOPE, GMAIL_DRAFT_SCOPE})

_INSTRUCTION_BLOCK = re.compile(
    r"(?im)^\s*(?:system|assistant|developer|tool|instruction|prompt)\s*:\s*.*$"
)
_INJECTION_PHRASE = re.compile(
    r"(?i)\b(?:ignore (?:all |any )?(?:previous|prior|system) instructions|"
    r"follow these instructions|you are now|call (?:the )?tool|execute (?:this|the following))\b"
)


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sanitize_email_content(value: str, *, limit: int) -> tuple[str, str | None]:
    sanitized = _INSTRUCTION_BLOCK.sub("[untrusted email instruction removed]", value)
    sanitized = _INJECTION_PHRASE.sub("[untrusted email instruction removed]", sanitized)
    warning = None if sanitized == value else "Instruction-like text was neutralized."
    return sanitized[:limit], warning


def _header(headers: object, name: str) -> str | None:
    if not isinstance(headers, list):
        return None
    for item in headers:
        if isinstance(item, Mapping) and str(item.get("name", "")).lower() == name.lower():
            value = item.get("value")
            return value if isinstance(value, str) else None
    return None


def _addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _body_text(part: object) -> str:
    if not isinstance(part, Mapping):
        return ""
    mime_type = part.get("mimeType")
    body = part.get("body")
    if (
        mime_type == "text/plain"
        and isinstance(body, Mapping)
        and isinstance(body.get("data"), str)
    ):
        return _decode(body["data"]).decode("utf-8", errors="replace")
    parts = part.get("parts")
    if isinstance(parts, list):
        return "\n".join(filter(None, (_body_text(child) for child in parts)))
    return ""


def _map_message(candidate: object) -> object:
    if not isinstance(candidate, Mapping) or not isinstance(candidate.get("payload"), Mapping):
        return {"malformed": True}
    payload = candidate["payload"]
    headers = payload.get("headers")
    body, warning = _sanitize_email_content(_body_text(payload), limit=50000)
    snippet, snippet_warning = _sanitize_email_content(
        str(candidate.get("snippet") or ""), limit=2000
    )
    sender, sender_warning = _sanitize_email_content(_header(headers, "From") or "", limit=1000)
    subject, subject_warning = _sanitize_email_content(
        _header(headers, "Subject") or "(no subject)", limit=1000
    )
    return {
        "message_id": candidate.get("id"),
        "thread_id": candidate.get("threadId"),
        "sender": sender or None,
        "recipients": _addresses(_header(headers, "To")),
        "cc": _addresses(_header(headers, "Cc")),
        "subject": subject,
        "date": _header(headers, "Date"),
        "labels": candidate.get("labelIds") or [],
        "snippet": snippet,
        "body": body,
        "content_warning": warning or snippet_warning or sender_warning or subject_warning,
    }


def _message_id(request: CreateEmailDraftAction) -> str:
    digest = hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest()
    return f"<li-draft-{digest}@li.local>"


class GoogleGmailProvider:
    """OAuth Gmail adapter. It can read and create drafts, but has no send method."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        user_id: str = "me",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._user_id = user_id
        self._timeout_seconds = timeout_seconds
        self._client = client

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        client = self._client or httpx
        try:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=self._timeout_seconds,
            )
            token_response.raise_for_status()
            token = token_response.json()
            access_token = token.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise EmailProviderError("Google OAuth returned no access token.")
            granted = token.get("scope")
            if isinstance(granted, str) and not REQUIRED_GMAIL_SCOPES.issubset(granted.split()):
                raise EmailProviderError("Google OAuth did not grant the required Gmail scopes.")
            response = client.request(
                method,
                f"{GOOGLE_GMAIL_API}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self._timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except EmailProviderError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise EmailProviderError("Google Gmail request failed.") from exc

    def _json(self, method: str, path: str, **kwargs: object) -> Mapping:
        try:
            payload = self._request(method, path, **kwargs).json()
        except (ValueError, TypeError) as exc:
            raise EmailProviderError("Google Gmail returned invalid JSON.") from exc
        if not isinstance(payload, Mapping):
            raise EmailProviderError("Google Gmail returned an invalid payload.")
        return payload

    def _get_message_id(self, message_id: str) -> object:
        payload = self._json(
            "GET",
            f"/users/{quote(self._user_id, safe='')}/messages/{quote(message_id, safe='')}",
            params={"format": "full"},
        )
        return _map_message(payload)

    def search_messages(self, request: SearchEmailAction) -> list[object]:
        terms = [request.query or ""]
        terms += [
            f"from:{request.sender}" if request.sender else "",
            f"to:{request.recipient}" if request.recipient else "",
            f"after:{request.after}" if request.after else "",
            f"before:{request.before}" if request.before else "",
        ]
        params: dict[str, object] = {
            "maxResults": request.max_results,
            "q": " ".join(filter(None, terms)),
        }
        if request.label_ids:
            params["labelIds"] = request.label_ids
        payload = self._json(
            "GET", f"/users/{quote(self._user_id, safe='')}/messages", params=params
        )
        items = payload.get("messages", [])
        if not isinstance(items, list):
            raise EmailProviderError("Google Gmail returned an invalid message list.")
        results = []
        for item in items:
            if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                try:
                    results.append(self._get_message_id(item["id"]))
                except EmailProviderError:
                    results.append({"malformed": True})
            else:
                results.append({"malformed": True})
        return results

    def get_message(self, request: GetEmailMessageAction) -> object:
        return self._get_message_id(request.message_id)

    def get_thread(self, request: GetEmailThreadAction) -> object:
        payload = self._json(
            "GET",
            f"/users/{quote(self._user_id, safe='')}/threads/{quote(request.thread_id, safe='')}",
            params={"format": "full"},
        )
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise EmailProviderError("Google Gmail returned an invalid thread.")
        return {
            "thread_id": payload.get("id"),
            "messages": [_map_message(item) for item in messages],
        }

    def create_draft(self, request: CreateEmailDraftAction) -> object:
        stable_id = _message_id(request)
        existing = self.search_messages(
            SearchEmailAction(
                action="email.search", query=f"in:drafts rfc822msgid:{stable_id}", max_results=1
            )
        )
        if existing and isinstance(existing[0], Mapping) and existing[0].get("message_id"):
            return {
                "draft_id": f"existing:{existing[0]['message_id']}",
                "message_id": existing[0]["message_id"],
                "thread_id": existing[0].get("thread_id"),
                "recipients": request.recipients,
                "cc": request.cc,
                "bcc": request.bcc,
                "subject": request.subject,
                "body": request.body,
            }
        message = MimeMessage()
        message["To"] = ", ".join(request.recipients)
        if request.cc:
            message["Cc"] = ", ".join(request.cc)
        if request.bcc:
            message["Bcc"] = ", ".join(request.bcc)
        message["Subject"] = request.subject
        message["Message-ID"] = stable_id
        if request.in_reply_to:
            message["In-Reply-To"] = request.in_reply_to
        if request.references:
            message["References"] = request.references
        message.set_content(request.body)
        body: dict[str, object] = {
            "message": {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")}
        }
        if request.thread_id:
            body["message"]["threadId"] = request.thread_id
        payload = self._json("POST", f"/users/{quote(self._user_id, safe='')}/drafts", json=body)
        draft_id = payload.get("id")
        raw_message = payload.get("message")
        if (
            not isinstance(draft_id, str)
            or not isinstance(raw_message, Mapping)
            or not isinstance(raw_message.get("id"), str)
        ):
            raise EmailProviderError("Google Gmail did not confirm draft creation.")
        return {
            "draft_id": draft_id,
            "message_id": raw_message["id"],
            "thread_id": raw_message.get("threadId"),
            "recipients": request.recipients,
            "cc": request.cc,
            "bcc": request.bcc,
            "subject": request.subject,
            "body": request.body,
        }
