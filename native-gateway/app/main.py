import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import google.auth.transport.requests
from fastapi import Depends, FastAPI, Header, HTTPException
from google.oauth2 import id_token

from app.backend import BackendClient
from app.config import Settings, get_settings
from app.contracts import (
    BootstrapRequest,
    ChatRequest,
    CoarsePlaceUpdate,
    RefreshRequest,
    RevokeInstallationRequest,
)
from app.tokens import (
    AccessClaims,
    TokenError,
    hash_refresh_token,
    issue_access_token,
    new_refresh_token,
    verify_access_token,
)

logger = logging.getLogger("li.native_gateway")
app = FastAPI(title="Li OS Native Gateway", version="1.0")
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _safe(response) -> dict:
    if response.status_code >= 400:
        detail = {
            401: "Authentication is expired or revoked.",
            403: "Request is not authorized.",
            409: "Request conflicts with current device state.",
            422: "Request payload was rejected.",
            429: "Request rate limit exceeded.",
        }.get(response.status_code, "Private service request failed.")
        raise HTTPException(response.status_code, detail)
    value = response.json()
    if not isinstance(value, dict):
        raise HTTPException(502, "Invalid private service response.")
    return value


def _tokens(settings: Settings, session_id: UUID, installation_id: UUID, refresh: str) -> dict:
    return {
        "token_type": "Bearer",
        "access_token": issue_access_token(
            session_id=session_id, installation_id=installation_id,
            owner=settings.allowed_email, signing_key=settings.token_signing_key.get_secret_value(),
            lifetime=settings.access_token_seconds,
        ),
        "expires_in": settings.access_token_seconds,
        "refresh_token": refresh,
        "installation_id": str(installation_id),
    }


async def require_session(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AccessClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = verify_access_token(
            authorization[7:], settings.token_signing_key.get_secret_value()
        )
    except TokenError as exc:
        raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc
    response = await BackendClient(settings).request(
        "POST", "/internal/native/sessions/status", {
            "session_id": str(claims.session_id),
            "installation_id": str(claims.installation_id),
        },
    )
    _safe(response)
    return claims


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "native_gateway"}


@app.get("/v1/capabilities")
async def capabilities(settings: SettingsDep) -> dict:
    return {
        "gateway": "configured" if settings.google_client_ids else "not_configured",
        "auth_mode": "google_oidc_bootstrap_bearer_refresh",
        "attestation": "not_configured",
        "mobile_place_contract": "1.0",
        "raw_coordinate_retention": "none",
        "chat_contract": "typed_text_or_transcript_no_raw_audio",
    }


@app.post("/v1/auth/bootstrap")
async def bootstrap(payload: BootstrapRequest, settings: SettingsDep) -> dict:
    if payload.attestation is not None:
        raise HTTPException(501, "Platform attestation is not configured.")
    try:
        identity = id_token.verify_oauth2_token(
            payload.google_id_token, google.auth.transport.requests.Request(), audience=None
        )
    except ValueError as exc:
        raise HTTPException(401, "Invalid identity token.") from exc
    if identity.get("aud") not in settings.google_client_ids or not identity.get("email_verified"):
        raise HTTPException(403, "Identity is not allowed.")
    if str(identity.get("email", "")).casefold() != settings.allowed_email.casefold():
        raise HTTPException(403, "Identity is not allowed.")
    refresh = new_refresh_token()
    expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
    result = _safe(await BackendClient(settings).request("POST", "/internal/native/sessions/bootstrap", {
        "platform": payload.platform,
        "owner_email": settings.allowed_email.casefold(),
        "refresh_token_hash": hash_refresh_token(
            refresh, settings.token_signing_key.get_secret_value()
        ),
        "refresh_expires_at": expires.isoformat(),
        "attestation_provider": None,
        "attestation_status": "not_configured",
    }))
    return _tokens(settings, UUID(result["session_id"]), UUID(result["installation_id"]), refresh)


@app.post("/v1/auth/refresh")
async def refresh(payload: RefreshRequest, settings: SettingsDep) -> dict:
    replacement = new_refresh_token()
    result = _safe(await BackendClient(settings).request("POST", "/internal/native/sessions/refresh", {
        "refresh_token_hash": hash_refresh_token(
            payload.refresh_token, settings.token_signing_key.get_secret_value()
        ),
        "replacement_hash": hash_refresh_token(
            replacement, settings.token_signing_key.get_secret_value()
        ),
        "refresh_expires_at": (
            datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
        ).isoformat(),
    }))
    return _tokens(settings, UUID(result["session_id"]), UUID(result["installation_id"]), replacement)


@app.post("/v1/auth/logout", status_code=204)
async def logout(claims: Annotated[AccessClaims, Depends(require_session)],
                 settings: SettingsDep) -> None:
    _safe(await BackendClient(settings).request("POST", "/internal/native/sessions/revoke", {
        "session_id": str(claims.session_id), "revoke_installation": False,
    }))


@app.post("/v1/auth/revoke-all", status_code=204)
async def revoke_all(_: Annotated[AccessClaims, Depends(require_session)],
                     settings: SettingsDep) -> None:
    _safe(await BackendClient(settings).request(
        "POST", "/internal/native/sessions/revoke-all", {}
    ))


@app.get("/v1/installations/status")
async def installation_status(
    claims: Annotated[AccessClaims, Depends(require_session)], settings: SettingsDep
) -> dict:
    return _safe(await BackendClient(settings).request("GET", "/internal/native/place"))


@app.post("/v1/installations/revoke", status_code=204)
async def revoke_installation(payload: RevokeInstallationRequest,
                              claims: Annotated[AccessClaims, Depends(require_session)],
                              settings: SettingsDep) -> None:
    if payload.installation_id != claims.installation_id:
        raise HTTPException(403, "Token is bound to another installation.")
    _safe(await BackendClient(settings).request("POST", "/internal/native/sessions/revoke", {
        "session_id": str(claims.session_id), "revoke_installation": True,
    }))


@app.post("/v1/place/updates")
async def place_update(payload: CoarsePlaceUpdate,
                       claims: Annotated[AccessClaims, Depends(require_session)],
                       settings: SettingsDep) -> dict:
    if payload.installation_id != claims.installation_id:
        raise HTTPException(403, "Token is bound to another installation.")
    return _safe(await BackendClient(settings).request(
        "POST", "/internal/native/place/updates", {"update": payload.model_dump(mode="json")}
    ))


@app.get("/v1/place/status")
async def place_status(_: Annotated[AccessClaims, Depends(require_session)],
                       settings: SettingsDep) -> dict:
    return _safe(await BackendClient(settings).request("GET", "/internal/native/place"))


@app.post("/v1/chat")
async def chat(payload: ChatRequest,
               _: Annotated[AccessClaims, Depends(require_session)],
               settings: SettingsDep) -> dict:
    body = payload.model_dump(mode="json")
    body.pop("input_mode", None)
    return _safe(await BackendClient(settings).request("POST", "/internal/native/chat", body))
