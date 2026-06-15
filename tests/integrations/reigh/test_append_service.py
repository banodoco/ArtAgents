from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from astrid.core.integrations.reigh.append_service import (
    AppendServiceConfig,
    create_append_service_server,
)
from astrid.core.integrations.reigh.worker_jwt import VerifiedJwt
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError, TimelineVersionConflict


@dataclass
class _FakeAppendResult:
    batch: Any
    config_version: int
    inserted_event_ids: tuple[str, ...]

    @property
    def primary_event(self) -> Any:
        return self.batch.events[0].event


class _FakeBookmarkTransport:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
        return dict(kwargs)


@contextmanager
def running_server(config: AppendServiceConfig) -> Generator[str, None, None]:
    server = create_append_service_server(config=config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _post_json(url: str, body: dict[str, Any], token: str | None = None) -> tuple[int, dict[str, Any]]:
    req = Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(req) as response:  # noqa: S310 - localhost test server only
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _config() -> AppendServiceConfig:
    return AppendServiceConfig(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role-key",
        internal_token="internal-token",
        jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
        timeout=5.0,
    )


def test_append_service_rejects_missing_auth_before_service_role_reads(monkeypatch) -> None:
    calls: list[str] = []

    def fail_get_json(*_args: object, **_kwargs: object) -> object:
        calls.append("get_json")
        raise AssertionError("service-role read should not happen without auth")

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fail_get_json)

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{uuid4()}/config-replaced",
            {"config": {"tracks": [], "clips": []}},
        )

    assert status == 401
    assert payload["error"] == "unauthorized"
    assert calls == []


def test_append_service_authorizes_user_jwt_before_append_rpc(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {"transport_created": False}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_service_get_json(url: str, **kwargs: object) -> object:
        seen.setdefault("authorization_reads", []).append((url, kwargs))
        assert kwargs["auth"] == ("service_role", "service-role-key")
        assert "rest/v1/timelines" in url
        return [{"id": timeline_id, "project_id": str(uuid4()), "user_id": user_id}]

    class FakeTransport:
        def __init__(self, **kwargs: object) -> None:
            seen["transport_created"] = True
            seen["transport_kwargs"] = kwargs

        def append_config_replaced(self, **kwargs: object) -> _FakeAppendResult:
            seen["append_kwargs"] = kwargs
            batch = kwargs["config_to_events_result"] if "config_to_events_result" in kwargs else None
            if batch is None:
                from astrid.core.integrations.reigh.event_construction import config_to_events
                from astrid.core.timeline.events.schema import TimelineActor

                batch = config_to_events(
                    {"tracks": [], "clips": []},
                    None,
                    timeline_id,
                    None,
                    1,
                    TimelineActor(type="human", id=user_id),
                    "editor_save",
                    expected_version=0,
                )
            return _FakeAppendResult(
                batch=batch,
                config_version=1,
                inserted_event_ids=batch.inserted_event_ids,
            )

        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            seen["bookmark_kwargs"] = kwargs
            return dict(kwargs)

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_service_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/config-replaced",
            {
                "config": {"tracks": [], "clips": []},
                "expected_version": 0,
                "actor": {"type": "agent", "id": "spoofed-agent"},
            },
            token="user-jwt",
        )

    assert status == 200
    assert payload["timeline_id"] == timeline_id
    assert payload["config_version"] == 1
    assert payload["inserted_event_ids"]
    assert payload["db_head"]["version"] == 1
    assert seen["transport_created"] is True
    assert seen["append_kwargs"]["actor"].type == "human"
    assert seen["append_kwargs"]["actor"].id == user_id
    assert seen["append_kwargs"]["expected_version"] == 0
    assert seen["bookmark_kwargs"]["spoke"] == "app"
    assert seen["bookmark_kwargs"]["hub_version"] == 1


