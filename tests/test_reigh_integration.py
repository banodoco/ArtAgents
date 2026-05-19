"""Integration test for the Reigh integration layer.

Unlike the per-module unit tests under ``tests/test_worker_jwt.py``,
``tests/test_supabase_data_provider.py``, and ``tests/test_task_client.py``
— each of which mocks out the next module down — this test wires the
real code paths together:

  * a real RSA keypair signs a real JWT
  * ``astrid.core.reigh.worker_jwt.verify_user_jwt`` decodes it against
    a real JWKS payload
  * ``SupabaseDataProvider.save_timeline`` calls real
    ``timeline_io.save_timeline`` which calls real
    ``timeline_io.fetch_timeline`` which calls real
    ``supabase_client.post_json`` / ``supabase_client.rpc``
  * Astrid's real ``timeline.Timeline`` round-trips the config

The only thing faked is the *external* HTTP boundary: ``urllib.request
.urlopen`` is patched to a small in-memory Supabase stand-in that records
each call (URL, headers, body) and serves canned responses. This lets a
JWT-claim regression, a missing ``config_version`` in the edge-function
payload, an RPC argument-shape drift, or a version-conflict retry-loop
bug surface end-to-end instead of being swallowed by a per-module mock.

The element-catalog pack loader has a pre-existing bug (the
``packs/local/elements/effects/_shared`` folder has no manifest and the
loader raises ``ElementValidationError`` while Astrid validates a clip's
``clipType`` against the effects catalog). We side-step that by stubbing
``timeline._effect_ids`` / ``_animation_ids`` / ``_transition_ids`` to
empty sets, which is exactly the surface ``validate_timeline`` consults.
This is flagged in the report, not silently fixed.
"""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
from dataclasses import dataclass, field
from typing import Any

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from astrid import timeline as timeline_mod
from astrid.core.reigh import worker_jwt
from astrid.core.reigh.data_provider import SupabaseDataProvider
from astrid.core.reigh.errors import (
    TimelineNotFoundError,
    TimelineVersionConflictError,
)
from astrid.core.reigh.worker_jwt import (
    DEFAULT_AUDIENCE,
    JwtVerificationError,
    verify_user_jwt,
)


# ---------------------------------------------------------------------------
# Shared fixtures: RSA keypair, JWKS, canonical timeline.
# ---------------------------------------------------------------------------

SUPABASE_URL = "https://example.supabase.co"
FETCH_URL = f"{SUPABASE_URL}/functions/v1/reigh-data-fetch"
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
RPC_URL = f"{SUPABASE_URL}/rest/v1/rpc/update_timeline_config_versioned"


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture(scope="module")
def rsa_keypair() -> rsa.RSAPrivateKey:
    # 2048-bit matches Supabase. Module-scoped so we pay this cost once.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def alt_rsa_keypair() -> rsa.RSAPrivateKey:
    """A second key used to forge a signature that must NOT verify."""

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def jwks(rsa_keypair: rsa.RSAPrivateKey) -> dict[str, Any]:
    pn = rsa_keypair.public_key().public_numbers()
    return {
        "keys": [
            {
                "kid": "test-kid-1",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": _b64url_uint(pn.n),
                "e": _b64url_uint(pn.e),
            }
        ]
    }


def _sign_jwt(
    key: rsa.RSAPrivateKey,
    claims: dict[str, Any],
    *,
    kid: str = "test-kid-1",
) -> str:
    return pyjwt.encode(
        claims, key, algorithm="RS256", headers={"kid": kid}
    )


