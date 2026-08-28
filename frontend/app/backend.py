from functools import lru_cache

import google.auth.transport.requests
import httpx
from google.oauth2 import id_token

from app.config import Settings


@lru_cache(maxsize=4)
def _identity_token(audience: str, minute: int) -> str:
    del minute
    request = google.auth.transport.requests.Request()
    return id_token.fetch_id_token(request, audience)


def cloud_run_identity_token(audience: str) -> str:
    import time

    return _identity_token(audience, int(time.time()) // 300)


async def request_backend(
    settings: Settings,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    authority: str = "li",
) -> httpx.Response:
    if authority not in {"li", "owner"}:
        raise ValueError("Unsupported backend authority.")
    token = settings.owner_api_token if authority == "owner" else settings.li_api_token
    headers = {
        "Authorization": f"Bearer {token.get_secret_value()}",
        "X-Serverless-Authorization": (
            f"Bearer {cloud_run_identity_token(settings.backend_audience)}"
        ),
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        return await client.request(
            method,
            f"{settings.backend_url.rstrip('/')}{path}",
            headers=headers,
            json=json_body,
        )