def test_append_service_returns_config_and_registry_events(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )

    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def append_config_replaced(self, **kwargs: object) -> _FakeAppendResult:
            seen["append_kwargs"] = kwargs
            from astrid.core.integrations.reigh.event_construction import config_to_events

            batch = config_to_events(
                kwargs["config"],
                kwargs["asset_registry"],
                timeline_id,
                "f" * 64,
                3,
                kwargs["actor"],
                kwargs["source"],
                expected_version=kwargs["expected_version"],
                txn_id=kwargs["txn_id"],
            )
            return _FakeAppendResult(
                batch=batch,
                config_version=kwargs["expected_version"] + 1,
                inserted_event_ids=batch.inserted_event_ids,
            )

        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            seen["bookmark_kwargs"] = kwargs
            return dict(kwargs)

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/config-replaced",
            {
                "config": {"tracks": [], "clips": []},
                "asset_registry": {"assets": {"new": {"url": "new"}}},
                "expected_version": 9,
                "txn_id": "01ARZ3NDEKTSV4RRFFQ69G5FZZ",
            },
            token="user-jwt",
        )

    assert status == 200
    assert payload["config_version"] == 10
    assert len(payload["events"]) == 2
    assert payload["events"][0]["kind"] == "timeline.config_replaced"
    assert payload["events"][1]["kind"] == "timeline.asset_registry_replaced"
    assert payload["db_head"]["version"] == 4
    assert seen["append_kwargs"]["asset_registry"] == {"assets": {"new": {"url": "new"}}}
    assert seen["append_kwargs"]["expected_version"] == 9
    assert seen["append_kwargs"]["txn_id"] == "01ARZ3NDEKTSV4RRFFQ69G5FZZ"
    assert seen["bookmark_kwargs"]["hub_version"] == 4


def test_append_service_forbids_user_jwt_for_someone_elses_timeline(monkeypatch) -> None:
    owner_id = str(uuid4())
    caller_id = str(uuid4())

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=caller_id,
            audience="authenticated",
            raw_claims={"sub": caller_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "user_id": owner_id,
        }],
    )

    def fail_transport(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("append transport should not be constructed for forbidden callers")

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        fail_transport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{uuid4()}/config-replaced",
            {"config": {"tracks": [], "clips": []}},
            token="user-jwt",
        )

    assert status == 403
    assert payload["error"] == "forbidden"


def test_append_service_maps_stale_version_conflict_to_http_409(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )

    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def append_config_replaced(self, **_kwargs: object) -> _FakeAppendResult:
            raise EventLogStaleVersionError(
                TimelineVersionConflict(
                    timeline_id=timeline_id,
                    expected_version=4,
                    current_version=6,
                    last_event_id="01ARZ3NDEKTSV4RRFFQ69G5FAY",
                    last_event_kind="timeline.asset_registry_replaced",
                    last_event_summary="timeline.asset_registry_replaced#01ARZ3NDEKTSV4RRFFQ69G5FAY",
                )
            )

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/config-replaced",
            {
                "config": {"tracks": [], "clips": []},
                "expected_version": 4,
            },
            token="user-jwt",
        )

    assert status == 409
    assert payload["error"] == "version_conflict"
    assert "expected 4, found 6" in payload["detail"]


def test_append_service_accepts_internal_token_for_append(monkeypatch) -> None:
    timeline_id = str(uuid4())
    owner_id = str(uuid4())
    seen: dict[str, Any] = {}

    def fail_verify(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("internal token should not be sent through JWT verification")

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.verify_user_jwt", fail_verify)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": owner_id,
        }],
    )

    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def append_config_replaced(self, **kwargs: object) -> _FakeAppendResult:
            seen["actor"] = kwargs["actor"]
            from astrid.core.integrations.reigh.event_construction import config_to_events

            batch = config_to_events(
                kwargs["config"],
                kwargs["asset_registry"],
                timeline_id,
                None,
                1,
                kwargs["actor"],
                kwargs["source"],
            )
            return _FakeAppendResult(
                batch=batch,
                config_version=1,
                inserted_event_ids=batch.inserted_event_ids,
            )

        def upsert_bookmark(self, **_kwargs: object) -> dict[str, object]:
            return {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/config-replaced",
            {
                "config": {"tracks": [], "clips": []},
                "actor": {"type": "agent", "id": "import-agent"},
            },
            token="internal-token",
        )

    assert status == 200
    assert seen["actor"].type == "agent"
    assert seen["actor"].id == "import-agent"
    assert payload["events"][0]["kind"] == "timeline.config_replaced"
    assert payload["db_head"]["version"] == 1


