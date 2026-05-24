from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.task.events import (
    EventLogError,
    ZERO_HASH,
    LEGACY_APPEND_EVENT_ALLOW_ENV,
    append_event,
    append_event_locked,
    canonical_event_json,
    make_run_started_event,
    make_step_completed_event,
    make_step_dispatched_event,
    read_events,
    verify_chain,
)


def _append_seed_event(events_path: Path, event: dict, *, expected_writer_epoch: int = 0) -> dict:
    lease_path = events_path.parent / "lease.json"
    if not lease_path.exists():
        lease_path.write_text(
            json.dumps(
                {
                    "writer_epoch": expected_writer_epoch,
                    "attached_session_id": "S-KERNEL-SEED",
                    "plan_hash": "",
                }
            ),
            encoding="utf-8",
        )
    events = read_events(events_path)
    expected_prev_hash = events[-1]["hash"] if events else ZERO_HASH
    return append_event_locked(
        events_path.parent,
        event,
        expected_writer_epoch=expected_writer_epoch,
        expected_prev_hash=expected_prev_hash,
    )


def test_append_three_events_then_verify_chain(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"

    _append_seed_event(events_path, make_run_started_event("run-1", "sha256:" + "1" * 64))
    _append_seed_event(events_path, make_step_dispatched_event("step-1", "echo one"))
    _append_seed_event(events_path, make_step_completed_event("step-1", 0))

    assert verify_chain(events_path) == (True, 2, None)


def test_mutating_non_hash_field_rejects_chain(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    _append_seed_event(events_path, make_run_started_event("run-1", "sha256:" + "1" * 64))
    _append_seed_event(events_path, make_step_dispatched_event("step-1", "echo one"))
    _append_seed_event(events_path, make_step_completed_event("step-1", 0))

    lines = events_path.read_text(encoding="utf-8").splitlines()
    mutated = json.loads(lines[1])
    mutated["command"] = "echo edited"
    lines[1] = json.dumps(mutated, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, index, error = verify_chain(events_path)
    assert ok is False
    assert index == 1
    assert error


def test_truncated_mid_line_rejects_chain(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    _append_seed_event(events_path, make_run_started_event("run-1", "sha256:" + "1" * 64))
    _append_seed_event(events_path, make_step_dispatched_event("step-1", "echo one"))

    events_path.write_text(events_path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")

    ok, index, error = verify_chain(events_path)
    assert ok is False
    assert index == 1
    assert error


def test_canonical_event_json_is_key_order_stable() -> None:
    left = {"kind": "step_completed", "plan_step_id": "step-1", "returncode": 0, "hash": "ignored"}
    right = {"returncode": 0, "hash": "also-ignored", "plan_step_id": "step-1", "kind": "step_completed"}

    assert canonical_event_json(left) == canonical_event_json(right)
    assert "hash" not in canonical_event_json(left)


def test_legacy_append_event_wrapper_is_guarded(monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(LEGACY_APPEND_EVENT_ALLOW_ENV, raising=False)

    with pytest.raises(EventLogError, match="legacy test/migration helper"):
        append_event(Path("/tmp/not-used/events.jsonl"), {"kind": "blocked"})
