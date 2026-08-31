from uuid import uuid4

import pytest

from app.tokens import TokenError, hash_refresh_token, issue_access_token, verify_access_token


def test_short_lived_access_token_expiration_and_binding():
    session_id, installation_id = uuid4(), uuid4()
    token = issue_access_token(session_id=session_id, installation_id=installation_id,
                               owner="owner@example.com", signing_key="k" * 32,
                               lifetime=600, now=1000)
    claims = verify_access_token(token, "k" * 32, now=1599)
    assert claims.session_id == session_id and claims.installation_id == installation_id
    with pytest.raises(TokenError, match="expired"):
        verify_access_token(token, "k" * 32, now=1600)


def test_refresh_hash_is_keyed_and_never_plaintext():
    value = hash_refresh_token("refresh-secret", "p" * 32)
    assert len(value) == 64 and "refresh-secret" not in value