def test_append_service_create_with_config_uses_create_rpc(monkeypatch) -> None:
    project_id = str(uuid4())
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{"id": project_id, "user_id": user_id}],
    )

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        seen["rpc"] = {"name": name, "params": params, "kwargs": kwargs}
        return {
            "timeline_id": params["p_timeline"]["id"],
            "config_version": 0,
            "inserted_event_ids": [params["p_event"]["event_id"]],
        }

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.rpc", fake_rpc)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        _FakeBookmarkTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/create-with-config",
            {
                "project_id": project_id,
                "timeline_id": timeline_id,
                "name": "Imported timeline",
                "config": {"tracks": [], "clips": []},
            },
            token="user-jwt",
        )

    assert status == 200
    assert payload["timeline_id"] == timeline_id
    assert payload["inserted_event_ids"]
    params = seen["rpc"]["params"]
    assert payload["db_head"] == {
        "version": 1,
        "hash": params["p_event"]["hash"],
        "event_id": params["p_event"]["event_id"],
    }
    assert seen["rpc"]["name"] == "create_timeline_with_initial_event"
    assert seen["rpc"]["kwargs"]["auth"] == ("service_role", "service-role-key")
    assert params["p_timeline"]["project_id"] == project_id
    assert params["p_timeline"]["user_id"] == user_id
    assert params["p_event"]["kind"] == "timeline.config_replaced"
    assert params["p_event"]["version"] == 1
    assert params["p_event"]["prev_hash"] is None


def test_append_service_records_app_bookmark_from_db_head(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )

    class FakeTransport(_FakeBookmarkTransport):
        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            seen["bookmark_kwargs"] = kwargs
            return dict(kwargs)

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-bookmark",
            {
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAY",
                },
                "synced_at": "2026-06-12T12:00:00Z",
            },
            token="user-jwt",
        )

    assert status == 200
    assert payload["bookmark"]["spoke"] == "app"
    assert payload["bookmark"]["hub_version"] == 4
    assert seen["bookmark_kwargs"]["spoke_hash"] == "b" * 64


def test_append_service_records_app_divergence_with_service_computed_app_head(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    bookmark_row = {
        "timeline_id": timeline_id,
        "spoke": "app",
        "spoke_version": 3,
        "spoke_hash": "a" * 64,
        "spoke_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "hub_version": 3,
        "hub_hash": "a" * 64,
        "hub_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "synced_at": "2026-06-12T12:00:00Z",
    }
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_get_json(url: str, **_kwargs: object) -> object:
        if "rest/v1/sync_bookmarks" in url:
            return [bookmark_row]
        if "rest/v1/timeline_events" in url:
            return [{
                "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                "version": 4,
                "kind": "timeline.config_replaced",
                "hash": "b" * 64,
                "prev_hash": "a" * 64,
                "ts": "2026-06-12T12:01:00Z",
                "actor": {"type": "human", "id": user_id},
                "payload": {"config": {"tracks": [], "clips": []}},
                "source_backend": None,
                "source_timeline_id": None,
                "source_event_id": None,
                "source_version": None,
                "source_hash": None,
                "idempotency_key": None,
                "txn_id": None,
                "erasure": None,
            }]
        return [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }]

    class FakeTransport(_FakeBookmarkTransport):
        def write_divergence(self, **kwargs: object) -> dict[str, object]:
            seen["divergence_kwargs"] = kwargs
            return {
                "id": str(uuid4()),
                "timeline_id": timeline_id,
                "spoke": "app",
            }

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
                "artifact_pointer": {"kind": "indexeddb", "id": "keep-both-1"},
            },
            token="user-jwt",
        )

    assert status == 200
    assert payload["db_head"]["version"] == 4
    assert payload["app_head"]["version"] == 4
    assert seen["divergence_kwargs"]["spoke"] == "app"
    assert seen["divergence_kwargs"]["artifact_pointer"] == {"kind": "indexeddb", "id": "keep-both-1"}


