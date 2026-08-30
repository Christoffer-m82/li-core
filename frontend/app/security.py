import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import Settings

SESSION_COOKIE = "li_session"
OAUTH_STATE_COOKIE = "li_oauth_state"


def _encode(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(value: str) -> dict[str, Any]:
    padding = "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(value + padding))


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    encoded = _encode(payload)
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_payload(value: str | None, secret: str, *, max_age: int) -> dict[str, Any] | None:
    if not value or "." not in value:
        return None
    encoded, signature = value.rsplit(".", 1)
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = _decode(encoded)
        issued_at = int(payload["iat"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if issued_at > int(time.time()) + 30 or int(time.time()) - issued_at > max_age:
        return None
    return payload


def new_state(settings: Settings) -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    signed = sign_payload({"state": state, "iat": int(time.time())}, _secret(settings))
    return state, signed


def new_session(email: str, settings: Settings, display_name: str | None = None) -> str:
    payload = {"email": email, "iat": int(time.time())}
    if display_name:
        payload["display_name"] = display_name[:120]
    return sign_payload(payload, _secret(settings))


def require_user(request: Request) -> str:
    settings: Settings = request.app.state.settings
    payload = verify_payload(request.cookies.get(SESSION_COOKIE), _secret(settings), max_age=28800)
    if not payload or str(payload.get("email", "")).casefold() != settings.allowed_email.casefold():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return str(payload["email"])


def _secret(settings: Settings) -> str:
    return settings.session_secret.get_secret_value()
