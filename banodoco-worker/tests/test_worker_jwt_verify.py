"""JWT verification tests (SD-022 + SD-034 identity surface).

Generates RSA key pairs in-memory, builds a JWT, exposes the matching
JWKS via a stub `httpx.Client`, and exercises the verifier.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt

from worker_jwt import (
    JwtVerificationError,
    verify_user_jwt,
)


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture()
def rsa_key_and_jwks() -> Dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    public_numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "test-kid",
        "use": "sig",
        "alg": "RS256",
        "n": _b64url_uint(public_numbers.n),
        "e": _b64url_uint(public_numbers.e),
    }
    return {
        "private_pem": pem,
        "jwks": {"keys": [jwk]},
        "kid": "test-kid",
    }


def _stub_http(jwks: Dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = jwks
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.get.return_value = response
    return client


def test_verify_user_jwt_happy_path(rsa_key_and_jwks):
    token = jose_jwt.encode(
        {
            "sub": "user-123",
            "aud": "authenticated",
            "exp": int(time.time()) + 600,
            "iat": int(time.time()),
        },
        rsa_key_and_jwks["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_key_and_jwks["kid"]},
    )
    http = _stub_http(rsa_key_and_jwks["jwks"])

    verified = verify_user_jwt(
        token,
        audience="authenticated",
        jwks_url="https://example.test/jwks",
        http=http,
    )
    assert verified.user_id == "user-123"
    assert verified.audience == "authenticated"


def test_verify_user_jwt_rejects_corrupted_token(rsa_key_and_jwks):
    http = _stub_http(rsa_key_and_jwks["jwks"])
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(
            "not.a.valid.jwt",
            audience="authenticated",
            jwks_url="https://example.test/jwks",
            http=http,
        )


def test_verify_user_jwt_rejects_wrong_audience(rsa_key_and_jwks):
    token = jose_jwt.encode(
        {
            "sub": "user-123",
            "aud": "service",  # wrong audience
            "exp": int(time.time()) + 600,
        },
        rsa_key_and_jwks["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_key_and_jwks["kid"]},
    )
    http = _stub_http(rsa_key_and_jwks["jwks"])
    with pytest.raises(JwtVerificationError) as exc:
        verify_user_jwt(
            token,
            audience="authenticated",
            jwks_url="https://example.test/jwks",
            http=http,
        )
    # python-jose surfaces "Invalid audience" or similar
    assert "audience" in str(exc.value).lower() or "verification failed" in str(exc.value).lower()


def test_verify_user_jwt_rejects_expired_token(rsa_key_and_jwks):
    token = jose_jwt.encode(
        {
            "sub": "user-123",
            "aud": "authenticated",
            "exp": int(time.time()) - 60,  # expired
            "iat": int(time.time()) - 600,
        },
        rsa_key_and_jwks["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_key_and_jwks["kid"]},
    )
    http = _stub_http(rsa_key_and_jwks["jwks"])
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(
            token,
            audience="authenticated",
            jwks_url="https://example.test/jwks",
            http=http,
        )


def test_verify_user_jwt_rejects_missing_sub(rsa_key_and_jwks):
    token = jose_jwt.encode(
        {
            # No 'sub' claim
            "aud": "authenticated",
            "exp": int(time.time()) + 600,
        },
        rsa_key_and_jwks["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_key_and_jwks["kid"]},
    )
    http = _stub_http(rsa_key_and_jwks["jwks"])
    # Either the verifier raises with a "sub" message OR python-jose
    # rejects the token outright before we get to our sub check. Both
    # outcomes are correct (no JWT lacking `sub` should ever be honored).
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(
            token,
            audience="authenticated",
            jwks_url="https://example.test/jwks",
            http=http,
        )


def test_verify_user_jwt_rejects_empty_token():
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(
            "",
            audience="authenticated",
            jwks_url="https://example.test/jwks",
            http=_stub_http({"keys": []}),
        )


def test_verify_user_jwt_rejects_when_no_kid_match(rsa_key_and_jwks):
    token = jose_jwt.encode(
        {
            "sub": "user-123",
            "aud": "authenticated",
            "exp": int(time.time()) + 600,
        },
        rsa_key_and_jwks["private_pem"],
        algorithm="RS256",
        headers={"kid": "totally-different-kid"},
    )
    # JWKS only contains the original kid — but the token says totally-different-kid.
    http = _stub_http(rsa_key_and_jwks["jwks"])
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(
            token,
            audience="authenticated",
            jwks_url="https://example.test/jwks",
            http=http,
        )
