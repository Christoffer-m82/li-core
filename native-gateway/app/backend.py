import time
from functools import lru_cache

import google.auth.transport.requests
import httpx
from google.oauth2 import id_token

from app.config import Settings


@lru_cache(maxsize=4)
def _identity_token(audience: str, minute: int) -> str:
    del minute
    return id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)


def cloud_run_identity_token(audience: str) -> str:
    return _identity_token(audience, int(time.time()) // 300)


class BackendClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def request(self, method: str, path: str, body: dict | None = None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.settings.backend_api_token.get_secret_value()}"}
        if self.settings.environment.lower() == "production":
            headers["X-Serverless-Authorization"] = (
                f"Bearer {cloud_run_identity_token(self.settings.backend_audience)}"
            )
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            return await client.request(method, f"{self.settings.backend_url.rstrip('/')}{path}",
                                        headers=headers, json=body)
