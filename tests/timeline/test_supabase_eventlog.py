from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core.integrations.reigh.supabase_client import SupabaseHTTPError
from astrid.core.timeline.eventlog.supabase import (
    LiveSupabaseAppendTransport,
    SupabaseBackend,
)
from astrid.core.timeline.eventlog.types import (
    EventLogStaleVersionError,
    EventLogTransportError,
    EventLogUnsupportedRpcError,
)
from astrid.core.timeline.events.schema import EVENT_SCHEMA_VERSION, TimelineActor

_ACTOR = TimelineActor(type="human", id="user-1", display="User One")
_SQL_CONTRACT_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "reigh-app"
    / "supabase"
    / "migrations"
    / "20260612100000_create_timeline_events_contract.sql"
)


def test_live_append_transport_appends_config_only_without_registry_event(monkeypatch) -> None:
    timeline_id = str(uuid4())
    seen: dict[str, object] = {}

    def fake_get_json(url: str, **kwargs: object) -> object:
        seen.setdefault("reads", []).append((url, kwargs))
        if "rest/v1/timelines" in url:
            return [{
                "id": timeline_id,
                "config": {"tracks": [], "clips": []},
                "config_version": 7,
                "asset_registry": {"assets": {"old": {"url": "old"}}},
            }]
        if "rest/v1/timeline_events" in url:
            return [{
                "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAP",
                "version": 4,
                "hash": "e" * 64,
                "kind": "timeline.future_unknown",
            }]
        raise AssertionError(url)

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        seen["rpc"] = {"name": name, "params": params, "kwargs": kwargs}
        return {
            "config_version": 8,
            "inserted_event_ids": [params["p_events"][0]["event_id"]],
        }

    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.get_json", fake_get_json)
    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.rpc", fake_rpc)

    transport = LiveSupabaseAppendTransport(
        supabase_url="https://example.supabase.co",
        auth_token="service-role-token",
    )

    result = transport.append_config_replaced(
        timeline_id=timeline_id,
        config={"tracks": [], "clips": []},
        asset_registry=None,
        actor=_ACTOR,
        source="editor_save",
        expected_version=7,
    )

    assert result.config_version == 8
    assert len(result.batch.events) == 1
    assert result.batch.events[0].version == 5
    assert result.batch.events[0].event.kind == "timeline.config_replaced"
    assert result.batch.events[0].event.prev_hash == "e" * 64
    assert result.batch.events[0].event.schema_version == EVENT_SCHEMA_VERSION
    assert result.batch.projected_asset_registry is None

    rpc_call = seen["rpc"]
    assert rpc_call["name"] == "append_timeline_event"
    assert len(rpc_call["params"]["p_events"]) == 1
    assert rpc_call["params"]["p_expected_config_version"] == 7
    assert rpc_call["params"]["p_projected_asset_registry"] is None


def test_live_append_transport_appends_config_and_registry_batch(monkeypatch) -> None:
    timeline_id = str(uuid4())
    seen: dict[str, object] = {}

    def fake_get_json(url: str, **kwargs: object) -> object:
        seen.setdefault("reads", []).append((url, kwargs))
        if "rest/v1/timelines" in url:
            return [{
                "id": timeline_id,
                "config": {"tracks": [], "clips": []},
                "config_version": 4,
                "asset_registry": {"assets": {"old": {"url": "old"}}},
            }]
        if "rest/v1/timeline_events" in url:
            return [{
                "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                "version": 2,
                "hash": "b" * 64,
                "kind": "timeline.future_unknown",
            }]
        raise AssertionError(url)

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        seen["rpc"] = {"name": name, "params": params, "kwargs": kwargs}
        return {
            "config_version": 5,
            "inserted_event_ids": [
                params["p_events"][0]["event_id"],
                params["p_events"][1]["event_id"],
            ],
        }

    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.get_json", fake_get_json)
    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.rpc", fake_rpc)

    transport = LiveSupabaseAppendTransport(
        supabase_url="https://example.supabase.co",
        auth_token="service-role-token",
    )

    result = transport.append_config_replaced(
        timeline_id=timeline_id,
        config={"tracks": [], "clips": []},
        asset_registry={"assets": {"new": {"url": "new"}}},
        actor=_ACTOR,
        source="editor_save",
        expected_version=4,
        txn_id="01ARZ3NDEKTSV4RRFFQ69G5FAC",
    )

    assert result.config_version == 5
    assert len(result.batch.events) == 2
    assert result.batch.events[0].version == 3
    assert result.batch.events[0].event.prev_hash == "b" * 64
    assert result.batch.events[0].event.kind == "timeline.config_replaced"
    assert result.batch.events[1].version == 4
    assert result.batch.events[1].event.kind == "timeline.asset_registry_replaced"
    assert result.batch.events[1].event.prev_hash == result.batch.events[0].event.hash

    rpc_call = seen["rpc"]
    assert rpc_call["name"] == "append_timeline_event"
    assert rpc_call["params"]["p_expected_config_version"] == 4
    assert rpc_call["params"]["p_projected_config"] == result.batch.projected_config
    assert rpc_call["params"]["p_projected_asset_registry"] == result.batch.projected_asset_registry


