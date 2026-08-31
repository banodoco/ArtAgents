"""Generation repository tests: receipt-free commands over the pack v2
tables (27-build-spec section 2.3).

This suite proves the shots-pack ``GenerationRepository`` over the v2
``generations``/``generation_variants`` schema:

- ``record_completion`` creates one generation plus exactly one original
  primary variant inside the caller's unit of work, with same-project
  media agreement and succeeded-task lineage enforced before any write;
- star/unstar, set-primary, viewed, and soft-delete are small
  writer-serialized, receipt-free, event-free commands (the heartbeat
  precedent) whose DDL invariants — the ``generation_one_primary``
  partial unique index, ``UNIQUE (generation_id, media_id)`` membership,
  and ``media_id ... ON DELETE RESTRICT`` — hold under direct probes;
- reads are transaction-free on a separate read-only connection, ordered
  primary-first, and hide soft-deleted generations by default while
  preserving their rows and variants.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import (
    MediaRepository,
    ProjectNotFoundError,
    ProjectRepository,
    TaskRepository,
)
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.shots.generation_repository import (
    GenerationAlreadyExistsError,
    GenerationDeletedError,
    GenerationMediaError,
    GenerationNotFoundError,
    GenerationPrimaryError,
    GenerationRepository,
    GenerationValidationError,
    VariantNotFoundError,
)

TS = "2026-08-22T00:00:00.000000+00:00"
TS2 = "2026-08-22T01:00:00.000000+00:00"
TS3 = "2026-08-22T02:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

SPEC = {"prompt": "a lighthouse at dusk", "seed": 7}


@pytest.fixture
def env(tmp_path: Path, standard_registry):
    """Fresh standard-Astrid writer plus project/media/task/generation repos."""
    writer = DatabaseWriter(tmp_path / "generations.sqlite3", standard_registry)
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
            generations=GenerationRepository(),
        )
    finally:
        writer.close()


def _create_project(env, *, slug: str = "pilot"):
    return UnitOfWork(env.writer).run(
        lambda u: env.project_repo.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={"fps": 24},
            idempotency_key=f"create-{slug}-k",
            created_at=TS,
        )
    )


_MEDIA_SALT = iter(range(10000))


def _import_media(env, *, project_id: str, data: bytes | None = None):
    payload = data if data is not None else PNG_BYTES + next(_MEDIA_SALT).to_bytes(2, "big")
    path = env.projects_root / f"media-{generate_lowercase_ulid()}.png"
    path.write_bytes(payload)
    prepared = prepare_media_file(path)
    return UnitOfWork(env.writer).run(
        lambda u: env.media_repo.import_prepared(
            u,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=f"import-{generate_lowercase_ulid()}",
            realm=EXTERNAL_LOCAL_REALM,
            created_at=TS,
        )
    )


def _seed_succeeded_task(env, *, project_id: str, task_id: str | None = None):
    """Admit one kernel task then flip it to terminal-with-winner in place."""
    task_id = task_id or generate_lowercase_ulid()
    task = UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u,
            project_id=project_id,
            capability="generation.generate_video",
            spec=dict(SPEC),
            input_manifest=[],
            idempotency_key=f"admit-{task_id}",
            task_id=task_id,
            created_at=TS,
        )
    )

    def _bump(u: UnitOfWork) -> None:
        u.execute(
            "UPDATE tasks SET status = 'succeeded', winning_attempt_id = ?, "
            "updated_at = ? WHERE id = ?",
            (f"{task_id}:attempt-1", TS2, task_id),
        )

    UnitOfWork(env.writer).run(_bump)
    assert task.id == task_id
    return task_id


def _record(
    env,
    *,
    project_id: str,
    task_id: str,
    media_id: str,
    type: str = "image",
    generation_id: str | None = None,
    variant: dict | None = None,
    params: dict | None = None,
    created_at: str = TS2,
):
    args = {
        "project_id": project_id,
        "task_id": task_id,
        "type": type,
        "params": params,
        "variant": variant or {"media_id": media_id},
        "generation_id": generation_id,
        "created_at": created_at,
    }
    return UnitOfWork(env.writer).run(
        lambda u: env.generations.record_completion(u, **args)
    )


def _add_variant_row(
    env,
    *,
    generation_id: str,
    media_id: str,
    is_primary: int,
    created_at: str = TS3,
) -> str:
    """Insert one variant row directly (a DDL-level membership probe)."""
    variant_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: u.execute(
            "INSERT INTO generation_variants "
            "(id, generation_id, media_id, variant_type, params_json, "
            "is_primary, starred, created_at) "
            "VALUES (?, ?, ?, 'upscale', '{}', ?, 0, ?)",
            (variant_id, generation_id, media_id, is_primary, created_at),
        )
    )
    return variant_id


def _event_and_receipt_counts(
    writer: DatabaseWriter, project_id: str
) -> tuple[int, int]:
    def _counts(session) -> tuple[int, int]:
        events = session.query_one(
            "SELECT COUNT(*) FROM events WHERE project_id = ?", (project_id,)
        )[0]
        receipts = session.query_one(
            "SELECT COUNT(*) FROM command_receipts WHERE project_id = ?",
            (project_id,),
        )[0]
        return int(events), int(receipts)

    return writer.submit(_counts)


# ---------------------------------------------------------------------------
# record_completion
# ---------------------------------------------------------------------------


def test_record_completion_creates_generation_with_one_original_primary(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    before = _event_and_receipt_counts(env.writer, project.id)

    model = _record(env, project_id=project.id, task_id=task_id, media_id=media.id)
    assert _event_and_receipt_counts(env.writer, project.id) == before

    assert model.project_id == project.id
    assert model.task_id == task_id
    assert model.type == "image"
    assert model.starred is False
    assert model.deleted_at is None
    assert len(model.variants) == 1
    variant = model.variants[0]
    assert variant.media_id == media.id
    assert variant.variant_type == "original"
    assert variant.is_primary is True
    assert variant.viewed_at is None

    # The committed state is visible through the transaction-free read.
    shown = env.generations.show(env.writer, project.id, model.id)
    assert shown.to_dict() == model.to_dict()

    # No event stream, event, or receipt exists for generations.
    def _stream_count(session):
        return int(
            session.query_one(
                "SELECT COUNT(*) FROM event_streams WHERE aggregate_id = ?",
                (model.id,),
            )[0]
        )

    assert env.writer.submit(_stream_count) == 0


def test_record_completion_accepts_all_distinct_variants_in_stable_order(env) -> None:
    project = _create_project(env)
    primary = _import_media(env, project_id=project.id)
    alternate = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)

    model = UnitOfWork(env.writer).run(
        lambda u: env.generations.record_completion(
            u,
            project_id=project.id,
            task_id=task_id,
            type="image",
            variants=[
                {"media_id": primary.id, "is_primary": True},
                {
                    "media_id": alternate.id,
                    "is_primary": False,
                    "variant_type": "upscale",
                    "name": "2x",
                    "params": {"scale": 2},
                },
            ],
            created_at=TS2,
        )
    )
    assert [(v.media_id, v.is_primary) for v in model.variants] == [
        (primary.id, True),
        (alternate.id, False),
    ]
    assert model.variants[0].variant_type == "original"
    assert model.variants[1].variant_type == "upscale"
    assert model.variants[1].name == "2x"
    assert model.variants[1].params == {"scale": 2}


def test_record_completion_rejects_foreign_variant_before_any_generation_write(env) -> None:
    project = _create_project(env)
    other_project = _create_project(env, slug="foreign-variants")
    primary = _import_media(env, project_id=project.id)
    foreign = _import_media(env, project_id=other_project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)

    before = env.writer.submit(
        lambda conn: conn.execute(
            "SELECT COUNT(*) FROM generations WHERE project_id = ?", (project.id,)
        ).fetchone()[0]
    )
    with pytest.raises(GenerationMediaError) as foreign_exc:
        UnitOfWork(env.writer).run(
            lambda u: env.generations.record_completion(
                u,
                project_id=project.id,
                task_id=task_id,
                type="image",
                variants=[
                    {"media_id": primary.id, "is_primary": True},
                    {"media_id": foreign.id, "is_primary": False},
                ],
            )
        )
    assert foreign_exc.value.detail == "foreign"
    after = env.writer.submit(
        lambda conn: conn.execute(
            "SELECT COUNT(*) FROM generations WHERE project_id = ?", (project.id,)
        ).fetchone()[0]
    )
    assert after == before == 0


def test_record_completion_rejections_change_zero_rows(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    other_project = _create_project(env, slug="other")
    foreign_media = _import_media(env, project_id=other_project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    queued_task_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.task_repo.create(
            u,
            project_id=project.id,
            capability="generation.generate_video",
            spec=dict(SPEC),
            input_manifest=[],
            idempotency_key=f"admit-{queued_task_id}",
            task_id=queued_task_id,
            created_at=TS,
        )
    )

    with pytest.raises(ProjectNotFoundError):
        _record(env, project_id="missing-project", task_id=task_id, media_id=media.id)
    with pytest.raises(GenerationValidationError):
        _record(env, project_id=project.id, task_id=queued_task_id, media_id=media.id)
    with pytest.raises(GenerationValidationError):
        _record(
            env,
            project_id=project.id,
            task_id=task_id,
            media_id=media.id,
            type="collage",
        )
    with pytest.raises(GenerationMediaError) as missing:
        _record(
            env,
            project_id=project.id,
            task_id=task_id,
            media_id=generate_lowercase_ulid(),
        )
    assert missing.value.detail == "missing"
    with pytest.raises(GenerationMediaError) as foreign:
        _record(
            env,
            project_id=project.id,
            task_id=task_id,
            media_id=foreign_media.id,
        )
    assert foreign.value.detail == "foreign"

    duplicate = generate_lowercase_ulid()
    _record(
        env,
        project_id=project.id,
        task_id=task_id,
        media_id=media.id,
        generation_id=duplicate,
    )
    second_media = _import_media(env, project_id=project.id)
    with pytest.raises(GenerationAlreadyExistsError):
        _record(
            env,
            project_id=project.id,
            task_id=task_id,
            media_id=second_media.id,
            generation_id=duplicate,
        )


# ---------------------------------------------------------------------------
# Star / primary / viewed / soft-delete
# ---------------------------------------------------------------------------


def test_set_starred_is_an_exact_toggle(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=media.id)

    starred = UnitOfWork(env.writer).run(
        lambda u: env.generations.set_starred(
            u,
            project_id=project.id,
            generation_id=model.id,
            starred=True,
            updated_at=TS3,
        )
    )
    assert starred.starred is True and starred.updated_at == TS3

    # Same-state request: zero rows change, updated_at keeps TS3.
    repeat = UnitOfWork(env.writer).run(
        lambda u: env.generations.set_starred(
            u,
            project_id=project.id,
            generation_id=model.id,
            starred=True,
            updated_at=TS2,
        )
    )
    assert repeat.starred is True and repeat.updated_at == TS3


def test_set_primary_demotes_and_promotes_atomically(env) -> None:
    project = _create_project(env)
    first = _import_media(env, project_id=project.id)
    second = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=first.id)

    sibling_id = _add_variant_row(
        env, generation_id=model.id, media_id=second.id, is_primary=0
    )

    change = UnitOfWork(env.writer).run(
        lambda u: env.generations.set_primary(
            u,
            project_id=project.id,
            generation_id=model.id,
            variant_id=sibling_id,
            updated_at=TS3,
        )
    )
    assert change.previous_variant_id == model.variants[0].id
    assert change.variant_id == sibling_id

    shown = env.generations.show(env.writer, project.id, model.id)
    assert [v.id for v in shown.variants] == [sibling_id, model.variants[0].id]
    assert shown.variants[0].is_primary and not shown.variants[1].is_primary
    assert shown.updated_at == TS3

    with pytest.raises(GenerationPrimaryError) as already:
        UnitOfWork(env.writer).run(
            lambda u: env.generations.set_primary(
                u,
                project_id=project.id,
                generation_id=model.id,
                variant_id=sibling_id,
            )
        )
    assert already.value.detail == "already_primary"
    with pytest.raises(VariantNotFoundError):
        UnitOfWork(env.writer).run(
            lambda u: env.generations.set_primary(
                u,
                project_id=project.id,
                generation_id=model.id,
                variant_id=generate_lowercase_ulid(),
            )
        )


def test_mark_viewed_stamps_the_variant(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=media.id)

    viewed = UnitOfWork(env.writer).run(
        lambda u: env.generations.mark_viewed(
            u,
            project_id=project.id,
            generation_id=model.id,
            variant_id=model.variants[0].id,
            viewed_at=TS3,
        )
    )
    assert viewed.viewed_at == TS3


def test_delete_is_soft_idempotent_and_hides_from_default_reads(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=media.id)

    deleted = UnitOfWork(env.writer).run(
        lambda u: env.generations.delete(
            u,
            project_id=project.id,
            generation_id=model.id,
            deleted_at=TS3,
        )
    )
    assert deleted.deleted_at == TS3

    # Idempotent replay changes nothing.
    again = UnitOfWork(env.writer).run(
        lambda u: env.generations.delete(
            u,
            project_id=project.id,
            generation_id=model.id,
            deleted_at=TS2,
        )
    )
    assert again.deleted_at == TS3

    with pytest.raises(GenerationDeletedError):
        env.generations.show(env.writer, project.id, model.id)
    shown = env.generations.show(
        env.writer, project.id, model.id, include_deleted=True
    )
    assert len(shown.variants) == 1
    assert shown.variants[0].is_primary

    listing = env.generations.list(env.writer, project.id)
    assert listing == []
    kept = env.generations.list(env.writer, project.id, include_deleted=True)
    assert [row.id for row in kept] == [model.id]

    with pytest.raises(GenerationDeletedError):
        UnitOfWork(env.writer).run(
            lambda u: env.generations.set_starred(
                u,
                project_id=project.id,
                generation_id=model.id,
                starred=True,
            )
        )
    with pytest.raises(GenerationNotFoundError):
        UnitOfWork(env.writer).run(
            lambda u: env.generations.delete(
                u,
                project_id=project.id,
                generation_id=generate_lowercase_ulid(),
            )
        )


# ---------------------------------------------------------------------------
# DDL invariants: one-primary, unique membership, media RESTRICT
# ---------------------------------------------------------------------------


def test_one_primary_partial_index_rejects_a_second_primary(env) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project_id=project.id)
    media_b = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=media_a.id)

    with pytest.raises(sqlite3.IntegrityError):
        _add_variant_row(
            env, generation_id=model.id, media_id=media_b.id, is_primary=1
        )


def test_unique_membership_rejects_duplicate_media_per_generation(env) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project_id=project.id)
    media_b = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=media_a.id)

    with pytest.raises(sqlite3.IntegrityError):
        _add_variant_row(
            env, generation_id=model.id, media_id=media_a.id, is_primary=0
        )

    # The same media may join a *different* generation of the same project.
    other = _record(
        env,
        project_id=project.id,
        task_id=task_id,
        media_id=media_b.id,
        generation_id=generate_lowercase_ulid(),
    )
    _add_variant_row(env, generation_id=other.id, media_id=media_a.id, is_primary=0)


def test_variant_pins_media_through_on_delete_restrict(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    model = _record(env, project_id=project.id, task_id=task_id, media_id=media.id)

    def _delete_media(u: UnitOfWork) -> None:
        u.execute("DELETE FROM media WHERE id = ?", (media.id,))

    with pytest.raises(sqlite3.IntegrityError):
        UnitOfWork(env.writer).run(_delete_media)

    # Deleting the generation cascades its variants but never the media row.
    def _delete_generation(u: UnitOfWork) -> None:
        u.execute("DELETE FROM generations WHERE id = ?", (model.id,))

    UnitOfWork(env.writer).run(_delete_generation)
    still_there = env.writer.submit(
        lambda session: session.query_one(
            "SELECT id FROM media WHERE id = ?", (media.id,)
        )
    )
    assert still_there is not None


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_list_orders_desc_and_carries_primary_summary(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id)
    task_id = _seed_succeeded_task(env, project_id=project.id)
    first = _record(
        env,
        project_id=project.id,
        task_id=task_id,
        media_id=media.id,
        generation_id=generate_lowercase_ulid(),
        params={"n": 1},
    )
    second_media = _import_media(env, project_id=project.id)
    second = _record(
        env,
        project_id=project.id,
        task_id=task_id,
        media_id=second_media.id,
        generation_id=generate_lowercase_ulid(),
        params={"n": 2},
        created_at=TS3,
    )
    UnitOfWork(env.writer).run(
        lambda u: env.generations.set_starred(
            u,
            project_id=project.id,
            generation_id=first.id,
            starred=True,
        )
    )

    listing = env.generations.list(env.writer, project.id)
    assert [row.id for row in listing] == [second.id, first.id]
    assert listing[0].primary_media_id == second_media.id
    assert all(row.variant_count == 1 for row in listing)
    assert listing[1].starred is True

    star_only = env.generations.list(env.writer, project.id, starred_only=True)
    assert [row.id for row in star_only] == [first.id]

    typed = env.generations.list(env.writer, project.id, type="video")
    assert typed == []

    bounded = env.generations.list(env.writer, project.id, limit=1)
    assert [row.id for row in bounded] == [second.id]

    with pytest.raises(ProjectNotFoundError):
        env.generations.list(env.writer, "missing-project")
    with pytest.raises(ProjectNotFoundError):
        env.generations.show(env.writer, "missing-project", first.id)
    with pytest.raises(GenerationNotFoundError):
        env.generations.show(env.writer, project.id, generate_lowercase_ulid())
