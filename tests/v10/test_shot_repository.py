"""Shot repository tests: immutable shot containers and position-aware item
mutations (m3 plan steps 10-11, T11 + T12).

This suite proves the shots pack repository over the frozen two-table schema
(``shots``, ``shot_items``) with exact kernel media ids only:

- ``create`` atomicity: one ``BEGIN IMMEDIATE`` command writes the
  ``shot.shot`` stream, the ``shots`` row with a deterministic normalized
  ``sort_key`` derived from stable facts (``created_at|id`` — never a
  caller-supplied floating rank), one hash-chained ``shot.created`` event,
  both heads, and the complete receipt together;
- ``add_item`` inserts an exact same-project kernel media id at a validated
  position (empty/single/middle/end), renormalizes every item to the
  deterministic zero-padded position keys, and rejects missing/foreign
  media, negative source frames, out-of-range positions, and duplicate item
  identity before any write;
- ``remove_item`` deletes only the ``shot_items`` row — the kernel media
  row, its location, and its bytes are preserved — renormalizes the
  remaining items, and rejects missing or foreign-shot items before any
  write;
- ``reorder`` accepts exactly the shot's current item ids as one exact
  permutation (rejecting omissions, duplicates, extras, and foreign-shot
  items before any write), renumbers with collision-safe temporary keys
  followed by normalized final keys in one transaction, appends one
  ``shot.reordered`` event, and stores the exact item and media order in
  the receipt;
- replay returns the stored result with zero new rows, mismatch fails
  before any mutation, and a crash at any statement boundary reopens to
  the old (zero-row) state (old-or-complete at commit);
- reads are transaction-free on a separate read-only connection with stable
  ``sort_key``/``id`` ordering for both shots and items;
- the pack never FK's to or imports the timeline pack, and the standard
  catalog stays exactly the frozen 23 tables.

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
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_CREATE_COMMAND_KIND,
    SHOT_CREATED_EVENT_KIND,
    SHOT_ITEM_ADDED_EVENT_KIND,
    SHOT_ITEM_REMOVED_EVENT_KIND,
    SHOT_REMOVE_ITEM_COMMAND_KIND,
    SHOT_REORDER_COMMAND_KIND,
    SHOT_REORDERED_EVENT_KIND,
    SHOT_STREAM_TYPE,
    ShotAlreadyExistsError,
    ShotItemMutationReadModel,
    ShotItemNotFoundError,
    ShotItemReadModel,
    ShotListRow,
    ShotMediaError,
    ShotNotFoundError,
    ShotReadModel,
    ShotReorderError,
    ShotReorderReadModel,
    ShotRepository,
    ShotValidationError,
)

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _InjectedCrash(RuntimeError):
    """Sentinel raised at one statement boundary by the crash test."""


@pytest.fixture
def env(tmp_path: Path, standard_registry):
    """Fresh standard-Astrid writer plus project/media/shot repositories."""
    writer = DatabaseWriter(tmp_path / "shots.sqlite3", standard_registry)
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
            shot_repo=ShotRepository(events=events, receipts=receipts),
        )
    finally:
        writer.close()


def _fresh_namespace(root: Path, registry):
    """Build a fresh writer + repository namespace rooted at ``root``."""
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
        shot_repo=ShotRepository(events=events, receipts=receipts),
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


def _create_shot(
    env,
    *,
    project_id: str,
    name: str = "Opening",
    shot_id: str | None = None,
    idempotency_key: str = "shot-create-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "name": name,
        "idempotency_key": idempotency_key,
        "shot_id": shot_id,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.shot_repo.create(u, **args)
    )


def _add_item(
    env,
    *,
    project_id: str,
    shot_id: str,
    media_id: str,
    position: int | None = None,
    source_frame: int | None = None,
    metadata=None,
    item_id: str | None = None,
    idempotency_key: str = "shot-add-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "shot_id": shot_id,
        "media_id": media_id,
        "position": position,
        "source_frame": source_frame,
        "metadata": metadata,
        "item_id": item_id,
        "idempotency_key": idempotency_key,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.shot_repo.add_item(u, **args)
    )


def _remove_item(
    env,
    *,
    project_id: str,
    shot_id: str,
    item_id: str,
    idempotency_key: str = "shot-remove-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "shot_id": shot_id,
        "item_id": item_id,
        "idempotency_key": idempotency_key,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.shot_repo.remove_item(u, **args)
    )


def _reorder(
    env,
    *,
    project_id: str,
    shot_id: str,
    item_ids,
    idempotency_key: str = "shot-reorder-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "shot_id": shot_id,
        "item_ids": item_ids,
        "idempotency_key": idempotency_key,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.shot_repo.reorder(u, **args)
    )


def _counts(writer: DatabaseWriter) -> tuple[int, ...]:
    """(shots, shot_items, events, command_receipts, event_streams, media,
    media_locations)."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM shots")[0],
            session.query_one("SELECT count(*) FROM shot_items")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM media")[0],
            session.query_one("SELECT count(*) FROM media_locations")[0],
        )
    )


def _shot_row(writer: DatabaseWriter, shot_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM shots WHERE id = ?", (shot_id,)
        )
    )


