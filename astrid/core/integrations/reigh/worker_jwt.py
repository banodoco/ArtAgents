"""JWKS-backed user-JWT verification for the AA banodoco worker.

Mirrors ``banodoco-worker/worker_jwt.py``: verifies a Reigh user JWT against
the Reigh Supabase JWKS endpoint (signature, audience, expiry) and returns the
verified subject.

USED FOR AUTHORIZATION ONLY. The worker still writes via service-role; JWKS
verification proves *identity*, not project ownership. ``banodoco_worker`` is
responsible for the additional project-ownership read against
``projects.user_id`` (FLAG-013) before invoking the service-role RPC.

The reference implementation uses ``python-jose``; this one uses PyJWT (which
is already in the AA test runner's environment) for an equivalent verification
surface.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import jwt as pyjwt  # PyJWT
from jwt import InvalidTokenError, PyJWKClient

from . import env as reigh_env

logger = logging.getLogger(__name__)


DEFAULT_AUDIENCE = "authenticated"
JWKS_CACHE_TTL_SEC = 300


class JwtVerificationError(RuntimeError):
    """Raised when a user JWT fails verification."""


class JwksConfigurationError(JwtVerificationError):
    """The configured JWKS URL/value is malformed (e.g. a placeholder)."""


class JwksFetchError(JwtVerificationError):
    """The JWKS endpoint could not be reached or returned an unexpected payload."""


@dataclass(frozen=True)
class VerifiedJwt:
    user_id: str
    audience: str
    raw_claims: dict[str, Any]


_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _fetch_jwks(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    now = time.time()
    cached = _jwks_cache.get(url)
    if cached and (now - cached[0]) < JWKS_CACHE_TTL_SEC:
        return cached[1]
    try:
        request = urllib.request.Request(url, method="GET")
    except (ValueError, TypeError) as exc:
        raise JwksConfigurationError(f"Malformed JWKS URL: {url!r}") from exc
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise JwksFetchError(f"Failed to fetch JWKS from {url}: {exc}") from exc
    if not isinstance(data, dict) or "keys" not in data:
        raise JwksFetchError(f"JWKS endpoint at {url} returned unexpected payload")
    _jwks_cache[url] = (now, data)
    return data


def _select_signing_key(jwks: Mapping[str, Any], token: str) -> Any:
    try:
        unverified_header = pyjwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise JwtVerificationError(f"Malformed JWT header: {exc}") from exc
    kid = unverified_header.get("kid")
    keys = jwks.get("keys") or []
    matched: Optional[Mapping[str, Any]] = None
    for key in keys:
        if not isinstance(key, dict):
            continue
        if key.get("kid") == kid or kid is None:
            matched = key
            break
    if matched is None:
        raise JwtVerificationError(f"No JWKS key matched JWT kid={kid!r}")
    try:
        return PyJWKClient.signing_key_from_jwk(json.dumps(matched)).key  # type: ignore[attr-defined]
    except AttributeError:
        from jwt.algorithms import RSAAlgorithm

        return RSAAlgorithm.from_jwk(json.dumps(matched))


def verify_user_jwt(
    token: str,
    *,
    audience: str | None = None,
    jwks_url: str | None = None,
    jwt_secret: str | None = None,
    timeout: float = 10.0,
) -> VerifiedJwt:
    """Verify a user JWT against the configured JWKS.

    Returns a :class:`VerifiedJwt` on success; raises
    :class:`JwtVerificationError` on bad signature, wrong audience, expiry,
    missing ``sub``, or JWKS failure. Worker callers should reject the task
    with ``failure_code='auth_failed'`` on this exception.
    """

    if not isinstance(token, str) or not token:
        raise JwtVerificationError("token must be a non-empty string")

    expected_audience = audience or DEFAULT_AUDIENCE
    try:
        unverified_header = pyjwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise JwtVerificationError(f"Malformed JWT header: {exc}") from exc
    algorithm = unverified_header.get("alg") or "RS256"

    # Supabase GoTrue access tokens are HS256, signed with the project JWT
    # secret; the project JWKS endpoint often serves an EMPTY key set for such
    # projects, so JWKS verification can never succeed. Verify HS256 tokens
    # with the configured JWT secret instead.
    if algorithm == "HS256":
        if not jwt_secret:
            raise JwksConfigurationError(
                "HS256 user token requires the project JWT secret "
                "(REIGH_SUPABASE_JWT_SECRET / SUPABASE_JWT_SECRET)"
            )
        try:
            claims = pyjwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience=expected_audience,
                options={"verify_signature": True, "verify_aud": True, "verify_exp": True},
            )
        except InvalidTokenError as exc:
            raise JwtVerificationError(f"JWT signature/claims verification failed: {exc}") from exc
    else:
        url = jwks_url or reigh_env.resolve_jwks_url()
        jwks = _fetch_jwks(url, timeout=timeout)
        key = _select_signing_key(jwks, token)
        try:
            claims = pyjwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=expected_audience,
                options={"verify_signature": True, "verify_aud": True, "verify_exp": True},
            )
        except InvalidTokenError as exc:
            raise JwtVerificationError(f"JWT signature/claims verification failed: {exc}") from exc

    if not isinstance(claims, dict):
        raise JwtVerificationError("Decoded JWT did not yield a claims object")

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise JwtVerificationError("JWT missing required 'sub' claim")

    aud_claim = claims.get("aud")
    if isinstance(aud_claim, str):
        audience_str = aud_claim
    elif isinstance(aud_claim, list) and aud_claim:
        audience_str = str(aud_claim[0])
    else:
        audience_str = ""

    return VerifiedJwt(user_id=user_id, audience=audience_str, raw_claims=dict(claims))


__all__ = [
    "DEFAULT_AUDIENCE",
    "JwtVerificationError",
    "VerifiedJwt",
    "verify_user_jwt",
]
