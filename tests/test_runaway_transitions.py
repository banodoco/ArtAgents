"""Canonical Runaway transition repository coverage.

Legacy source conversion is tested by the standalone runtime migrator. These
tests cover only the product pack's canonical read/write contract.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.repositories.runs import RunRepository
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.runaway.repository import RunawayRepository, RunawayValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path: Path):
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    packs_root = REPO_ROOT / "astrid" / "packs"
    for pack_id in ("timeline", "shots", "references", "runaway"):
        registry.register_pack(load_schema_pack_manifest(packs_root / pack_id / "schema-pack.yaml"))
    registry = registry.freeze()
    writer = DatabaseWriter(tmp_path / "runaway.sqlite3", registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    try:
        yield writer, ProjectRepository(events=events, receipts=receipts), RunRepository(events=events, receipts=receipts), RunawayRepository(receipts=receipts, events=events)
    finally:
        writer.close()


def _project_and_run(env) -> tuple[str, str]:
    writer, projects, runs, _ = env
    project_id = generate_lowercase_ulid()
    run_id = generate_lowercase_ulid()

    def create(uow: UnitOfWork) -> None:
        projects.create(uow, project_id=project_id, slug=f"project-{project_id}", name="Project", settings={}, idempotency_key=f"test:project:{project_id}")
        runs.create(uow, project_id=project_id, run_id=run_id, children=[], evidence=[], kind="runaway:timing-v1", title="Runaway timing", input={}, idempotency_key=f"test:run:{run_id}")

    UnitOfWork(writer).run(create)
    return project_id, run_id


def _rows(count: int = 3) -> list[dict]:
    return [{"ordinal": index, "start_ms": index * 20, "duration_ms": 20, "prompt": f"transition {index}", "metadata": {"frame": index}} for index in range(count)]


def test_create_list_and_show_are_canonical(env) -> None:
    project_id, run_id = _project_and_run(env)
    writer, _, _, repository = env
    result = UnitOfWork(writer).run(lambda uow: repository.create(uow, project_id=project_id, run_id=run_id, transitions=_rows()))
    assert result.first_ordinal == 0 and result.last_ordinal == 2
    with writer.read_only_connection() as conn:
        conn.row_factory = sqlite3.Row
        listed = repository.list(conn, project_id=project_id, run_id=run_id)
        assert [row.ordinal for row in listed] == [0, 1, 2]
        assert repository.show(conn, id=listed[0].id).prompt == "transition 0"


def test_run_foreign_key_is_enforced(env) -> None:
    writer, _, _, repository = env
    with pytest.raises(RunawayValidationError):
        UnitOfWork(writer).run(lambda uow: repository.create(uow, project_id=generate_lowercase_ulid(), run_id=generate_lowercase_ulid(), transitions=_rows(1)))


def test_create_is_receipt_idempotent(env) -> None:
    project_id, run_id = _project_and_run(env)
    writer, _, _, repository = env
    first = UnitOfWork(writer).run(lambda uow: repository.create(uow, project_id=project_id, run_id=run_id, transitions=_rows()))
    second = UnitOfWork(writer).run(lambda uow: repository.create(uow, project_id=project_id, run_id=run_id, transitions=_rows()))
    assert first.transition_ids == second.transition_ids