def _item_rows(writer: DatabaseWriter, shot_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM shot_items WHERE shot_id = ? "
            "ORDER BY sort_key ASC, id ASC",
            (shot_id,),
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


def _crash_run(writer: DatabaseWriter, *, kind: str | None, sql_sub: str | None, fn):
    """Run ``fn`` inside a UoW that raises :class:`_InjectedCrash` at the
    first boundary matching ``kind`` or ``sql_sub``."""
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
# create: stream, row, event, receipt
# ---------------------------------------------------------------------------


def test_shot_create_stream_row_event_receipt(env) -> None:
    project = _create_project(env)
    shot_id = generate_lowercase_ulid()
    counts = _counts(env.writer)

    created = _create_shot(
        env,
        project_id=project.id,
        name="Opening",
        metadata={"camera": "wide"},
        shot_id=shot_id,
        idempotency_key="shot-create-c1",
    )
    assert isinstance(created, ShotReadModel)
    assert created.id == shot_id
    assert created.project_id == project.id
    assert created.name == "Opening"
    assert created.metadata == {"camera": "wide"}
    assert created.items == ()
    assert created.event_head_seq == 1
    # Deterministic normalized sort key from stable facts (created_at|id).
    assert created.sort_key == f"{TS}|{shot_id}"

    # One stream + row + event + receipt; nothing else changed.
    assert _counts(env.writer) == (
        counts[0] + 1,
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
    )

    row = _shot_row(env.writer, shot_id)
    assert row is not None
    assert row["project_id"] == project.id
    assert row["name"] == "Opening"
    assert row["sort_key"] == f"{TS}|{shot_id}"
    assert json.loads(row["metadata_json"]) == {"camera": "wide"}
    assert row["created_at"] == TS
    assert row["updated_at"] == TS

    # Its own registered shot.shot stream with one created event.
    stream_id = f"{shot_id}:{SHOT_STREAM_TYPE}"
    assert _stream_row(env.writer, stream_id)["stream_type"] == SHOT_STREAM_TYPE
    assert _stream_row(env.writer, stream_id)["aggregate_id"] == shot_id
    assert _stream_row(env.writer, stream_id)["head_seq"] == 1
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [SHOT_CREATED_EVENT_KIND]
    data = json.loads(events[0]["payload_json"])["data"]
    assert data["shot_id"] == shot_id
    assert data["name"] == "Opening"
    assert data["metadata"] == {"camera": "wide"}
    assert data["sort_key"] == f"{TS}|{shot_id}"

    # One complete receipt keyed on the frozen shot.create command kind.
    receipt = _receipt_row(env.writer, project.id, "shot-create-c1")
    assert receipt["command_kind"] == SHOT_CREATE_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 1
    stored = json.loads(receipt["result_json"])
    assert stored["id"] == shot_id
    assert stored["items"] == []


def test_shot_create_rejections_change_zero_rows(env) -> None:
    project = _create_project(env)
    counts = _counts(env.writer)

    with pytest.raises(ShotValidationError):
        _create_shot(
            env,
            project_id=project.id,
            name="   ",
            idempotency_key="shot-create-bad1",
        )
    with pytest.raises(ShotValidationError):
        _create_shot(
            env,
            project_id=project.id,
            name="Opening",
            metadata=["not", "an", "object"],
            idempotency_key="shot-create-bad2",
        )
    # Missing project is a typed project error.
    with pytest.raises(ProjectNotFoundError):
        _create_shot(
            env,
            project_id=generate_lowercase_ulid(),
            name="Opening",
            idempotency_key="shot-create-bad3",
        )
    # Duplicate shot identity is rejected before allocation.
    shot_id = generate_lowercase_ulid()
    _create_shot(
        env,
        project_id=project.id,
        name="Opening",
        shot_id=shot_id,
        idempotency_key="shot-create-bad4a",
    )
    with pytest.raises(ShotAlreadyExistsError):
        _create_shot(
            env,
            project_id=project.id,
            name="Another",
            shot_id=shot_id,
            idempotency_key="shot-create-bad4b",
        )
    assert _counts(env.writer) == (
        counts[0] + 1,
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
    )


def test_shot_create_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    shot_id = generate_lowercase_ulid()
    counts = _counts(env.writer)

    first = _create_shot(
        env,
        project_id=project.id,
        name="Opening",
        shot_id=shot_id,
        idempotency_key="shot-create-replay",
    )
    # Identical retry (same stable shot id): stored result, zero new rows.
    second = _create_shot(
        env,
        project_id=project.id,
        name="Opening",
        shot_id=shot_id,
        idempotency_key="shot-create-replay",
    )
    assert second == first
    assert second.id == shot_id
    assert _counts(env.writer) == (
        counts[0] + 1,
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
    )

    # Changed request under the same key: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _create_shot(
            env,
            project_id=project.id,
            name="A Different Name",
            idempotency_key="shot-create-replay",
        )
    assert _counts(env.writer) == (
        counts[0] + 1,
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
    )


# ---------------------------------------------------------------------------
# reads: stable sort-key/id ordering
# ---------------------------------------------------------------------------