def test_event_schema_version_matches_sql_contract_seed_value() -> None:
    migration_sql = _SQL_CONTRACT_MIGRATION.read_text(encoding="utf-8")
    match = re.search(
        r"insert into public\.timeline_event_contract \(id, current_schema_version\)\s+values \(1, (\d+)\)",
        migration_sql,
        re.IGNORECASE,
    )
    assert match is not None, "timeline_event_contract seed row must set current_schema_version"
    assert int(match.group(1)) == EVENT_SCHEMA_VERSION


def test_supabase_backend_uses_live_transport_for_config_replaced(monkeypatch) -> None:
    timeline_id = str(uuid4())

    def fake_get_json(url: str, **kwargs: object) -> object:
        if "rest/v1/timelines" in url:
            return [{
                "id": timeline_id,
                "config": {"tracks": [], "clips": []},
                "config_version": 0,
                "asset_registry": None,
            }]
        if "rest/v1/timeline_events" in url:
            return []
        raise AssertionError(url)

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        return {
            "config_version": 1,
            "inserted_event_ids": [params["p_events"][0]["event_id"]],
        }

    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.get_json", fake_get_json)
    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.rpc", fake_rpc)

    backend = SupabaseBackend(
        timeline_id=timeline_id,
        supabase_url="https://example.supabase.co",
        auth_token="service-role-token",
        enabled=True,
        verified_subject="user-1",
    )

    event = backend.append_event(
        timeline_id,
        "timeline.config_replaced",
        {"config": {"tracks": [], "clips": []}, "source": "editor_save"},
        actor=_ACTOR,
        expected_version=0,
    )

    assert event.kind == "timeline.config_replaced"
    assert event.expected_version == 0


def test_live_append_transport_maps_cas_conflict_to_stale_version_error(monkeypatch) -> None:
    timeline_id = str(uuid4())
    reads = {"count": 0}

    def fake_get_json(url: str, **kwargs: object) -> object:
        reads["count"] += 1
        if "rest/v1/timelines" in url:
            version = 4 if reads["count"] == 1 else 5
            return [{
                "id": timeline_id,
                "config": {"tracks": [], "clips": []},
                "config_version": version,
                "asset_registry": None,
            }]
        if "rest/v1/timeline_events" in url:
            if reads["count"] <= 2:
                return [{
                    "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAD",
                    "version": 2,
                    "hash": "c" * 64,
                    "kind": "timeline.config_replaced",
                }]
            return [{
                "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAE",
                "version": 3,
                "hash": "d" * 64,
                "kind": "timeline.config_replaced",
            }]
        raise AssertionError(url)

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        raise SupabaseHTTPError(
            "Supabase POST failed: HTTP 409: timeline config_version mismatch: expected 4, found 5",
            status=409,
            body="timeline config_version mismatch: expected 4, found 5",
        )

    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.get_json", fake_get_json)
    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.rpc", fake_rpc)

    transport = LiveSupabaseAppendTransport(
        supabase_url="https://example.supabase.co",
        auth_token="service-role-token",
    )

    with pytest.raises(EventLogStaleVersionError) as excinfo:
        transport.append_config_replaced(
            timeline_id=timeline_id,
            config={"tracks": [], "clips": []},
            asset_registry=None,
            actor=_ACTOR,
            expected_version=4,
        )

    conflict = excinfo.value.conflict
    assert conflict.timeline_id == timeline_id
    assert conflict.expected_version == 4
    assert conflict.current_version == 5
    assert conflict.last_event_id == "01ARZ3NDEKTSV4RRFFQ69G5FAE"


def test_live_append_transport_maps_rpc_failure_to_transport_error(monkeypatch) -> None:
    timeline_id = str(uuid4())

    def fake_get_json(url: str, **kwargs: object) -> object:
        if "rest/v1/timelines" in url:
            return [{
                "id": timeline_id,
                "config": {"tracks": [], "clips": []},
                "config_version": 1,
                "asset_registry": None,
            }]
        if "rest/v1/timeline_events" in url:
            return []
        raise AssertionError(url)

    def fake_rpc(name: str, params: dict[str, object], **kwargs: object) -> object:
        raise SupabaseHTTPError(
            "Supabase POST failed: HTTP 500: boom",
            status=500,
            body="boom",
        )

    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.get_json", fake_get_json)
    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.rpc", fake_rpc)

    transport = LiveSupabaseAppendTransport(
        supabase_url="https://example.supabase.co",
        auth_token="service-role-token",
    )

    with pytest.raises(EventLogTransportError, match="append_timeline_event failed"):
        transport.append_config_replaced(
            timeline_id=timeline_id,
            config={"tracks": [], "clips": []},
            asset_registry=None,
            actor=_ACTOR,
            expected_version=1,
        )


def test_live_append_transport_rejects_unsupported_kind_before_network(monkeypatch) -> None:
    backend = SupabaseBackend(
        timeline_id=str(uuid4()),
        supabase_url="https://example.supabase.co",
        auth_token="service-role-token",
        enabled=True,
    )

    def fail_get_json(*args: object, **kwargs: object) -> object:
        raise AssertionError("network should not be used for unsupported event kinds")

    monkeypatch.setattr("astrid.core.timeline.eventlog.supabase.get_json", fail_get_json)

    with pytest.raises(EventLogUnsupportedRpcError, match="only supports"):
        backend.append_event(
            backend.timeline_id,
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="codex:test"),
        )
