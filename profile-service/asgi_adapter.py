"""Minimal ASGI transport adapter for the private profile HTTP contract.

This is an injectable application object, not a configured server or deployment entry point.
It deliberately contains no identity verifier, storage provider, framework dependency or fallback.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from http_contract import PRIVATE_HEADERS, PrivateResponse, ProfileHttpContract
from upload_input import MAX_INPUT_BYTES, UploadTooLarge

MAX_HEADER_COUNT = 64
MAX_HEADER_BYTES = 16 * 1024
REQUEST_SECONDS = 30
_SINGLE_HEADERS = frozenset({"authorization", "content-length", "content-type", "if-match"})
_ROUTES = {
    "/v1/profile": frozenset({"GET", "PUT", "DELETE"}),
    "/v1/profile/image": frozenset({"GET"}),
}

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class InvalidTransport(ValueError):
    """Malformed ASGI request data; messages never include attacker-controlled values."""


def _json_error(status: int, detail: str, **headers: str) -> PrivateResponse:
    body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
    return PrivateResponse(
        status,
        body,
        {**PRIVATE_HEADERS, "Content-Type": "application/json", **headers},
    )


def _headers(raw: Any) -> Mapping[str, str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise InvalidTransport("Invalid request headers.")
    if len(raw) > MAX_HEADER_COUNT:
        raise InvalidTransport("Invalid request headers.")
    result: dict[str, str] = {}
    total = 0
    for item in raw:
        if not isinstance(item, Sequence) or len(item) != 2:
            raise InvalidTransport("Invalid request headers.")
        name, value = item
        if not isinstance(name, bytes) or not isinstance(value, bytes):
            raise InvalidTransport("Invalid request headers.")
        total += len(name) + len(value)
        if total > MAX_HEADER_BYTES:
            raise InvalidTransport("Invalid request headers.")
        try:
            key = name.decode("ascii").lower()
            decoded = value.decode("ascii")
        except UnicodeDecodeError:
            raise InvalidTransport("Invalid request headers.") from None
        if not key or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in key):
            raise InvalidTransport("Invalid request headers.")
        if key in _SINGLE_HEADERS and key in result:
            raise InvalidTransport("Invalid request headers.")
        if key in _SINGLE_HEADERS:
            result[key] = decoded
    return result


async def _send_response(send: Send, response: PrivateResponse) -> None:
    headers = [(key.lower().encode("ascii"), value.encode("ascii"))
               for key, value in response.headers.items()]
    headers.append((b"content-length", str(len(response.body)).encode("ascii")))
    await send({"type": "http.response.start", "status": response.status, "headers": headers})
    await send({"type": "http.response.body", "body": response.body})


class ProfileAsgiAdapter:
    """Expose one injected profile contract through an exact, bounded ASGI surface."""

    def __init__(self, contract: ProfileHttpContract) -> None:
        required = ("metadata", "image", "replace", "remove")
        if not all(callable(getattr(contract, name, None)) for name in required):
            raise TypeError("Profile ASGI contract is invalid.")
        self._contract = contract
        self._upload_lock = asyncio.Lock()

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if not isinstance(scope, dict) or scope.get("type") != "http":
            raise ValueError("Profile adapter accepts HTTP scopes only.")
        disconnected = False
        try:
            method = scope.get("method")
            path = scope.get("path")
            if not isinstance(method, str) or not method.isascii() or method != method.upper():
                raise InvalidTransport("Invalid request method.")
            if not isinstance(path, str) or not path.isascii():
                raise InvalidTransport("Invalid request path.")
            raw_path = scope.get("raw_path")
            query = scope.get("query_string", b"")
            if ((raw_path is not None and raw_path != path.encode("ascii"))
                    or not isinstance(query, bytes) or query):
                raise InvalidTransport("Invalid request path.")
            headers = _headers(scope.get("headers", ()))

            allowed = _ROUTES.get(path)
            if allowed is None:
                await _send_response(send, _json_error(404, "Profile route not found."))
                return
            if method not in allowed:
                await _send_response(send, _json_error(
                    405, "Method not allowed.", Allow=", ".join(sorted(allowed)),
                ))
                return

            authorization = headers.get("authorization")
            if method == "GET":
                response = (self._contract.metadata(authorization) if path == "/v1/profile"
                            else self._contract.image(authorization))
            elif method == "DELETE":
                response = self._contract.remove(authorization, if_match=headers.get("if-match"))
            else:
                if self._upload_lock.locked():
                    response = _json_error(503, "Profile photo processing is unavailable.")
                else:
                    async with self._upload_lock:
                        async def chunks():
                            nonlocal disconnected
                            while True:
                                message = await receive()
                                if not isinstance(message, dict):
                                    raise OSError("Upload transport failed.")
                                if message.get("type") == "http.disconnect":
                                    disconnected = True
                                    raise OSError("Upload transport disconnected.")
                                if message.get("type") != "http.request":
                                    raise OSError("Upload transport failed.")
                                body = message.get("body", b"")
                                if not isinstance(body, bytes):
                                    raise OSError("Upload transport failed.")
                                if len(body) > MAX_INPUT_BYTES:
                                    raise UploadTooLarge("Profile photo exceeds the upload limit.")
                                more_body = message.get("more_body", False)
                                if not isinstance(more_body, bool):
                                    raise OSError("Upload transport failed.")
                                if body:
                                    yield body
                                if not more_body:
                                    return

                        try:
                            async with asyncio.timeout(REQUEST_SECONDS):
                                response = await self._contract.replace(
                                    authorization,
                                    chunks(),
                                    content_type=headers.get("content-type", ""),
                                    file_length=headers.get("content-length"),
                                    if_match=headers.get("if-match"),
                                )
                        except TimeoutError:
                            response = _json_error(503, "Profile photo processing is unavailable.")
            if not disconnected:
                await _send_response(send, response)
        except InvalidTransport:
            await _send_response(send, _json_error(400, "Invalid profile request."))