def test_shot_list_and_show_stable_ordering(env) -> None:
    project = _create_project(env)
    shot_a = _create_shot(
        env,
        project_id=project.id,
        name="First",
        shot_id=generate_lowercase_ulid(),
        idempotency_key="shot-list-a",
    )
    shot_b = _create_shot(
        env,
        project_id=project.id,
        name="Second",
        shot_id=generate_lowercase_ulid(),
        idempotency_key="shot-list-b",
        created_at=TS2,
    )
    rows = env.shot_repo.list(env.writer, project.id)
    assert [row.id for row in rows] == [shot_a.id, shot_b.id]
    assert all(isinstance(row, ShotListRow) for row in rows)
    assert rows[0].sort_key == f"{TS}|{shot_a.id}"
    assert rows[1].sort_key == f"{TS2}|{shot_b.id}"

    shown = env.shot_repo.show(env.writer, project.id, shot_b.id)
    assert shown.id == shot_b.id
    assert shown.event_head_seq == 1
    assert shown.items == ()

    # Missing project is a typed project error; a missing or foreign shot
    # is a typed not-found error.
    with pytest.raises(ProjectNotFoundError):
        env.shot_repo.list(env.writer, generate_lowercase_ulid())
    with pytest.raises(ProjectNotFoundError):
        env.shot_repo.show(env.writer, generate_lowercase_ulid(), shot_a.id)
    with pytest.raises(ShotNotFoundError):
        env.shot_repo.show(env.writer, project.id, generate_lowercase_ulid())
    other = _create_project(env, slug="gamma")
    with pytest.raises(ShotNotFoundError):
        env.shot_repo.show(env.writer, other.id, shot_a.id)


# ---------------------------------------------------------------------------
# add_item: position-aware insertion and renormalization
# ---------------------------------------------------------------------------


def test_shot_add_item_positions_and_renormalization(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-add-p0"
    )
    media_a = _import_media(env, project_id=project.id, idempotency_key="import-pa")
    media_b = _import_media(env, project_id=project.id, idempotency_key="import-pb")
    media_c = _import_media(env, project_id=project.id, idempotency_key="import-pc")

    # Empty shot: first item appends at position 0.
    first = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_a.id,
        source_frame=0,
        idempotency_key="shot-add-p1",
    )
    assert isinstance(first, ShotItemMutationReadModel)
    assert first.item.media_id == media_a.id
    assert first.item.position == 0
    assert first.item.sort_key == "000000000000"
    assert first.item_ids == (first.item.id,)

    # End position: appended after the existing item.
    last = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_c.id,
        position=1,
        idempotency_key="shot-add-p2",
    )
    assert last.item.position == 1
    assert last.item.sort_key == "000000000001"
    assert last.item_ids == (first.item.id, last.item.id)

    # Middle position: inserted at 1; existing items renormalize to 0..2.
    middle = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_b.id,
        position=1,
        source_frame=42,
        idempotency_key="shot-add-p3",
    )
    assert middle.item.position == 1
    assert middle.item.sort_key == "000000000001"
    assert middle.item_ids == (first.item.id, middle.item.id, last.item.id)

    # Position omitted appends at the end.
    end = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_a.id,
        idempotency_key="shot-add-p4",
    )
    assert end.item.position == 3
    assert end.item_ids == (
        first.item.id,
        middle.item.id,
        last.item.id,
        end.item.id,
    )

    # Rows carry the normalized zero-padded keys, and show exposes the
    # stable sort-key/id order with derived positions.
    rows = _item_rows(env.writer, shot.id)
    assert [r["sort_key"] for r in rows] == [
        "000000000000",
        "000000000001",
        "000000000002",
        "000000000003",
    ]
    shown = env.shot_repo.show(env.writer, project.id, shot.id)
    assert [item.id for item in shown.items] == list(end.item_ids)
    assert [item.position for item in shown.items] == [0, 1, 2, 3]
    assert [item.media_id for item in shown.items] == [
        media_a.id,
        media_b.id,
        media_c.id,
        media_a.id,
    ]
    assert shown.items[1].source_frame == 42
    # Stream head: 1 created + 4 item_added events.
    assert shown.event_head_seq == 5


def test_shot_add_item_rejections_change_zero_rows(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_a = _import_media(env, project_id=project_a.id, idempotency_key="import-ra")
    media_b = _import_media(env, project_id=project_b.id, idempotency_key="import-rb")
    shot = _create_shot(
        env, project_id=project_a.id, idempotency_key="shot-add-r0"
    )
    shot_b = _create_shot(
        env, project_id=project_b.id, idempotency_key="shot-add-rb"
    )
    item_id = generate_lowercase_ulid()
    _add_item(
        env,
        project_id=project_a.id,
        shot_id=shot.id,
        media_id=media_a.id,
        item_id=item_id,
        idempotency_key="shot-add-r1",
    )
    counts = _counts(env.writer)

    # Missing shot and foreign shot.
    with pytest.raises(ShotNotFoundError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=generate_lowercase_ulid(),
            media_id=media_a.id,
            idempotency_key="shot-add-r2",
        )
    with pytest.raises(ShotNotFoundError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot_b.id,
            media_id=media_a.id,
            idempotency_key="shot-add-r3",
        )
    # Missing and foreign media.
    with pytest.raises(ShotMediaError) as excinfo:
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=generate_lowercase_ulid(),
            idempotency_key="shot-add-r4",
        )
    assert excinfo.value.detail == "missing"
    with pytest.raises(ShotMediaError) as excinfo:
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=media_b.id,
            idempotency_key="shot-add-r5",
        )
    assert excinfo.value.detail == "foreign"
    # Negative source frame.
    with pytest.raises(ShotValidationError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=media_a.id,
            source_frame=-1,
            idempotency_key="shot-add-r6",
        )
    # Out-of-range insertion position (current count is 1).
    with pytest.raises(ShotValidationError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=media_a.id,
            position=2,
            idempotency_key="shot-add-r7",
        )
    with pytest.raises(ShotValidationError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=media_a.id,
            position=-1,
            idempotency_key="shot-add-r8",
        )
    # Non-object metadata and duplicate item identity.
    with pytest.raises(ShotValidationError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=media_a.id,
            metadata="nope",
            idempotency_key="shot-add-r9",
        )
    with pytest.raises(ShotValidationError):
        _add_item(
            env,
            project_id=project_a.id,
            shot_id=shot.id,
            media_id=media_a.id,
            item_id=item_id,
            idempotency_key="shot-add-r10",
        )
    assert _counts(env.writer) == counts


