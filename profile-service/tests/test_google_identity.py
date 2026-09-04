"""Identity tests use synthetic claims and never decode or transmit a real token."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google_identity import GoogleWorkloadIdentityVerifier
from http_contract import IdentityVerificationError
from profile_application import VerifiedWorkloadIdentity

TOKEN = "synthetic.signed.token"
AUDIENCE = "https://profile.example"
MISSING = object()


class VerificationFailure(Exception):
    pass


class Verifier:
    def __init__(self, claims=MISSING, error=None):
        self.claims = {
            "iss": "https://accounts.google.com",
            "aud": AUDIENCE,
            "sub": "123456789012345678901",
            "email": "not-forwarded@example.invalid",
        } if claims is MISSING else claims
        self.error = error
        self.calls = []

    def __call__(self, token, request, *, audience):
        self.calls.append((token, request, audience))
        if self.error:
            raise self.error
        return self.claims


def identity(verifier=None):
    request = object()
    verifier = verifier or Verifier()
    return GoogleWorkloadIdentityVerifier(
        request, verifier, (VerificationFailure, ValueError),
    ), request, verifier


class GoogleIdentityTests(unittest.TestCase):
    def test_verified_token_is_reduced_to_audience_and_subject(self):
        adapter, request, verifier = identity()
        result = adapter.verify(TOKEN, audience=AUDIENCE)
        self.assertEqual(result, VerifiedWorkloadIdentity(AUDIENCE, "123456789012345678901"))
        self.assertEqual(verifier.calls, [(TOKEN, request, AUDIENCE)])
        self.assertFalse(hasattr(result, "email"))

    def test_both_documented_google_issuers_are_accepted(self):
        for issuer in ("accounts.google.com", "https://accounts.google.com"):
            verifier = Verifier({"iss": issuer, "aud": AUDIENCE, "sub": "123"})
            self.assertEqual(identity(verifier)[0].verify(TOKEN, audience=AUDIENCE).subject, "123")

    def test_library_verification_failures_are_generic(self):
        for error in (VerificationFailure("private certificate detail"), ValueError("private claim detail")):
            adapter, _, _ = identity(Verifier(error=error))
            with self.assertRaises(IdentityVerificationError) as raised:
                adapter.verify(TOKEN, audience=AUDIENCE)
            self.assertEqual(str(raised.exception), "Authentication failed.")

    def test_invalid_minimized_claims_fail_closed(self):
        cases = (
            None,
            {},
            {"iss": [], "aud": AUDIENCE, "sub": "123"},
            {"iss": "https://issuer.invalid", "aud": AUDIENCE, "sub": "123"},
            {"iss": "https://accounts.google.com", "aud": "wrong", "sub": "123"},
            {"iss": "https://accounts.google.com", "aud": AUDIENCE, "sub": ""},
            {"iss": "https://accounts.google.com", "aud": AUDIENCE, "sub": "bad subject"},
            {"iss": "https://accounts.google.com", "aud": AUDIENCE, "sub": 123},
        )
        for claims in cases:
            verifier = Verifier(claims)
            with self.assertRaises(IdentityVerificationError):
                identity(verifier)[0].verify(TOKEN, audience=AUDIENCE)

    def test_malformed_token_and_audience_never_reach_verifier(self):
        invalid = (
            ("", AUDIENCE),
            ("has whitespace", AUDIENCE),
            ("å", AUDIENCE),
            ("x" * 8193, AUDIENCE),
            (TOKEN, ""),
            (TOKEN, "bad audience"),
            (TOKEN, "å"),
        )
        for token, audience in invalid:
            adapter, _, verifier = identity()
            with self.assertRaises(IdentityVerificationError):
                adapter.verify(token, audience=audience)
            self.assertEqual(verifier.calls, [])

    def test_constructor_rejects_unbound_or_overbroad_dependencies(self):
        with self.assertRaises(TypeError):
            GoogleWorkloadIdentityVerifier(None, Verifier(), (ValueError,))
        with self.assertRaises(TypeError):
            GoogleWorkloadIdentityVerifier(object(), object(), (ValueError,))
        for errors in ((), (Exception,), ("ValueError",)):
            with self.assertRaises(TypeError):
                GoogleWorkloadIdentityVerifier(object(), Verifier(), errors)

    def test_unclassified_programming_errors_are_not_hidden(self):
        adapter, _, _ = identity(Verifier(error=RuntimeError("synthetic bug")))
        with self.assertRaises(RuntimeError):
            adapter.verify(TOKEN, audience=AUDIENCE)


if __name__ == "__main__":
    unittest.main()
