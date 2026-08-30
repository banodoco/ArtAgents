"""Focused coverage for runtime-only SDK event reads."""

from __future__ import annotations

from pathlib import Path

from astrid.sdk import events


class _Result:
    ok = True

    def __init__(self, data):
        self.data = data


class _Runs:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def events(self, project, run_id):
        self.calls.append((project, run_id))
        return _Result(self.payload)


class _Client:
    def __init__(self, payload):
        self.runs = _Runs(payload)


def _event(sequence=1):
    return {
        "event_id": "event-1",
        "sequence": sequence,
        "cursor": str(sequence),
        "event_type": "task.admitted",
        "aggregate_type": "task",
        "aggregate_id": "task-1",
        "payload": {"capability": "render.basic"},
        "occurred_at": "2026-08-30T00:00:00Z",
    }


def test_read_events_uses_injected_runtime_run_events() -> None:
    client = _Client([_event()])

    records = events.read_events(
        "demo",
        "run-1",
        projects_root=Path("/legacy/projects"),
        include_audit=False,
        verify=False,
        _client=client,
    )

    assert client.runs.calls == [("demo", "run-1")]
    assert len(records) == 1
    assert records[0].source == "task"
    assert records[0].kind == "task.admitted"
    assert records[0].payload["kind"] == "task.admitted"
    assert records[0].payload["capability"] == "render.basic"


def test_subscribe_events_polls_the_injected_runtime_client() -> None:
    client = _Client([_event()])

    records = list(
        events.subscribe_events(
            "demo",
            "run-1",
            follow=False,
            _client=client,
        )
    )

    assert [record.line for record in records] == [1]
    assert client.runs.calls == [("demo", "run-1"), ("demo", "run-1")]


def test_event_module_has_no_local_storage_authority() -> None:
    source = Path(events.__file__).read_text(encoding="utf-8")
    assert "sqlite3" not in source
    assert "events.jsonl" not in source
    assert "derive_database_path" not in source
