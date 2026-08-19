"""Timeline repository tests: create, address resolution, list, and show.

(m1 plan step 13 / T27 and NSA-3.) This suite proves the timeline identity
projection contract end to end:

- create atomicity: one ``BEGIN IMMEDIATE`` command writes the
  ``timeline.timeline`` stream, the whole-document ``timelines`` projection,
  one hash-chained ``timeline.created`` event (canonical SD2 envelope), both
  heads, and the complete receipt together; every failure path (slug/ULID
  conflict, existing id, validation, receipt mismatch) changes zero rows;
- canonical identities: the timeline id is a lowercase canonical UUID
  (``8-4-4-4-12``) and the alias is a lowercase 26-character Crockford ULID,
  both persisted only inside the ``timeline.created`` envelope (SD1);
- address resolution: UUID, lowercase ULID, and immutable slug all resolve
  within one project (bridge §8 order), with typed missing-project,
  missing-timeline, and invalid-address errors;
- alias uniqueness under ``BEGIN IMMEDIATE``: the slug and ULID uniqueness
  queries run inside the command's transaction over the project's
  ``timeline.created`` events — there are no convenience columns;
- wrong-project isolation: the same slug/ULID in another project is a
  different timeline, and resolution never leaks across projects;
- initial head semantics: after create, the timeline stream head is 1,
  ``config_version`` equals that head, and the project event head advanced
  by exactly one;
- sorted lists: ``list`` returns exactly the frozen bridge rows
  ``{timeline_id, timeline_ulid, slug, name, is_default}`` ordered by slug;
- exact bridge-shaped rows: ``show`` returns the §5.2 load shape with loose
  ``config``, ``registry.assets``, and ``config_version``;
- missing cases: every read raises typed errors and never an empty
  authority-dependent view;
- restart reconstruction solely from event payload and ``settings_json``:
  after a clean close/reopen, aliases and default state are rebuilt from the
  ``timeline.created`` envelope and the repository-owned settings key — the
  frozen DDL has no slug/ULID/default columns (SD1) and no filesystem
  timeline authority exists;
- whole-document CAS save (plan step 14): a successful save atomically
  updates the document and registry projections, appends one hash-chained
  ``timeline.saved`` event carrying the command delta, advances both heads,
  and records the complete receipt, and reload returns exactly the saved
  load shape;
- save replay and mismatch: an identical retry replays the stored result
  with zero new rows, a changed payload never replays a previous result
  (it surfaces as the typed version conflict or a fresh save), and a
  receipt whose stored hash disagrees with the derived key is rejected by
  the receipt gate before any mutation;
- stale-head and validation failure atomicity: a stale expected head
  raises :class:`TimelineVersionConflictError` carrying the typed current
  version, boolean/non-integer ``expected_version`` and every malformed
  payload are rejected, and each failed save leaves the document, registry,
  events, both heads, and receipts unchanged;
- save project isolation: saving one project's timeline never mutates
  another project's document, registry, events, heads, or receipts, and a
  foreign timeline id is not an address outside its project.

Every command runs inside the caller's one ``BEGIN IMMEDIATE`` unit of work
(:class:`astrid.core.store.uow.UnitOfWork`); every read runs on a separate
read-only connection.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from astrid.core.events.service import EventAppendService, EventChainError
from astrid.core.ids import generate_lowercase_ulid, is_lowercase_ulid
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import ProjectNotFoundError, ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.timeline.repository import (
    TIMELINE_ARCHIVE_COMMAND_KIND,
    TIMELINE_ARCHIVED_EVENT_KIND,
    TIMELINE_CREATE_COMMAND_KIND,
    TIMELINE_CREATED_EVENT_KIND,
    TIMELINE_SAVE_COMMAND_KIND,
    TIMELINE_SAVED_EVENT_KIND,
    TIMELINE_STREAM_TYPE,
    TimelineAlreadyExistsError,
    TimelineArchivedError,
    TimelineNotFoundError,
    TimelineRepository,
    TimelineSlugConflictError,
    TimelineUlidConflictError,
    TimelineValidationError,
    TimelineVersionConflictError,
)

TS = "2026-08-15T00:00:00.000000+00:00"
TS2 = "2026-08-15T01:00:00.000000+00:00"
TS3 = "2026-08-15T02:00:00.000000+00:00"

_CROCKFORD_ULID_RE = re.compile(r"^[0123456789abcdefghjkmnpqrstvwxyz]{26}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

CONFIG = {"fps": 24, "resolution": "1920x1080", "nested": {"scene": "s01"}}
ASSETS = {"hero": {"path": "hero.png", "kind": "image"}}
SAVED_CONFIG = {"fps": 30, "resolution": "2560x1440", "nested": {"scene": "s02"}}
SAVED_ASSETS = {"hero": {"path": "hero-v2.png", "kind": "image"}}


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
    """A stateless project repository over the kernel services."""
    return ProjectRepository(
        events=EventAppendService(standard_registry),
        receipts=ReceiptService(),
    )


@pytest.fixture
def repo(standard_registry, project_repo) -> TimelineRepository:
    """A stateless timeline repository over the kernel services."""
    return TimelineRepository(
        events=EventAppendService(standard_registry),
        receipts=ReceiptService(),
        projects=project_repo,
    )


def _create_project(repo: ProjectRepository, writer: DatabaseWriter, **overrides):
    """Run one project-create command inside its own unit of work."""
    args = {
        "slug": "pilot",
        "name": "Pilot",
        "settings": {"fps": 24},
        "idempotency_key": "proj-create-1",
        "project_id": None,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(writer).run(lambda u: repo.create(u, **args))


def _create_timeline(
    repo: TimelineRepository,
    writer: DatabaseWriter,
    project_id: str,
    **overrides,
):
    """Run one timeline-create command inside its own unit of work."""
    args = {
        "slug": "main",
        "name": "Main",
        "config": CONFIG,
        "registry": {"assets": ASSETS},
        "idempotency_key": "tl-create-1",
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(writer).run(
        lambda u: repo.create(u, project_id=project_id, **args)
    )


def _save_timeline(
    repo: TimelineRepository,
    writer: DatabaseWriter,
    project_id: str,
    ref: str,
    **overrides,
):
    """Run one whole-document CAS save inside its own unit of work."""
    args = {
        "config": SAVED_CONFIG,
        "registry": {"assets": SAVED_ASSETS},
        "expected_version": 1,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(writer).run(
        lambda u: repo.save(u, project_id=project_id, ref=ref, **args)
    )


def _archive_timeline(
    repo: TimelineRepository,
    writer: DatabaseWriter,
    project_id: str,
    ref: str,
    **overrides,
):
    """Run one event-backed archive inside its own unit of work."""
    args = {"idempotency_key": "tl-archive-1", "created_at": TS3}
    args.update(overrides)
    return UnitOfWork(writer).run(
        lambda u: repo.archive(u, project_id=project_id, ref=ref, **args)
    )


def _save_surfaces(
    writer: DatabaseWriter, project_id: str, timeline_id: str
) -> dict[str, Any]:
    """Snapshot the six persisted surfaces a save touches, project-scoped.

    Every failed save must leave document, registry, events, both heads,
    and receipts exactly as they were: ``document_json`` and
    ``asset_registry_json`` (the whole-document projection), ``updated_at``,
    the project-scoped event and receipt row counts, the timeline stream
    head, and the project event head.
    """

    def snapshot(session) -> dict[str, Any]:
        timeline = session.query_one(
            "SELECT document_json, asset_registry_json, updated_at, name "
            "FROM timelines WHERE id = ?",
            (timeline_id,),
        )
        assert timeline is not None
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
            "name": timeline["name"],
            "event_count": session.query_one(
                "SELECT count(*) FROM events WHERE project_id = ?",
                (project_id,),
            )[0],
            "receipt_count": session.query_one(
                "SELECT count(*) FROM command_receipts WHERE project_id = ?",
                (project_id,),
            )[0],
            "stream_head": stream["head_seq"] if stream is not None else None,
            "project_head": project["event_head_seq"] if project is not None else None,
        }

    return writer.submit(snapshot)


def _counts(writer: DatabaseWriter) -> tuple[int, int, int, int]:
    """(timelines, event_streams, events, command_receipts) row counts."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM timelines")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )


def _stream_row(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
        )
    )


def _timeline_row(writer: DatabaseWriter, timeline_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM timelines WHERE id = ?", (timeline_id,)
        )
    )


def _project_row(writer: DatabaseWriter, project_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
    )


# ---------------------------------------------------------------------------
# Create atomicity and initial head semantics
# ---------------------------------------------------------------------------


def test_create_commits_stream_projection_event_and_receipt_atomically(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    standard_registry,
) -> None:
    project = _create_project(project_repo, writer, slug="pilot")
    timeline_id = "0f8fad5b-d9cb-469f-a165-70867728950e"
    timeline_ulid = "0123456789abcdefghjkmnpqrs"
    created = _create_timeline(
        repo,
        writer,
        project.id,
        slug="main",
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
    )

    stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
    stream = _stream_row(writer, stream_id)
    assert stream is not None
    assert stream["project_id"] == project.id
    assert stream["stream_type"] == TIMELINE_STREAM_TYPE
    assert stream["aggregate_id"] == timeline_id
    # Initial head semantics: the create advanced the timeline stream from
    # 0 to exactly 1 and the project event head by exactly one.
    assert stream["head_seq"] == 1
    project_row = _project_row(writer, project.id)
    assert project_row["event_head_seq"] == 2

    timeline = _timeline_row(writer, timeline_id)
    assert timeline["name"] == "Main"
    assert json.loads(timeline["document_json"]) == CONFIG
    assert json.loads(timeline["asset_registry_json"]) == ASSETS

    # Exactly one timeline.created event on the stream, with the alias
    # metadata and the canonical SD2 envelope (genesis previous hash null).
    event = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM events WHERE stream_id = ?", (stream_id,)
        )
    )
    assert event["kind"] == TIMELINE_CREATED_EVENT_KIND
    assert event["seq"] == 1
    assert event["project_seq"] == 2
    assert event["subject_type"] == "timeline"
    assert event["subject_id"] == timeline_id
    payload = json.loads(event["payload_json"])
    assert payload["data"] == {
        "timeline_id": timeline_id,
        "timeline_ulid": timeline_ulid,
        "slug": "main",
        "name": "Main",
        "config": CONFIG,
        "registry": {"assets": ASSETS},
    }
    integrity = payload["_integrity"]
    assert integrity["previous_event_hash"] is None
    assert _SHA256_HEX_RE.fullmatch(integrity["event_hash"]) is not None

    # The receipt points at the stream with the exact sequence range.
    receipt = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = ? AND idempotency_key = ?",
            (project.id, "tl-create-1"),
        )
    )
    assert receipt["command_kind"] == TIMELINE_CREATE_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 1
    assert receipt["first_project_seq"] == 2
    assert receipt["last_project_seq"] == 2
    assert json.loads(receipt["event_ids_json"]) == [event["event_id"]]

    # Initial config_version is the numeric stream head.
    assert created.config_version == 1

    # The chain verifies from genesis to head (NSA-2 executable gate).
    verification = EventAppendService(standard_registry).verify_stream(
        writer, stream_id
    )
    assert verification.event_count == 1
    assert verification.head_seq == 1
    assert verification.head_hash == integrity["event_hash"]


def test_create_generates_canonical_uuid_and_lowercase_ulid(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="gen")
    assert _UUID_RE.fullmatch(created.timeline_id) is not None
    assert _CROCKFORD_ULID_RE.fullmatch(created.timeline_ulid) is not None
    assert is_lowercase_ulid(created.timeline_ulid)


def test_create_slug_conflict_changes_zero_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="main")
    before = _counts(writer)

    with pytest.raises(TimelineSlugConflictError) as excinfo:
        _create_timeline(
            repo, writer, project.id, slug="main", idempotency_key="tl-create-2"
        )
    assert excinfo.value.slug == "main"
    assert excinfo.value.project_id == project.id
    # Alias uniqueness is transactional: zero new rows of any kind.
    assert _counts(writer) == before


def test_create_ulid_conflict_changes_zero_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(
        repo, writer, project.id, slug="one", timeline_ulid="0123456789abcdefghjkmnpqrs"
    )
    before = _counts(writer)

    with pytest.raises(TimelineUlidConflictError) as excinfo:
        _create_timeline(
            repo,
            writer,
            project.id,
            slug="two",
            timeline_ulid="0123456789abcdefghjkmnpqrs",
            idempotency_key="tl-create-2",
        )
    assert excinfo.value.timeline_ulid == "0123456789abcdefghjkmnpqrs"
    assert _counts(writer) == before


def test_create_existing_timeline_id_rejected(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    before = _counts(writer)

    with pytest.raises(TimelineAlreadyExistsError) as excinfo:
        _create_timeline(
            repo,
            writer,
            project.id,
            slug="other",
            timeline_id=created.timeline_id,
            idempotency_key="tl-create-2",
        )
    assert excinfo.value.timeline_id == created.timeline_id
    assert _counts(writer) == before


def test_create_validation_failures_change_zero_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)

    invalid_calls = [
        {"slug": "Bad Slug!"},
        {"slug": ""},
        {"name": ""},
        {"config": ["not", "an", "object"]},
        {"registry": "not-an-object"},
        {"registry": {"assets": ["not", "an", "object"]}},
        {"actor_kind": "remote"},
        {"set_default": "yes"},
    ]
    for index, overrides in enumerate(invalid_calls):
        with pytest.raises(TimelineValidationError):
            _create_timeline(
                repo,
                writer,
                project.id,
                idempotency_key=f"invalid-{index}",
                **overrides,
            )
    # Every validation failure happened before any mutation.
    assert _counts(writer) == (0, 1, 1, 1)


# ---------------------------------------------------------------------------
# Address resolution: UUID, lowercase ULID, slug (bridge §8 order)
# ---------------------------------------------------------------------------