def test_shot_add_item_event_head_receipt(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-add-e0"
    )
    media = _import_media(env, project_id=project.id, idempotency_key="import-e1")
    counts = _counts(env.writer)

    result = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        source_frame=7,
        metadata={"note": "hero"},
        idempotency_key="shot-add-e1",
    )
    # One item row + one event + one receipt; the shot row refreshes.
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6],
    )
    assert _shot_row(env.writer, shot.id)["updated_at"] == TS

    stream_id = f"{shot.id}:{SHOT_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        SHOT_CREATED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
    ]
    data = json.loads(events[1]["payload_json"])["data"]
    assert data["shot_id"] == shot.id
    assert data["item_id"] == result.item.id
    assert data["media_id"] == media.id
    assert data["source_frame"] == 7
    assert data["metadata"] == {"note": "hero"}
    assert data["position"] == 0
    assert _stream_row(env.writer, stream_id)["head_seq"] == 2
    assert result.event_head_seq == 2

    receipt = _receipt_row(env.writer, project.id, "shot-add-e1")
    assert receipt["command_kind"] == SHOT_ADD_ITEM_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 2
    stored = json.loads(receipt["result_json"])
    assert stored["item"]["id"] == result.item.id
    assert stored["item"]["media_id"] == media.id
    assert stored["item_ids"] == [result.item.id]


def test_shot_add_item_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-add-rep0"
    )
    media = _import_media(env, project_id=project.id, idempotency_key="import-rep")
    counts = _counts(env.writer)
    item_id = generate_lowercase_ulid()

    first = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        item_id=item_id,
        idempotency_key="shot-add-replay",
    )
    second = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        item_id=item_id,
        idempotency_key="shot-add-replay",
    )
    assert second == first
    assert second.item.id == item_id
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6],
    )
    # Changed request under the same key: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _add_item(
            env,
            project_id=project.id,
            shot_id=shot.id,
            media_id=media.id,
            source_frame=99,
            idempotency_key="shot-add-replay",
        )
    assert _counts(env.writer) == (
        counts[0],
        counts[1] + 1,
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6],
    )


# ---------------------------------------------------------------------------
# remove_item: exact identity, media preservation, renormalization
# ---------------------------------------------------------------------------


def test_shot_remove_item_preserves_media_and_renormalizes(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-rem-0"
    )
    path = _write_png(env, "remove-me.png")
    prepared = prepare_media_file(path)
    media = UnitOfWork(env.writer).run(
        lambda u: env.media_repo.import_prepared(
            u,
            project_id=project.id,
            prepared=prepared,
            idempotency_key="import-rem",
            media_id=generate_lowercase_ulid(),
            realm=EXTERNAL_LOCAL_REALM,
            created_at=TS,
        )
    )
    media_b = _import_media(env, project_id=project.id, idempotency_key="import-rem2")
    media_c = _import_media(env, project_id=project.id, idempotency_key="import-rem3")
    a = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        idempotency_key="shot-rem-1",
    )
    b = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_b.id,
        idempotency_key="shot-rem-2",
    )
    c = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_c.id,
        idempotency_key="shot-rem-3",
    )
    assert path.exists()
    counts = _counts(env.writer)

    removed = _remove_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_id=b.item.id,
        idempotency_key="shot-rem-mid",
    )
    # The result carries the removed item's preserved media identity and
    # the remaining ordered item ids.
    assert isinstance(removed, ShotItemMutationReadModel)
    assert removed.item.id == b.item.id
    assert removed.item.media_id == media_b.id
    assert removed.item_ids == (a.item.id, c.item.id)
    # Stream head: 1 created + 3 item_added + 1 item_removed events.
    assert removed.event_head_seq == 5

    # Only the shot_items row was deleted: the media row, its location, and
    # its bytes are preserved.
    assert _counts(env.writer) == (
        counts[0],
        counts[1] - 1,
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6],
    )
    assert path.exists()
    assert path.read_bytes() == PNG_BYTES
    media_row = env.writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM media WHERE id = ?", (media_b.id,)
        )
    )
    assert media_row is not None
    location = env.writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM media_locations WHERE media_id = ?", (media_b.id,)
        )
    )
    assert location is not None

    # Remaining items are renormalized to deterministic positions.
    rows = _item_rows(env.writer, shot.id)
    assert [r["id"] for r in rows] == [a.item.id, c.item.id]
    assert [r["sort_key"] for r in rows] == [
        "000000000000",
        "000000000001",
    ]
    shown = env.shot_repo.show(env.writer, project.id, shot.id)
    assert [item.id for item in shown.items] == [a.item.id, c.item.id]
    assert [item.position for item in shown.items] == [0, 1]

    # The removal event carries the preserved media identity.
    stream_id = f"{shot.id}:{SHOT_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        SHOT_CREATED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
        SHOT_ITEM_REMOVED_EVENT_KIND,
    ]
    data = json.loads(events[4]["payload_json"])["data"]
    assert data["item_id"] == b.item.id
    assert data["media_id"] == media_b.id

    # The receipt result carries the preserved media id and the remaining
    # ordered item ids.
    receipt = _receipt_row(env.writer, project.id, "shot-rem-mid")
    assert receipt["command_kind"] == SHOT_REMOVE_ITEM_COMMAND_KIND
    stored = json.loads(receipt["result_json"])
    assert stored["item"]["media_id"] == media_b.id
    assert stored["item_ids"] == [a.item.id, c.item.id]


