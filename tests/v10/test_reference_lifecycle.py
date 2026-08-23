"""Reference lifecycle tests: immutable reads, create, and soft archive.

(m3 plan step 7, T8.) This suite proves the references pack's aggregate
lifecycle contract over the frozen three-table schema:

- create atomicity: one ``BEGIN IMMEDIATE`` command writes the
  ``reference.reference`` stream, the active ``project_references`` row,
  the exact primary canonical ``media_references`` row (same-project media,
  ordinal 0, ``is_primary`` 1), one hash-chained ``reference.created``
  event, both heads, and the complete receipt together;
- rejections before allocation: empty/whitespace names, invalid kinds,
  duplicate reference identity, and missing/foreign media all change zero
  rows;
- replay and mismatch: an identical retry returns the stored result with
  zero new rows, and a changed request under the same key fails before any
  mutation;
- soft archive: ``archived_at`` hides a reference only from default lists,
  while associations, links, events, media rows, and bytes are preserved
  (non-cascading archive, SD1), direct historical lookup keeps working, and
  new active mutations of archived references fail;
- reads are transaction-free on a separate read-only connection, and the
  standard catalog stays exactly the frozen 20 tables.

Every command runs inside the caller's one ``BEGIN IMMEDIATE`` unit of work
(:class:`astrid.core.store.uow.UnitOfWork`); every read runs on a separate
read-only connection.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import managed_media_path, prepare_media_file
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import (
    MediaRepository,
    ProjectNotFoundError,
    ProjectRepository,
)
from astrid.core.repositories.media import (
    EXTERNAL_LOCAL_REALM,
    MANAGED_LOCAL_REALM,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.references.repository import (
    PRIMARY_CANONICAL_ROLE,
    REFERENCE_ARCHIVE_COMMAND_KIND,
    REFERENCE_ARCHIVED_EVENT_KIND,
    REFERENCE_CREATE_COMMAND_KIND,
    REFERENCE_CREATED_EVENT_KIND,
    REFERENCE_KINDS,
    REFERENCE_STREAM_TYPE,
    ReferenceAlreadyExistsError,
    ReferenceArchiveReadModel,
    ReferenceArchivedError,
    ReferenceMediaError,
    ReferenceNotFoundError,
    ReferenceReadModel,
    ReferenceRepository,
    ReferenceValidationError,
)

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def env(tmp_path: Path, standard_registry):
    """Fresh standard-Astrid writer plus project/media/reference repositories."""
    writer = DatabaseWriter(tmp_path / "references.sqlite3", standard_registry)
    events = EventAppendService(standard_registry)
    receipts = ReceiptService()
    try:
        yield SimpleNamespace(
            writer=writer,
            projects_root=tmp_path,
            project_repo=ProjectRepository(events=events, receipts=receipts),
            media_repo=MediaRepository(
                events=events, receipts=receipts, projects_root=tmp_path
            ),
            reference_repo=ReferenceRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


def _create_project(env, *, slug: str = "pilot", project_id: str | None = None):
    args = {
        "slug": slug,
        "name": slug.title(),
        "settings": {"fps": 24},
        "idempotency_key": f"create-{slug}-k",
        "project_id": project_id or generate_lowercase_ulid(),
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(lambda u: env.project_repo.create(u, **args))


def _write_png(env, name: str, data: bytes = PNG_BYTES) -> Path:
    path = env.projects_root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _import_media(
    env,
    *,
    project_id: str,
    media_id: str | None = None,
    data: bytes = PNG_BYTES,
    realm: str = EXTERNAL_LOCAL_REALM,
    idempotency_key: str = "import-k-1",
):
    path = _write_png(env, f"media-{generate_lowercase_ulid()}.png", data)
    prepared = prepare_media_file(path)
    args = {
        "project_id": project_id,
        "prepared": prepared,
        "idempotency_key": idempotency_key,
        "media_id": media_id or generate_lowercase_ulid(),
        "realm": realm,
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(
        lambda u: env.media_repo.import_prepared(u, **args)
    )


def _create_reference(
    env,
    *,
    project_id: str,
    kind: str = "character",
    name: str = "Ada",
    media_id: str,
    reference_id: str | None = None,
    idempotency_key: str = "ref-create-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "kind": kind,
        "name": name,
        "media_id": media_id,
        "idempotency_key": idempotency_key,
        "reference_id": reference_id,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.create(u, **args)
    )


def _archive_reference(
    env,
    *,
    project_id: str,
    reference_id: str,
    idempotency_key: str = "ref-archive-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "reference_id": reference_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.archive(u, **args)
    )


def _counts(writer: DatabaseWriter) -> tuple[int, ...]:
    """(project_references, media_references, reference_links, events,
    command_receipts, event_streams, media, media_locations)."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM project_references")[0],
            session.query_one("SELECT count(*) FROM media_references")[0],
            session.query_one("SELECT count(*) FROM reference_links")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM media")[0],
            session.query_one("SELECT count(*) FROM media_locations")[0],
        )
    )


