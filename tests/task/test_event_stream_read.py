from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.audit import AuditContext
from astrid.core.task.event_stream import read_event_stream, subscribe_event_stream
from astrid.core.task.events import ZERO_HASH, _event_hash
from astrid.core.contracts.event_log_error import EventLogError


def _write_task_events(events_path: Path, raw_events: list[dict[str, object]]) -> None:
    prev_hash = ZERO_HASH
    lines: list[str] = []
    for raw_event in raw_events:
        event = dict(raw_event)
        event["hash"] = _event_hash(prev_hash, event)
        prev_hash = str(event["hash"])
        lines.append(json.dumps(event, sort_keys=True, separators=(",", ":")))
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_event_stream_reads_task_records_without_audit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_task_events(
        run_dir / "events.jsonl",
        [
            {"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"},
            {"kind": "run_completed", "ts": "2026-01-01T00:00:01Z"},
        ],
    )

    records = read_event_stream(run_dir)

    assert [record.source for record in records] == ["task", "task"]
    assert [record.kind for record in records] == ["run_started", "run_completed"]
    assert [record.line for record in records] == [1, 2]


def test_read_event_stream_includes_legacy_audit_records_without_mutating_ledger(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _write_task_events(
        run_dir / "events.jsonl",
        [{"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"}],
    )
    ledger_path = run_dir / "audit" / "ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_record = {
        "schema_version": 1,
        "created_at": "2026-01-01T00:00:02Z",
        "event": "node.created",
        "node_id": "legacy-node",
        "stage": "legacy",
        "kind": "step",
        "label": "Legacy",
        "parents": [],
        "outputs": [],
    }
    original = json.dumps(legacy_record) + "\n"
    ledger_path.write_text(original, encoding="utf-8")

    records = read_event_stream(run_dir)

    assert [record.source for record in records] == ["task", "audit"]
    assert records[1].kind == "node.created"
    assert records[1].line == 1
    assert ledger_path.read_text(encoding="utf-8") == original


def test_read_event_stream_rejects_corrupted_task_events_when_verify_enabled(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    events_path = run_dir / "events.jsonl"
    _write_task_events(
        events_path,
        [{"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"}],
    )
    payload = json.loads(events_path.read_text(encoding="utf-8"))
    payload["kind"] = "tampered"
    events_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(EventLogError, match="task event verification failed"):
        read_event_stream(run_dir, verify=True)


def test_read_event_stream_rejects_corrupted_audit_records_when_verify_enabled(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_task_events(
        run_dir / "events.jsonl",
        [{"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"}],
    )
    ctx = AuditContext.for_run(run_dir)
    ctx.register_node(stage="prepare", label="Prepare")
    ledger_path = run_dir / "audit" / "ledger.jsonl"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["stage"] = "tampered"
    ledger_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(EventLogError, match="audit ledger verification failed"):
        read_event_stream(run_dir, verify=True)


def test_subscribe_event_stream_reads_finite_snapshot_without_follow(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_task_events(
        run_dir / "events.jsonl",
        [
            {"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"},
            {"kind": "run_completed", "ts": "2026-01-01T00:00:01Z"},
        ],
    )

    records = list(subscribe_event_stream(run_dir, follow=False))

    assert [record.kind for record in records] == ["run_started", "run_completed"]


def test_subscribe_event_stream_follow_mode_yields_appended_records_without_session_requirements(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    events_path = run_dir / "events.jsonl"
    _write_task_events(
        events_path,
        [{"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"}],
    )

    stream = subscribe_event_stream(
        run_dir,
        follow=True,
        poll_interval=0,
        idle_polls=1,
    )

    first = next(stream)
    assert first.kind == "run_started"

    _write_task_events(
        events_path,
        [
            {"kind": "run_started", "run_id": "run-1", "plan_hash": "sha256:abc", "ts": "2026-01-01T00:00:00Z"},
            {"kind": "step_completed", "step_id": "step-1", "ts": "2026-01-01T00:00:01Z"},
        ],
    )

    second = next(stream)
    assert second.kind == "step_completed"
    assert list(stream) == []