def test_create_with_config_upserts_app_bookmark_with_hub_hash(monkeypatch) -> None:
    project_id = str(uuid4())
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{"id": project_id, "user_id": user_id}],
    )

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        seen["rpc"] = {"name": name, "params": params, "kwargs": kwargs}
        return {
            "timeline_id": params["p_timeline"]["id"],
            "config_version": 0,
            "inserted_event_ids": [params["p_event"]["event_id"]],
        }

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.rpc", fake_rpc)

    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            seen["bookmark_kwargs"] = kwargs
            return dict(kwargs)

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/create-with-config",
            {
                "project_id": project_id,
                "timeline_id": timeline_id,
                "name": "Test Timeline",
                "config": {"tracks": [], "clips": []},
            },
            token="***",
        )

    assert status == 200
    assert "bookmark_kwargs" in seen, "create-with-config must upsert app bookmark"
    bk = seen["bookmark_kwargs"]
    assert bk["spoke"] == "app"
    assert bk["hub_version"] == 1
    assert isinstance(bk["hub_hash"], str) and len(bk["hub_hash"]) == 64, (
        "hub_hash must be a 64-char hex string (SD2: mandatory hash)"
    )
    assert isinstance(bk["spoke_hash"], str) and len(bk["spoke_hash"]) == 64
    assert bk["hub_event_id"] is not None
    assert bk["spoke_event_id"] is not None
    assert payload["db_head"]["hash"] == bk["hub_hash"]


def test_config_replaced_events_include_hashes_no_ts_hash_computation(monkeypatch) -> None:
    """Regression: TypeScript clients must never compute event hashes."""
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )

    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def append_config_replaced(self, **kwargs: object) -> _FakeAppendResult:
            seen["append_kwargs"] = kwargs
            from astrid.core.integrations.reigh.event_construction import config_to_events

            batch = config_to_events(
                kwargs["config"],
                kwargs["asset_registry"],
                timeline_id,
                "f" * 64,
                3,
                kwargs["actor"],
                kwargs["source"],
                expected_version=kwargs["expected_version"],
                txn_id=kwargs["txn_id"],
            )
            return _FakeAppendResult(
                batch=batch,
                config_version=kwargs["expected_version"] + 1,
                inserted_event_ids=batch.inserted_event_ids,
            )

        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            seen["bookmark_kwargs"] = kwargs
            return dict(kwargs)

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/config-replaced",
            {
                "config": {"tracks": [], "clips": []},
                "asset_registry": {"assets": {"new": {"url": "new"}}},
                "expected_version": 3,
            },
            token="***",
        )

    assert status == 200
    # Every event in the response must carry its hash — TypeScript never computes them.
    for i, event in enumerate(payload["events"]):
        assert isinstance(event.get("hash"), str) and len(event["hash"]) == 64, (
            f"event[{i}] must include a server-computed 64-char hash field"
        )
        assert isinstance(event.get("event_id"), str) and event["event_id"], (
            f"event[{i}] must include a server-assigned event_id"
        )
    assert isinstance(payload["db_head"].get("hash"), str) and len(payload["db_head"]["hash"]) == 64
    assert isinstance(payload["db_head"].get("event_id"), str) and payload["db_head"]["event_id"]