def _reference_row(writer: DatabaseWriter, reference_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM project_references WHERE id = ?", (reference_id,)
        )
    )


def _media_reference_rows(writer: DatabaseWriter, reference_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM media_references WHERE reference_id = ? "
            "ORDER BY role ASC, ordinal ASC, id ASC",
            (reference_id,),
        )
    )


def _stream_row(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
        )
    )


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )


def _receipt_row(writer: DatabaseWriter, project_id: str, key: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts WHERE project_id = ? "
            "AND idempotency_key = ?",
            (project_id, key),
        )
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_reference_create_with_primary_canonical_media(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-c1")
    reference_id = generate_lowercase_ulid()
    counts = _counts(env.writer)

    created = _create_reference(
        env,
        project_id=project.id,
        kind="character",
        name="Ada",
        media_id=media.id,
        reference_id=reference_id,
        idempotency_key="ref-create-c1",
    )
    assert created.id == reference_id
    assert created.project_id == project.id
    assert created.kind == "character"
    assert created.name == "Ada"
    assert created.description == ""
    assert created.metadata == {}
    assert created.archived_at is None
    assert created.event_head_seq == 1
    assert len(created.media) == 1
    primary = created.media[0]
    assert primary.media_id == media.id
    assert primary.role == PRIMARY_CANONICAL_ROLE
    assert primary.ordinal == 0
    assert primary.is_primary is True
    assert primary.context_task_id is None

    # One stream + row + event + receipt, one media association, and the
    # media rows themselves are untouched by the reference create.
    assert _counts(env.writer) == (
        counts[0] + 1,
        counts[1] + 1,
        counts[2],
        counts[3] + 1,
        counts[4] + 1,
        counts[5] + 1,
        counts[6],
        counts[7],
    )

    row = _reference_row(env.writer, reference_id)
    assert row is not None
    assert row["project_id"] == project.id
    assert row["archived_at"] is None
    assoc = _media_reference_rows(env.writer, reference_id)
    assert len(assoc) == 1
    assert assoc[0]["media_id"] == media.id
    assert assoc[0]["role"] == "canonical"
    assert assoc[0]["ordinal"] == 0
    assert assoc[0]["is_primary"] == 1
    assert assoc[0]["context_task_id"] is None

    # Its own registered reference.reference stream with one created event.
    stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"
    assert _stream_row(env.writer, stream_id)["stream_type"] == REFERENCE_STREAM_TYPE
    assert _stream_row(env.writer, stream_id)["aggregate_id"] == reference_id
    assert _stream_row(env.writer, stream_id)["head_seq"] == 1
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [REFERENCE_CREATED_EVENT_KIND]
    data = json.loads(events[0]["payload_json"])["data"]
    assert data["reference_id"] == reference_id
    assert data["kind"] == "character"
    assert data["name"] == "Ada"
    assert data["media"] == {
        "media_reference_id": assoc[0]["id"],
        "media_id": media.id,
        "role": "canonical",
        "context_task_id": None,
        "ordinal": 0,
        "is_primary": True,
    }

    # One complete receipt keyed on the frozen command kind.
    receipt = _receipt_row(env.writer, project.id, "ref-create-c1")
    assert receipt["command_kind"] == REFERENCE_CREATE_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 1
    assert json.loads(receipt["event_ids_json"]) == [events[0]["event_id"]]
    assert json.loads(receipt["result_json"]) == created.to_dict()
    # The read model round-trips from its stored receipt result.
    assert ReferenceReadModel.from_mapping(created.to_dict()) == created


def test_reference_create_rejects_invalid_inputs(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-c2")
    counts = _counts(env.writer)

    with pytest.raises(ReferenceValidationError):
        _create_reference(
            env, project_id=project.id, name="", media_id=media.id
        )
    with pytest.raises(ReferenceValidationError):
        _create_reference(
            env, project_id=project.id, name="   ", media_id=media.id
        )
    with pytest.raises(ReferenceValidationError):
        _create_reference(
            env, project_id=project.id, kind="planet", name="Ada", media_id=media.id
        )
    with pytest.raises(ReferenceValidationError):
        _create_reference(
            env,
            project_id=project.id,
            name="Ada",
            media_id=media.id,
            metadata="not-an-object",
        )
    with pytest.raises(ReferenceValidationError):
        _create_reference(env, project_id=project.id, name="Ada", media_id="")
    with pytest.raises(ReferenceValidationError):
        _create_reference(
            env, project_id=project.id, name="Ada", media_id=media.id, actor_kind="scheduler"
        )
    with pytest.raises(ProjectNotFoundError):
        _create_reference(
            env,
            project_id=generate_lowercase_ulid(),
            name="Ada",
            media_id=media.id,
        )
    assert _counts(env.writer) == counts


def test_reference_create_rejects_duplicate_identity(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-c3")
    reference_id = generate_lowercase_ulid()
    _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        reference_id=reference_id,
        idempotency_key="ref-create-dup-1",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceAlreadyExistsError):
        _create_reference(
            env,
            project_id=project.id,
            name="Another",
            media_id=media.id,
            reference_id=reference_id,
            idempotency_key="ref-create-dup-2",
        )
    assert _counts(env.writer) == counts


def test_reference_create_rejects_missing_and_foreign_media(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    foreign = _import_media(
        env, project_id=project_b.id, idempotency_key="import-c4b"
    )
    counts = _counts(env.writer)
    # Missing media row -> typed missing error, zero mutation.
    with pytest.raises(ReferenceMediaError) as excinfo:
        _create_reference(
            env,
            project_id=project_a.id,
            name="Ada",
            media_id=generate_lowercase_ulid(),
        )
    assert excinfo.value.detail == "missing"
    # A media row that belongs to another project is foreign.
    with pytest.raises(ReferenceMediaError) as excinfo:
        _create_reference(
            env, project_id=project_a.id, name="Ada", media_id=foreign.id
        )
    assert excinfo.value.detail == "foreign"
    assert _counts(env.writer) == counts


def test_reference_create_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-c5")
    reference_id = generate_lowercase_ulid()
    first = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        reference_id=reference_id,
        idempotency_key="ref-create-replay",
    )
    counts = _counts(env.writer)
    # Identical retry returns the stored result with zero new rows.
    second = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        reference_id=reference_id,
        idempotency_key="ref-create-replay",
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(env.writer) == counts
    # A changed request under the same key fails before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _create_reference(
            env,
            project_id=project.id,
            name="Not Ada",
            media_id=media.id,
            reference_id=reference_id,
            idempotency_key="ref-create-replay",
        )
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# Soft archive
# ---------------------------------------------------------------------------


def test_reference_archive_preserves_associations_links_events_media_and_bytes(
    env,
) -> None:
    project = _create_project(env)
    # Managed import materializes bytes at the frozen sharded path so the
    # archive can prove byte preservation.
    media = _import_media(
        env,
        project_id=project.id,
        realm=MANAGED_LOCAL_REALM,
        idempotency_key="import-a1",
    )
    ref_a = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key="ref-create-a1",
    )
    ref_b = _create_reference(
        env,
        project_id=project.id,
        name="Byron",
        media_id=media.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key="ref-create-a2",
    )
    # A second association (depicts, non-primary) and one typed link row.
    UnitOfWork(env.writer).run(
        lambda u: (
            u.execute(
                "INSERT INTO media_references "
                "(id, reference_id, media_id, role, context_task_id, ordinal, "
                "is_primary, metadata_json, created_at) "
                "VALUES (?, ?, ?, 'depicts', NULL, 1, 0, '{}', ?)",
                (generate_lowercase_ulid(), ref_a.id, media.id, TS),
            ),
            u.execute(
                "INSERT INTO reference_links "
                "(from_reference_id, to_reference_id, kind, metadata_json, "
                "created_at) VALUES (?, ?, 'associated_with', '{}', ?)",
                (ref_a.id, ref_b.id, TS),
            ),
        )
    )
    managed_path = managed_media_path(env.projects_root, _digest_of(env, media.id))
    assert managed_path.exists()
    counts_before = _counts(env.writer)
    stream_id = f"{ref_a.id}:{REFERENCE_STREAM_TYPE}"

    archived = _archive_reference(
        env, project_id=project.id, reference_id=ref_a.id, idempotency_key="ref-archive-a1"
    )
    assert archived.reference_id == ref_a.id
    assert archived.project_id == project.id
    assert archived.archived_at == TS2
    assert archived.preserved == {
        "media_references": 2,
        "reference_links": 1,
        "events": 1,
    }
    assert ReferenceArchiveReadModel.from_mapping(archived.to_dict()) == archived

    # Non-cascading archive: every row stays, plus exactly one archived
    # event and one archive receipt.
    assert _counts(env.writer) == (
        counts_before[0],
        counts_before[1],
        counts_before[2],
        counts_before[3] + 1,
        counts_before[4] + 1,
        counts_before[5],
        counts_before[6],
        counts_before[7],
    )
    row = _reference_row(env.writer, ref_a.id)
    assert row["archived_at"] == TS2
    assert row["updated_at"] == TS2
    # Associations and links are fully retained.
    assert len(_media_reference_rows(env.writer, ref_a.id)) == 2
    link_count = env.writer.submit(
        lambda session: session.query_one(
            "SELECT count(*) AS n FROM reference_links "
            "WHERE from_reference_id = ? OR to_reference_id = ?",
            (ref_a.id, ref_a.id),
        )["n"]
    )
    assert link_count == 1
    # Media rows, locations, and bytes are untouched.
    assert _counts(env.writer)[6] == counts_before[6]
    assert _counts(env.writer)[7] == counts_before[7]
    assert managed_path.exists()
    assert managed_path.read_bytes() == PNG_BYTES
    # The reference stream now has created + archived, both hash-chained.
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        REFERENCE_CREATED_EVENT_KIND,
        REFERENCE_ARCHIVED_EVENT_KIND,
    ]
    assert events[1]["seq"] == 2
    assert json.loads(events[1]["payload_json"])["data"] == {
        "reference_id": ref_a.id,
        "archived_at": TS2,
        "preserved": {
            "media_references": 2,
            "reference_links": 1,
            "events": 1,
        },
    }
    # One archive receipt keyed on the frozen command kind.
    receipt = _receipt_row(env.writer, project.id, "ref-archive-a1")
    assert receipt["command_kind"] == REFERENCE_ARCHIVE_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2
    assert json.loads(receipt["result_json"]) == archived.to_dict()
    # The stream head advanced by exactly one.
    assert _stream_row(env.writer, stream_id)["head_seq"] == 2


