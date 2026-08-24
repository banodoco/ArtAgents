"""Kernel-ledger fallback coverage for portable restored run event reads."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import astrid
from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import RunRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter


def _seed_kernel_run(root: Path) -> tuple[str, str]:
    database = root / ".astrid" / "astrid.sqlite3"
    database.parent.mkdir(parents=True)
    registry = core_only_registry()
    writer = DatabaseWriter(database, registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        runs = RunRepository(events=events, receipts=receipts)
        project_id = generate_lowercase_ulid()
        UnitOfWork(writer).run(
            lambda uow: projects.create(
                uow,
                slug="restored-demo",
                name="Restored Demo",
                settings={},
                idempotency_key="project-create",
                project_id=project_id,
            )
        )
        run_id = generate_lowercase_ulid()
        UnitOfWork(writer).run(
            lambda uow: runs.create(
                uow,
                project_id=project_id,
                children=[],
                evidence=(),
                idempotency_key="run-create",
                run_id=run_id,
                kind="test",
                title="Restored run",
                created_at="2026-01-01T00:00:00Z",
            )
        )
        return project_id, run_id
    finally:
        writer.close()


def test_read_events_falls_back_to_kernel_when_projection_is_absent(tmp_path: Path) -> None:
    _project_id, run_id = _seed_kernel_run(tmp_path)

    records = astrid.read_events(
        "restored-demo", run_id, projects_root=tmp_path, verify=True
    )

    assert [record.source for record in records] == ["kernel"]
    assert [record.kind for record in records] == ["core.run.created"]
    assert records[0].line == 1
    assert isinstance(records[0].payload["event_id"], str)
    assert records[0].hash == records[0].payload["event_hash"]


def test_read_events_rejects_cross_project_run_address(tmp_path: Path) -> None:
    _project_id, run_id = _seed_kernel_run(tmp_path)

    with pytest.raises(astrid.CapabilityPreconditionError, match="not found"):
        astrid.read_events("other-project", run_id, projects_root=tmp_path)


def test_read_events_fails_closed_on_kernel_hash_corruption(tmp_path: Path) -> None:
    _project_id, run_id = _seed_kernel_run(tmp_path)
    database = tmp_path / ".astrid" / "astrid.sqlite3"
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT payload_json FROM events WHERE stream_id = ?",
            (f"{run_id}:core.run",),
        ).fetchone()
        payload = json.loads(row[0])
        payload["data"]["title"] = "tampered"
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE stream_id = ?",
            (json.dumps(payload, separators=(",", ":")), f"{run_id}:core.run"),
        )
        connection.commit()

    with pytest.raises(astrid.CapabilityEventLogError, match="hash mismatch"):
        astrid.read_events("restored-demo", run_id, projects_root=tmp_path, verify=True)