def test_shot_remove_item_rejections_change_zero_rows(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-rem-r0"
    )
    shot_other = _create_shot(
        env,
        project_id=project.id,
        name="Other",
        idempotency_key="shot-rem-r0b",
    )
    media = _import_media(env, project_id=project.id, idempotency_key="import-rr")
    item = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        idempotency_key="shot-rem-r1",
    )
    counts = _counts(env.writer)

    # Missing shot and missing item.
    with pytest.raises(ShotNotFoundError):
        _remove_item(
            env,
            project_id=project.id,
            shot_id=generate_lowercase_ulid(),
            item_id=item.item.id,
            idempotency_key="shot-rem-r2",
        )
    with pytest.raises(ShotItemNotFoundError):
        _remove_item(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_id=generate_lowercase_ulid(),
            idempotency_key="shot-rem-r3",
        )
    # An item that belongs to another shot is a typed item-not-found error
    # (unique identity validation).
    with pytest.raises(ShotItemNotFoundError):
        _remove_item(
            env,
            project_id=project.id,
            shot_id=shot_other.id,
            item_id=item.item.id,
            idempotency_key="shot-rem-r4",
        )
    assert _counts(env.writer) == counts


def test_shot_remove_item_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-rem-rep0"
    )
    media = _import_media(env, project_id=project.id, idempotency_key="import-repr")
    item = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        idempotency_key="shot-rem-rep1",
    )
    first = _remove_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_id=item.item.id,
        idempotency_key="shot-rem-replay",
    )
    counts = _counts(env.writer)
    # Identical retry: stored result, zero new rows.
    second = _remove_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_id=item.item.id,
        idempotency_key="shot-rem-replay",
    )
    assert second == first
    assert _counts(env.writer) == counts
    # Changed request under the same key: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _remove_item(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_id=generate_lowercase_ulid(),
            idempotency_key="shot-rem-replay",
        )
    assert _counts(env.writer) == counts


# ---------------------------------------------------------------------------
# reorder: exact permutation, atomic state, replay/mismatch
# ---------------------------------------------------------------------------


def test_shot_reorder_exact_permutation_and_atomic_state(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-reo-0"
    )
    media_a = _import_media(env, project_id=project.id, idempotency_key="import-reoa")
    media_b = _import_media(env, project_id=project.id, idempotency_key="import-reob")
    media_c = _import_media(env, project_id=project.id, idempotency_key="import-reoc")
    a = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_a.id,
        idempotency_key="shot-reo-1",
    )
    b = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_b.id,
        idempotency_key="shot-reo-2",
    )
    c = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_c.id,
        idempotency_key="shot-reo-3",
    )
    counts = _counts(env.writer)
    assert _shot_row(env.writer, shot.id)["updated_at"] == TS

    # One exact permutation: [c, a, b].
    result = _reorder(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_ids=[c.item.id, a.item.id, b.item.id],
        idempotency_key="shot-reorder-p1",
    )
    assert isinstance(result, ShotReorderReadModel)
    assert result.shot_id == shot.id
    assert result.project_id == project.id
    assert result.item_ids == (c.item.id, a.item.id, b.item.id)
    # The receipt result carries the exact ordered media ids too.
    assert result.media_ids == (media_c.id, media_a.id, media_b.id)
    # Stream head: 1 created + 3 item_added + 1 reordered events.
    assert result.event_head_seq == 5

    # Exactly one event and one receipt; nothing else changed.
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4],
        counts[5],
        counts[6],
    )
    assert _shot_row(env.writer, shot.id)["updated_at"] == TS

    # Rows carry the normalized zero-padded keys in the new order, and
    # show exposes the stable sort-key/id order with derived positions.
    rows = _item_rows(env.writer, shot.id)
    assert [r["id"] for r in rows] == [c.item.id, a.item.id, b.item.id]
    assert [r["sort_key"] for r in rows] == [
        "000000000000",
        "000000000001",
        "000000000002",
    ]
    shown = env.shot_repo.show(env.writer, project.id, shot.id)
    assert [item.id for item in shown.items] == [
        c.item.id,
        a.item.id,
        b.item.id,
    ]
    assert [item.media_id for item in shown.items] == [
        media_c.id,
        media_a.id,
        media_b.id,
    ]
    assert [item.position for item in shown.items] == [0, 1, 2]
    assert shown.event_head_seq == 5

    # The single shot.reordered event carries the exact ordered ids.
    stream_id = f"{shot.id}:{SHOT_STREAM_TYPE}"
    events = _event_rows(env.writer, stream_id)
    assert [e["kind"] for e in events] == [
        SHOT_CREATED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
        SHOT_ITEM_ADDED_EVENT_KIND,
        SHOT_REORDERED_EVENT_KIND,
    ]
    data = json.loads(events[4]["payload_json"])["data"]
    assert data["shot_id"] == shot.id
    assert data["item_ids"] == [c.item.id, a.item.id, b.item.id]
    assert data["media_ids"] == [media_c.id, media_a.id, media_b.id]
    assert _stream_row(env.writer, stream_id)["head_seq"] == 5

    # The receipt stores the exact item and media order.
    receipt = _receipt_row(env.writer, project.id, "shot-reorder-p1")
    assert receipt["command_kind"] == SHOT_REORDER_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_id
    assert receipt["resulting_stream_seq"] == 5
    stored = json.loads(receipt["result_json"])
    assert stored["shot_id"] == shot.id
    assert stored["item_ids"] == [c.item.id, a.item.id, b.item.id]
    assert stored["media_ids"] == [media_c.id, media_a.id, media_b.id]
    assert stored["event_head_seq"] == 5

    # An empty shot accepts exactly its current (empty) item list as a
    # degenerate permutation: one event + one receipt, empty orders.
    empty = _create_shot(
        env,
        project_id=project.id,
        name="Empty",
        idempotency_key="shot-reo-empty",
    )
    empty_counts = _counts(env.writer)
    empty_result = _reorder(
        env,
        project_id=project.id,
        shot_id=empty.id,
        item_ids=[],
        idempotency_key="shot-reorder-empty",
    )
    assert empty_result.item_ids == ()
    assert empty_result.media_ids == ()
    assert empty_result.event_head_seq == 2
    assert _counts(env.writer) == (
        empty_counts[0],
        empty_counts[1],
        empty_counts[2] + 1,
        empty_counts[3] + 1,
        empty_counts[4],
        empty_counts[5],
        empty_counts[6],
    )


