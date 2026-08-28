import time

from app.security import sign_payload, verify_payload


def test_signed_payload_round_trip():
    secret = "a-secure-test-secret"
    value = sign_payload({"email": "owner@example.com", "iat": int(time.time())}, secret)
    assert verify_payload(value, secret, max_age=60)["email"] == "owner@example.com"


def test_tampered_payload_is_rejected():
    secret = "a-secure-test-secret"
    value = sign_payload({"iat": int(time.time())}, secret)
    assert verify_payload(value + "x", secret, max_age=60) is None


def test_expired_payload_is_rejected():
    secret = "a-secure-test-secret"
    value = sign_payload({"iat": int(time.time()) - 120}, secret)
    assert verify_payload(value, secret, max_age=60) is None