def test_create_with_config_events_include_hashes_no_ts_hash_computation(monkeypatch) -> None:
    """Regression: create responses carry server-computed hashes so TypeScript never hashes."""
    project_id = str(uuid4())
    timeline_id = str(uuid4())
    user_id = str(uuid4())

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{"id": project_id, "user_id": user_id}],
    )

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        return {
            "timeline_id": params["p_timeline"]["id"],
            "config_version": 0,
            "inserted_event_ids": [params["p_event"]["event_id"]],
        }

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.rpc", fake_rpc)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        _FakeBookmarkTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/create-with-config",
            {
                "project_id": project_id,
                "timeline_id": timeline_id,
                "name": "Test",
                "config": {"tracks": [], "clips": []},
            },
            token="***",
        )

    assert status == 200
    for i, event in enumerate(payload["events"]):
        assert isinstance(event.get("hash"), str) and len(event["hash"]) == 64, (
            f"create event[{i}] must include a server-computed 64-char hash field"
        )
        assert isinstance(event.get("event_id"), str) and event["event_id"], (
            f"create event[{i}] must include a server-assigned event_id"
        )
    assert isinstance(payload["db_head"].get("hash"), str) and len(payload["db_head"]["hash"]) == 64
    assert isinstance(payload["db_head"].get("event_id"), str) and payload["db_head"]["event_id"]


def test_app_bookmark_rejects_missing_auth(monkeypatch) -> None:
    timeline_id = str(uuid4())
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": str(uuid4()),
        }],
    )
    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-bookmark",
            {
                "db_head": {
                    "version": 1,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAY",
                },
            },
        )
    assert status == 401
    assert payload["error"] == "unauthorized"


def test_app_bookmark_rejects_wrong_owner(monkeypatch) -> None:
    owner_id = str(uuid4())
    caller_id = str(uuid4())
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=caller_id,
            audience="authenticated",
            raw_claims={"sub": caller_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "user_id": owner_id,
        }],
    )
    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{uuid4()}/app-bookmark",
            {
                "db_head": {
                    "version": 1,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAY",
                },
            },
            token="***",
        )
    assert status == 403
    assert payload["error"] == "forbidden"


def test_app_bookmark_rejects_invalid_db_head(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )
    with running_server(_config()) as base_url:
        # Missing db_head entirely
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-bookmark",
            {},
            token="***",
        )
    assert status == 400
    assert "db_head" in payload.get("error", "")

    with running_server(_config()) as base_url:
        # db_head missing version
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-bookmark",
            {"db_head": {"hash": "b" * 64, "event_id": "evt"}},
            token="***",
        )
    assert status == 400
    assert "db_head" in payload.get("error", "")


def test_app_divergence_rejects_missing_auth(monkeypatch) -> None:
    timeline_id = str(uuid4())
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": str(uuid4()),
        }],
    )
    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
            },
        )
    assert status == 401
    assert payload["error"] == "unauthorized"


def test_app_divergence_rejects_wrong_owner(monkeypatch) -> None:
    owner_id = str(uuid4())
    caller_id = str(uuid4())
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=caller_id,
            audience="authenticated",
            raw_claims={"sub": caller_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": str(uuid4()),
            "project_id": str(uuid4()),
            "user_id": owner_id,
        }],
    )
    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{uuid4()}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
            },
            token="***",
        )
    assert status == 403
    assert payload["error"] == "forbidden"


def test_app_divergence_rejects_missing_bookmark(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_get_json(url: str, **_kwargs: object) -> object:
        if "rest/v1/sync_bookmarks" in url:
            return []
        return [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }]

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        _FakeBookmarkTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
            },
            token="***",
        )
    assert status == 409
    assert payload["error"] == "bookmark_missing"


def test_app_divergence_rejects_db_head_not_advanced(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    bookmark_row = {
        "timeline_id": timeline_id,
        "spoke": "app",
        "spoke_version": 3,
        "spoke_hash": "a" * 64,
        "spoke_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "hub_version": 3,
        "hub_hash": "a" * 64,
        "hub_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "synced_at": "2026-06-12T12:00:00Z",
    }
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_get_json(url: str, **_kwargs: object) -> object:
        if "rest/v1/sync_bookmarks" in url:
            return [bookmark_row]
        return [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }]

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        _FakeBookmarkTransport,
    )

    with running_server(_config()) as base_url:
        # db_head version same as bookmarked hub — not advanced
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 3,
                    "hash": "a" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
                },
            },
            token="***",
        )
    assert status == 409
    assert payload["error"] == "not_divergent"


