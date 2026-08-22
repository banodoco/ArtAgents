"""Direct TimelineRepository.replace_config tests (fix round 2-A, item 5).

The census passes over ``replace_config`` via string mentions and the
managed-write suite covers the gateway path; nothing exercised the repository
command directly. This suite proves the whole-document CAS replacement
contract at the repo surface:

- happy path: one atomic commit updates document + registry projections,
  appends exactly one hash-chained ``timeline.config_replaced`` event
  (advancing both heads), and records the complete receipt under the
  canonical key ``timeline.replace_config:{timeline_id}:{expected_version}``;
- CAS fence: a stale ``expected_version`` raises the typed
  :class:`TimelineVersionConflictError` carrying the current version and
  leaves every persisted surface unchanged (zero mutation);
- replay: an identical retry under the same key replays the stored result
  with zero new rows (caller-supplied and derived keys);
- mismatch: a changed request under the same key is rejected by the receipt
  gate before any mutation;
- archive/terminal fences: an archived timeline rejects a later replacement
  with :class:`TimelineArchivedError` and zero mutation;
- validation: boolean/non-integer versions and non-mapping payloads are
  rejected with zero mutation.

Every command runs inside the caller's one ``BEGIN IMMEDIATE`` unit of work
(:class:`astrid.core.store.uow.UnitOfWork`), mirroring the save() suites.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.timeline.repository import (
    TIMELINE_CONFIG_REPLACED_EVENT_KIND,
    TIMELINE_REPLACE_CONFIG_COMMAND_KIND,
    TIMELINE_STREAM_TYPE,
    TimelineArchivedError,
    TimelineRepository,
    TimelineValidationError,
    TimelineVersionConflictError,
)

TS = "2026-08-20T00:00:00.000000+00:00"
TS2 = "2026-08-20T01:00:00.000000+00:00"
TS3 = "2026-08-20T02:00:00.000000+00:00"

CONFIG = {"fps": 24, "resolution": "1920x1080", "nested": {"scene": "s01"}}
ASSETS = {"hero": {"path": "hero.png", "kind": "image"}}
REPLACED_CONFIG = {"fps": 30, "resolution": "2560x1440", "nested": {"scene": "s02"}}
REPLACED_ASSETS = {"hero": {"path": "hero-v2.png", "kind": "image"}}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@pytest.fixture
def writer(tmp_path: Path, standard_registry):
    """A fresh standard-Astrid writer at ``<tmp>/astrid.sqlite3``."""
    w = DatabaseWriter(tmp_path / "astrid.sqlite3", standard_registry)
    try:
        yield w
    finally:
        w.close()


@pytest.fixture
def project_repo(standard_registry) -> ProjectRepository:
    return ProjectRepository(
        events=EventAppendService(standard_registry),
        receipts=ReceiptService(),
    )


@pytest.fixture
def repo(standard_registry, project_repo) -> TimelineRepository:
    return TimelineRepository(
        events=EventAppendService(standard_registry),
        receipts=ReceiptService(),
        projects=project_repo,
    )


def _create_project(repo: ProjectRepository, writer: DatabaseWriter) -> str:
    return UnitOfWork(writer).run(
        lambda u: repo.create(
            u,
            slug="pilot",
            name="Pilot",
            settings={},
            idempotency_key="proj-create-1",
            project_id=None,
            created_at=TS,
        )
    ).id


def _create_timeline(
    repo: TimelineRepository, writer: DatabaseWriter, project_id: str
) -> str:
    return UnitOfWork(writer).run(
        lambda u: repo.create(
            u,
            project_id=project_id,
            slug="main",
            name="Main",
            config=CONFIG,
            registry={"assets": ASSETS},
            idempotency_key="tl-create-1",
            created_at=TS,
        )
    ).timeline_id


def _replace(
    repo: TimelineRepository,
    writer: DatabaseWriter,
    project_id: str,
    *,
    expected_version: int = 1,
    config: Any = REPLACED_CONFIG,
    registry: Any = None,
    idempotency_key: str | None = None,
    created_at: str | None = TS2,
    **overrides: Any,
):
    args: dict[str, Any] = {
        "config": config,
        "registry": registry if registry is not None else {"assets": REPLACED_ASSETS},
        "expected_version": expected_version,
        "created_at": created_at,
        **overrides,
    }
    if idempotency_key is not None:
        args["idempotency_key"] = idempotency_key
    return UnitOfWork(writer).run(
        lambda u: repo.replace_config(u, project_id=project_id, ref="main", **args)
    )


def _surfaces(
    writer: DatabaseWriter, project_id: str, timeline_id: str
) -> dict[str, Any]:
    """Snapshot every persisted surface a replace_config touches."""

    def snapshot(session) -> dict[str, Any]:
        timeline = session.query_one(
            "SELECT document_json, asset_registry_json, updated_at "
            "FROM timelines WHERE id = ?",
            (timeline_id,),
        )
        stream = session.query_one(
            "SELECT head_seq FROM event_streams "
            "WHERE aggregate_id = ? AND stream_type = ?",
            (timeline_id, TIMELINE_STREAM_TYPE),
        )
        project = session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
        )
        return {
            "document_json": timeline["document_json"],
            "asset_registry_json": timeline["asset_registry_json"],
            "updated_at": timeline["updated_at"],
            "event_count": session.query_one(
                "SELECT count(*) FROM events WHERE project_id = ?",
                (project_id,),
            )[0],
            "receipt_count": session.query_one(
                "SELECT count(*) FROM command_receipts WHERE project_id = ?",
                (project_id,),
            )[0],
            "stream_head": stream["head_seq"] if stream is not None else None,
            "project_head": (
                project["event_head_seq"] if project is not None else None
            ),
        }

    return writer.submit(snapshot)


def _receipt_row(writer: DatabaseWriter, project_id: str, key: str):
    def read(session):
        return session.query_one(
            "SELECT * FROM command_receipts WHERE project_id = ? "
            "AND idempotency_key = ?",
            (project_id, key),
        )

    return writer.submit(read)


def test_replace_config_commits_event_and_canonical_receipt(
    repo, writer, project_repo
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)
    assert _UUID_RE.fullmatch(timeline_id)

    key = f"timeline.replace_config:{timeline_id}:1"
    model = _replace(repo, writer, project_id, idempotency_key=key)

    # Frozen load shape: new stream head is exactly expected_version + 1.
    assert model.timeline_id == timeline_id
    assert model.config == REPLACED_CONFIG
    assert model.registry == {"assets": REPLACED_ASSETS}
    assert model.config_version == 2

    surfaces = _surfaces(writer, project_id, timeline_id)
    assert surfaces["stream_head"] == 2

    receipt = _receipt_row(writer, project_id, key)
    assert receipt is not None
    assert receipt["command_kind"] == TIMELINE_REPLACE_CONFIG_COMMAND_KIND
    assert receipt["primary_stream_id"] == f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
    assert receipt["resulting_stream_seq"] == 2

    # Exactly ONE hash-chained timeline.config_replaced event exists on the
    # stream, positioned right after the create (seq 2).
    def read_events(session):
        count = session.query_one(
            "SELECT count(*) AS n FROM events WHERE stream_id = ? AND kind = ?",
            (
                f"{timeline_id}:{TIMELINE_STREAM_TYPE}",
                TIMELINE_CONFIG_REPLACED_EVENT_KIND,
            ),
        )["n"]
        seq = session.query_one(
            "SELECT seq FROM events WHERE stream_id = ? AND kind = ?",
            (
                f"{timeline_id}:{TIMELINE_STREAM_TYPE}",
                TIMELINE_CONFIG_REPLACED_EVENT_KIND,
            ),
        )["seq"]
        return int(count), (int(seq) if seq is not None else None)

    replaced_count, replaced_seq = writer.submit(read_events)
    assert replaced_count == 1
    assert replaced_seq == 2


def test_stale_expected_version_conflicts_with_zero_mutation(
    repo, writer, project_repo
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)
    before = _surfaces(writer, project_id, timeline_id)

    with pytest.raises(TimelineVersionConflictError) as excinfo:
        _replace(repo, writer, project_id, expected_version=99)

    assert excinfo.value.current_version == 1
    assert excinfo.value.expected_version == 99
    assert _surfaces(writer, project_id, timeline_id) == before


def test_identical_replay_under_same_key_adds_zero_rows(
    repo, writer, project_repo
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)
    key = f"timeline.replace_config:{timeline_id}:1"

    first = _replace(repo, writer, project_id, idempotency_key=key)
    after_first = _surfaces(writer, project_id, timeline_id)

    replay = _replace(repo, writer, project_id, idempotency_key=key)

    # Replay returns the stored result verbatim; zero new rows anywhere.
    assert replay.to_dict() == first.to_dict()
    assert replay.config_version == first.config_version
    assert _surfaces(writer, project_id, timeline_id) == after_first


def test_changed_request_under_same_key_is_rejected_before_mutation(
    repo, writer, project_repo
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)
    key = f"timeline.replace_config:{timeline_id}:1"

    _replace(repo, writer, project_id, idempotency_key=key)
    after_first = _surfaces(writer, project_id, timeline_id)

    with pytest.raises(ReceiptMismatchError):
        _replace(
            repo,
            writer,
            project_id,
            idempotency_key=key,
            config={"fps": 60},
        )

    assert _surfaces(writer, project_id, timeline_id) == after_first


def test_derived_key_replay_without_caller_key(repo, writer, project_repo):
    """The no-key canonical form replays deterministically too."""
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)

    first = _replace(repo, writer, project_id, idempotency_key=None)
    after_first = _surfaces(writer, project_id, timeline_id)

    replay = _replace(repo, writer, project_id, idempotency_key=None)

    assert replay.to_dict() == first.to_dict()
    assert _surfaces(writer, project_id, timeline_id) == after_first
    assert after_first["stream_head"] == 2


def test_archived_timeline_rejects_replacement_with_zero_mutation(
    repo, writer, project_repo
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)

    UnitOfWork(writer).run(
        lambda u: repo.archive(
            u,
            project_id=project_id,
            ref="main",
            idempotency_key="tl-archive-1",
            created_at=TS3,
        )
    )
    archived_head = _surfaces(writer, project_id, timeline_id)["stream_head"]

    with pytest.raises(TimelineArchivedError):
        _replace(
            repo,
            writer,
            project_id,
            expected_version=archived_head,
            created_at=None,
        )


@pytest.mark.parametrize("bad_version", [True, False, "1", 1.5])
def test_non_integer_expected_version_rejected(
    repo, writer, project_repo, bad_version
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)
    before = _surfaces(writer, project_id, timeline_id)

    with pytest.raises(TimelineValidationError):
        _replace(repo, writer, project_id, expected_version=bad_version)

    assert _surfaces(writer, project_id, timeline_id) == before


def test_non_mapping_payloads_rejected_with_zero_mutation(
    repo, writer, project_repo
):
    project_id = _create_project(project_repo, writer)
    timeline_id = _create_timeline(repo, writer, project_id)
    before = _surfaces(writer, project_id, timeline_id)

    with pytest.raises(TimelineValidationError):
        _replace(repo, writer, project_id, config=["not", "an", "object"])
    with pytest.raises(TimelineValidationError):
        _replace(repo, writer, project_id, registry={"assets": ["nope"]})

    assert _surfaces(writer, project_id, timeline_id) == before