def test_resolve_all_three_address_forms(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")

    assert repo.resolve(writer, project.id, created.timeline_id) == created.timeline_id
    assert repo.resolve(writer, project.id, created.timeline_ulid) == created.timeline_id
    assert repo.resolve(writer, project.id, "main") == created.timeline_id

    # show accepts every form too.
    assert repo.show(writer, project.id, created.timeline_id) == created
    assert repo.show(writer, project.id, created.timeline_ulid) == created
    assert repo.show(writer, project.id, "main") == created


def test_resolve_missing_cases_raise_typed_errors(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="main")

    # Missing project: every read raises project-not-found, never an empty
    # authority-dependent view.
    missing_project = generate_lowercase_ulid()
    with pytest.raises(ProjectNotFoundError):
        repo.resolve(writer, missing_project, "main")
    with pytest.raises(ProjectNotFoundError):
        repo.list(writer, missing_project)
    with pytest.raises(ProjectNotFoundError):
        repo.show(writer, missing_project, "main")

    # Invalid address grammar is a validation error.
    with pytest.raises(TimelineValidationError):
        repo.resolve(writer, project.id, "NOT_A_VALID_REF!")

    # Valid-form addresses that name no timeline are not-found.
    with pytest.raises(TimelineNotFoundError) as uuid_miss:
        repo.resolve(writer, project.id, "9f8fad5b-d9cb-469f-a165-70867728950e")
    assert uuid_miss.value.project_id == project.id
    with pytest.raises(TimelineNotFoundError) as slug_miss:
        repo.resolve(writer, project.id, "absent")
    assert slug_miss.value.ref == "absent"


def test_wrong_project_isolation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project_a = _create_project(project_repo, writer, slug="alpha")
    project_b = _create_project(project_repo, writer, slug="beta")
    shared_ulid = "0123456789abcdefghjkmnpqrs"

    in_a = _create_timeline(
        repo,
        writer,
        project_a.id,
        slug="shared",
        timeline_ulid=shared_ulid,
        idempotency_key="a-1",
    )
    in_b = _create_timeline(
        repo,
        writer,
        project_b.id,
        slug="shared",
        timeline_ulid=shared_ulid,
        idempotency_key="b-1",
    )
    assert in_a.timeline_id != in_b.timeline_id

    # The same slug and ULID resolve to different timelines per project.
    assert repo.resolve(writer, project_a.id, "shared") == in_a.timeline_id
    assert repo.resolve(writer, project_b.id, "shared") == in_b.timeline_id
    assert repo.resolve(writer, project_a.id, shared_ulid) == in_a.timeline_id
    assert repo.resolve(writer, project_b.id, shared_ulid) == in_b.timeline_id

    # A timeline from another project never resolves or shows here.
    with pytest.raises(TimelineNotFoundError):
        repo.resolve(writer, project_b.id, in_a.timeline_id)
    with pytest.raises(TimelineNotFoundError):
        repo.show(writer, project_a.id, in_b.timeline_id)

    # Lists are project-scoped.
    assert [row.slug for row in repo.list(writer, project_a.id)] == ["shared"]
    assert [row.slug for row in repo.list(writer, project_b.id)] == ["shared"]
    assert repo.list(writer, project_a.id)[0].timeline_id == in_a.timeline_id


# ---------------------------------------------------------------------------
# Sorted bridge-shaped lists and exact show rows
# ---------------------------------------------------------------------------


def test_list_returns_sorted_bridge_shaped_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    assert repo.list(writer, project.id) == []

    created_by_slug = {}
    for index, (slug, name) in enumerate(
        [
            ("zulu", "Zulu"),
            ("alpha", "Alpha"),
            ("mid-2", "Mid 2"),
            ("alpha-1", "Alpha 1"),
            ("beta", "Beta"),
        ]
    ):
        created = _create_timeline(
            repo,
            writer,
            project.id,
            slug=slug,
            name=name,
            idempotency_key=f"list-{index}",
        )
        created_by_slug[slug] = created

    rows = repo.list(writer, project.id)
    assert [row.slug for row in rows] == [
        "alpha",
        "alpha-1",
        "beta",
        "mid-2",
        "zulu",
    ]
    for row in rows:
        # Exactly the frozen bridge list shape (§5.1), nothing more.
        assert set(row.to_dict().keys()) == {
            "timeline_id",
            "timeline_ulid",
            "slug",
            "name",
            "is_default",
        }
        assert row.timeline_ulid == created_by_slug[row.slug].timeline_ulid
        assert row.name == created_by_slug[row.slug].name
        assert row.is_default is False


def test_show_returns_exact_bridge_load_shape(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")

    shown = repo.show(writer, project.id, "main")
    # Exactly the frozen load shape (§5.2).
    assert set(shown.to_dict().keys()) == {
        "timeline_id",
        "timeline_ulid",
        "slug",
        "name",
        "is_default",
        "config",
        "registry",
        "config_version",
    }
    assert shown == created
    assert shown.config == CONFIG
    assert shown.registry == {"assets": ASSETS}
    assert shown.config_version == 1


def test_set_default_projects_default_state(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    default = _create_timeline(
        repo, writer, project.id, slug="main", set_default=True
    )
    other = _create_timeline(
        repo,
        writer,
        project.id,
        slug="other",
        idempotency_key="tl-create-2",
    )

    assert default.is_default is True
    assert other.is_default is False
    assert repo.show(writer, project.id, "main").is_default is True
    assert repo.show(writer, project.id, "other").is_default is False
    assert repo.list(writer, project.id)[0].is_default is True

    # The default is repository-owned settings_json state (SD1).
    settings = json.loads(_project_row(writer, project.id)["settings_json"])
    assert settings["default_timeline_id"] == default.timeline_id


# ---------------------------------------------------------------------------
# Idempotent replay and mismatch-before-mutation
# ---------------------------------------------------------------------------


def test_create_replay_returns_stored_result_with_zero_new_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    args = {
        "slug": "main",
        "name": "Main",
        "config": CONFIG,
        "registry": {"assets": ASSETS},
        "idempotency_key": "tl-create-1",
        "created_at": TS,
        "timeline_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "timeline_ulid": "0123456789abcdefghjkmnpqrs",
    }
    first = UnitOfWork(writer).run(
        lambda u: repo.create(u, project_id=project.id, **args)
    )
    before = _counts(writer)

    replayed = UnitOfWork(writer).run(
        lambda u: repo.create(u, project_id=project.id, **args)
    )
    assert replayed == first
    assert _counts(writer) == before


def test_create_mismatch_rejected_before_mutation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="main")
    before = _counts(writer)

    with pytest.raises(ReceiptMismatchError):
        _create_timeline(
            repo, writer, project.id, slug="different", idempotency_key="tl-create-1"
        )
    assert _counts(writer) == before


# ---------------------------------------------------------------------------
# Restart reconstruction and the absence of a second authority (NSA-3)
# ---------------------------------------------------------------------------


def test_restart_reconstruction_solely_from_events_and_settings(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    tmp_path: Path,
    standard_registry,
) -> None:
    db_path = tmp_path / "astrid.sqlite3"
    writer = DatabaseWriter(db_path, standard_registry)
    try:
        project = _create_project(project_repo, writer, slug="pilot")
        default = _create_timeline(
            repo, writer, project.id, slug="main", set_default=True
        )
        other = _create_timeline(
            repo,
            writer,
            project.id,
            slug="other",
            idempotency_key="tl-create-2",
        )
        before_default = repo.show(writer, project.id, "main")
        before_other = repo.show(writer, project.id, "other")
    finally:
        writer.close()

    # No filesystem timeline authority: only the database and WAL sidecars.
    sidecar_names = {"astrid.sqlite3", "astrid.sqlite3-wal", "astrid.sqlite3-shm"}
    leftover = [
        path.name
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name not in sidecar_names
    ]
    assert leftover == []

    reopened = DatabaseWriter(db_path, standard_registry)
    try:
        # The frozen DDL has no alias/default convenience columns (SD1);
        # identity must come from events and settings_json alone.
        columns = reopened.submit(
            lambda session: [
                row["name"] for row in session.query("PRAGMA table_info(timelines)")
            ]
        )
        for forbidden in ("slug", "timeline_ulid", "is_default"):
            assert forbidden not in columns

        # All three address forms reconstruct after restart.
        assert reopened.submit(
            lambda session: session.query_one(
                "SELECT count(*) FROM events WHERE kind = ?",
                (TIMELINE_CREATED_EVENT_KIND,),
            )[0]
        ) == 2
        assert repo.resolve(reopened, project.id, "main") == default.timeline_id
        assert repo.resolve(reopened, project.id, default.timeline_ulid) == (
            default.timeline_id
        )
        assert repo.resolve(reopened, project.id, default.timeline_id) == (
            default.timeline_id
        )
        # Reads reconstruct exactly the pre-restart models.
        assert repo.show(reopened, project.id, "main") == before_default
        assert repo.show(reopened, project.id, "other") == before_other
        rows = repo.list(reopened, project.id)
        assert [row.slug for row in rows] == ["main", "other"]
        by_slug = {row.slug: row for row in rows}
        assert by_slug["main"].is_default is True
        assert by_slug["other"].is_default is False
        # The default timeline id lives only in settings_json.
        settings = json.loads(
            reopened.submit(
                lambda session: session.query_one(
                    "SELECT settings_json FROM projects WHERE id = ?",
                    (project.id,),
                )["settings_json"]
            )
        )
        assert settings["default_timeline_id"] == default.timeline_id
        # The event chain still verifies after restart (NSA-2).
        EventAppendService(standard_registry).verify_stream(
            reopened, f"{default.timeline_id}:{TIMELINE_STREAM_TYPE}"
        )
    finally:
        reopened.close()


def test_verify_stream_rejects_timeline_created_tampering(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    standard_registry,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    stream_id = f"{created.timeline_id}:{TIMELINE_STREAM_TYPE}"
    service = EventAppendService(standard_registry)

    # Tamper the alias-bearing domain data inside the timeline.created
    # envelope: the chain gate must fail even though the JSON stays valid.
    def tamper(session) -> None:
        row = session.query_one(
            "SELECT payload_json FROM events WHERE stream_id = ? AND kind = ?",
            (stream_id, TIMELINE_CREATED_EVENT_KIND),
        )
        payload = json.loads(row["payload_json"])
        payload["data"]["slug"] = "tampered"
        session.execute(
            "UPDATE events SET payload_json = ? WHERE stream_id = ? AND kind = ?",
            (json.dumps(payload, sort_keys=True), stream_id, TIMELINE_CREATED_EVENT_KIND),
        )

    writer.submit(tamper)
    with pytest.raises(EventChainError):
        service.verify_stream(writer, stream_id)


# ---------------------------------------------------------------------------
# Whole-document CAS save: success, replay, mismatch, stale head, and
# zero-mutation failure atomicity (plan step 14 / T29)
# ---------------------------------------------------------------------------


def test_save_commits_document_registry_event_heads_and_receipt_atomically(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    standard_registry,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(
        repo, writer, project.id, slug="main", set_default=True
    )
    stream_id = f"{created.timeline_id}:{TIMELINE_STREAM_TYPE}"
    saved = _save_timeline(repo, writer, project.id, "main")

    # The committed load shape: new config/registry, config_version is the
    # new stream head (exactly one greater than the CAS expected head), and
    # aliases, name, and default state survive the save.
    assert saved.config_version == 2
    assert saved.config == SAVED_CONFIG
    assert saved.registry == {"assets": SAVED_ASSETS}
    assert saved.slug == "main"
    assert saved.name == "Main"
    assert saved.timeline_id == created.timeline_id
    assert saved.timeline_ulid == created.timeline_ulid
    assert saved.is_default is True

    # The whole-document projection was updated atomically with the save.
    timeline = _timeline_row(writer, created.timeline_id)
    assert json.loads(timeline["document_json"]) == SAVED_CONFIG
    assert json.loads(timeline["asset_registry_json"]) == SAVED_ASSETS
    assert timeline["updated_at"] == TS2
    assert timeline["name"] == "Main"

    # Exactly one timeline.saved event, chained onto the created event.
    events = writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )
    assert [event["kind"] for event in events] == [
        TIMELINE_CREATED_EVENT_KIND,
        TIMELINE_SAVED_EVENT_KIND,
    ]
    saved_event = events[1]
    assert saved_event["seq"] == 2
    # project_seq 4: project create (1), timeline.created (2), the nested
    # default-timeline settings event (3), and this timeline.saved (4).
    assert saved_event["project_seq"] == 4
    assert saved_event["subject_type"] == "timeline"
    assert saved_event["subject_id"] == created.timeline_id
    assert json.loads(saved_event["changes_json"]) == ["config", "registry"]
    # The derived internal key carries command kind, project, timeline,
    # expected head, and canonical digest (bridge §6.1 derivation rule).
    assert saved_event["idempotency_key"].startswith(
        f"{TIMELINE_SAVE_COMMAND_KIND}:{project.id}:{created.timeline_id}:1:"
    )
    payload = json.loads(saved_event["payload_json"])
    assert payload["data"] == {
        "timeline_id": created.timeline_id,
        "config": SAVED_CONFIG,
        "registry": {"assets": SAVED_ASSETS},
        "expected_version": 1,
    }
    integrity = payload["_integrity"]
    created_payload = json.loads(events[0]["payload_json"])
    assert integrity["previous_event_hash"] == created_payload["_integrity"][
        "event_hash"
    ]
    assert _SHA256_HEX_RE.fullmatch(integrity["event_hash"]) is not None

    # Both heads advanced by exactly one in the same transaction.
    stream = _stream_row(writer, stream_id)
    assert stream["head_seq"] == 2
    project_row = _project_row(writer, project.id)
    assert project_row["event_head_seq"] == 4

    # The complete save receipt: stream association, exact project range,
    # the ordered event id, and the committed result.
    receipt = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = ? AND command_kind = ?",
            (project.id, TIMELINE_SAVE_COMMAND_KIND),
        )
    )
    assert receipt is not None
    assert receipt["txn_id"] == saved_event["txn_id"]
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2
    assert receipt["first_project_seq"] == 4
    assert receipt["last_project_seq"] == 4
    assert json.loads(receipt["event_ids_json"]) == [saved_event["event_id"]]
    assert json.loads(receipt["result_json"]) == saved.to_dict()

    # The chain still verifies from genesis to the saved head (NSA-2).
    verification = EventAppendService(standard_registry).verify_stream(
        writer, stream_id
    )
    assert verification.event_count == 2
    assert verification.head_seq == 2
    assert verification.head_hash == integrity["event_hash"]

    # Reload (separate read-only connection) returns exactly the saved shape.
    assert repo.show(writer, project.id, "main") == saved
    assert repo.show(writer, project.id, created.timeline_id) == saved
    assert repo.show(writer, project.id, created.timeline_ulid) == saved


def test_save_replay_returns_stored_result_with_zero_new_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    first = _save_timeline(repo, writer, project.id, "main")
    before_counts = _counts(writer)
    before_surfaces = _save_surfaces(writer, project.id, created.timeline_id)

    # An identical retry (same identity, payload, and expected head) derives
    # the same internal key and replays exactly the stored result.
    replayed = _save_timeline(repo, writer, project.id, "main")
    assert replayed == first
    assert _counts(writer) == before_counts
    assert _save_surfaces(writer, project.id, created.timeline_id) == before_surfaces


def test_save_changed_payload_never_replays_previous_result(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    first = _save_timeline(repo, writer, project.id, "main")
    assert first.config_version == 2
    before = _save_surfaces(writer, project.id, created.timeline_id)
    other_config = {"fps": 60, "resolution": "3840x2160"}

    # The same expected head with a changed payload must never replay the
    # stored result: the derived key differs, the CAS sees head 2, and the
    # typed conflict surfaces with zero mutation.
    with pytest.raises(TimelineVersionConflictError) as excinfo:
        _save_timeline(
            repo,
            writer,
            project.id,
            "main",
            config=other_config,
            expected_version=1,
        )
    assert excinfo.value.expected_version == 1
    assert excinfo.value.current_version == 2
    assert _save_surfaces(writer, project.id, created.timeline_id) == before

    # At the fresh head the changed payload is a NEW save with its own
    # receipt and event — never a replay of the first result.
    second = _save_timeline(
        repo,
        writer,
        project.id,
        "main",
        config=other_config,
        expected_version=2,
    )
    assert second.config_version == 3
    assert second.config == other_config
    receipts = writer.submit(
        lambda session: session.query(
            "SELECT idempotency_key FROM command_receipts "
            "WHERE project_id = ? AND command_kind = ?",
            (project.id, TIMELINE_SAVE_COMMAND_KIND),
        )
    )
    assert len(receipts) == 2
    assert receipts[0]["idempotency_key"] != receipts[1]["idempotency_key"]

    # The original retry still replays exactly its own stored result.
    replayed = _save_timeline(repo, writer, project.id, "main")
    assert replayed == first


def test_save_receipt_layer_hash_mismatch_rejected_before_mutation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    _save_timeline(repo, writer, project.id, "main")
    before = _save_surfaces(writer, project.id, created.timeline_id)

    # The derived key embeds the canonical digest, so a changed payload can
    # never collide with a stored key through the public API. To prove the
    # receipt gate still rejects a disagreement before any allocation, make
    # the stored request hash disagree with the derived key (as an external
    # tamper would).
    def tamper(session) -> None:
        row = session.query_one(
            "SELECT idempotency_key FROM command_receipts "
            "WHERE project_id = ? AND command_kind = ?",
            (project.id, TIMELINE_SAVE_COMMAND_KIND),
        )
        session.execute(
            "UPDATE command_receipts SET request_hash = ? "
            "WHERE project_id = ? AND idempotency_key = ?",
            ("0" * 64, project.id, row["idempotency_key"]),
        )

    writer.submit(tamper)

    with pytest.raises(ReceiptMismatchError) as excinfo:
        _save_timeline(repo, writer, project.id, "main", expected_version=1)
    assert excinfo.value.project_id == project.id
    assert excinfo.value.stored_request_hash == "0" * 64
    assert excinfo.value.attempted_request_hash != "0" * 64
    # The mismatch fired before the stale-head CAS and before any mutation:
    # document, registry, events, both heads, and receipts are unchanged
    # apart from the intentional request_hash tamper.
    assert _save_surfaces(writer, project.id, created.timeline_id) == before


def test_save_stale_head_raises_typed_conflict_and_changes_nothing(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    first = _save_timeline(repo, writer, project.id, "main")
    assert first.config_version == 2
    before = _save_surfaces(writer, project.id, created.timeline_id)

    # A fresh payload under a stale expected head: no stored receipt (the
    # derived key differs), so the CAS rejects it carrying the CURRENT head.
    with pytest.raises(TimelineVersionConflictError) as excinfo:
        _save_timeline(
            repo,
            writer,
            project.id,
            "main",
            config={"fps": 60},
            expected_version=1,
        )
    err = excinfo.value
    assert err.project_id == project.id
    assert err.timeline_id == created.timeline_id
    assert err.expected_version == 1
    assert err.current_version == 2
    assert str(err) == (
        f"timeline save version conflict: timeline {created.timeline_id!r} in "
        f"project {project.id!r} has head 2, expected 1"
    )

    # The never-observed head 0 is stale for every timeline too.
    with pytest.raises(TimelineVersionConflictError) as zero:
        _save_timeline(repo, writer, project.id, "main", expected_version=0)
    assert zero.value.current_version == 2

    # Stale saves change zero rows on every surface: the timeline stream,
    # the created + first saved events, and the three receipts.
    assert _save_surfaces(writer, project.id, created.timeline_id) == before
    assert _counts(writer) == (1, 2, 3, 3)


def test_save_boolean_and_non_integer_expected_version_rejected(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    before = _save_surfaces(writer, project.id, created.timeline_id)

    for bad_version in (True, False, "2", 2.0, None):
        with pytest.raises(TimelineValidationError):
            _save_timeline(
                repo, writer, project.id, "main", expected_version=bad_version
            )

    assert _save_surfaces(writer, project.id, created.timeline_id) == before
    assert _counts(writer) == (1, 2, 2, 2)


def test_save_validation_failures_change_nothing(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    before = _save_surfaces(writer, project.id, created.timeline_id)

    invalid_calls = [
        {"config": ["not", "an", "object"]},
        {"registry": "not-an-object"},
        {"registry": {"assets": ["not", "an", "object"]}},
        {"actor_kind": "remote"},
        {"created_at": 123},
    ]
    for overrides in invalid_calls:
        with pytest.raises(TimelineValidationError):
            _save_timeline(repo, writer, project.id, "main", **overrides)

    # Invalid address grammar is a validation error too.
    with pytest.raises(TimelineValidationError):
        _save_timeline(repo, writer, project.id, "NOT_A_VALID_REF!")

    # Typed not-found paths before any mutation.
    with pytest.raises(ProjectNotFoundError):
        _save_timeline(repo, writer, generate_lowercase_ulid(), "main")
    with pytest.raises(TimelineNotFoundError):
        _save_timeline(repo, writer, project.id, "absent")

    assert _save_surfaces(writer, project.id, created.timeline_id) == before
    assert _counts(writer) == (1, 2, 2, 2)


def test_save_project_isolation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project_a = _create_project(project_repo, writer, slug="alpha")
    project_b = _create_project(project_repo, writer, slug="beta")
    in_a = _create_timeline(
        repo, writer, project_a.id, slug="shared", idempotency_key="a-1"
    )
    in_b = _create_timeline(
        repo, writer, project_b.id, slug="shared", idempotency_key="b-1"
    )
    assert in_a.timeline_id != in_b.timeline_id

    # Each project's own save advances only its own surfaces.
    saved_a = _save_timeline(repo, writer, project_a.id, "shared")
    saved_b = _save_timeline(repo, writer, project_b.id, "shared")
    assert saved_a.config_version == 2
    assert saved_b.config_version == 2
    surfaces_a = _save_surfaces(writer, project_a.id, in_a.timeline_id)
    surfaces_b = _save_surfaces(writer, project_b.id, in_b.timeline_id)
    assert surfaces_a["stream_head"] == 2
    assert surfaces_b["stream_head"] == 2

    # Resolution is project-scoped: B's timeline id is not an address in A.
    with pytest.raises(TimelineNotFoundError):
        _save_timeline(repo, writer, project_a.id, in_b.timeline_id)
    assert _save_surfaces(writer, project_a.id, in_a.timeline_id) == surfaces_a
    assert _save_surfaces(writer, project_b.id, in_b.timeline_id) == surfaces_b

    # A stale save in B carries B's current head and mutates neither side.
    with pytest.raises(TimelineVersionConflictError) as excinfo:
        _save_timeline(
            repo,
            writer,
            project_b.id,
            "shared",
            config={"fps": 120},
            expected_version=1,
        )
    assert excinfo.value.project_id == project_b.id
    assert excinfo.value.current_version == 2
    assert _save_surfaces(writer, project_a.id, in_a.timeline_id) == surfaces_a
    assert _save_surfaces(writer, project_b.id, in_b.timeline_id) == surfaces_b

    # A fresh save in A never touches B's surfaces or receipts.
    saved_a2 = _save_timeline(
        repo,
        writer,
        project_a.id,
        "shared",
        config={"fps": 60},
        expected_version=2,
    )
    assert saved_a2.config_version == 3
    assert _save_surfaces(writer, project_b.id, in_b.timeline_id) == surfaces_b


def test_save_survives_restart_reconstruction(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    tmp_path: Path,
    standard_registry,
) -> None:
    db_path = tmp_path / "astrid.sqlite3"
    writer = DatabaseWriter(db_path, standard_registry)
    try:
        project = _create_project(project_repo, writer, slug="pilot")
        created = _create_timeline(
            repo, writer, project.id, slug="main", set_default=True
        )
        _save_timeline(repo, writer, project.id, "main")
        before = repo.show(writer, project.id, "main")
        assert before.config_version == 2
    finally:
        writer.close()

    reopened = DatabaseWriter(db_path, standard_registry)
    try:
        # Reload after restart returns exactly the saved load shape.
        assert repo.show(reopened, project.id, "main") == before
        assert repo.show(reopened, project.id, created.timeline_id) == before
        # The saved document and registry persisted in the projection.
        row = reopened.submit(
            lambda session: session.query_one(
                "SELECT document_json, asset_registry_json "
                "FROM timelines WHERE id = ?",
                (created.timeline_id,),
            )
        )
        assert json.loads(row["document_json"]) == SAVED_CONFIG
        assert json.loads(row["asset_registry_json"]) == SAVED_ASSETS
        # The chain still verifies through the saved event after restart.
        EventAppendService(standard_registry).verify_stream(
            reopened, f"{created.timeline_id}:{TIMELINE_STREAM_TYPE}"
        )
        # Default-timeline state survives the save untouched.
        settings = json.loads(
            reopened.submit(
                lambda session: session.query_one(
                    "SELECT settings_json FROM projects WHERE id = ?",
                    (project.id,),
                )["settings_json"]
            )
        )
        assert settings["default_timeline_id"] == created.timeline_id
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# Caller-keyed save (m4 plan step 6, task T7)
# ---------------------------------------------------------------------------


def test_save_with_caller_key_commits_and_replays(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    stream_id = f"{created.timeline_id}:{TIMELINE_STREAM_TYPE}"

    saved = _save_timeline(
        repo, writer, project.id, "main", idempotency_key="sdk-key-1"
    )
    assert saved.config_version == 2
    assert saved.config == SAVED_CONFIG

    # The receipt is keyed on the caller key, not the bridge-derived key.
    receipt = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = ? AND idempotency_key = ?",
            (project.id, "sdk-key-1"),
        )
    )
    assert receipt is not None
    assert receipt["command_kind"] == TIMELINE_SAVE_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2

    # The saved event carries the caller key verbatim.
    event = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM events WHERE stream_id = ? AND kind = ?",
            (stream_id, TIMELINE_SAVED_EVENT_KIND),
        )
    )
    assert event["idempotency_key"] == "sdk-key-1"

    # Lost-response replay: an identical retry returns the committed result
    # with zero new rows.
    before = _counts(writer)
    replayed = _save_timeline(
        repo, writer, project.id, "main", idempotency_key="sdk-key-1"
    )
    assert replayed == saved
    assert _counts(writer) == before


def test_save_with_caller_key_mismatch_rejected_before_mutation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    first = _save_timeline(
        repo, writer, project.id, "main", idempotency_key="sdk-key-1"
    )
    assert first.config_version == 2
    before = _save_surfaces(writer, project.id, created.timeline_id)

    # The same caller key with a changed payload must raise
    # idempotency_mismatch before the CAS check and before any mutation.
    with pytest.raises(ReceiptMismatchError) as excinfo:
        _save_timeline(
            repo,
            writer,
            project.id,
            "main",
            idempotency_key="sdk-key-1",
            config={"fps": 60},
            expected_version=1,
        )
    assert excinfo.value.idempotency_key == "sdk-key-1"
    assert excinfo.value.project_id == project.id
    assert _save_surfaces(writer, project.id, created.timeline_id) == before


def test_save_with_caller_key_rejects_same_payload_for_another_timeline(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="main")
    other = _create_timeline(
        repo,
        writer,
        project.id,
        slug="other",
        idempotency_key="tl-create-2",
    )
    _save_timeline(
        repo, writer, project.id, "main", idempotency_key="sdk-key-1"
    )
    before = _save_surfaces(writer, project.id, other.timeline_id)

    # Receipt keys are project-scoped, so the resolved timeline target is
    # semantic input even when the config, registry, and expected head are
    # byte-identical. The mismatch gate fires before touching ``other``.
    with pytest.raises(ReceiptMismatchError):
        _save_timeline(
            repo, writer, project.id, "other", idempotency_key="sdk-key-1"
        )
    assert _save_surfaces(writer, project.id, other.timeline_id) == before


def test_save_caller_key_and_bridge_derived_key_coexist(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")

    # A caller-keyed save at head 1.
    first = _save_timeline(
        repo, writer, project.id, "main", idempotency_key="sdk-key-1"
    )
    assert first.config_version == 2

    # A bridge-derived save (no caller key) at the fresh head 2.
    second = _save_timeline(
        repo, writer, project.id, "main", config={"fps": 60}, expected_version=2
    )
    assert second.config_version == 3

    receipts = writer.submit(
        lambda session: session.query(
            "SELECT idempotency_key FROM command_receipts "
            "WHERE project_id = ? AND command_kind = ?",
            (project.id, TIMELINE_SAVE_COMMAND_KIND),
        )
    )
    assert len(receipts) == 2
    keys = {row["idempotency_key"] for row in receipts}
    assert "sdk-key-1" in keys
    bridge_keys = keys - {"sdk-key-1"}
    assert len(bridge_keys) == 1
    (bridge_key,) = bridge_keys
    # The absent-caller-key path still derives the frozen bridge key.
    assert bridge_key.startswith(
        f"{TIMELINE_SAVE_COMMAND_KIND}:{project.id}:{created.timeline_id}:2:"
    )


def test_save_with_caller_key_survives_restart_reconstruction(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    tmp_path: Path,
    standard_registry,
) -> None:
    db_path = tmp_path / "astrid.sqlite3"
    writer = DatabaseWriter(db_path, standard_registry)
    try:
        project = _create_project(project_repo, writer, slug="pilot")
        created = _create_timeline(repo, writer, project.id, slug="main")
        _save_timeline(
            repo, writer, project.id, "main", idempotency_key="sdk-key-1"
        )
        before = repo.show(writer, project.id, "main")
        assert before.config_version == 2
    finally:
        writer.close()

    reopened = DatabaseWriter(db_path, standard_registry)
    try:
        # Reload after restart returns the caller-keyed saved shape.
        assert repo.show(reopened, project.id, "main") == before
        # The caller-keyed receipt persists and still replays after restart.
        replayed = _save_timeline(
            repo, reopened, project.id, "main", idempotency_key="sdk-key-1"
        )
        assert replayed == before
        assert repo.show(reopened, project.id, created.timeline_id) == before
    finally:
        reopened.close()


@pytest.mark.parametrize("idempotency_key", [None, "sdk-key-crash"])
def test_save_identity_paths_roll_back_every_surface_on_crash(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    idempotency_key: str | None,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    before = _save_surfaces(writer, project.id, created.timeline_id)

    def crash_after_projection(kind: str, sql: str, _params: tuple) -> None:
        if kind == "statement" and sql.startswith("UPDATE timelines SET"):
            raise RuntimeError("simulated crash after timeline projection write")

    with pytest.raises(RuntimeError):
        UnitOfWork(writer, on_statement=crash_after_projection).run(
            lambda u: repo.save(
                u,
                project_id=project.id,
                ref="main",
                config=SAVED_CONFIG,
                registry={"assets": SAVED_ASSETS},
                expected_version=1,
                idempotency_key=idempotency_key,
                created_at=TS2,
            )
        )

    # Projection, event, both heads, and receipt all roll back together for
    # caller and bridge-derived identities; no partial save is observable.
    assert _save_surfaces(writer, project.id, created.timeline_id) == before


# ---------------------------------------------------------------------------
# Event-backed archive, ordered history, and adjacent-version diffs
# (m4 plan step 7, task T8)
# ---------------------------------------------------------------------------


def test_archive_commits_archived_event_and_receipt_atomically(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
    standard_registry,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    stream_id = f"{created.timeline_id}:{TIMELINE_STREAM_TYPE}"

    archived = _archive_timeline(repo, writer, project.id, "main")

    # The archive read model: no projection changed (SD1), config_version is
    # the stream head after the archive event.
    assert archived.timeline_id == created.timeline_id
    assert archived.project_id == project.id
    assert archived.archived_at == TS3
    assert archived.config_version == 2

    # Exactly [created, archived] on the stream; the archived event is
    # hash-chained onto the created event and advances both heads.
    events = writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )
    assert [event["kind"] for event in events] == [
        TIMELINE_CREATED_EVENT_KIND,
        TIMELINE_ARCHIVED_EVENT_KIND,
    ]
    archived_event = events[1]
    assert archived_event["seq"] == 2
    assert archived_event["project_seq"] == 3
    assert archived_event["subject_type"] == "timeline"
    assert archived_event["subject_id"] == created.timeline_id
    assert json.loads(archived_event["changes_json"]) == [
        "timeline_id",
        "archived_at",
    ]
    payload = json.loads(archived_event["payload_json"])
    assert payload["data"] == {
        "timeline_id": created.timeline_id,
        "archived_at": TS3,
    }
    created_payload = json.loads(events[0]["payload_json"])
    assert payload["_integrity"]["previous_event_hash"] == created_payload[
        "_integrity"
    ]["event_hash"]

    # The archive receipt points at the stream with the exact sequence.
    receipt = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = ? AND command_kind = ?",
            (project.id, TIMELINE_ARCHIVE_COMMAND_KIND),
        )
    )
    assert receipt is not None
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2
    assert receipt["first_project_seq"] == 3
    assert receipt["last_project_seq"] == 3
    assert json.loads(receipt["event_ids_json"]) == [archived_event["event_id"]]
    assert json.loads(receipt["result_json"]) == archived.to_dict()

    # Both heads advanced by exactly one; the chain verifies genesis→head.
    assert _stream_row(writer, stream_id)["head_seq"] == 2
    assert _project_row(writer, project.id)["event_head_seq"] == 3
    verification = EventAppendService(standard_registry).verify_stream(
        writer, stream_id
    )
    assert verification.event_count == 2
    assert verification.head_seq == 2

    # No projection row changed: the archived state lives only in the event.
    timeline = _timeline_row(writer, created.timeline_id)
    assert json.loads(timeline["document_json"]) == CONFIG
    assert json.loads(timeline["asset_registry_json"]) == ASSETS

    # Direct historical lookup still returns the archived timeline.
    assert repo.show(writer, project.id, "main").timeline_id == created.timeline_id


def test_archive_replay_returns_stored_result_with_zero_new_rows(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    first = _archive_timeline(repo, writer, project.id, "main")
    before = _counts(writer)

    replayed = _archive_timeline(repo, writer, project.id, "main")
    assert replayed == first
    assert _counts(writer) == before
    assert _stream_row(writer, f"{created.timeline_id}:{TIMELINE_STREAM_TYPE}")[
        "head_seq"
    ] == 2


def test_archive_mismatch_rejected_before_mutation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="main")
    _create_timeline(
        repo, writer, project.id, slug="other", idempotency_key="tl-create-2"
    )
    _archive_timeline(repo, writer, project.id, "main")
    before = _counts(writer)

    # Same caller key, different timeline: idempotency mismatch before any
    # mutation.
    with pytest.raises(ReceiptMismatchError):
        _archive_timeline(repo, writer, project.id, "other")
    assert _counts(writer) == before


def test_archive_already_archived_rejected_with_zero_mutation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    _archive_timeline(repo, writer, project.id, "main")
    before = _counts(writer)

    with pytest.raises(TimelineArchivedError) as excinfo:
        _archive_timeline(
            repo, writer, project.id, "main", idempotency_key="tl-archive-2"
        )
    assert excinfo.value.timeline_id == created.timeline_id
    assert excinfo.value.project_id == project.id
    assert _counts(writer) == before


def test_save_after_archive_rejected_with_zero_mutation(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    _save_timeline(repo, writer, project.id, "main")
    _archive_timeline(repo, writer, project.id, "main")
    before = _save_surfaces(writer, project.id, created.timeline_id)

    # A fresh save against the archived timeline is rejected before the CAS
    # and before any mutation (the derived key differs, so the archived fence
    # fires).
    with pytest.raises(TimelineArchivedError) as excinfo:
        _save_timeline(
            repo,
            writer,
            project.id,
            "main",
            config={"fps": 60},
            expected_version=3,
        )
    assert excinfo.value.timeline_id == created.timeline_id
    assert _save_surfaces(writer, project.id, created.timeline_id) == before

    # A caller-keyed save is rejected the same way.
    with pytest.raises(TimelineArchivedError):
        _save_timeline(
            repo,
            writer,
            project.id,
            "main",
            idempotency_key="post-archive-save",
            config={"fps": 60},
            expected_version=3,
        )
    assert _save_surfaces(writer, project.id, created.timeline_id) == before


def test_list_hides_archived_timelines_but_show_still_works(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="keep")
    _create_timeline(
        repo, writer, project.id, slug="gone", idempotency_key="tl-create-2"
    )
    assert [row.slug for row in repo.list(writer, project.id)] == ["gone", "keep"]

    _archive_timeline(repo, writer, project.id, "gone")

    # The archived timeline disappears from the ordinary list, while show
    # (direct historical lookup) still returns it.
    assert [row.slug for row in repo.list(writer, project.id)] == ["keep"]
    shown = repo.show(writer, project.id, "gone")
    assert shown.slug == "gone"
    assert shown.config_version == 2


def test_history_returns_ordered_lifecycle_events(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    created = _create_timeline(repo, writer, project.id, slug="main")
    _save_timeline(repo, writer, project.id, "main")
    _archive_timeline(repo, writer, project.id, "main")

    history = repo.history(writer, project.id, "main")
    assert [entry.kind for entry in history] == [
        TIMELINE_CREATED_EVENT_KIND,
        TIMELINE_SAVED_EVENT_KIND,
        TIMELINE_ARCHIVED_EVENT_KIND,
    ]
    assert [entry.version for entry in history] == [1, 2, 3]

    created_entry = history[0]
    assert created_entry.config == CONFIG
    assert created_entry.registry == {"assets": ASSETS}
    assert created_entry.archived_at is None

    saved_entry = history[1]
    assert saved_entry.config == SAVED_CONFIG
    assert saved_entry.registry == {"assets": SAVED_ASSETS}

    archived_entry = history[2]
    assert archived_entry.config is None
    assert archived_entry.registry is None
    assert archived_entry.archived_at == TS3

    # History resolves through every address form, like show.
    assert repo.history(writer, project.id, created.timeline_id) == history
    assert repo.history(writer, project.id, created.timeline_ulid) == history


def test_diff_returns_deterministic_adjacent_diffs(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    writer: DatabaseWriter,
) -> None:
    project = _create_project(project_repo, writer)
    _create_timeline(repo, writer, project.id, slug="main")
    _save_timeline(repo, writer, project.id, "main")
    _save_timeline(
        repo,
        writer,
        project.id,
        "main",
        config={"fps": 60},
        registry={"assets": {"hero": {"path": "hero-v3.png"}, "side": {"path": "side.png"}}},
        expected_version=2,
    )

    diffs = repo.diff(writer, project.id, "main")
    assert len(diffs) == 2

    # 1 → 2: every config key changed; hero's asset entry changed.
    first = diffs[0]
    assert (first.from_version, first.to_version) == (1, 2)
    assert first.from_kind == TIMELINE_CREATED_EVENT_KIND
    assert first.to_kind == TIMELINE_SAVED_EVENT_KIND
    assert first.document["added"] == []
    assert first.document["removed"] == []
    assert first.document["changed"] == ["fps", "nested", "resolution"]
    assert first.registry["added"] == []
    assert first.registry["removed"] == []
    assert first.registry["changed"] == ["hero"]

    # 2 → 3: nested + resolution dropped, fps changed; side asset added.
    second = diffs[1]
    assert (second.from_version, second.to_version) == (2, 3)
    assert second.document["added"] == []
    assert second.document["removed"] == ["nested", "resolution"]
    assert second.document["changed"] == ["fps"]
    assert second.registry["added"] == ["side"]
    assert second.registry["removed"] == []
    assert second.registry["changed"] == ["hero"]


def test_archive_state_survives_restart(
    repo: TimelineRepository,
    project_repo: ProjectRepository,
    tmp_path: Path,
    standard_registry,
) -> None:
    db_path = tmp_path / "astrid.sqlite3"
    writer = DatabaseWriter(db_path, standard_registry)
    try:
        project = _create_project(project_repo, writer, slug="pilot")
        _create_timeline(repo, writer, project.id, slug="keep")
        _create_timeline(
            repo, writer, project.id, slug="gone", idempotency_key="tl-create-2"
        )
        _save_timeline(repo, writer, project.id, "gone")
        _archive_timeline(repo, writer, project.id, "gone")
        before_history = repo.history(writer, project.id, "gone")
        before_diffs = repo.diff(writer, project.id, "gone")
    finally:
        writer.close()

    reopened = DatabaseWriter(db_path, standard_registry)
    try:
        # The archived state is reconstructed from the ordered events (SD1):
        # the list hides it, show still returns it, save is still rejected,
        # and history/diff are deterministic after restart.
        assert [row.slug for row in repo.list(reopened, project.id)] == ["keep"]
        assert repo.show(reopened, project.id, "gone").slug == "gone"
        with pytest.raises(TimelineArchivedError):
            _save_timeline(
                repo, reopened, project.id, "gone", config={"fps": 120}, expected_version=3
            )
        assert repo.history(reopened, project.id, "gone") == before_history
        assert repo.diff(reopened, project.id, "gone") == before_diffs
        EventAppendService(standard_registry).verify_stream(
            reopened, f"{repo.resolve(reopened, project.id, 'gone')}:{TIMELINE_STREAM_TYPE}"
        )
    finally:
        reopened.close()
