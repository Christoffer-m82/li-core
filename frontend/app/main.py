from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel, Field

from app.backend import request_backend
from app.config import get_settings
from app.security import (
    OAUTH_STATE_COOKIE,
    SESSION_COOKIE,
    new_session,
    new_state,
    require_user,
    verify_payload,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
settings = get_settings()
app = FastAPI(title="Li OS Web", docs_url=None, redoc_url=None, openapi_url=None)
app.state.settings = settings
app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    conversation_id: str | None = None


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'self'; form-action 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/login")
def login() -> Response:
    if not settings.google_client_id or not settings.google_client_secret.get_secret_value():
        raise HTTPException(status_code=503, detail="Google sign-in is not configured.")
    state, signed_state = new_state(settings)
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": f"{settings.public_origin.rstrip('/')}/auth/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        signed_state,
        max_age=600,
        httponly=True,
        secure=settings.production,
        samesite="lax",
        path="/auth/callback",
    )
    return response


@app.get("/auth/callback")
async def callback(request: Request, code: str, state: str) -> Response:
    signed = verify_payload(
        request.cookies.get(OAUTH_STATE_COOKIE),
        settings.session_secret.get_secret_value(),
        max_age=600,
    )
    if not signed or signed.get("state") != state:
        raise HTTPException(status_code=400, detail="Invalid sign-in state.")
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "redirect_uri": f"{settings.public_origin.rstrip('/')}/auth/callback",
                "grant_type": "authorization_code",
            },
        )
    if token_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Google sign-in failed.")
    token = token_response.json().get("id_token")
    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.google_client_id
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Google sign-in failed.") from exc
    email = str(claims.get("email", ""))
    if not claims.get("email_verified") or email.casefold() != settings.allowed_email.casefold():
        raise HTTPException(status_code=403, detail="This account is not allowed.")
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth/callback")
    response.set_cookie(
        SESSION_COOKIE,
        new_session(email, settings),
        max_age=28800,
        httponly=True,
        secure=settings.production,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/auth/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/session")
def session(email: str = Depends(require_user)) -> dict[str, str]:
    return {"email": email}


@app.get("/api/ready")
async def ready(_: str = Depends(require_user)) -> Response:
    return await proxy("GET", "/ready")


@app.post("/api/chat")
async def chat(payload: ChatRequest, _: str = Depends(require_user)) -> Response:
    body = {"message": payload.message}
    if payload.conversation_id:
        body["conversation_id"] = payload.conversation_id
    return await proxy("POST", "/li/chat", json_body=body)


async def proxy(method: str, path: str, json_body: dict | None = None) -> Response:
    try:
        upstream = await request_backend(settings, method, path, json_body=json_body)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Li is temporarily unreachable.") from exc
    content_type = upstream.headers.get("content-type", "application/json")
    return Response(upstream.content, status_code=upstream.status_code, media_type=content_type)


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/{path:path}", include_in_schema=False)
def shell(path: str) -> FileResponse:
    del path
    return FileResponse(STATIC_DIR / "index.html")
