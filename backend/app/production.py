"""Production HTTP controls and JSON logging without credential values."""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
SENSITIVE = re.compile(r"(?i)(authorization|api[-_]?key|token|secret|password)")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = SENSITIVE.sub("[REDACTED]", record.getMessage())
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
                "request_id": request_id_context.get(),
            },
            separators=(",", ":"),
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        *,
        requests: int,
        window_seconds: int,
        trust_proxy_headers: bool,
    ) -> None:
        super().__init__(app)
        self.limit = requests
        self.window = window_seconds
        self.trust_proxy_headers = trust_proxy_headers
        self.hits: defaultdict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))[:128]
        token = request_id_context.set(request_id)
        try:
            client = request.client.host if request.client else "unknown"
            if self.trust_proxy_headers:
                client = request.headers.get("x-forwarded-for", client).split(",", 1)[0].strip()
            now = time.monotonic()
            bucket = self.hits[client]
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return JSONResponse(
                    {"detail": "Too many requests."},
                    status_code=429,
                    headers={"Retry-After": str(self.window), "X-Request-ID": request_id},
                )
            bucket.append(now)
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            request_id_context.reset(token)