def test_shot_reorder_rejections_change_zero_rows(env) -> None:
    project = _create_project(env, slug="alpha")
    other_project = _create_project(env, slug="beta")
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-reo-r0"
    )
    shot_other = _create_shot(
        env,
        project_id=project.id,
        name="Other",
        idempotency_key="shot-reo-r0b",
    )
    foreign_shot = _create_shot(
        env,
        project_id=other_project.id,
        name="Foreign",
        idempotency_key="shot-reo-r0c",
    )
    media_a = _import_media(env, project_id=project.id, idempotency_key="import-rra")
    media_b = _import_media(env, project_id=project.id, idempotency_key="import-rrb")
    media_c = _import_media(env, project_id=other_project.id, idempotency_key="import-rrc")
    a = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_a.id,
        idempotency_key="shot-reo-r1",
    )
    b = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_b.id,
        idempotency_key="shot-reo-r2",
    )
    other_item = _add_item(
        env,
        project_id=project.id,
        shot_id=shot_other.id,
        media_id=media_a.id,
        idempotency_key="shot-reo-r3",
    )
    foreign_item = _add_item(
        env,
        project_id=other_project.id,
        shot_id=foreign_shot.id,
        media_id=media_c.id,
        idempotency_key="shot-reo-r4",
    )
    counts = _counts(env.writer)

    # Omission: a current item id is missing from the request.
    with pytest.raises(ShotReorderError) as excinfo:
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id],
            idempotency_key="shot-reorder-r1",
        )
    assert excinfo.value.detail == "omission"
    # Duplicate: an id appears more than once.
    with pytest.raises(ShotReorderError) as excinfo:
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id, a.item.id, b.item.id],
            idempotency_key="shot-reorder-r2",
        )
    assert excinfo.value.detail == "duplicate"
    # Extra: an id that is not a shot item at all.
    with pytest.raises(ShotReorderError) as excinfo:
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id, b.item.id, generate_lowercase_ulid()],
            idempotency_key="shot-reorder-r3",
        )
    assert excinfo.value.detail == "extra"
    # Foreign-shot item: an id that belongs to a different shot (all
    # current ids present, plus the foreign item).
    with pytest.raises(ShotReorderError) as excinfo:
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id, b.item.id, other_item.item.id],
            idempotency_key="shot-reorder-r4",
        )
    assert excinfo.value.detail == "foreign"
    # Foreign project's item is still a foreign-shot item (same category).
    with pytest.raises(ShotReorderError) as excinfo:
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id, b.item.id, foreign_item.item.id],
            idempotency_key="shot-reorder-r5",
        )
    assert excinfo.value.detail == "foreign"
    # Missing and foreign shots are typed not-found errors.
    with pytest.raises(ShotNotFoundError):
        _reorder(
            env,
            project_id=project.id,
            shot_id=generate_lowercase_ulid(),
            item_ids=[a.item.id],
            idempotency_key="shot-reorder-r6",
        )
    with pytest.raises(ShotNotFoundError):
        _reorder(
            env,
            project_id=project.id,
            shot_id=foreign_shot.id,
            item_ids=[foreign_item.item.id],
            idempotency_key="shot-reorder-r7",
        )
    # Non-sequence and empty-string element requests are validation errors.
    with pytest.raises(ShotValidationError):
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids="not-a-sequence",
            idempotency_key="shot-reorder-r8",
        )
    with pytest.raises(ShotValidationError):
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id, ""],
            idempotency_key="shot-reorder-r9",
        )
    assert _counts(env.writer) == counts
    # The order is unchanged after every rejection.
    shown = env.shot_repo.show(env.writer, project.id, shot.id)
    assert [item.id for item in shown.items] == [a.item.id, b.item.id]


