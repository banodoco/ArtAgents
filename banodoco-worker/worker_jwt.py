"""User-JWT verification for the banodoco-worker (SD-022 + SD-034 identity).

Primary mechanism: verify the user JWT against Reigh's Supabase JWKS endpoint
using `python-jose`. Confirm `aud=authenticated`. Reject without considering
the service-role on the success path — service-role lives only behind the
optional `verify_via_service_role_fallback` path documented for outages.

Configuration:
  REIGH_SUPABASE_URL                — base URL for the Reigh project
                                       (e.g. https://abc.supabase.co)
  REIGH_SUPABASE_JWKS_URL           — explicit JWKS URL override (optional)
  REIGH_SUPABASE_JWT_AUDIENCE       — defaults to "authenticated"
  REIGH_SUPABASE_SERVICE_ROLE_KEY   — fallback only, see notes below

The JWKS URL canonical path is:
    {REIGH_SUPABASE_URL}/auth/v1/.well-known/jwks.json
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError

logger = logging.getLogger(__name__)


DEFAULT_AUDIENCE = "authenticated"
JWKS_CACHE_TTL_SEC = 300  # 5 minutes


@dataclass
class VerifiedJwt:
    user_id: str
    audience: str
    raw_claims: Dict[str, Any]


class JwtVerificationError(Exception):
    """Raised when a JWT fails verification — the worker rejects the task."""


# In-process JWKS cache keyed by URL. JWKS endpoints are tiny and rarely
# change; a 5-minute TTL trades a small staleness window for hugely fewer
# round-trips when a worker is processing many tasks for the same project.
_jwks_cache: Dict[str, Dict[str, Any]] = {}
_jwks_cache_at: Dict[str, float] = {}


def _resolve_jwks_url() -> str:
    explicit = os.getenv("REIGH_SUPABASE_JWKS_URL")
    if explicit:
        return explicit
    base = os.getenv("REIGH_SUPABASE_URL", "").rstrip("/")
    if not base:
        raise JwtVerificationError(
            "Either REIGH_SUPABASE_URL or REIGH_SUPABASE_JWKS_URL must be set"
        )
    return f"{base}/auth/v1/.well-known/jwks.json"


def _fetch_jwks(url: str, *, http: Optional[httpx.Client] = None) -> Dict[str, Any]:
    import time

    now = time.time()
    cached_at = _jwks_cache_at.get(url, 0.0)
    if url in _jwks_cache and (now - cached_at) < JWKS_CACHE_TTL_SEC:
        return _jwks_cache[url]

    client = http or httpx.Client(timeout=10)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise JwtVerificationError(f"Failed to fetch JWKS from {url}: {exc}") from exc
    finally:
        if http is None:
            client.close()

    if not isinstance(data, dict) or "keys" not in data:
        raise JwtVerificationError(f"JWKS endpoint at {url} returned unexpected payload")

    _jwks_cache[url] = data
    _jwks_cache_at[url] = now
    return data


def verify_user_jwt(
    token: str,
    *,
    audience: Optional[str] = None,
    jwks_url: Optional[str] = None,
    http: Optional[httpx.Client] = None,
) -> VerifiedJwt:
    """Verify a Reigh user JWT using JWKS.

    Returns a VerifiedJwt on success; raises JwtVerificationError on any
    failure mode (bad signature, wrong audience, missing sub, JWKS fetch
    failed). Worker callers should reject the task with code `auth_failed`.
    """
    if not token or not isinstance(token, str):
        raise JwtVerificationError("token must be a non-empty string")

    expected_audience = audience or os.getenv(
        "REIGH_SUPABASE_JWT_AUDIENCE", DEFAULT_AUDIENCE
    )
    url = jwks_url or _resolve_jwks_url()
    jwks = _fetch_jwks(url, http=http)

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JwtVerificationError(f"Malformed JWT header: {exc}") from exc

    kid = unverified_header.get("kid")
    matching_key: Optional[Dict[str, Any]] = None
    for key in jwks.get("keys", []):
        if not isinstance(key, dict):
            continue
        if key.get("kid") == kid or kid is None:
            matching_key = key
            break
    if matching_key is None:
        raise JwtVerificationError(f"No JWKS key matched JWT kid={kid!r}")

    try:
        claims = jwt.decode(
            token,
            matching_key,
            algorithms=[matching_key.get("alg") or unverified_header.get("alg") or "RS256"],
            audience=expected_audience,
            options={"verify_aud": True, "verify_signature": True, "verify_exp": True},
        )
    except JWTError as exc:
        raise JwtVerificationError(f"JWT signature/claims verification failed: {exc}") from exc

    if not isinstance(claims, dict):
        raise JwtVerificationError("Decoded JWT did not yield a claims object")

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise JwtVerificationError("JWT missing required 'sub' claim")

    aud_claim = claims.get("aud")
    audience_str = (
        aud_claim
        if isinstance(aud_claim, str)
        else (aud_claim[0] if isinstance(aud_claim, list) and aud_claim else "")
    )

    return VerifiedJwt(user_id=user_id, audience=audience_str, raw_claims=claims)


def verify_via_service_role_fallback(
    token: str,
    *,
    http: Optional[httpx.Client] = None,
) -> VerifiedJwt:
    """SD-022 fallback path — only used when JWKS fetch fails.

    NOT optimized in v1 (per sprint brief: "Document but don't optimize the
    fallback"). This calls Reigh's service-role-protected /auth/v1/user
    endpoint with the user JWT to confirm identity. Production code should
    prefer the JWKS path; reach this function only when JWKS is unreachable.
    """
    base = os.getenv("REIGH_SUPABASE_URL", "").rstrip("/")
    service_role = os.getenv("REIGH_SUPABASE_SERVICE_ROLE_KEY")
    if not base or not service_role:
        raise JwtVerificationError(
            "Service-role fallback requires REIGH_SUPABASE_URL + "
            "REIGH_SUPABASE_SERVICE_ROLE_KEY"
        )

    url = f"{base}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": service_role,
    }
    client = http or httpx.Client(timeout=10)
    try:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            raise JwtVerificationError(
                f"Service-role fallback rejected token: {resp.status_code} {resp.text[:200]}"
            )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise JwtVerificationError(f"Service-role fallback failed: {exc}") from exc
    finally:
        if http is None:
            client.close()

    user_id = data.get("id") if isinstance(data, dict) else None
    if not isinstance(user_id, str) or not user_id.strip():
        raise JwtVerificationError(
            "Service-role fallback response missing user id"
        )
    return VerifiedJwt(user_id=user_id, audience=DEFAULT_AUDIENCE, raw_claims=data)


__all__ = [
    "DEFAULT_AUDIENCE",
    "JwtVerificationError",
    "VerifiedJwt",
    "verify_user_jwt",
    "verify_via_service_role_fallback",
]