def _digest_of(env, media_id: str) -> str:
    return env.writer.submit(
        lambda session: session.query_one(
            "SELECT content_hash FROM media WHERE id = ?", (media_id,)
        )["content_hash"]
    )


def test_reference_archive_rejects_missing_foreign_and_already_archived(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_a = _import_media(env, project_id=project_a.id, idempotency_key="import-a2a")
    media_b = _import_media(env, project_id=project_b.id, idempotency_key="import-a2b")
    ref = _create_reference(
        env,
        project_id=project_a.id,
        name="Ada",
        media_id=media_a.id,
        idempotency_key="ref-create-a2",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceNotFoundError):
        _archive_reference(
            env,
            project_id=project_a.id,
            reference_id=generate_lowercase_ulid(),
            idempotency_key="ref-archive-missing",
        )
    assert _counts(env.writer) == counts
    # A reference owned by another project is foreign.
    ref_b = _create_reference(
        env,
        project_id=project_b.id,
        name="Byron",
        media_id=media_b.id,
        idempotency_key="ref-create-a2b",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceNotFoundError):
        _archive_reference(
            env,
            project_id=project_a.id,
            reference_id=ref_b.id,
            idempotency_key="ref-archive-foreign",
        )
    assert _counts(env.writer) == counts
    # Double archive is a typed archived-mutation rejection.
    _archive_reference(
        env, project_id=project_a.id, reference_id=ref.id, idempotency_key="ref-archive-1"
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceArchivedError):
        _archive_reference(
            env,
            project_id=project_a.id,
            reference_id=ref.id,
            idempotency_key="ref-archive-2",
        )
    assert _counts(env.writer) == counts


def test_reference_archive_replay(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-a3")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-a3",
    )
    first = _archive_reference(
        env,
        project_id=project.id,
        reference_id=ref.id,
        idempotency_key="ref-archive-replay",
    )
    counts = _counts(env.writer)
    second = _archive_reference(
        env,
        project_id=project.id,
        reference_id=ref.id,
        idempotency_key="ref-archive-replay",
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(env.writer) == counts
    # A changed request under the same key fails before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _archive_reference(
            env,
            project_id=project.id,
            reference_id=generate_lowercase_ulid(),
            idempotency_key="ref-archive-replay",
        )
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# Reads: list visibility and direct historical lookup
# ---------------------------------------------------------------------------


def test_reference_list_hides_archived_by_default_and_includes_with_flag(
    env,
) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-l1")
    active = _create_reference(
        env,
        project_id=project.id,
        kind="object",
        name="Amulet",
        media_id=media.id,
        idempotency_key="ref-create-l1",
    )
    hidden = _create_reference(
        env,
        project_id=project.id,
        kind="place",
        name="Tower",
        media_id=media.id,
        idempotency_key="ref-create-l2",
    )
    _archive_reference(
        env,
        project_id=project.id,
        reference_id=hidden.id,
        idempotency_key="ref-archive-l1",
    )

    default_rows = env.reference_repo.list(env.writer, project.id)
    assert [row.id for row in default_rows] == [active.id]
    assert default_rows[0].kind == "object"
    assert default_rows[0].archived_at is None

    inclusive = env.reference_repo.list(
        env.writer, project.id, include_archived=True
    )
    assert {row.id for row in inclusive} == {active.id, hidden.id}
    by_id = {row.id: row for row in inclusive}
    assert by_id[hidden.id].archived_at == TS2
    # Deterministic ordering: kind, then name, then id.
    assert [row.id for row in inclusive] == sorted(
        (active.id, hidden.id),
        key=lambda rid: (
            by_id[rid].kind,
            by_id[rid].name,
            by_id[rid].id,
        ),
    )


def test_reference_show_retains_archived_direct_lookup(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-s1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-s1",
    )
    _archive_reference(
        env,
        project_id=project.id,
        reference_id=ref.id,
        idempotency_key="ref-archive-s1",
    )
    # Direct historical lookup still returns the full immutable model,
    # including the preserved primary canonical media association.
    shown = env.reference_repo.show(env.writer, project.id, ref.id)
    assert shown.id == ref.id
    assert shown.archived_at == TS2
    assert shown.event_head_seq == 2
    assert len(shown.media) == 1
    assert shown.media[0].media_id == media.id
    assert shown.media[0].is_primary is True
    # A missing project is a typed project error; an existing project that
    # does not own the reference is a typed not-found error.
    with pytest.raises(ProjectNotFoundError):
        env.reference_repo.show(env.writer, generate_lowercase_ulid(), ref.id)
    other = _create_project(env, slug="gamma")
    with pytest.raises(ReferenceNotFoundError):
        env.reference_repo.show(env.writer, other.id, ref.id)


def test_reference_reads_reject_missing_project(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-r1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-r1",
    )
    missing_project = generate_lowercase_ulid()
    with pytest.raises(ProjectNotFoundError):
        env.reference_repo.show(env.writer, missing_project, ref.id)
    with pytest.raises(ProjectNotFoundError):
        env.reference_repo.list(env.writer, missing_project)


# ---------------------------------------------------------------------------
# Catalog fence
# ---------------------------------------------------------------------------


def test_reference_lifecycle_leaves_catalog_unchanged(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-t1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-t1",
    )
    _archive_reference(
        env,
        project_id=project.id,
        reference_id=ref.id,
        idempotency_key="ref-archive-t1",
    )
    present = env.writer.submit(
        lambda session: {
            row[0]
            for row in session.query(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    )
    # The frozen standard catalog: 14 kernel tables + timelines + shots +
    # shot_items + three reference tables + runaway transitions = 21.
    assert len(present) == 21
    for table in (
        "project_references",
        "media_references",
        "reference_links",
        "timelines",
        "shots",
        "shot_items",
    ):
        assert table in present
    for forbidden in ("plans", "steps", "plan_steps"):
        assert forbidden not in present
