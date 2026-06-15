from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from astrid.core.timeline.banodoco_schema import canonical_empty_timeline

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    path = SCRIPTS_DIR / "reigh_seed_timeline_events.py"
    spec = importlib.util.spec_from_file_location("reigh_seed_timeline_events", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["reigh_seed_timeline_events"] = module
    spec.loader.exec_module(module)
    return module


def test_build_seed_event_row_preserves_valid_config_version_and_seed_key() -> None:
    mod = _load_module()

    row, error = mod._build_seed_event_row(
        timeline_id="123e4567-e89b-12d3-a456-426614174000",
        config=canonical_empty_timeline(),
        config_version=7,
    )

    assert error is None
    assert row is not None
    assert row["version"] == 1
    assert row["kind"] == "timeline.config_replaced"
    assert row["idempotency_key"] == (
        "seed:config_replaced:123e4567-e89b-12d3-a456-426614174000"
    )
    assert row["expected_version"] == 7
    assert row["payload"]["config"] == canonical_empty_timeline()


def test_run_seed_dry_run_skips_existing_events_and_reports_invalid_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    valid_config = canonical_empty_timeline()
    timelines = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "config": valid_config,
            "config_version": 3,
        },
        {
            "id": "123e4567-e89b-12d3-a456-426614174001",
            "config": valid_config,
            "config_version": 4,
        },
        {
            "id": "123e4567-e89b-12d3-a456-426614174002",
            "config": {"broken": True},
            "config_version": 5,
        },
    ]
    writes: list[object] = []

    monkeypatch.setattr(mod, "_list_timelines", lambda **_: timelines)
    monkeypatch.setattr(
        mod,
        "_timeline_has_any_events",
        lambda **kwargs: kwargs["timeline_id"] == "123e4567-e89b-12d3-a456-426614174001",
    )
    monkeypatch.setattr(mod, "_insert_timeline_events", lambda **kwargs: writes.append(kwargs["rows"]))

    summary = mod.run_seed(
        supabase_url="https://example.supabase.co",
        auth=("service_role", "token"),
        apply=False,
    )

    assert summary["mode"] == "dry_run"
    assert summary["status"] == "invalid_configs_found"
    assert summary["counts"] == {
        "timelines_seen": 3,
        "seeded": 0,
        "would_seed": 1,
        "skipped_existing_events": 1,
        "invalid_configs": 1,
    }
    assert writes == []
    assert [item["action"] for item in summary["results"]] == [
        "would_seed",
        "skipped_existing_events",
        "invalid_config",
    ]


def test_apply_then_rollback_is_idempotent_and_deletes_only_seed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    valid_config = canonical_empty_timeline()
    timeline_id = "123e4567-e89b-12d3-a456-426614174000"
    state = {
        "timelines": [
            {
                "id": timeline_id,
                "config": valid_config,
                "config_version": 2,
            }
        ],
        "events": [],
    }

    def fake_list_timelines(**_: object):
        return list(state["timelines"])

    def fake_has_events(**kwargs: object) -> bool:
        target = kwargs["timeline_id"]
        return any(event["timeline_id"] == target for event in state["events"])

    def fake_insert(**kwargs: object):
        for row in kwargs["rows"]:
            state["events"].append(dict(row))
        return kwargs["rows"]

    def fake_list_seed_rows(**_: object):
        return [
            {
                "timeline_id": event["timeline_id"],
                "event_id": event["event_id"],
                "idempotency_key": event["idempotency_key"],
            }
            for event in state["events"]
            if str(event.get("idempotency_key", "")).startswith(mod.SEED_IDEMPOTENCY_PREFIX)
        ]

    def fake_delete_seed_rows(**_: object):
        state["events"] = [
            event
            for event in state["events"]
            if not str(event.get("idempotency_key", "")).startswith(mod.SEED_IDEMPOTENCY_PREFIX)
        ]

    monkeypatch.setattr(mod, "_list_timelines", fake_list_timelines)
    monkeypatch.setattr(mod, "_timeline_has_any_events", fake_has_events)
    monkeypatch.setattr(mod, "_insert_timeline_events", fake_insert)
    monkeypatch.setattr(mod, "_list_seed_rows", fake_list_seed_rows)
    monkeypatch.setattr(mod, "_delete_seed_rows", fake_delete_seed_rows)

    first = mod.run_seed(
        supabase_url="https://example.supabase.co",
        auth=("service_role", "token"),
        apply=True,
    )
    second = mod.run_seed(
        supabase_url="https://example.supabase.co",
        auth=("service_role", "token"),
        apply=True,
    )

    assert first["status"] == "ok"
    assert first["counts"]["seeded"] == 1
    assert len(state["events"]) == 1
    assert second["counts"]["skipped_existing_events"] == 1
    assert len(state["events"]) == 1

    state["events"].append(
        {
            "timeline_id": timeline_id,
            "event_id": "01HNONSEED0000000000000000",
            "idempotency_key": "manual:keep",
        }
    )
    rollback = mod.run_rollback(
        supabase_url="https://example.supabase.co",
        auth=("service_role", "token"),
    )

    assert rollback["counts"]["seed_rows_deleted"] == 1
    assert state["events"] == [
        {
            "timeline_id": timeline_id,
            "event_id": "01HNONSEED0000000000000000",
            "idempotency_key": "manual:keep",
        }
    ]


def test_main_defaults_to_dry_run_and_returns_nonzero_for_invalid_configs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load_module()

    monkeypatch.setattr(mod.reigh_env, "resolve_supabase_url", lambda *_: "https://example.supabase.co")
    monkeypatch.setattr(mod.reigh_env, "resolve_service_role_key", lambda *_: "token")
    monkeypatch.setattr(
        mod,
        "run_seed",
        lambda **_: {
            "mode": "dry_run",
            "status": "invalid_configs_found",
            "counts": {
                "timelines_seen": 1,
                "seeded": 0,
                "would_seed": 0,
                "skipped_existing_events": 0,
                "invalid_configs": 1,
            },
            "results": [{"timeline_id": "t1", "action": "invalid_config", "reason": "bad"}],
        },
    )

    rc = mod.main([])

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert payload["status"] == "invalid_configs_found"