def test_shot_reorder_replay_and_mismatch(env) -> None:
    project = _create_project(env)
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-reo-rep0"
    )
    media_a = _import_media(env, project_id=project.id, idempotency_key="import-repra")
    media_b = _import_media(env, project_id=project.id, idempotency_key="import-reprb")
    media_c = _import_media(env, project_id=project.id, idempotency_key="import-reprc")
    a = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_a.id,
        idempotency_key="shot-reo-rep1",
    )
    b = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_b.id,
        idempotency_key="shot-reo-rep2",
    )
    c = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media_c.id,
        idempotency_key="shot-reo-rep3",
    )
    first = _reorder(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_ids=[c.item.id, a.item.id, b.item.id],
        idempotency_key="shot-reorder-replay",
    )
    counts = _counts(env.writer)
    # Identical retry: stored result, zero new rows.
    second = _reorder(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_ids=[c.item.id, a.item.id, b.item.id],
        idempotency_key="shot-reorder-replay",
    )
    assert second == first
    assert second.item_ids == (c.item.id, a.item.id, b.item.id)
    assert _counts(env.writer) == counts
    # Changed request under the same key: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _reorder(
            env,
            project_id=project.id,
            shot_id=shot.id,
            item_ids=[a.item.id, b.item.id, c.item.id],
            idempotency_key="shot-reorder-replay",
        )
    assert _counts(env.writer) == counts
    shown = env.shot_repo.show(env.writer, project.id, shot.id)
    assert [item.id for item in shown.items] == [
        c.item.id,
        a.item.id,
        b.item.id,
    ]


# ---------------------------------------------------------------------------
# crash atomicity: old-or-complete at every statement boundary
# ---------------------------------------------------------------------------