def test_app_divergence_rejects_invalid_chosen_side(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    bookmark_row = {
        "timeline_id": timeline_id,
        "spoke": "app",
        "spoke_version": 3,
        "spoke_hash": "a" * 64,
        "spoke_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "hub_version": 3,
        "hub_hash": "a" * 64,
        "hub_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "synced_at": "2026-06-12T12:00:00Z",
    }
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_get_json(url: str, **_kwargs: object) -> object:
        if "rest/v1/sync_bookmarks" in url:
            return [bookmark_row]
        return [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }]

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        _FakeBookmarkTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
                "chosen_side": "neither",
            },
            token="***",
        )
    assert status == 400
    assert payload["error"] == "invalid_chosen_side"


def test_app_divergence_rejects_missing_config(monkeypatch) -> None:
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    bookmark_row = {
        "timeline_id": timeline_id,
        "spoke": "app",
        "spoke_version": 3,
        "spoke_hash": "a" * 64,
        "spoke_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "hub_version": 3,
        "hub_hash": "a" * 64,
        "hub_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "synced_at": "2026-06-12T12:00:00Z",
    }
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_get_json(url: str, **_kwargs: object) -> object:
        if "rest/v1/sync_bookmarks" in url:
            return [bookmark_row]
        return [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }]

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        _FakeBookmarkTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
            },
            token="***",
        )
    assert status == 400
    assert "config" in payload.get("error", "")


def test_bookmark_response_includes_hub_hash_mandatory_sd2(monkeypatch) -> None:
    """SD2 regression: hub_hash is mandatory in all bookmark shapes."""
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )

    class FakeTransport(_FakeBookmarkTransport):
        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            seen["bookmark_kwargs"] = kwargs
            return dict(kwargs)

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-bookmark",
            {
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAY",
                },
                "synced_at": "2026-06-12T12:00:00Z",
            },
            token="***",
        )

    assert status == 200
    # Response bookmark must include hub_hash (SD2)
    bk = payload["bookmark"]
    assert bk["spoke"] == "app"
    assert isinstance(bk["hub_hash"], str) and len(bk["hub_hash"]) == 64, (
        "SD2: hub_hash is mandatory in all bookmark shapes"
    )
    assert isinstance(bk["spoke_hash"], str) and len(bk["spoke_hash"]) == 64
    assert isinstance(bk["hub_event_id"], str) and bk["hub_event_id"]
    assert isinstance(bk["spoke_event_id"], str) and bk["spoke_event_id"]
    # db_head in response must also carry hash
    assert isinstance(payload["db_head"].get("hash"), str) and len(payload["db_head"]["hash"]) == 64