def _canonical_timeline() -> dict[str, Any]:
    return {
        "theme": "banodoco-default",
        "clips": [
            {
                "id": "c1",
                "at": 0,
                "track": "main",
                "clipType": "text",
                "text": {"content": "hello"},
                "hold": 1.0,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Fake Supabase HTTP backend — replaces urllib.request.urlopen.
# ---------------------------------------------------------------------------


@dataclass
class _CapturedRequest:
    url: str
    method: str
    headers: dict[str, str]
    body: dict[str, Any] | None


@dataclass
class FakeSupabase:
    """Tiny in-memory Supabase that records every call and serves canned data.

    Routes:
      * GET  ``.../.well-known/jwks.json``  -> the JWKS payload
      * POST ``.../functions/v1/reigh-data-fetch`` -> latest timeline row
      * POST ``.../rest/v1/rpc/update_timeline_config_versioned``
              -> writes the config and bumps config_version, or raises
                 a 409 on the first ``conflict_count`` attempts.
    """

    jwks_payload: dict[str, Any]
    timeline_id: str = "tl-1"
    project_id: str = "proj-1"
    config: dict[str, Any] = field(default_factory=_canonical_timeline)
    config_version: int = 7
    conflict_count: int = 0  # raise 409 this many times before succeeding
    fetch_returns_no_row: bool = False
    fetch_omits_version: bool = False
    calls: list[_CapturedRequest] = field(default_factory=list)

    def __call__(self, request: Any, *, timeout: float = 0) -> Any:
        url = request.full_url
        method = request.get_method()
        body: dict[str, Any] | None = None
        if request.data:
            try:
                body = json.loads(request.data.decode("utf-8"))
            except json.JSONDecodeError:
                body = None
        self.calls.append(
            _CapturedRequest(
                url=url,
                method=method,
                headers=dict(request.headers),
                body=body,
            )
        )

        if "/.well-known/jwks.json" in url:
            payload = json.dumps(self.jwks_payload).encode("utf-8")
            return _FakeHTTPResponse(200, payload)

        if "/functions/v1/reigh-data-fetch" in url:
            if self.fetch_returns_no_row:
                payload = json.dumps({"timelines": []}).encode("utf-8")
                return _FakeHTTPResponse(200, payload)
            row: dict[str, Any] = {
                "id": self.timeline_id,
                "config": self.config,
            }
            if not self.fetch_omits_version:
                row["config_version"] = self.config_version
            payload = json.dumps({"timelines": [row]}).encode("utf-8")
            return _FakeHTTPResponse(200, payload)

        if "/rest/v1/rpc/update_timeline_config_versioned" in url:
            if self.conflict_count > 0:
                self.conflict_count -= 1
                raise urllib.error.HTTPError(
                    url,
                    409,
                    "Conflict",
                    hdrs={},  # type: ignore[arg-type]
                    fp=io.BytesIO(b"version_conflict expected_version mismatch"),
                )
            assert body is not None
            assert body["p_timeline_id"] == self.timeline_id
            assert body["p_expected_version"] == self.config_version
            # commit the write: bump version, store new config
            self.config = body["p_config"]
            self.config_version += 1
            payload = json.dumps({"config_version": self.config_version}).encode("utf-8")
            return _FakeHTTPResponse(200, payload)

        raise AssertionError(f"FakeSupabase: unexpected URL {url!r}")


class _FakeHTTPResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


# ---------------------------------------------------------------------------
# Autouse: side-step the pre-existing pack-loader bug.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_element_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    """``timeline.validate_timeline`` consults the element catalog to know
    which ``clipType`` strings are real effects. The pack loader trips on
    ``packs/local/elements/effects/_shared/`` (no manifest) — pre-existing
    bug, unrelated to this test. Substitute empty sets so validation still
    runs (allowlist checks, required fields, transition rules, etc.) but
    no element catalog is loaded."""

    monkeypatch.setattr(timeline_mod, "_effect_ids", lambda theme=None: set())
    monkeypatch.setattr(timeline_mod, "_animation_ids", lambda: set())
    monkeypatch.setattr(timeline_mod, "_transition_ids", lambda: set())


@pytest.fixture(autouse=True)
def _reset_jwks_cache() -> None:
    worker_jwt._jwks_cache.clear()


# ---------------------------------------------------------------------------
# 1. Happy path — JWT issue + verify, save_timeline + load_timeline round-trip.
# ---------------------------------------------------------------------------


def test_full_flow_jwt_then_save_then_reload_roundtrips_losslessly(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: rsa.RSAPrivateKey,
    jwks: dict[str, Any],
) -> None:
    """End-to-end: real JWT → real verify → real save → real load.

    Asserts (a) the verified JWT exposes the ``sub``/``aud`` claims we
    expect, (b) ``save_timeline`` issued *exactly one* RPC call with the
    locked 3-param shape, (c) the saved config round-trips through
    ``astrid.timeline`` and is byte-for-byte equivalent on read-back, and
    (d) every Supabase POST carried the user JWT in its Authorization
    header (i.e. the auth scheme was honoured down the stack).
    """

    backend = FakeSupabase(jwks_payload=jwks, config_version=7)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    # (a) Real JWT signed and verified through the real worker_jwt path.
    now = int(time.time())
    user_id = "user-abc"
    token = _sign_jwt(
        rsa_keypair,
        {
            "sub": user_id,
            "aud": DEFAULT_AUDIENCE,
            "exp": now + 300,
            "iat": now,
            "role": "authenticated",
        },
    )
    verified = verify_user_jwt(token, jwks_url=JWKS_URL)
    assert verified.user_id == user_id
    assert verified.audience == DEFAULT_AUDIENCE
    assert verified.raw_claims["role"] == "authenticated"

    # (b)-(c) Save then load via the real data_provider.
    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
    )

    def mutator(config: dict[str, Any], version: int) -> dict[str, Any]:
        assert version == 7  # the fetched version is passed in
        new = dict(config)
        new["clips"] = list(config["clips"]) + [
            {
                "id": "c2",
                "at": 2.0,
                "track": "main",
                "clipType": "text",
                "text": {"content": "world"},
                "hold": 1.0,
            }
        ]
        return new

    result = provider.save_timeline(
        "tl-1",
        mutator,
        project_id="proj-1",
        auth=("user_jwt", token),
        read_auth=("user_jwt", token),
        expected_version=7,
    )
    assert result.new_version == 8
    assert result.attempts == 1
    assert [c["id"] for c in result.timeline["clips"]] == ["c1", "c2"]

    # Read-back returns what we wrote and the new config_version.
    config, version = provider.load_timeline(
        "proj-1", "tl-1", auth=("user_jwt", token)
    )
    assert version == 8
    assert [c["id"] for c in config["clips"]] == ["c1", "c2"]

    # (d) Every Supabase POST carried Authorization: Bearer <jwt>.
    posts = [c for c in backend.calls if c.method == "POST"]
    assert posts, "expected at least one POST against Supabase"
    for call in posts:
        assert call.headers.get("Authorization") == f"Bearer {token}"
        # user_jwt scheme must NOT set apikey (that's service-role only).
        assert "Apikey" not in call.headers and "apikey" not in call.headers

    # The RPC body shape is the locked 3-param contract.
    rpc_calls = [c for c in posts if "/rpc/update_timeline_config_versioned" in c.url]
    assert len(rpc_calls) == 1
    assert rpc_calls[0].body is not None
    assert set(rpc_calls[0].body.keys()) == {
        "p_timeline_id",
        "p_expected_version",
        "p_config",
    }


# ---------------------------------------------------------------------------
# 2. JWT with wrong audience — real verify rejects it.
# ---------------------------------------------------------------------------


def test_jwt_with_wrong_audience_is_rejected_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: rsa.RSAPrivateKey,
    jwks: dict[str, Any],
) -> None:
    backend = FakeSupabase(jwks_payload=jwks)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    token = _sign_jwt(
        rsa_keypair,
        {
            "sub": "user-1",
            "aud": "some-other-service",
            "exp": int(time.time()) + 300,
        },
    )
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(token, jwks_url=JWKS_URL)


# ---------------------------------------------------------------------------
# 3. JWT signed by a different key — signature must fail to verify.
# ---------------------------------------------------------------------------


def test_jwt_signed_by_unknown_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    alt_rsa_keypair: rsa.RSAPrivateKey,
    jwks: dict[str, Any],
) -> None:
    """The JWKS publishes the original keypair only. A token signed by
    a different RSA key must fail signature verification even though its
    claims (aud, exp, sub) are well-formed."""

    backend = FakeSupabase(jwks_payload=jwks)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    token = _sign_jwt(
        alt_rsa_keypair,
        {
            "sub": "user-1",
            "aud": DEFAULT_AUDIENCE,
            "exp": int(time.time()) + 300,
        },
    )
    with pytest.raises(JwtVerificationError):
        verify_user_jwt(token, jwks_url=JWKS_URL)


# ---------------------------------------------------------------------------
# 4. data_provider read-miss — Supabase returns timelines:[] -> NotFound.
# ---------------------------------------------------------------------------


def test_load_timeline_read_miss_raises_timeline_not_found(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    backend = FakeSupabase(jwks_payload=jwks, fetch_returns_no_row=True)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
    )
    with pytest.raises(TimelineNotFoundError):
        provider.load_timeline("proj-1", "tl-missing")


# ---------------------------------------------------------------------------
# 5. Malformed reigh-data-fetch payload — missing config_version -> NotFound.
# ---------------------------------------------------------------------------


def test_fetch_payload_missing_config_version_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    """``timeline_io.fetch_timeline`` requires ``config_version`` on the
    edge-function payload (Phase 2 contract; see ``timeline_io.py:117``).
    A row that omits the field must surface as a clear NotFound, not a
    silent default-to-zero."""

    backend = FakeSupabase(jwks_payload=jwks, fetch_omits_version=True)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
    )
    with pytest.raises(TimelineNotFoundError, match="config_version"):
        provider.load_timeline("proj-1", "tl-1")


# ---------------------------------------------------------------------------
# 6. RPC version conflict — save_timeline exhausts retries.
# ---------------------------------------------------------------------------


def test_save_timeline_version_conflict_exhausts_retries(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    """If every RPC attempt comes back as a 409 ``version_conflict``,
    ``save_timeline`` must re-fetch + re-apply the mutator the configured
    number of times before raising :class:`TimelineVersionConflictError`."""

    backend = FakeSupabase(jwks_payload=jwks, conflict_count=5)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
    )
    with pytest.raises(TimelineVersionConflictError) as excinfo:
        provider.save_timeline(
            "tl-1",
            lambda config, _v: config,
            project_id="proj-1",
            service_role_key="srv-key",
            expected_version=7,
            retries=3,
        )
    assert excinfo.value.attempts == 3
    # Each retry refetched then RPC'd: 3 fetches + 3 rpc attempts.
    rpc_attempts = sum(
        1
        for c in backend.calls
        if "/rpc/update_timeline_config_versioned" in c.url
    )
    fetch_attempts = sum(
        1 for c in backend.calls if "/functions/v1/reigh-data-fetch" in c.url
    )
    assert rpc_attempts == 3
    assert fetch_attempts == 3
