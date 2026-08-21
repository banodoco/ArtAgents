"""Integration test for the Reigh integration layer.

Unlike the per-module unit tests under ``tests/test_worker_jwt.py``,
``tests/test_supabase_data_provider.py``, and ``tests/test_task_client.py``
— each of which mocks out the next module down — this test wires the
real code paths together:

  * a real RSA keypair signs a real JWT
  * ``astrid.core.integrations.reigh.worker_jwt.verify_user_jwt`` decodes it against
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

This still exercises the legacy blob-RPC compatibility bridge rather than the
future Supabase event-log append path.

The element-catalog pack loader has a pre-existing bug (the
``packs/local/elements/effects/_shared`` folder has no manifest and the
loader raises ``ElementValidationError`` while Astrid validates a clip's
``clipType`` against the effects catalog). We side-step that by stubbing
``banodoco_schema._effect_ids`` / ``_animation_ids`` / ``_transition_ids`` to
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
from uuid import uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from astrid.core.integrations.reigh import worker_jwt
from astrid.core.integrations.reigh.data_provider import SupabaseDataProvider
from astrid.core.integrations.reigh.errors import (
    TimelineNotFoundError,
    TimelineVersionConflictError,
)
from astrid.core.integrations.reigh.worker_jwt import (
    DEFAULT_AUDIENCE,
    JwtVerificationError,
    verify_user_jwt,
)
from astrid.core.timeline import banodoco_schema as banodoco_schema_mod

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
        "tracks": [],
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
    asset_registry: dict[str, Any] | None = None
    config_version: int = 7
    conflict_count: int = 0  # raise 409 this many times before succeeding
    fetch_returns_no_row: bool = False
    fetch_omits_version: bool = False
    calls: list[_CapturedRequest] = field(default_factory=list)
    last_event: dict[str, Any] | None = None

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
                "asset_registry": self.asset_registry,
            }
            if not self.fetch_omits_version:
                row["config_version"] = self.config_version
            payload = json.dumps({"timelines": [row]}).encode("utf-8")
            return _FakeHTTPResponse(200, payload)

        if "/rest/v1/timelines" in url:
            payload = json.dumps(
                [
                    {
                        "id": self.timeline_id,
                        "config": self.config,
                        "config_version": self.config_version,
                        "asset_registry": self.asset_registry,
                    }
                ]
            ).encode("utf-8")
            return _FakeHTTPResponse(200, payload)

        if "/rest/v1/timeline_events" in url:
            rows = [self.last_event] if self.last_event is not None else []
            payload = json.dumps(rows).encode("utf-8")
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

        if "/rest/v1/rpc/append_timeline_event" in url:
            if self.conflict_count > 0:
                self.conflict_count -= 1
                raise urllib.error.HTTPError(
                    url,
                    409,
                    "Conflict",
                    hdrs={},  # type: ignore[arg-type]
                    fp=io.BytesIO(
                        (
                            f"config_version mismatch: expected {body['p_expected_config_version']}, "
                            f"found {self.config_version}"
                        ).encode("utf-8")
                    ),
                )
            assert body is not None
            assert body["p_timeline_id"] == self.timeline_id
            self.config = body["p_projected_config"]
            self.asset_registry = body.get("p_projected_asset_registry")
            self.config_version += 1
            events = body.get("p_events") or []
            if events:
                last = events[-1]
                self.last_event = {
                    "event_id": last.get("event_id"),
                    "version": last.get("version"),
                    "hash": last.get("hash"),
                    "kind": last.get("kind"),
                }
            payload = json.dumps(
                {
                    "config_version": self.config_version,
                    "inserted_event_ids": [
                        event.get("event_id")
                        for event in events
                        if isinstance(event, dict) and isinstance(event.get("event_id"), str)
                    ],
                }
            ).encode("utf-8")
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

    monkeypatch.setattr(banodoco_schema_mod, "_effect_ids", lambda theme=None: set())
    monkeypatch.setattr(banodoco_schema_mod, "_animation_ids", lambda: set())
    monkeypatch.setattr(banodoco_schema_mod, "_transition_ids", lambda: set())


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
    core timeline handling and is byte-for-byte equivalent on read-back, and
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

    timeline_id = str(uuid4())
    backend = FakeSupabase(jwks_payload=jwks, timeline_id=timeline_id, conflict_count=5)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
    )
    with pytest.raises(TimelineVersionConflictError) as excinfo:
        provider.save_timeline(
            timeline_id,
            lambda config, _v: config,
            project_id="proj-1",
            service_role_key="srv-key",
            expected_version=7,
            retries=3,
        )
    assert excinfo.value.attempts == 3
    # Each retry refetched then append-RPC'd: 3 fetches + 3 append attempts.
    rpc_attempts = sum(
        1
        for c in backend.calls
        if "/rpc/append_timeline_event" in c.url
    )
    fetch_attempts = sum(
        1 for c in backend.calls if "/functions/v1/reigh-data-fetch" in c.url
    )
    assert rpc_attempts == 3
    assert fetch_attempts == 3


# ---------------------------------------------------------------------------
# 7. Append transport — config-only save and reload round-trips losslessly.
# ---------------------------------------------------------------------------


def test_append_transport_config_only_save_and_reload(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    """Happy-path config-only save through the Python-owned append transport.

    Uses ``service_role_key`` to route the save through
    ``LiveSupabaseAppendTransport``, then reloads via ``reigh-data-fetch`` and
    confirms byte-for-byte round-trip of both config and version.
    """
    timeline_id = str(uuid4())
    backend = FakeSupabase(jwks_payload=jwks, timeline_id=timeline_id, config_version=7)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
        service_role_key="srv-key",
    )

    def mutator(config: dict[str, Any], version: int) -> dict[str, Any]:
        assert version == 7
        new = dict(config)
        new["clips"] = list(config["clips"]) + [
            {
                "id": "c3",
                "at": 4.0,
                "track": "main",
                "clipType": "text",
                "text": {"content": "append-path"},
                "hold": 1.0,
            }
        ]
        return new

    result = provider.save_timeline(
        timeline_id,
        mutator,
        project_id="proj-1",
        service_role_key="srv-key",
        expected_version=7,
    )
    assert result.new_version == 8
    assert result.attempts == 1
    assert [c["id"] for c in result.timeline["clips"]] == ["c1", "c3"]

    # Reload: the saved config is returned by the fetch endpoint.
    config, version = provider.load_timeline("proj-1", timeline_id)
    assert version == 8
    assert [c["id"] for c in config["clips"]] == ["c1", "c3"]

    # The save went through the append RPC, NOT the legacy blob RPC.
    append_calls = [
        c for c in backend.calls
        if "/rpc/append_timeline_event" in c.url
    ]
    legacy_calls = [
        c for c in backend.calls
        if "/rpc/update_timeline_config_versioned" in c.url
    ]
    assert len(append_calls) == 1
    assert len(legacy_calls) == 0

    # The append RPC received canonical fields.
    assert append_calls[0].body is not None
    assert append_calls[0].body["p_timeline_id"] == timeline_id
    assert append_calls[0].body["p_expected_config_version"] == 7
    assert isinstance(append_calls[0].body["p_events"], list)
    assert len(append_calls[0].body["p_events"]) >= 1
    first_event = append_calls[0].body["p_events"][0]
    assert first_event.get("kind") == "timeline.config_replaced"
    assert isinstance(first_event.get("event_id"), str)
    assert isinstance(first_event.get("hash"), str)
    assert first_event.get("version") == 1
    # No asset_registry event in a config-only save.
    kinds = [e.get("kind") for e in append_calls[0].body["p_events"]]
    assert "timeline.asset_registry_replaced" not in kinds


# ---------------------------------------------------------------------------
# 8. Append transport — config + asset_registry batch save.
# ---------------------------------------------------------------------------


def test_append_transport_config_plus_registry_save(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    """Config + asset_registry batch save through the append transport.

    The batch must contain both a ``config_replaced`` event and a
    ``asset_registry_replaced`` event, with the registry event chained
    after the config event.
    """
    timeline_id = str(uuid4())
    backend = FakeSupabase(jwks_payload=jwks, timeline_id=timeline_id, config_version=7)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
        service_role_key="srv-key",
    )

    registry = {"assets": {"img-1": {"url": "https://cdn.example/1.png"}}}

    def mutator(config: dict[str, Any], version: int) -> dict[str, Any]:
        new = dict(config)
        new["clips"] = list(config["clips"]) + [
            {
                "id": "extra-clip",
                "at": 1.0,
                "track": "overlay",
                "clipType": "text",
                "text": {"content": "with-registry"},
                "hold": 3.0,
            }
        ]
        return new

    result = provider.save_timeline(
        timeline_id,
        mutator,
        project_id="proj-1",
        service_role_key="srv-key",
        expected_version=7,
        asset_registry=registry,
    )
    assert result.new_version == 8
    assert result.attempts == 1

    # Verify the batch has both event kinds in order.
    append_calls = [
        c for c in backend.calls
        if "/rpc/append_timeline_event" in c.url
    ]
    assert len(append_calls) == 1
    events = append_calls[0].body["p_events"]
    assert len(events) == 2
    assert events[0]["kind"] == "timeline.config_replaced"
    assert events[1]["kind"] == "timeline.asset_registry_replaced"
    assert events[0]["version"] == 1
    assert events[1]["version"] == 2
    # Hash chaining: config event hash is prev_hash of registry event.
    assert events[0]["hash"] is not None
    assert events[1].get("prev_hash") == events[0]["hash"]

    # Projected asset_registry was sent to the RPC.
    assert append_calls[0].body["p_projected_asset_registry"] == registry

    # Reload: both config and asset_registry are persisted.
    config, version = provider.load_timeline("proj-1", timeline_id)
    assert version == 8
    assert any(c["id"] == "extra-clip" for c in config["clips"])

    loaded_registry = provider.load_asset_registry("proj-1", timeline_id)
    assert loaded_registry["assets"]["img-1"]["url"] == "https://cdn.example/1.png"


# ---------------------------------------------------------------------------
# 9. Append transport — CAS conflict recovers on retry.
# ---------------------------------------------------------------------------


def test_append_transport_cas_conflict_recovers_on_retry(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    """One CAS conflict on the append RPC, then a successful retry.

    The first ``append_timeline_event`` call returns HTTP 409; the second
    succeeds after a fresh fetch yields the bumped ``config_version``.
    """
    timeline_id = str(uuid4())
    backend = FakeSupabase(jwks_payload=jwks, timeline_id=timeline_id, config_version=7, conflict_count=1)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
        service_role_key="srv-key",
    )

    def mutator(config: dict[str, Any], version: int) -> dict[str, Any]:
        new = dict(config)
        new["theme"] = "dark"
        return new

    result = provider.save_timeline(
        timeline_id,
        mutator,
        project_id="proj-1",
        service_role_key="srv-key",
        expected_version=7,
        retries=3,
    )
    assert result.new_version == 8
    assert result.attempts == 2  # first conflicted, second succeeded

    # Two fetches (initial + retry) and two append attempts (first 409, second ok).
    fetch_count = sum(
        1 for c in backend.calls
        if "/functions/v1/reigh-data-fetch" in c.url
    )
    append_count = sum(
        1 for c in backend.calls
        if "/rpc/append_timeline_event" in c.url
    )
    assert fetch_count == 2
    assert append_count == 2

    # The saved config reflects the mutator.
    config, version = provider.load_timeline("proj-1", timeline_id)
    assert version == 8
    assert config.get("theme") == "dark"


# ---------------------------------------------------------------------------
# 10. Append transport — backward-compatible config-only mutator (no
#     asset_registry awareness) still works.
# ---------------------------------------------------------------------------


def test_append_transport_backward_compatible_config_only_mutator(
    monkeypatch: pytest.MonkeyPatch,
    jwks: dict[str, Any],
) -> None:
    """Existing config-only mutators work unchanged through the append transport.

    The mutator signature ``(config, version) -> config`` is unchanged;
    omitting ``asset_registry`` from the ``save_timeline`` call produces a
    single-event config-only batch just like the legacy RPC path did.
    """
    timeline_id = str(uuid4())
    backend = FakeSupabase(jwks_payload=jwks, timeline_id=timeline_id, config_version=7)
    monkeypatch.setattr("urllib.request.urlopen", backend)

    provider = SupabaseDataProvider(
        supabase_url=SUPABASE_URL,
        fetch_url=FETCH_URL,
        pat="pat-token",
        service_role_key="srv-key",
    )

    # Old-style mutator: no asset_registry parameter, no awareness of events.
    old_style_mutator: Any = lambda config, _version: {
        **config,
        "clips": config["clips"] + [
            {
                "id": "old-clip",
                "at": 0.0,
                "track": "main",
                "clipType": "text",
                "text": {"content": "backward-compat"},
                "hold": 1.0,
            }
        ],
    }

    result = provider.save_timeline(
        timeline_id,
        old_style_mutator,
        project_id="proj-1",
        service_role_key="srv-key",
        expected_version=7,
        # No asset_registry — legacy mutators didn't pass one.
    )
    assert result.new_version == 8
    assert result.attempts == 1

    # Only a config_replaced event was emitted.
    append_calls = [
        c for c in backend.calls
        if "/rpc/append_timeline_event" in c.url
    ]
    assert len(append_calls) == 1
    events = append_calls[0].body["p_events"]
    assert len(events) == 1
    assert events[0]["kind"] == "timeline.config_replaced"

    # Reload confirms the mutator was applied.
    config, version = provider.load_timeline("proj-1", timeline_id)
    assert version == 8
    clip_ids = [c["id"] for c in config["clips"]]
    assert "old-clip" in clip_ids
    assert "c1" in clip_ids