def test_divergence_response_includes_all_head_hashes(monkeypatch) -> None:
    """Regression: divergence response must include all head hashes for TS consumption."""
    timeline_id = str(uuid4())
    user_id = str(uuid4())
    bookmark_row = {
        "timeline_id": timeline_id,
        "spoke": "app",
        "spoke_version": 3,
        "spoke_hash": "a" * 64,
        "spoke_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "hub_version": 3,
        "hub_hash": "a" * 64,
        "hub_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
        "synced_at": "2026-06-12T12:00:00Z",
    }
    seen: dict[str, Any] = {}

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )

    def fake_get_json(url: str, **_kwargs: object) -> object:
        if "rest/v1/sync_bookmarks" in url:
            return [bookmark_row]
        if "rest/v1/timeline_events" in url:
            return [{
                "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                "version": 4,
                "kind": "timeline.config_replaced",
                "hash": "b" * 64,
                "prev_hash": "a" * 64,
                "ts": "2026-06-12T12:01:00Z",
                "actor": {"type": "human", "id": user_id},
                "payload": {"config": {"tracks": [], "clips": []}},
                "source_backend": None,
                "source_timeline_id": None,
                "source_event_id": None,
                "source_version": None,
                "source_hash": None,
                "idempotency_key": None,
                "txn_id": None,
                "erasure": None,
            }]
        return [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }]

    class FakeTransport(_FakeBookmarkTransport):
        def write_divergence(self, **kwargs: object) -> dict[str, object]:
            seen["divergence_kwargs"] = kwargs
            return {
                "id": str(uuid4()),
                "timeline_id": timeline_id,
                "spoke": "app",
            }

    monkeypatch.setattr("astrid.core.integrations.reigh.append_service.get_json", fake_get_json)
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/app-divergence",
            {
                "config": {"tracks": [], "clips": []},
                "db_head": {
                    "version": 4,
                    "hash": "b" * 64,
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                },
                "artifact_pointer": {"kind": "indexeddb", "id": "keep-both-1"},
            },
            token="***",
        )

    assert status == 200
    # db_head in response must carry hash
    assert isinstance(payload["db_head"].get("hash"), str) and len(payload["db_head"]["hash"]) == 64
    assert isinstance(payload["db_head"].get("event_id"), str) and payload["db_head"]["event_id"]
    # app_head computed by service must carry hash
    assert isinstance(payload["app_head"].get("hash"), str) and len(payload["app_head"]["hash"]) == 64
    assert isinstance(payload["app_head"].get("event_id"), str) and payload["app_head"]["event_id"]
    # divergence row must include hashes
    assert seen["divergence_kwargs"]["spoke"] == "app"
    assert isinstance(seen["divergence_kwargs"]["spoke_hash"], str) and len(seen["divergence_kwargs"]["spoke_hash"]) == 64
    assert isinstance(seen["divergence_kwargs"]["hub_hash"], str) and len(seen["divergence_kwargs"]["hub_hash"]) == 64


def test_config_replaced_head_bearing_fields_complete(monkeypatch) -> None:
    """Verify the full shape of db_head in config-replaced responses."""
    timeline_id = str(uuid4())
    user_id = str(uuid4())

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.verify_user_jwt",
        lambda token, **_kwargs: VerifiedJwt(
            user_id=user_id,
            audience="authenticated",
            raw_claims={"sub": user_id, "aud": "authenticated"},
        ),
    )
    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.get_json",
        lambda *_args, **_kwargs: [{
            "id": timeline_id,
            "project_id": str(uuid4()),
            "user_id": user_id,
        }],
    )

    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def append_config_replaced(self, **kwargs: object) -> _FakeAppendResult:
            from astrid.core.integrations.reigh.event_construction import config_to_events

            batch = config_to_events(
                kwargs["config"], None, timeline_id, None, 1,
                kwargs["actor"], kwargs["source"],
            )
            return _FakeAppendResult(
                batch=batch,
                config_version=1,
                inserted_event_ids=batch.inserted_event_ids,
            )

        def upsert_bookmark(self, **kwargs: object) -> dict[str, object]:
            return dict(kwargs)

    monkeypatch.setattr(
        "astrid.core.integrations.reigh.append_service.LiveSupabaseAppendTransport",
        FakeTransport,
    )

    with running_server(_config()) as base_url:
        status, payload = _post_json(
            f"{base_url}/v1/timelines/{timeline_id}/config-replaced",
            {"config": {"tracks": [], "clips": []}},
            token="***",
        )

    assert status == 200
    assert "db_head" in payload, "config-replaced response must include db_head"
    head = payload["db_head"]
    assert isinstance(head.get("version"), int) and head["version"] >= 1
    assert isinstance(head.get("hash"), str) and len(head["hash"]) == 64
    assert isinstance(head.get("event_id"), str) and head["event_id"]
    # All three head-bearing fields must be present
    assert set(head.keys()) == {"version", "hash", "event_id"}, (
        f"db_head must contain exactly version, hash, event_id; got {set(head.keys())}"
    )
