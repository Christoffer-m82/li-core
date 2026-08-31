import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from uuid import UUID


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessClaims:
    session_id: UUID
    installation_id: UUID
    owner: str
    expires_at: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_access_token(*, session_id: UUID, installation_id: UUID, owner: str,
                       signing_key: str, lifetime: int, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else now
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "iss": "li-native-gateway", "aud": "li-native", "sub": owner.lower(),
        "sid": str(session_id), "iid": str(installation_id), "iat": issued,
        "exp": issued + lifetime,
    }, separators=(",", ":")).encode())
    signed = f"{header}.{payload}"
    signature = _b64(hmac.new(signing_key.encode(), signed.encode(), hashlib.sha256).digest())
    return f"{signed}.{signature}"


def verify_access_token(token: str, signing_key: str, now: int | None = None) -> AccessClaims:
    try:
        header, payload, signature = token.split(".")
        signed = f"{header}.{payload}"
        expected = _b64(hmac.new(signing_key.encode(), signed.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise TokenError("Invalid access token.")
        token_header = json.loads(_unb64(header))
        body = json.loads(_unb64(payload))
        current = int(time.time()) if now is None else now
        if token_header != {"alg": "HS256", "typ": "JWT"}:
            raise TokenError("Invalid access token.")
        if body.get("iss") != "li-native-gateway" or body.get("aud") != "li-native":
            raise TokenError("Invalid access token.")
        if not isinstance(body.get("sub"), str) or not body["sub"]:
            raise TokenError("Invalid access token.")
        if not isinstance(body.get("iat"), int) or body["iat"] > current + 60:
            raise TokenError("Invalid access token.")
        if not isinstance(body.get("exp"), int) or current >= body["exp"]:
            raise TokenError("Access token expired.")
        return AccessClaims(UUID(body["sid"]), UUID(body["iid"]), body["sub"], body["exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, TokenError):
            raise
        raise TokenError("Invalid access token.") from exc


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()
