import base64
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
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
    temporary_upload_context: str | None = Field(default=None, max_length=6000)


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "application/pdf", "text/plain", "text/markdown", "text/csv",
    "application/json", "image/png", "image/jpeg", "image/webp",
}
SPECIALISTS = (
    {"id": "sofia", "name": "Sofia", "role": "Health & medical", "initials": "SO"},
    {"id": "marco", "name": "Marco", "role": "Fitness & performance", "initials": "MA"},
    {"id": "elena", "name": "Elena", "role": "Nutrition, food & drink", "initials": "EL"},
    {"id": "amelia", "name": "Amelia", "role": "Relationships & social", "initials": "AM"},
    {"id": "freja", "name": "Freja", "role": "Parenting & family", "initials": "FR"},
    {"id": "oliver", "name": "Oliver", "role": "Legal & regulatory", "initials": "OL"},
    {"id": "james", "name": "James", "role": "Finance & wealth", "initials": "JA"},
    {"id": "nora", "name": "Nora", "role": "Research & evidence", "initials": "NO"},
    {"id": "victor", "name": "Victor", "role": "Strategy & decisions", "initials": "VI"},
    {"id": "milo", "name": "Milo", "role": "Travel & experiences", "initials": "MI"},
    {"id": "iris", "name": "Iris", "role": "Home, design & garden", "initials": "IR"},
    {"id": "clara", "name": "Clara", "role": "Wellbeing & habits", "initials": "CL"},
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if (
        request.url.path == "/api/uploads"
        and content_length
        and int(content_length) > MAX_UPLOAD_BYTES + 256 * 1024
    ):
        response = JSONResponse(status_code=413, content={"detail": "Files must be 10 MB or smaller."})
    else:
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
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(self)",
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


@app.get("/api/capabilities")
async def capabilities(_: str = Depends(require_user)) -> Response:
    return await proxy("GET", "/capabilities")


@app.post("/api/chat")
async def chat(payload: ChatRequest, _: str = Depends(require_user)) -> Response:
    body = {"message": payload.message}
    if payload.conversation_id:
        body["conversation_id"] = payload.conversation_id
    if payload.temporary_upload_context:
        body["temporary_upload_context"] = payload.temporary_upload_context
    return await proxy("POST", "/li/chat", json_body=body)


@app.post("/api/uploads")
async def upload_for_chat(
    file: UploadFile = File(...), save: bool = Form(False), _: str = Depends(require_user)
) -> Response:
    """Validate an upload and send it to Li's temporary analysis boundary."""
    filename = Path(file.filename or "").name
    if not filename or filename != (file.filename or ""):
        await file.close()
        raise HTTPException(status_code=400, detail="The filename is invalid.")
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        await file.close()
        raise HTTPException(status_code=415, detail="This file type is not supported.")
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Files must be 10 MB or smaller.")
    return await proxy("POST", "/artifacts/uploads", json_body={
        "filename": filename, "content_type": file.content_type,
        "data_base64": base64.b64encode(contents).decode("ascii"), "save": save,
    })


@app.get("/api/artifacts/{artifact_id}")
async def download_artifact(artifact_id: str, _: str = Depends(require_user)) -> Response:
    try:
        from uuid import UUID
        UUID(artifact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artifact identifier.")
    try:
        upstream = await request_backend(settings, "GET", f"/artifacts/{artifact_id}")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Artifact is temporarily unreachable.") from exc
    return Response(upstream.content, status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
        headers={"Content-Disposition": upstream.headers.get("content-disposition", "attachment")})


@app.get("/api/artifacts")
async def artifact_library(_: str = Depends(require_user)) -> Response:
    return await proxy("GET", "/artifacts")


@app.post("/api/artifacts/{artifact_id}/retention")
async def artifact_retention(artifact_id: str, request: Request,
                             _: str = Depends(require_user)) -> Response:
    try:
        action = (await request.json()).get("action")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid request.") from exc
    return await proxy("POST", f"/artifacts/{artifact_id}/retention", json_body={"action": action})


@app.get("/api/specialists")
async def specialists(_: str = Depends(require_user)) -> dict[str, object]:
    upstream = await request_backend(settings, "GET", "/specialists/interactions")
    events = upstream.json().get("interactions", []) if upstream.status_code == 200 else []
    active = {event["specialist_key"] for event in events if event["status"] == "active"}
    return {"specialists": [dict(item, active=item["id"] in active,
        status="Working" if item["id"] in active else "Available") for item in SPECIALISTS],
        "live_events_available": True}


@app.get("/api/specialists/{specialist_id}/interactions")
async def specialist_interactions(
    specialist_id: str, _: str = Depends(require_user)
) -> dict[str, object]:
    specialist = next((item for item in SPECIALISTS if item["id"] == specialist_id), None)
    if specialist is None:
        raise HTTPException(status_code=404, detail="Specialist not found.")
    upstream = await request_backend(
        settings, "GET", f"/specialists/interactions?specialist={specialist_id}"
    )
    interactions = upstream.json().get("interactions", []) if upstream.status_code == 200 else []
    return {"specialist": specialist, "active": any(x["status"] == "active" for x in interactions),
        "interactions": interactions, "live_events_available": True,
        "message": "No real Li-specialist interactions have been recorded yet."}


@app.get("/api/conversations")
async def conversations(_: str = Depends(require_user)) -> Response:
    return await proxy("GET", "/conversations")


@app.get("/api/agents/analytics")
async def agents_analytics(period: str = "30d", _: str = Depends(require_user)) -> Response:
    return await proxy("GET", f"/agents/analytics?period={period}")


@app.post("/api/agents/relevance-review")
async def agents_relevance_review(request: Request, _: str = Depends(require_user)) -> Response:
    period = (await request.json()).get("period", "90d")
    return await proxy("POST", f"/agents/relevance-review?period={period}")


@app.post("/api/agents/settings")
async def agents_settings(request: Request, _: str = Depends(require_user)) -> Response:
    return await proxy("POST", "/agents/settings", json_body=await request.json())


@app.post("/api/agents/recommendations/{recommendation_id}/review")
async def agent_recommendation_review(recommendation_id: str, request: Request,
                                      _: str = Depends(require_user)) -> Response:
    try:
        from uuid import UUID
        UUID(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recommendation identifier.")
    return await proxy("POST", f"/agents/recommendations/{recommendation_id}/review",
                       json_body=await request.json())


@app.post("/api/agents/recommendations/{recommendation_id}/execute")
async def agent_recommendation_execute(recommendation_id: str, request: Request,
                                       _: str = Depends(require_user)) -> Response:
    try:
        from uuid import UUID
        UUID(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recommendation identifier.")
    return await proxy("POST", f"/owner/agents/recommendations/{recommendation_id}/execute",
                       json_body=await request.json(), authority="owner")


@app.get("/api/conversations/{conversation_id}")
async def conversation(conversation_id: str, _: str = Depends(require_user)) -> Response:
    return await proxy("GET", f"/conversations/{conversation_id}")


@app.post("/api/conversations/{conversation_id}/delete")
async def delete_conversation(conversation_id: str, request: Request,
                              _: str = Depends(require_user)) -> Response:
    try:
        from uuid import UUID
        UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation identifier.")
    return await proxy("POST", f"/owner/conversations/{conversation_id}/delete",
                       json_body=await request.json(), authority="owner")


@app.get("/api/privacy/settings")
async def privacy_settings(_: str = Depends(require_user)) -> Response:
    return await proxy("GET", "/privacy/settings")


@app.post("/api/privacy/settings")
async def update_privacy_settings(request: Request, _: str = Depends(require_user)) -> Response:
    return await proxy("POST", "/privacy/settings", json_body=await request.json())


async def proxy(method: str, path: str, json_body: dict | None = None,
                authority: str = "li") -> Response:
    try:
        upstream = await request_backend(settings, method, path, json_body=json_body,
                                         authority=authority)
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


@app.api_route("/api/{path:path}", methods=["GET", "POST"], include_in_schema=False)
def unknown_api(path: str) -> Response:
    del path
    raise HTTPException(status_code=404, detail="API route not found.")


@app.get("/{path:path}", include_in_schema=False)
def shell(path: str) -> FileResponse:
    del path
    return FileResponse(STATIC_DIR / "index.html")
