"""Reference media tests: exact association, bulk association, and primary
replacement (m3 plan step 8, T9).

This suite proves the references pack's media-mutation contract over the
frozen three-table schema, on top of the T8 lifecycle vertical:

- ``associate`` / ``associate_many`` insert exact ``media_references`` rows
  for the four frozen roles (``canonical``, ``used_as_input``, ``depicts``,
  ``inspired_by``) with deterministic canonical ordinals (``max + 1``) and
  exactly one primary canonical;
- every reference/media pair must share a project; ``used_as_input`` must
  name a context task; a context task is permitted only for
  ``used_as_input``/``inspired_by``; and every context task must share the
  project and have produced the exact media through ``task_outputs``
  (cross-table provenance rules DDL cannot express — the raw-SQL
  adversarial fixtures below);
- ``set_primary`` replaces the primary canonical in one transaction without
  transiently violating the ``reference_one_primary_canonical`` partial
  unique index, clearing the old primary before setting the new one;
- every command returns its expanded association/media IDs in the event
  changes and the complete receipt, so variants never inherit associations
  invisibly; and replay, mismatch-before-mutation, and representative
  statement-boundary old-or-complete atomicity hold.

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
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import (
    MediaRepository,
    ProjectNotFoundError,
    ProjectRepository,
)
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.references.repository import (
    CONTEXT_REQUIRED_ROLE,
    CONTEXT_ROLES,
    MEDIA_REFERENCE_ROLES,
    PRIMARY_CANONICAL_ROLE,
    REFERENCE_ASSOCIATE_COMMAND_KIND,
    REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND,
    REFERENCE_PRIMARY_CHANGED_EVENT_KIND,
    REFERENCE_SET_PRIMARY_COMMAND_KIND,
    REFERENCE_STREAM_TYPE,
    ReferenceArchivedError,
    ReferenceAssociateReadModel,
    ReferenceAssociationError,
    ReferenceMediaReadModel,
    ReferenceNotFoundError,
    ReferencePrimaryChangeReadModel,
    ReferencePrimaryError,
    ReferenceRepository,
    ReferenceValidationError,
)

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _InjectedCrash(RuntimeError):
    """Sentinel raised at one statement boundary by the crash tests."""


@pytest.fixture
def env(tmp_path: Path, standard_registry):
    """Fresh standard-Astrid writer plus project/media/task/reference repos."""
    writer = DatabaseWriter(tmp_path / "references_media.sqlite3", standard_registry)
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
            task_repo=TaskRepository(events=events, receipts=receipts),
            reference_repo=ReferenceRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


def _fresh_namespace(root: Path, registry):
    """Build a fresh writer + repository namespace rooted at ``root``.

    Used by the crash tests to open several independent scratch databases
    inside one test function (the function-scoped ``env`` fixture only owns
    a single writer).
    """
    writer = DatabaseWriter(root / "scratch.sqlite3", registry)
    events = EventAppendService(registry)
    receipts = ReceiptService()
    return SimpleNamespace(
        writer=writer,
        projects_root=root,
        project_repo=ProjectRepository(events=events, receipts=receipts),
        media_repo=MediaRepository(
            events=events, receipts=receipts, projects_root=root
        ),
        task_repo=TaskRepository(events=events, receipts=receipts),
        reference_repo=ReferenceRepository(events=events, receipts=receipts),
    )


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
    idempotency_key: str = "import-k-1",
):
    media_id = media_id or generate_lowercase_ulid()
    # Media identity is the byte SHA-256 and import is project-scoped
    # byte-deduped, so make each import's bytes unique per media_id unless a
    # caller deliberately reuses bytes (which the import then dedupes).
    data = data + media_id.encode()
    path = _write_png(env, f"media-{generate_lowercase_ulid()}.png", data)
    prepared = prepare_media_file(path)
    args = {
        "project_id": project_id,
        "prepared": prepared,
        "idempotency_key": idempotency_key,
        "media_id": media_id,
        "realm": EXTERNAL_LOCAL_REALM,
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


def _admit_task(
    env,
    *,
    project_id: str,
    task_id: str | None = None,
    capability: str = "generation.generate_image",
):
    task_id = task_id or generate_lowercase_ulid()
    args = {
        "project_id": project_id,
        "capability": capability,
        "spec": {"backend": "deterministic"},
        "input_manifest": [],
        "idempotency_key": f"admit-{task_id}-k",
        "task_id": task_id,
        "max_attempts": 1,
        "created_at": TS,
    }
    return UnitOfWork(env.writer).run(lambda u: env.task_repo.create(u, **args))


def _insert_task_output(env, *, task_id: str, media_id: str) -> None:
    """Raw-SQL fixture: record that ``task_id`` produced ``media_id``.

    ``task_outputs`` is the exact provenance currency the association rule
    reads; completing a task through the full executor journey is out of
    scope for a reference-media test, so the row is seeded directly.
    """
    env.writer.submit(
        lambda session: session.execute(
            "INSERT INTO task_outputs "
            "(task_id, ordinal, role, media_id, is_primary, params_json, created_at) "
            "VALUES (?, 0, 'result', ?, 1, '{}', ?)",
            (task_id, media_id, TS),
        )
    )


def _associate(
    env,
    *,
    project_id: str,
    reference_id: str,
    media_id: str,
    role: str,
    context_task_id: str | None = None,
    ordinal: int | None = None,
    metadata: dict | None = None,
    idempotency_key: str = "associate-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "reference_id": reference_id,
        "media_id": media_id,
        "role": role,
        "context_task_id": context_task_id,
        "ordinal": ordinal,
        "metadata": metadata,
        "idempotency_key": idempotency_key,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.associate(u, **args)
    )


def _associate_many(
    env,
    *,
    project_id: str,
    reference_id: str,
    associations: list,
    idempotency_key: str = "associate-many-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "reference_id": reference_id,
        "associations": associations,
        "idempotency_key": idempotency_key,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.associate_many(u, **args)
    )


def _set_primary(
    env,
    *,
    project_id: str,
    reference_id: str,
    media_reference_id: str,
    idempotency_key: str = "set-primary-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "reference_id": reference_id,
        "media_reference_id": media_reference_id,
        "idempotency_key": idempotency_key,
        "now": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.set_primary(u, **args)
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


def _primary_count(writer: DatabaseWriter, reference_id: str) -> int:
    return int(
        writer.submit(
            lambda session: session.query_one(
                "SELECT count(*) AS n FROM media_references "
                "WHERE reference_id = ? AND role = ? AND is_primary = 1",
                (reference_id, PRIMARY_CANONICAL_ROLE),
            )["n"]
        )
    )


def _primary_state(writer: DatabaseWriter, reference_id: str) -> dict:
    """Structural primary/head/receipt state for crash old-or-complete checks."""
    stream_id = f"{reference_id}:{REFERENCE_STREAM_TYPE}"
    return writer.submit(
        lambda session: {
            "primary_media_ids": sorted(
                row["media_id"]
                for row in session.query(
                    "SELECT media_id FROM media_references "
                    "WHERE reference_id = ? AND role = ? AND is_primary = 1",
                    (reference_id, PRIMARY_CANONICAL_ROLE),
                )
            ),
            "canonical_ordinals": [
                (int(row["ordinal"]), int(row["is_primary"]))
                for row in session.query(
                    "SELECT ordinal, is_primary FROM media_references "
                    "WHERE reference_id = ? AND role = ? ORDER BY ordinal ASC",
                    (reference_id, PRIMARY_CANONICAL_ROLE),
                )
            ],
            "head_seq": int(
                session.query_one(
                    "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
                )["head_seq"]
            ),
            "event_count": int(
                session.query_one(
                    "SELECT count(*) AS n FROM events e "
                    "JOIN event_streams s ON s.id = e.stream_id "
                    "WHERE s.aggregate_id = ?",
                    (reference_id,),
                )["n"]
            ),
            "receipt_count": int(
                session.query_one(
                    "SELECT count(*) AS n FROM command_receipts "
                    "WHERE primary_stream_id = ?",
                    (stream_id,),
                )["n"]
            ),
        }
    )


def _crash_run(writer: DatabaseWriter, *, kind: str | None, sql_sub: str | None, fn):
    """Run ``fn`` inside a UoW that raises :class:`_InjectedCrash` at the
    first boundary matching ``kind`` or ``sql_sub``.

    Returns ``"crashed"`` when the crash fired, else ``"completed"``.
    """
    state = {"crashed": False}

    def observer(k: str, sql: str, params: tuple) -> None:
        if (kind is not None and k == kind) or (sql_sub is not None and sql_sub in sql):
            state["crashed"] = True
            raise _InjectedCrash()

    try:
        UnitOfWork(writer, on_statement=observer).run(fn)
    except _InjectedCrash:
        return "crashed"
    return "completed"


# ---------------------------------------------------------------------------
# associate: exact media association
# ---------------------------------------------------------------------------


def test_associate_depicts_expands_result_and_event(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-d1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key="ref-create-d1",
    )
    counts = _counts(env.writer)
    stream_id = f"{ref.id}:{REFERENCE_STREAM_TYPE}"

    result = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media.id,
        role="depicts",
        ordinal=1,
        metadata={"crop": "face"},
        idempotency_key="associate-d1",
    )
    assert isinstance(result, ReferenceAssociateReadModel)
    assert result.reference_id == ref.id
    assert result.project_id == project.id
    assert result.event_head_seq == 2
    assert len(result.associations) == 1
    entry = result.associations[0]
    assert entry.media_id == media.id
    assert entry.role == "depicts"
    assert entry.context_task_id is None
    assert entry.ordinal == 1
    assert entry.is_primary is False
    assert entry.metadata == {"crop": "face"}
    assert entry.created_at == TS2
    assert ReferenceAssociateReadModel.from_mapping(result.to_dict()) == result

    # Exactly one new association + one event + one receipt; the reference
    # row is refreshed (updated_at) but no new project_references/stream row.
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2],
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )
    # The reference's updated_at advanced to the command stamp.
    ref_row = env.writer.submit(
        lambda s: s.query_one(
            "SELECT updated_at FROM project_references WHERE id = ?", (ref.id,)
        )
    )
    assert ref_row["updated_at"] == TS2

    # The media_associated event carries the expanded association.
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        "reference.created",
        REFERENCE_MEDIA_ASSOCIATED_EVENT_KIND,
    ]
    data = json.loads(events[1]["payload_json"])["data"]
    assert data["reference_id"] == ref.id
    assert data["media"] == [
        {
            "media_reference_id": entry.id,
            "media_id": media.id,
            "role": "depicts",
            "context_task_id": None,
            "ordinal": 1,
            "is_primary": False,
        }
    ]
    assert json.loads(events[1]["changes_json"]) == ["reference_id", "media"]
    # The receipt result enumerates the expanded association/media id.
    receipt = _receipt_row(env.writer, project.id, "associate-d1")
    assert receipt["command_kind"] == REFERENCE_ASSOCIATE_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2
    assert json.loads(receipt["result_json"]) == result.to_dict()
    assert _stream_row(env.writer, stream_id)["head_seq"] == 2
    # Exactly one primary canonical persists after a non-canonical associate.
    assert _primary_count(env.writer, ref.id) == 1


def test_associate_used_as_input_requires_context(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-u1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-u1",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role=CONTEXT_REQUIRED_ROLE,
            idempotency_key="associate-u1",
        )
    assert excinfo.value.detail == "missing_context"
    assert _counts(env.writer) == counts


def test_associate_used_as_input_provenance(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-p1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-p1",
    )
    producer = _admit_task(env, project_id=project.id)
    _insert_task_output(env, task_id=producer.id, media_id=media.id)
    # A second same-project task that never produced this media.
    non_producer = _admit_task(env, project_id=project.id)

    # Success: the producing task yields a valid contextual association.
    counts = _counts(env.writer)
    result = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media.id,
        role=CONTEXT_REQUIRED_ROLE,
        context_task_id=producer.id,
        idempotency_key="associate-p1",
    )
    assert result.associations[0].context_task_id == producer.id
    assert result.associations[0].role == "used_as_input"
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2],
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )

    # A task that did not produce the exact media is rejected pre-write.
    counts = _counts(env.writer)
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role=CONTEXT_REQUIRED_ROLE,
            context_task_id=non_producer.id,
            idempotency_key="associate-p2",
        )
    assert excinfo.value.detail == "task_did_not_produce_media"
    assert _counts(env.writer) == counts

    # A missing context task is rejected before any write.
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role=CONTEXT_REQUIRED_ROLE,
            context_task_id=generate_lowercase_ulid(),
            idempotency_key="associate-p3",
        )
    assert excinfo.value.detail == "missing_task"
    assert _counts(env.writer) == counts


def test_associate_context_task_must_share_project(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media = _import_media(env, project_id=project_a.id, idempotency_key="import-x1")
    ref = _create_reference(
        env,
        project_id=project_a.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-x1",
    )
    foreign_task = _admit_task(env, project_id=project_b.id)
    counts = _counts(env.writer)
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project_a.id,
            reference_id=ref.id,
            media_id=media.id,
            role=CONTEXT_REQUIRED_ROLE,
            context_task_id=foreign_task.id,
            idempotency_key="associate-x1",
        )
    assert excinfo.value.detail == "foreign_task"
    assert _counts(env.writer) == counts


def test_associate_context_role_permissions(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-r1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-r1",
    )
    producer = _admit_task(env, project_id=project.id)
    _insert_task_output(env, task_id=producer.id, media_id=media.id)
    counts = _counts(env.writer)

    # A context task is only permitted on the DDL-approved pair.
    for role in ("canonical", "depicts"):
        with pytest.raises(ReferenceAssociationError) as excinfo:
            _associate(
                env,
                project_id=project.id,
                reference_id=ref.id,
                media_id=media.id,
                role=role,
                context_task_id=producer.id,
                idempotency_key=f"associate-r-{role}",
            )
        assert excinfo.value.detail == "context_not_permitted"
    assert _counts(env.writer) == counts

    # inspired_by may optionally carry a context task.
    result = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media.id,
        role="inspired_by",
        context_task_id=producer.id,
        idempotency_key="associate-r-inspired",
    )
    assert result.associations[0].context_task_id == producer.id
    assert result.associations[0].role == "inspired_by"


def test_associate_rejects_foreign_and_missing_media(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_a = _import_media(env, project_id=project_a.id, idempotency_key="import-f1a")
    media_b = _import_media(env, project_id=project_b.id, idempotency_key="import-f1b")
    ref = _create_reference(
        env,
        project_id=project_a.id,
        name="Ada",
        media_id=media_a.id,
        idempotency_key="ref-create-f1",
    )
    counts = _counts(env.writer)
    # A media row owned by another project is a same-project-pair violation
    # the DDL cannot express — caught by the repository pre-write gate.
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project_a.id,
            reference_id=ref.id,
            media_id=media_b.id,
            role="depicts",
            idempotency_key="associate-f1",
        )
    assert excinfo.value.detail == "foreign_media"
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project_a.id,
            reference_id=ref.id,
            media_id=generate_lowercase_ulid(),
            role="depicts",
            idempotency_key="associate-f2",
        )
    assert excinfo.value.detail == "missing_media"
    assert _counts(env.writer) == counts


def test_associate_rejects_duplicate(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-dup1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-dup1",
    )
    _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media.id,
        role="depicts",
        idempotency_key="associate-dup1",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role="depicts",
            idempotency_key="associate-dup2",
        )
    assert excinfo.value.detail == "duplicate"
    assert _counts(env.writer) == counts


def test_associate_rejects_bad_role_and_ordinal(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-b1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-b1",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role="mood_board",
            idempotency_key="associate-b1",
        )
    assert excinfo.value.detail == "bad_role"
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role="depicts",
            ordinal=-1,
            idempotency_key="associate-b2",
        )
    assert excinfo.value.detail == "bad_ordinal"
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# explicit bulk association
# ---------------------------------------------------------------------------


def test_bulk_associate_deterministic_canonical_ordinals(env) -> None:
    project = _create_project(env)
    primary = _import_media(env, project_id=project.id, idempotency_key="import-m1")
    c1 = _import_media(env, project_id=project.id, idempotency_key="import-m2")
    c2 = _import_media(env, project_id=project.id, idempotency_key="import-m3")
    dep = _import_media(env, project_id=project.id, idempotency_key="import-m4")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=primary.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key="ref-create-m1",
    )
    counts = _counts(env.writer)

    result = _associate_many(
        env,
        project_id=project.id,
        reference_id=ref.id,
        associations=[
            {"media_id": c1.id, "role": "canonical"},
            {"media_id": dep.id, "role": "depicts", "ordinal": 7},
            {"media_id": c2.id, "role": "canonical"},
            {"media_id": dep.id, "role": "inspired_by", "ordinal": 3},
        ],
        idempotency_key="associate-m1",
    )
    assert len(result.associations) == 4
    by_key = {(a.media_id, a.role): a for a in result.associations}
    # Deterministic canonical ordinals: max(canonical ordinal) + 1 each.
    assert by_key[(c1.id, "canonical")].ordinal == 1
    assert by_key[(c2.id, "canonical")].ordinal == 2
    assert by_key[(c1.id, "canonical")].is_primary is False
    assert by_key[(c2.id, "canonical")].is_primary is False
    # Non-canonical ordinals are the caller's normalized values.
    assert by_key[(dep.id, "depicts")].ordinal == 7
    assert by_key[(dep.id, "inspired_by")].ordinal == 3
    # Four associations + one event + one receipt; still exactly one primary.
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 4,
        counts[2],
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )
    assert _primary_count(env.writer, ref.id) == 1

    # The event data enumerates every expanded association/media id.
    stream_id = f"{ref.id}:{REFERENCE_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    data = json.loads(events[-1]["payload_json"])["data"]
    assert len(data["media"]) == 4
    assert {m["media_id"] for m in data["media"]} == {c1.id, c2.id, dep.id}
    assert all("media_reference_id" in m for m in data["media"])
    assert [m["ordinal"] for m in data["media"] if m["role"] == "canonical"] == [1, 2]


def test_bulk_associate_rejects_within_batch_duplicate(env) -> None:
    project = _create_project(env)
    primary = _import_media(env, project_id=project.id, idempotency_key="import-w1")
    c1 = _import_media(env, project_id=project.id, idempotency_key="import-w2")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=primary.id,
        idempotency_key="ref-create-w1",
    )
    counts = _counts(env.writer)
    # The same canonical media twice in one explicit bulk command is a
    # duplicate the DDL unique index would otherwise surface as a raw
    # IntegrityError; the pre-write gate must catch it first.
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate_many(
            env,
            project_id=project.id,
            reference_id=ref.id,
            associations=[
                {"media_id": c1.id, "role": "canonical"},
                {"media_id": c1.id, "role": "canonical"},
            ],
            idempotency_key="associate-w1",
        )
    assert excinfo.value.detail == "duplicate"
    assert _counts(env.writer) == counts


def test_bulk_associate_rejects_cross_project_entry_atomically(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_a = _import_media(env, project_id=project_a.id, idempotency_key="import-a1")
    media_b = _import_media(env, project_id=project_b.id, idempotency_key="import-a2")
    ref = _create_reference(
        env,
        project_id=project_a.id,
        name="Ada",
        media_id=media_a.id,
        idempotency_key="ref-create-a1",
    )
    counts = _counts(env.writer)
    # A mixed bulk command whose second entry is foreign must reject before
    # any write — the first (valid) entry must not materialize.
    with pytest.raises(ReferenceAssociationError) as excinfo:
        _associate_many(
            env,
            project_id=project_a.id,
            reference_id=ref.id,
            associations=[
                {"media_id": media_a.id, "role": "depicts", "ordinal": 1},
                {"media_id": media_b.id, "role": "depicts", "ordinal": 2},
            ],
            idempotency_key="associate-a1",
        )
    assert excinfo.value.detail == "foreign_media"
    assert _counts(env.writer) == counts


def test_associate_many_rejects_empty_and_non_list(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-e1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-e1",
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceValidationError):
        _associate_many(
            env,
            project_id=project.id,
            reference_id=ref.id,
            associations=[],
            idempotency_key="associate-e1",
        )
    with pytest.raises(ReferenceValidationError):
        _associate_many(
            env,
            project_id=project.id,
            reference_id=ref.id,
            associations="not-a-list",
            idempotency_key="associate-e2",
        )
    assert _counts(env.writer) == counts


def test_associate_on_archived_reference_rejected(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-ar1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-ar1",
    )
    UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.archive(
            u,
            project_id=project.id,
            reference_id=ref.id,
            idempotency_key="ref-archive-ar1",
            now=TS2,
        )
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceArchivedError):
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role="depicts",
            idempotency_key="associate-ar1",
        )
    assert _counts(env.writer) == counts


def test_associate_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-rp1")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media.id,
        idempotency_key="ref-create-rp1",
    )
    first = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media.id,
        role="depicts",
        ordinal=2,
        idempotency_key="associate-rp1",
    )
    counts = _counts(env.writer)
    second = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media.id,
        role="depicts",
        ordinal=2,
        idempotency_key="associate-rp1",
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(env.writer) == counts
    with pytest.raises(ReceiptMismatchError):
        _associate(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_id=media.id,
            role="depicts",
            ordinal=3,
            idempotency_key="associate-rp1",
        )
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# set_primary: atomic primary replacement
# ---------------------------------------------------------------------------


def test_set_primary_replaces_primary_collision_safe(env) -> None:
    project = _create_project(env)
    primary = _import_media(env, project_id=project.id, idempotency_key="import-s1")
    alt = _import_media(env, project_id=project.id, idempotency_key="import-s2")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=primary.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key="ref-create-s1",
    )
    assoc = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=alt.id,
        role="canonical",
        idempotency_key="associate-s1",
    )
    alt_assoc = assoc.associations[0]
    assert alt_assoc.ordinal == 1
    assert alt_assoc.is_primary is False

    old_primary_id = _media_reference_rows(env.writer, ref.id)[0]["id"]
    counts = _counts(env.writer)
    stream_id = f"{ref.id}:{REFERENCE_STREAM_TYPE}"

    result = _set_primary(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_reference_id=alt_assoc.id,
        idempotency_key="set-primary-s1",
    )
    assert isinstance(result, ReferencePrimaryChangeReadModel)
    assert result.reference_id == ref.id
    assert result.project_id == project.id
    assert result.previous_primary == {
        "media_reference_id": old_primary_id,
        "media_id": primary.id,
    }
    assert result.new_primary == {
        "media_reference_id": alt_assoc.id,
        "media_id": alt.id,
    }
    assert result.event_head_seq == 3
    assert ReferencePrimaryChangeReadModel.from_mapping(result.to_dict()) == result

    # Two UPDATEs (clear + set) and no new association/stream rows.
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2],
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )
    # Exactly one primary canonical, and it is now the alternate media.
    rows = _media_reference_rows(env.writer, ref.id)
    canonicals = [r for r in rows if r["role"] == "canonical"]
    assert [r["is_primary"] for r in canonicals] == [0, 1]
    assert canonicals[0]["media_id"] == primary.id
    assert canonicals[1]["media_id"] == alt.id

    # The primary_changed event carries previous and new identities.
    events = _event_rows(env.writer, stream_id)
    assert events[-1]["kind"] == REFERENCE_PRIMARY_CHANGED_EVENT_KIND
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data == {
        "reference_id": ref.id,
        "previous_primary": result.previous_primary,
        "new_primary": result.new_primary,
    }
    assert json.loads(events[-1]["changes_json"]) == [
        "reference_id",
        "previous_primary",
        "new_primary",
    ]
    receipt = _receipt_row(env.writer, project.id, "set-primary-s1")
    assert receipt["command_kind"] == REFERENCE_SET_PRIMARY_COMMAND_KIND
    assert json.loads(receipt["result_json"]) == result.to_dict()
    assert _stream_row(env.writer, stream_id)["head_seq"] == 3


def test_set_primary_rejections(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_a = _import_media(env, project_id=project_a.id, idempotency_key="import-t1")
    media_b = _import_media(env, project_id=project_b.id, idempotency_key="import-t2")
    ref_a = _create_reference(
        env,
        project_id=project_a.id,
        name="Ada",
        media_id=media_a.id,
        idempotency_key="ref-create-t1",
    )
    ref_b = _create_reference(
        env,
        project_id=project_b.id,
        name="Byron",
        media_id=media_b.id,
        idempotency_key="ref-create-t2",
    )
    # A non-canonical association can never become primary.
    depicts = _associate(
        env,
        project_id=project_a.id,
        reference_id=ref_a.id,
        media_id=media_a.id,
        role="depicts",
        idempotency_key="associate-t1",
    ).associations[0]
    canonical_b = _media_reference_rows(env.writer, ref_b.id)[0]["id"]
    counts = _counts(env.writer)

    # Missing reference.
    with pytest.raises(ReferenceNotFoundError):
        _set_primary(
            env,
            project_id=project_a.id,
            reference_id=generate_lowercase_ulid(),
            media_reference_id=depicts.id,
            idempotency_key="sp-t1",
        )
    # Foreign reference (owned by another project).
    with pytest.raises(ReferenceNotFoundError):
        _set_primary(
            env,
            project_id=project_a.id,
            reference_id=ref_b.id,
            media_reference_id=canonical_b,
            idempotency_key="sp-t2",
        )
    # Missing association.
    with pytest.raises(ReferencePrimaryError) as excinfo:
        _set_primary(
            env,
            project_id=project_a.id,
            reference_id=ref_a.id,
            media_reference_id=generate_lowercase_ulid(),
            idempotency_key="sp-t3",
        )
    assert excinfo.value.detail == "not_found"
    # Association owned by another reference.
    with pytest.raises(ReferencePrimaryError) as excinfo:
        _set_primary(
            env,
            project_id=project_a.id,
            reference_id=ref_a.id,
            media_reference_id=canonical_b,
            idempotency_key="sp-t4",
        )
    assert excinfo.value.detail == "foreign"
    # Non-canonical association.
    with pytest.raises(ReferencePrimaryError) as excinfo:
        _set_primary(
            env,
            project_id=project_a.id,
            reference_id=ref_a.id,
            media_reference_id=depicts.id,
            idempotency_key="sp-t5",
        )
    assert excinfo.value.detail == "not_canonical"
    assert _counts(env.writer) == counts

    # Archived reference rejects the mutation.
    UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.archive(
            u,
            project_id=project_a.id,
            reference_id=ref_a.id,
            idempotency_key="ref-archive-t1",
            now=TS2,
        )
    )
    counts = _counts(env.writer)
    with pytest.raises(ReferenceArchivedError):
        _set_primary(
            env,
            project_id=project_a.id,
            reference_id=ref_a.id,
            media_reference_id=depicts.id,
            idempotency_key="sp-t6",
        )
    assert _counts(env.writer) == counts


def test_set_primary_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    primary = _import_media(env, project_id=project.id, idempotency_key="import-rp2")
    alt = _import_media(env, project_id=project.id, idempotency_key="import-rp3")
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=primary.id,
        idempotency_key="ref-create-rp2",
    )
    alt_assoc = _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=alt.id,
        role="canonical",
        idempotency_key="associate-rp2",
    ).associations[0]
    first = _set_primary(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_reference_id=alt_assoc.id,
        idempotency_key="sp-rp1",
    )
    counts = _counts(env.writer)
    second = _set_primary(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_reference_id=alt_assoc.id,
        idempotency_key="sp-rp1",
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(env.writer) == counts
    with pytest.raises(ReceiptMismatchError):
        _set_primary(
            env,
            project_id=project.id,
            reference_id=ref.id,
            media_reference_id=generate_lowercase_ulid(),
            idempotency_key="sp-rp1",
        )
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# representative statement-boundary atomicity
# ---------------------------------------------------------------------------


def _seed_set_primary_crash(env):
    """Seed a reference with primary canonical ``media-a`` and a second
    non-primary canonical ``media-b``; return (project, ref_id, alt_assoc_id)."""
    project = _create_project(env, project_id="crash-proj")
    media_a = _import_media(
        env, project_id=project.id, media_id="media-a", idempotency_key="import-ca"
    )
    media_b = _import_media(
        env, project_id=project.id, media_id="media-b", idempotency_key="import-cb"
    )
    ref = _create_reference(
        env,
        project_id=project.id,
        name="Ada",
        media_id=media_a.id,
        reference_id="ref-crash",
        idempotency_key="ref-create-ca",
    )
    _associate(
        env,
        project_id=project.id,
        reference_id=ref.id,
        media_id=media_b.id,
        role="canonical",
        idempotency_key="associate-ca",
    )
    alt_assoc_id = env.writer.submit(
        lambda s: s.query_one(
            "SELECT id FROM media_references "
            "WHERE reference_id = ? AND media_id = ? AND role = ?",
            (ref.id, media_b.id, PRIMARY_CANONICAL_ROLE),
        )["id"]
    )
    return project, ref.id, alt_assoc_id


def test_set_primary_statement_boundary_atomicity(tmp_path, standard_registry) -> None:
    """Representative crash at clear/set/commit leaves old-or-complete state.

    The collision-safe replacement order (clear old primary, then set the new
    one) plus the single ``BEGIN IMMEDIATE`` transaction means a crash at any
    observed boundary reopens to exactly the old state or the complete state —
    never zero primaries, never two primaries, never a half-committed event.
    """
    # Learn the old and complete states from two clean, deterministic runs.
    old_root = tmp_path / "sp-old"
    old_root.mkdir()
    env_old = _fresh_namespace(old_root, standard_registry)
    try:
        _, ref_id, _ = _seed_set_primary_crash(env_old)
        old = _primary_state(env_old.writer, ref_id)
    finally:
        env_old.writer.close()

    complete_root = tmp_path / "sp-complete"
    complete_root.mkdir()
    env_comp = _fresh_namespace(complete_root, standard_registry)
    try:
        _, ref_id, alt_assoc_id = _seed_set_primary_crash(env_comp)
        UnitOfWork(env_comp.writer).run(
            lambda u: env_comp.reference_repo.set_primary(
                u,
                project_id="crash-proj",
                reference_id=ref_id,
                media_reference_id=alt_assoc_id,
                idempotency_key="sp-complete-k",
                now=TS2,
            )
        )
        complete = _primary_state(env_comp.writer, ref_id)
    finally:
        env_comp.writer.close()

    assert old != complete
    assert old["primary_media_ids"] == ["media-a"]
    assert complete["primary_media_ids"] == ["media-b"]
    assert [o for (_, o) in old["canonical_ordinals"]] == [1, 0]
    assert [o for (_, o) in complete["canonical_ordinals"]] == [0, 1]

    for label, crash in (
        ("clear-old-primary", {"sql_sub": "SET is_primary = 0"}),
        ("set-new-primary", {"sql_sub": "SET is_primary = 1"}),
        ("commit", {"kind": "commit"}),
    ):
        root = tmp_path / f"sp-crash-{label}"
        root.mkdir()
        env2 = _fresh_namespace(root, standard_registry)
        try:
            _, ref_id, alt_assoc_id = _seed_set_primary_crash(env2)
            outcome = _crash_run(
                env2.writer,
                kind=crash.get("kind"),
                sql_sub=crash.get("sql_sub"),
                fn=lambda u: env2.reference_repo.set_primary(
                    u,
                    project_id="crash-proj",
                    reference_id=ref_id,
                    media_reference_id=alt_assoc_id,
                    idempotency_key=f"sp-crash-{label}-k",
                    now=TS2,
                ),
            )
            assert outcome == "crashed"
            state = _primary_state(env2.writer, ref_id)
            assert state in (old, complete), f"{label}: {state}"
            # Exactly one primary canonical at every observable boundary.
            assert len(state["primary_media_ids"]) == 1
        finally:
            env2.writer.close()


def test_associate_statement_boundary_atomicity(tmp_path, standard_registry) -> None:
    """Representative crash mid-bulk-associate leaves the old (zero-row) state."""
    root = tmp_path / "assoc-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, standard_registry)
    try:
        project = _create_project(env2, project_id="crash-proj")
        media_a = _import_media(
            env2, project_id=project.id, media_id="media-a", idempotency_key="import-aa"
        )
        media_c = _import_media(
            env2, project_id=project.id, media_id="media-c", idempotency_key="import-ac"
        )
        ref = _create_reference(
            env2,
            project_id=project.id,
            name="Ada",
            media_id=media_a.id,
            reference_id="ref-crash",
            idempotency_key="ref-create-aa",
        )
        counts_before = _counts(env2.writer)

        # Crash after the first media_references INSERT; the whole explicit
        # bulk command must roll back (no partial association set).
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO media_references",
            fn=lambda u: env2.reference_repo.associate_many(
                u,
                project_id=project.id,
                reference_id=ref.id,
                associations=[
                    {"media_id": media_c.id, "role": "depicts", "ordinal": 1},
                    {"media_id": media_c.id, "role": "inspired_by", "ordinal": 2},
                ],
                idempotency_key="assoc-crash-k",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before
        # Only the single created canonical association remains.
        rows = _media_reference_rows(env2.writer, ref.id)
        assert len(rows) == 1
        assert rows[0]["role"] == "canonical"
    finally:
        env2.writer.close()
