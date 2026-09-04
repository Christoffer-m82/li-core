"""ASGI transport tests use only synthetic identities, bytes and storage."""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asgi_adapter import MAX_HEADER_BYTES, ProfileAsgiAdapter
from http_contract import (
    IdentityVerificationError,
    PrivateResponse,
    ProfileHttpContract,
)
from profile_application import ProfileApplication, VerifiedWorkloadIdentity
from profile_state import ProfileState, Snapshot

AUTH = (b"authorization", b"Bearer synthetic.test.token")
JPEG = b"\xff\xd8\xffsynthetic"
NORMALIZED = b"\xff\xd8normalized-photo\xff\xd9"
REVISION = "00000000-0000-0000-0000-000000000001"


class Repository:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.reads = 0
        self.writes = 0

    def read(self):
        self.reads += 1
        return self.snapshot

    def compare_and_swap(self, expected, replacement):
        self.writes += 1
        actual = self.snapshot.revision if self.snapshot else "absent"
        if actual != expected:
            return False
        self.snapshot = replacement
        return True


class Decoder:
    async def normalize(self, _upload):
        return NORMALIZED


class Verifier:
    def __init__(self):
        self.calls = 0

    def verify(self, token, *, audience):
        self.calls += 1
        if token != "synthetic.test.token" or audience != "profile-service":
            raise IdentityVerificationError("synthetic rejection")
        return VerifiedWorkloadIdentity("profile-service", "frontend-bff")


def adapter(snapshot=None):
    repository = Repository(snapshot)
    verifier = Verifier()
    application = ProfileApplication(
        ProfileState(repository), Decoder(), expected_audience="profile-service",
        allowed_subject="frontend-bff",
    )
    contract = ProfileHttpContract(application, verifier, audience="profile-service")
    return ProfileAsgiAdapter(contract), repository, verifier


async def request(app, method="GET", path="/v1/profile", headers=(), messages=None, **scope_values):
    incoming = list(messages or [{"type": "http.request", "body": b"", "more_body": False}])
    sent = []
    receives = 0

    async def receive():
        nonlocal receives
        receives += 1
        return incoming.pop(0)

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": method, "path": path, "headers": list(headers)}
    scope.update(scope_values)
    await app(scope, receive, send)
    return sent, receives


def response(sent):
    start, body = sent
    headers = {key.decode(): value.decode() for key, value in start["headers"]}
    return start["status"], headers, body["body"]


class AsgiAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_read_routes_emit_private_complete_responses(self):
        app, repository, verifier = adapter(Snapshot(REVISION, NORMALIZED))
        sent, receives = await request(app, headers=[AUTH])
        status, headers, body = response(sent)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"revision": REVISION, "state": "available"})
        self.assertEqual(headers["cache-control"], "private, no-store")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(int(headers["content-length"]), len(body))
        image_sent, _ = await request(app, path="/v1/profile/image", headers=[AUTH])
        self.assertEqual(response(image_sent), (200, {
            "cache-control": "private, no-store", "x-content-type-options": "nosniff",
            "content-type": "image/jpeg", "content-length": str(len(NORMALIZED)),
        }, NORMALIZED))
        self.assertEqual(receives, 0)
        self.assertEqual(repository.reads, 2)
        self.assertEqual(verifier.calls, 2)

    async def test_upload_streams_only_after_auth_and_commits_normalized_photo(self):
        app, repository, _ = adapter()
        headers = [AUTH, (b"content-type", b"image/jpeg"),
                   (b"content-length", str(len(JPEG)).encode()), (b"if-match", b"absent")]
        sent, receives = await request(app, method="PUT", headers=headers, messages=[
            {"type": "http.request", "body": JPEG[:5], "more_body": True},
            {"type": "http.request", "body": JPEG[5:], "more_body": False},
        ])
        status, _, body = response(sent)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["state"], "available")
        self.assertEqual(repository.snapshot.photo, NORMALIZED)
        self.assertEqual(receives, 2)

    async def test_auth_and_declared_size_rejections_do_not_read_request_body(self):
        for headers, expected in (
            ([(b"content-type", b"image/jpeg"), (b"if-match", b"absent")], 401),
            ([AUTH, (b"content-type", b"image/jpeg"), (b"content-length", b"6000000"),
              (b"if-match", b"absent")], 413),
        ):
            app, repository, _ = adapter()
            sent, receives = await request(app, method="PUT", headers=headers)
            self.assertEqual(response(sent)[0], expected)
            self.assertEqual(receives, 0)
            self.assertEqual(repository.reads, 0 if expected == 401 else 1)
            self.assertEqual(repository.writes, 0)

    async def test_duplicate_non_ascii_and_oversized_headers_fail_closed(self):
        cases = (
            [AUTH, AUTH],
            [(b"authorization", b"Bearer \xff")],
            [(b"x-padding", b"x" * MAX_HEADER_BYTES)],
        )
        for headers in cases:
            app, repository, verifier = adapter()
            sent, receives = await request(app, method="PUT", headers=headers)
            status, _, body = response(sent)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)["detail"], "Invalid profile request.")
            self.assertEqual((repository.reads, repository.writes, verifier.calls, receives), (0, 0, 0, 0))

    async def test_unknown_routes_and_wrong_methods_are_explicit(self):
        app, repository, verifier = adapter()
        missing, _ = await request(app, path="/v1/other", headers=[AUTH])
        self.assertEqual(response(missing)[0], 404)
        wrong, _ = await request(app, method="POST", headers=[AUTH])
        status, headers, _ = response(wrong)
        self.assertEqual(status, 405)
        self.assertEqual(headers["allow"], "DELETE, GET, PUT")
        self.assertEqual((repository.reads, repository.writes, verifier.calls), (0, 0, 0))

    async def test_query_and_encoded_path_aliases_are_rejected_before_auth(self):
        for scope_values in ({"query_string": b"debug=true"}, {"raw_path": b"/v1/%70rofile"}):
            app, repository, verifier = adapter()
            sent, receives = await request(app, headers=[AUTH], **scope_values)
            self.assertEqual(response(sent)[0], 400)
            self.assertEqual((repository.reads, verifier.calls, receives), (0, 0, 0))

    async def test_oversized_received_chunk_is_rejected_without_storage_write(self):
        app, repository, _ = adapter()
        headers = [AUTH, (b"content-type", b"image/jpeg"), (b"if-match", b"absent")]
        sent, receives = await request(app, method="PUT", headers=headers, messages=[
            {"type": "http.request", "body": b"x" * (5 * 1024 * 1024 + 1), "more_body": False},
        ])
        self.assertEqual(response(sent)[0], 413)
        self.assertEqual(receives, 1)
        self.assertEqual(repository.writes, 0)

    async def test_disconnect_aborts_without_response_or_storage_write(self):
        app, repository, _ = adapter()
        headers = [AUTH, (b"content-type", b"image/jpeg"), (b"if-match", b"absent")]
        sent, receives = await request(app, method="PUT", headers=headers, messages=[
            {"type": "http.disconnect"},
        ])
        self.assertEqual(sent, [])
        self.assertEqual(receives, 1)
        self.assertEqual(repository.writes, 0)

    async def test_malformed_continuation_flag_fails_without_storage_write(self):
        app, repository, _ = adapter()
        headers = [AUTH, (b"content-type", b"image/jpeg"), (b"if-match", b"absent")]
        sent, receives = await request(app, method="PUT", headers=headers, messages=[
            {"type": "http.request", "body": JPEG, "more_body": "false"},
        ])
        self.assertEqual(response(sent)[0], 422)
        self.assertEqual(receives, 1)
        self.assertEqual(repository.writes, 0)

    async def test_overall_deadline_returns_generic_unavailable_and_releases_slot(self):
        started = 0

        class SlowContract:
            def metadata(self, _authorization):
                raise AssertionError

            def image(self, _authorization):
                raise AssertionError

            def remove(self, _authorization, *, if_match):
                raise AssertionError

            async def replace(self, *_args, **_kwargs):
                nonlocal started
                started += 1
                await asyncio.Event().wait()

        app = ProfileAsgiAdapter(SlowContract())
        headers = [AUTH, (b"content-type", b"image/jpeg"), (b"if-match", b"absent")]
        with patch("asgi_adapter.REQUEST_SECONDS", 0.001):
            first, _ = await request(app, method="PUT", headers=headers)
            second, _ = await request(app, method="PUT", headers=headers)
        self.assertEqual((response(first)[0], response(second)[0], started), (503, 503, 2))

    async def test_second_upload_is_rejected_instead_of_queued(self):
        started = asyncio.Event()
        release = asyncio.Event()

        class BlockingContract:
            def metadata(self, _authorization):
                raise AssertionError

            def image(self, _authorization):
                raise AssertionError

            def remove(self, _authorization, *, if_match):
                raise AssertionError

            async def replace(self, *_args, **_kwargs):
                started.set()
                await release.wait()
                return PrivateResponse(200)

        app = ProfileAsgiAdapter(BlockingContract())
        headers = [AUTH, (b"content-type", b"image/jpeg"), (b"if-match", b"absent")]
        first_sent = []

        async def receive():
            return {"type": "http.request", "body": JPEG, "more_body": False}

        async def send(message):
            first_sent.append(message)

        first = asyncio.create_task(app(
            {"type": "http", "method": "PUT", "path": "/v1/profile", "headers": headers},
            receive, send,
        ))
        await started.wait()
        second, receives = await request(app, method="PUT", headers=headers)
        self.assertEqual(response(second)[0], 503)
        self.assertEqual(receives, 0)
        first.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await first

    async def test_non_http_scope_and_invalid_dependency_are_rejected(self):
        with self.assertRaises(TypeError):
            ProfileAsgiAdapter(object())
        app, _, _ = adapter()
        with self.assertRaises(ValueError):
            await app({"type": "lifespan"}, None, None)


if __name__ == "__main__":
    unittest.main()