def test_shot_create_statement_boundary_atomicity(
    tmp_path, standard_registry
) -> None:
    """A crash at any statement boundary leaves the old (zero-row) state."""
    root = tmp_path / "shot-create-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, standard_registry)
    try:
        project = _create_project(env2, project_id="crash-proj-c")
        counts_before = _counts(env2.writer)

        # Crash right after the event_streams INSERT: no shot may persist.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO event_streams",
            fn=lambda u: env2.shot_repo.create(
                u,
                project_id=project.id,
                name="Crash",
                idempotency_key="shot-crash-c1",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash right after the shots INSERT.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO shots",
            fn=lambda u: env2.shot_repo.create(
                u,
                project_id=project.id,
                name="Crash",
                idempotency_key="shot-crash-c2",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash at commit: old-or-complete (never a half-committed row).
        outcome = _crash_run(
            env2.writer,
            kind="commit",
            sql_sub=None,
            fn=lambda u: env2.shot_repo.create(
                u,
                project_id=project.id,
                name="Crash",
                idempotency_key="shot-crash-c3",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        after = _counts(env2.writer)
        committed = (
            counts_before[0] + 1,
            counts_before[1],
            counts_before[2] + 1,
            counts_before[3] + 1,
            counts_before[4] + 1,
            counts_before[5],
            counts_before[6],
        )
        assert after in (counts_before, committed)
    finally:
        env2.writer.close()


def test_shot_item_mutation_statement_boundary_atomicity(
    tmp_path, standard_registry
) -> None:
    """Crash mid-add and mid-remove leave the old (zero-row) state."""
    root = tmp_path / "shot-item-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, standard_registry)
    try:
        project = _create_project(env2, project_id="crash-proj-i")
        media = _import_media(
            env2, project_id=project.id, idempotency_key="import-crash"
        )
        shot = _create_shot(
            env2,
            project_id=project.id,
            shot_id="crash-shot",
            idempotency_key="shot-crash-s0",
        )
        counts_before = _counts(env2.writer)

        # Crash right after the shot_items INSERT on add: the whole add
        # (including the renormalization and the shot refresh) rolls back.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO shot_items",
            fn=lambda u: env2.shot_repo.add_item(
                u,
                project_id=project.id,
                shot_id=shot.id,
                media_id=media.id,
                idempotency_key="shot-crash-add",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Seed one item, then crash right after the shot_items DELETE on
        # remove: the whole remove rolls back.
        item = _add_item(
            env2,
            project_id=project.id,
            shot_id=shot.id,
            media_id=media.id,
            idempotency_key="shot-crash-seed",
        )
        before_remove = _counts(env2.writer)
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="DELETE FROM shot_items",
            fn=lambda u: env2.shot_repo.remove_item(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_id=item.item.id,
                idempotency_key="shot-crash-remove",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == before_remove

        # Crash at commit on remove: old-or-complete.
        outcome = _crash_run(
            env2.writer,
            kind="commit",
            sql_sub=None,
            fn=lambda u: env2.shot_repo.remove_item(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_id=item.item.id,
                idempotency_key="shot-crash-remove2",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        after = _counts(env2.writer)
        committed = (
            before_remove[0],
            before_remove[1] - 1,
            before_remove[2] + 1,
            before_remove[3] + 1,
            before_remove[4],
            before_remove[5],
            before_remove[6],
        )
        assert after in (before_remove, committed)
    finally:
        env2.writer.close()


def test_shot_reorder_statement_boundary_atomicity(
    tmp_path, standard_registry
) -> None:
    """Crash mid-reorder leaves the old order with zero new rows."""
    root = tmp_path / "shot-reorder-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, standard_registry)
    try:
        project = _create_project(env2, project_id="crash-proj-r")
        media_a = _import_media(
            env2, project_id=project.id, idempotency_key="import-crasha"
        )
        media_b = _import_media(
            env2, project_id=project.id, idempotency_key="import-crashb"
        )
        media_c = _import_media(
            env2, project_id=project.id, idempotency_key="import-crashc"
        )
        shot = _create_shot(
            env2,
            project_id=project.id,
            shot_id="crash-shot-r",
            idempotency_key="shot-crash-r0",
        )
        a = _add_item(
            env2,
            project_id=project.id,
            shot_id=shot.id,
            media_id=media_a.id,
            idempotency_key="shot-crash-r1",
        )
        b = _add_item(
            env2,
            project_id=project.id,
            shot_id=shot.id,
            media_id=media_b.id,
            idempotency_key="shot-crash-r2",
        )
        c = _add_item(
            env2,
            project_id=project.id,
            shot_id=shot.id,
            media_id=media_c.id,
            idempotency_key="shot-crash-r3",
        )
        order = [c.item.id, a.item.id, b.item.id]
        counts_before = _counts(env2.writer)

        # Crash right after the temporary-key pass: old order, zero rows.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="UPDATE shot_items SET sort_key = ? || id",
            fn=lambda u: env2.shot_repo.reorder(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_ids=order,
                idempotency_key="shot-crash-reo1",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash right after the first final-key UPDATE: old order, zero
        # rows (the tmp pass rolls back with the transaction).
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="UPDATE shot_items SET sort_key = ? WHERE id = ? AND shot_id = ?",
            fn=lambda u: env2.shot_repo.reorder(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_ids=order,
                idempotency_key="shot-crash-reo2",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash right after the event INSERT: old order, zero rows.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO events",
            fn=lambda u: env2.shot_repo.reorder(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_ids=order,
                idempotency_key="shot-crash-reo3",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash right after the receipt INSERT: old order, zero rows.
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO command_receipts",
            fn=lambda u: env2.shot_repo.reorder(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_ids=order,
                idempotency_key="shot-crash-reo4",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # The order is still the seeded order after every crash.
        shown = env2.shot_repo.show(env2.writer, project.id, shot.id)
        assert [item.id for item in shown.items] == [
            a.item.id,
            b.item.id,
            c.item.id,
        ]
        assert shown.event_head_seq == 4

        # Crash at commit: old-or-complete.
        outcome = _crash_run(
            env2.writer,
            kind="commit",
            sql_sub=None,
            fn=lambda u: env2.shot_repo.reorder(
                u,
                project_id=project.id,
                shot_id=shot.id,
                item_ids=order,
                idempotency_key="shot-crash-reo5",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        after = _counts(env2.writer)
        committed = (
            counts_before[0],
            counts_before[1],
            counts_before[2] + 1,
            counts_before[3] + 1,
            counts_before[4],
            counts_before[5],
            counts_before[6],
        )
        assert after in (counts_before, committed)
    finally:
        env2.writer.close()


# ---------------------------------------------------------------------------
# no timeline dependency and catalog fence
# ---------------------------------------------------------------------------


def test_shot_repository_has_no_timeline_dependency(env) -> None:
    project = _create_project(env)
    media = _import_media(env, project_id=project.id, idempotency_key="import-tl")
    shot = _create_shot(
        env, project_id=project.id, idempotency_key="shot-tl-0"
    )
    item = _add_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        media_id=media.id,
        idempotency_key="shot-tl-1",
    )
    _remove_item(
        env,
        project_id=project.id,
        shot_id=shot.id,
        item_id=item.item.id,
        idempotency_key="shot-tl-2",
    )

    # The shots tables never FK to the timeline pack: the shots and
    # shot_items DDL (the pack's own tables) reference only kernel tables
    # (projects, media) and never name the timeline pack's table.
    shot_ddl = env.writer.submit(
        lambda session: session.query(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('shots', 'shot_items')"
        )
    )
    assert len(shot_ddl) == 2
    for row in shot_ddl:
        assert "timelines" not in str(row["sql"])

    # The repository module never imports the timeline pack (or any other
    # pack); the only pack import is its own sibling modules.
    import astrid.packs.shots.repository as repo_module

    timeline_refs = [
        name
        for name in repo_module.__dict__.keys()
        if "timeline" in name.lower()
    ]
    assert timeline_refs == []
    source = Path(repo_module.__file__).read_text(encoding="utf-8")
    assert "astrid.packs.timeline" not in source

    # The frozen standard catalog is still exactly 23 tables (14 kernel +
    # timelines + shots + shot_items + generations + generation_variants +
    # the three reference tables + runaway_transitions), with no plan/step
    # tables.
    present = env.writer.submit(
        lambda session: {
            row[0]
            for row in session.query(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    )
    assert len(present) == 23
    for table in ("shots", "shot_items", "timelines", "runaway_transitions"):
        assert table in present
    for forbidden in ("plans", "steps", "plan_steps"):
        assert forbidden not in present
