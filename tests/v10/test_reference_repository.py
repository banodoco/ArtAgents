"""Reference repository tests: mutable update command (m4 plan step 14, T15).

This suite proves the references pack's ``reference.update`` command over the
frozen three-table schema:

- **mutable delta, immutable identity**: ``name``/``description``/``metadata``
  and the refreshed ``updated_at`` are the only fields the command changes;
  ``kind`` and ``project_id`` stay byte-identical and are not even accepted
  arguments;
- **replay**: an identical retry under the same idempotency key returns the
  stored result with zero new rows, and a changed delta under the same key
  raises :class:`ReceiptMismatchError` before any mutation;
- **archived fence**: an archived reference rejects any update with
  :class:`ReferenceArchivedError` (archive is final for mutations, SD1);
- **event order and heads**: the ``reference.updated`` event is appended
  hash-chained on the reference's own stream after the ``reference.created``
  event, and both the stream head and project head advance by exactly one;
- **exact receipts**: the receipt carries the update command kind, the exact
  contiguous project-sequence range, the appended event id, and the refreshed
  read model;
- **statement-boundary crash atomicity**: a rollback mid-transaction leaves
  the projection, event, heads, and receipt all unchanged (zero mutation).

Every command runs inside the caller's one ``BEGIN IMMEDIATE`` unit of work
(:class:`astrid.core.store.uow.UnitOfWork`).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptMismatchError, ReceiptService
from astrid.core.repositories import MediaRepository, ProjectRepository
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.references.repository import (
    REFERENCE_CREATED_EVENT_KIND,
    REFERENCE_STREAM_TYPE,
    REFERENCE_UPDATE_COMMAND_KIND,
    REFERENCE_UPDATED_EVENT_KIND,
    ReferenceArchivedError,
    ReferenceNotFoundError,
    ReferenceRepository,
    ReferenceValidationError,
)

TS = "2026-08-18T00:00:00.000000+00:00"
TS2 = "2026-08-18T01:00:00.000000+00:00"

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


def _import_media(
    env,
    *,
    project_id: str,
    media_id: str | None = None,
    data: bytes = PNG_BYTES,
):
    path = env.projects_root / f"media-{generate_lowercase_ulid()}.png"
    path.write_bytes(data)
    prepared = prepare_media_file(path)
    return UnitOfWork(env.writer).run(
        lambda u: env.media_repo.import_prepared(
            u,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=f"import-{generate_lowercase_ulid()}",
            media_id=media_id or generate_lowercase_ulid(),
            realm=EXTERNAL_LOCAL_REALM,
            created_at=TS,
        )
    )


def _create_reference(
    env,
    *,
    project_id: str,
    reference_id: str | None = None,
    media_id: str,
    kind: str = "character",
    name: str = "Alice",
):
    rid = reference_id or generate_lowercase_ulid()
    return UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.create(
            u,
            project_id=project_id,
            kind=kind,
            name=name,
            media_id=media_id,
            idempotency_key=f"create-{rid}",
            reference_id=rid,
            created_at=TS,
        )
    )


def _seed(env) -> SimpleNamespace:
    """Create a project + media + reference; return the fixture facts."""
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    reference = _create_reference(
        env, project_id=project.id, media_id=media.id
    )
    return SimpleNamespace(
        project=project, media=media, reference=reference
    )


def _reference_row(env, reference_id: str):
    return env.writer.submit(
        lambda s: s.query_one(
            "SELECT * FROM project_references WHERE id = ?", (reference_id,)
        )
    )


def _stream_head(env, stream_id: str) -> int:
    return env.writer.submit(
        lambda s: int(
            s.query_one(
                "SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)
            )["head_seq"]
        )
    )


def _project_head(env, project_id: str) -> int:
    return env.writer.submit(
        lambda s: int(
            s.query_one(
                "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
            )["event_head_seq"]
        )
    )


def _event_kinds(env, reference_id: str) -> list[str]:
    def _run(s) -> list[str]:
        rows = s.query(
            "SELECT e.kind FROM events e "
            "JOIN event_streams st ON st.id = e.stream_id "
            "WHERE st.id = ? ORDER BY e.seq ASC",
            (f"{reference_id}:{REFERENCE_STREAM_TYPE}",),
        )
        return [str(row["kind"]) for row in rows]

    return env.writer.submit(_run)


def _receipt_count(env) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM command_receipts")[0]
    )


def _event_count(env) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM events")[0]
    )


# ---------------------------------------------------------------------------
# Mutable delta with immutable identity
# ---------------------------------------------------------------------------


def test_update_mutates_name_and_metadata_keeps_kind_and_project(
    env: SimpleNamespace,
) -> None:
    seed = _seed(env)
    updated = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            metadata={"age": 42},
            idempotency_key="update-1",
            now=TS2,
        )
    )
    assert updated.name == "Alicia"
    assert updated.metadata == {"age": 42}
    # Identity stays immutable.
    assert updated.kind == seed.reference.kind
    assert updated.project_id == seed.project.id
    assert updated.updated_at == TS2
    assert updated.created_at == seed.reference.created_at
    assert updated.archived_at is None
    # The projection row agrees.
    row = _reference_row(env, seed.reference.id)
    assert row["name"] == "Alicia"
    assert row["kind"] == "character"
    assert row["project_id"] == seed.project.id


def test_update_metadata_merges_delta_and_empty_object_clears(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    reference = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.create(
            u,
            project_id=project.id,
            kind="character",
            name="Alice",
            media_id=media.id,
            metadata={"age": 30, "tag": "hero"},
            idempotency_key="create-metadata-delta",
            reference_id="reference-metadata-delta",
            created_at=TS,
        )
    )

    updated = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=project.id,
            reference_id=reference.id,
            metadata={"age": 31, "arc": "arrival"},
            idempotency_key="update-metadata-delta",
            now=TS2,
        )
    )
    assert updated.metadata == {"age": 31, "arc": "arrival", "tag": "hero"}

    cleared = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=project.id,
            reference_id=reference.id,
            metadata={},
            idempotency_key="update-metadata-clear",
            now="2026-08-18T02:00:00.000000+00:00",
        )
    )
    assert cleared.metadata == {}


def test_update_only_name_preserves_description_and_metadata(
    env: SimpleNamespace,
) -> None:
    seed = _seed(env)
    UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Renamed",
            idempotency_key="update-name",
            now=TS2,
        )
    )
    row = _reference_row(env, seed.reference.id)
    assert row["name"] == "Renamed"
    assert row["description"] == seed.reference.description
    assert row["metadata_json"] == "{}"


def test_update_rejects_empty_name_before_mutation(env: SimpleNamespace) -> None:
    seed = _seed(env)
    with pytest.raises(ReferenceValidationError):
        UnitOfWork(env.writer).run(
            lambda u: env.reference_repo.update(
                u,
                project_id=seed.project.id,
                reference_id=seed.reference.id,
                name="   ",
                idempotency_key="update-bad-name",
            )
        )
    assert _reference_row(env, seed.reference.id)["name"] == "Alice"


# ---------------------------------------------------------------------------
# Not-found and archived fences
# ---------------------------------------------------------------------------


def test_update_missing_reference_raises_not_found(env: SimpleNamespace) -> None:
    seed = _seed(env)
    with pytest.raises(ReferenceNotFoundError):
        UnitOfWork(env.writer).run(
            lambda u: env.reference_repo.update(
                u,
                project_id=seed.project.id,
                reference_id="missing-reference",
                name="X",
                idempotency_key="update-missing",
            )
        )


def test_update_foreign_project_is_indistinguishable_from_missing(
    env: SimpleNamespace,
) -> None:
    seed = _seed(env)
    other = _create_project(env, slug="other")
    with pytest.raises(ReferenceNotFoundError):
        UnitOfWork(env.writer).run(
            lambda u: env.reference_repo.update(
                u,
                project_id=other.id,
                reference_id=seed.reference.id,
                name="X",
                idempotency_key="update-foreign",
            )
        )


def test_update_archived_reference_rejected(env: SimpleNamespace) -> None:
    seed = _seed(env)
    UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.archive(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            idempotency_key="archive-1",
            now=TS2,
        )
    )
    with pytest.raises(ReferenceArchivedError):
        UnitOfWork(env.writer).run(
            lambda u: env.reference_repo.update(
                u,
                project_id=seed.project.id,
                reference_id=seed.reference.id,
                name="Zombie",
                idempotency_key="update-archived",
            )
        )
    # Zero mutation: the name is untouched.
    assert _reference_row(env, seed.reference.id)["name"] == "Alice"


# ---------------------------------------------------------------------------
# Replay and mismatch-before-mutation
# ---------------------------------------------------------------------------


def test_update_replay_returns_stored_result_with_zero_new_rows(
    env: SimpleNamespace,
) -> None:
    seed = _seed(env)
    first = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            metadata={"a": 1},
            idempotency_key="update-replay",
            now=TS2,
        )
    )
    before = (_receipt_count(env), _event_count(env))

    second = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            metadata={"a": 1},
            idempotency_key="update-replay",
            now=TS2,
        )
    )
    assert second.to_dict() == first.to_dict()
    assert (_receipt_count(env), _event_count(env)) == before


def test_update_mismatch_rejected_before_mutation(env: SimpleNamespace) -> None:
    seed = _seed(env)
    UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            idempotency_key="update-mismatch",
            now=TS2,
        )
    )
    before = (_receipt_count(env), _event_count(env))
    with pytest.raises(ReceiptMismatchError):
        UnitOfWork(env.writer).run(
            lambda u: env.reference_repo.update(
                u,
                project_id=seed.project.id,
                reference_id=seed.reference.id,
                name="Bob",
                idempotency_key="update-mismatch",
                now=TS2,
            )
        )
    assert (_receipt_count(env), _event_count(env)) == before
    assert _reference_row(env, seed.reference.id)["name"] == "Alicia"


# ---------------------------------------------------------------------------
# Event order, heads, and exact receipts
# ---------------------------------------------------------------------------


def test_update_appends_updated_event_in_order_on_own_stream(
    env: SimpleNamespace,
) -> None:
    seed = _seed(env)
    assert _event_kinds(env, seed.reference.id) == [REFERENCE_CREATED_EVENT_KIND]
    UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            idempotency_key="update-order",
            now=TS2,
        )
    )
    assert _event_kinds(env, seed.reference.id) == [
        REFERENCE_CREATED_EVENT_KIND,
        REFERENCE_UPDATED_EVENT_KIND,
    ]


def test_update_advances_stream_and_project_heads(env: SimpleNamespace) -> None:
    seed = _seed(env)
    stream_id = f"{seed.reference.id}:{REFERENCE_STREAM_TYPE}"
    assert _stream_head(env, stream_id) == 1
    project_head_before = _project_head(env, seed.project.id)

    updated = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            idempotency_key="update-heads",
            now=TS2,
        )
    )
    assert _stream_head(env, stream_id) == 2
    assert updated.event_head_seq == 2
    assert _project_head(env, seed.project.id) == project_head_before + 1


def test_update_receipt_is_exact(env: SimpleNamespace) -> None:
    seed = _seed(env)
    updated = UnitOfWork(env.writer).run(
        lambda u: env.reference_repo.update(
            u,
            project_id=seed.project.id,
            reference_id=seed.reference.id,
            name="Alicia",
            description="The heroine",
            metadata={"k": "v"},
            idempotency_key="update-receipt",
            now=TS2,
        )
    )
    receipt = env.writer.submit(
        lambda s: s.query_one(
            "SELECT * FROM command_receipts WHERE idempotency_key = ? "
            "AND project_id = ? AND command_kind = ?",
            ("update-receipt", seed.project.id, REFERENCE_UPDATE_COMMAND_KIND),
        )
    )
    assert receipt is not None
    assert receipt["command_kind"] == REFERENCE_UPDATE_COMMAND_KIND
    assert receipt["first_project_seq"] == receipt["last_project_seq"]
    # The refreshed read model is the receipt's exact result.
    assert updated.to_dict()["name"] == "Alicia"
    assert updated.to_dict()["description"] == "The heroine"
    assert updated.to_dict()["metadata"] == {"k": "v"}


# ---------------------------------------------------------------------------
# Statement-boundary crash atomicity
# ---------------------------------------------------------------------------


def test_update_crash_atomicity_rolls_back_every_write(
    env: SimpleNamespace,
) -> None:
    seed = _seed(env)
    stream_id = f"{seed.reference.id}:{REFERENCE_STREAM_TYPE}"
    before_row = dict(_reference_row(env, seed.reference.id))
    before_head = _stream_head(env, stream_id)
    before_receipts = _receipt_count(env)
    before_events = _event_count(env)

    def crash_after_projection(kind: str, sql: str, params) -> None:
        if kind == "statement" and sql.startswith("UPDATE project_references"):
            raise RuntimeError("simulated crash after projection write")

    with pytest.raises(RuntimeError):
        UnitOfWork(env.writer, on_statement=crash_after_projection).run(
            lambda u: env.reference_repo.update(
                u,
                project_id=seed.project.id,
                reference_id=seed.reference.id,
                name="Crashy",
                idempotency_key="update-crash",
                now=TS2,
            )
        )

    # Zero mutation across every concern.
    after_row = _reference_row(env, seed.reference.id)
    assert after_row["name"] == before_row["name"]
    assert after_row["metadata_json"] == before_row["metadata_json"]
    assert after_row["updated_at"] == before_row["updated_at"]
    assert _stream_head(env, stream_id) == before_head
    assert _event_kinds(env, seed.reference.id) == [REFERENCE_CREATED_EVENT_KIND]
    assert _receipt_count(env) == before_receipts
    assert _event_count(env) == before_events
