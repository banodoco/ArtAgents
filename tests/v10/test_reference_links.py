"""Reference link tests: receipt-backed typed links with symmetric
related_to canonicalization (m3 plan step 9, T10).

This suite proves the references pack's link contract over the frozen
``reference_links`` table, on top of the T8 lifecycle and T9 media
verticals:

- ``link`` inserts one ``reference_links`` row, appends one hash-chained
  ``reference.linked`` event on the *from* reference's own stream, and
  records one complete receipt keyed on ``reference.link`` — all inside the
  caller's single ``BEGIN IMMEDIATE`` unit of work;
- only ``related_to`` is symmetric (SD2): the stored pair is canonicalized
  to ``min(id)``/``max(id)`` **before** the request is hashed, so reversed
  retries under one idempotency key converge on the stored result with zero
  new rows, while the other four kinds (``belongs_to``, ``wears``,
  ``located_in``, ``associated_with``) preserve their submitted direction —
  a reversed directional retry is a ``ReceiptMismatchError`` and a reversed
  directional request under a new key is a distinct row;
- self-links, missing endpoints, cross-project pairs, archived endpoints,
  non-object metadata, and duplicates are all rejected **before any write**
  (zero rows changed);
- replay returns the stored result with zero new rows; the receipt result
  and event changes stay bounded (both affected reference ids plus kind,
  metadata, timestamp, and stream head); and a crash at any statement
  boundary reopens to old-or-complete state.

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
    ProjectRepository,
)
from astrid.core.repositories.media import EXTERNAL_LOCAL_REALM
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.references.repository import (
    REFERENCE_LINK_COMMAND_KIND,
    REFERENCE_LINK_KINDS,
    REFERENCE_LINKED_EVENT_KIND,
    REFERENCE_STREAM_TYPE,
    REFERENCE_SYMMETRIC_LINK_KIND,
    ReferenceLinkError,
    ReferenceLinkReadModel,
    ReferenceRepository,
)

TS = "2026-08-17T00:00:00.000000+00:00"
TS2 = "2026-08-17T01:00:00.000000+00:00"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _InjectedCrash(RuntimeError):
    """Sentinel raised at one statement boundary by the crash test."""


@pytest.fixture
def env(tmp_path: Path, standard_registry):
    """Fresh standard-Astrid writer plus project/media/reference repos."""
    writer = DatabaseWriter(tmp_path / "references_links.sqlite3", standard_registry)
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


def _link(
    env,
    *,
    project_id: str,
    from_reference_id: str,
    to_reference_id: str,
    kind: str = "related_to",
    metadata=None,
    idempotency_key: str = "link-k-1",
    **overrides,
):
    args = {
        "project_id": project_id,
        "from_reference_id": from_reference_id,
        "to_reference_id": to_reference_id,
        "kind": kind,
        "metadata": metadata,
        "idempotency_key": idempotency_key,
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.reference_repo.link(u, **args))


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


def _link_rows(writer: DatabaseWriter):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM reference_links ORDER BY from_reference_id ASC, "
            "to_reference_id ASC, kind ASC"
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


def _seed_two_references(env, *, project_id: str, prefix: str = "r"):
    media_a = _import_media(env, project_id=project_id, idempotency_key=f"import-{prefix}a")
    media_b = _import_media(env, project_id=project_id, idempotency_key=f"import-{prefix}b")
    ref_a = _create_reference(
        env,
        project_id=project_id,
        name=f"{prefix}A",
        media_id=media_a.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key=f"ref-create-{prefix}a",
    )
    ref_b = _create_reference(
        env,
        project_id=project_id,
        name=f"{prefix}B",
        media_id=media_b.id,
        reference_id=generate_lowercase_ulid(),
        idempotency_key=f"ref-create-{prefix}b",
    )
    return ref_a, ref_b


# ---------------------------------------------------------------------------
# link: directionality and symmetric canonicalization (SD2)
# ---------------------------------------------------------------------------


def test_link_directional_kind_preserves_direction(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    linked = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="belongs_to",
        metadata={"note": "a owns b"},
        idempotency_key="link-dir-1",
    )
    assert isinstance(linked, ReferenceLinkReadModel)
    assert linked.from_reference_id == ref_a.id
    assert linked.to_reference_id == ref_b.id
    assert linked.kind == "belongs_to"
    assert linked.metadata == {"note": "a owns b"}
    assert linked.created_at == TS

    # One row, one event, one receipt.
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )
    rows = _link_rows(env.writer)
    assert len(rows) == 1
    assert rows[0]["from_reference_id"] == ref_a.id
    assert rows[0]["to_reference_id"] == ref_b.id
    assert rows[0]["kind"] == "belongs_to"
    assert json.loads(rows[0]["metadata_json"]) == {"note": "a owns b"}

    # A reversed directional request under a new key is a *distinct* row.
    reversed_link = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_b.id,
        to_reference_id=ref_a.id,
        kind="belongs_to",
        idempotency_key="link-dir-2",
    )
    assert reversed_link.from_reference_id == ref_b.id
    assert reversed_link.to_reference_id == ref_a.id
    assert len(_link_rows(env.writer)) == 2


def test_link_related_to_canonicalized_storage(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    low, high = sorted((ref_a.id, ref_b.id))

    linked = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="related_to",
        metadata={"sym": True},
        idempotency_key="link-sym-1",
    )
    assert linked.kind == REFERENCE_SYMMETRIC_LINK_KIND
    # The stored/result pair is canonical min(id)/max(id).
    assert linked.from_reference_id == low
    assert linked.to_reference_id == high
    rows = _link_rows(env.writer)
    assert len(rows) == 1
    assert rows[0]["from_reference_id"] == low
    assert rows[0]["to_reference_id"] == high
    assert rows[0]["kind"] == "related_to"


def test_link_related_to_reversed_retry_converges(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    low, high = sorted((ref_a.id, ref_b.id))
    counts = _counts(env.writer)

    first = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="related_to",
        idempotency_key="link-converge",
    )
    # Reversed retry under the SAME key: the request hash canonicalizes the
    # pair before hashing, so this replays the stored result with zero new
    # rows — reversed retries converge on one canonical pair (SC10).
    second = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_b.id,
        to_reference_id=ref_a.id,
        kind="related_to",
        idempotency_key="link-converge",
    )
    assert second == first
    assert second.from_reference_id == low
    assert second.to_reference_id == high
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )
    assert len(_link_rows(env.writer)) == 1


def test_link_related_to_reversed_duplicate_rejected(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="related_to",
        idempotency_key="link-symdup-1",
    )
    # Reversed request under a NEW key: the canonical pair already exists,
    # so this is a typed duplicate before any write.
    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_b.id,
            to_reference_id=ref_a.id,
            kind="related_to",
            idempotency_key="link-symdup-2",
        )
    assert excinfo.value.detail == "duplicate"
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )


def test_link_directional_reversed_retry_mismatch(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="wears",
        idempotency_key="link-mismatch",
    )
    # Directional kinds keep their direction in the request identity, so a
    # reversed retry under the same key is a mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_b.id,
            to_reference_id=ref_a.id,
            kind="wears",
            idempotency_key="link-mismatch",
        )
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )
    assert len(_link_rows(env.writer)) == 1


def test_link_identical_retry_replays(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    first = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="associated_with",
        metadata={"k": "v"},
        idempotency_key="link-replay",
    )
    second = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="associated_with",
        metadata={"k": "v"},
        idempotency_key="link-replay",
    )
    assert second == first
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )


# ---------------------------------------------------------------------------
# link: pre-write rejections (zero rows changed)
# ---------------------------------------------------------------------------


def test_link_rejects_self_link(env) -> None:
    project = _create_project(env)
    ref_a, _ = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_a.id,
            kind="related_to",
            idempotency_key="link-self",
        )
    assert excinfo.value.detail == "self_link"
    assert _counts(env.writer) == counts


def test_link_rejects_missing_endpoints(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=generate_lowercase_ulid(),
            to_reference_id=ref_b.id,
            kind="located_in",
            idempotency_key="link-missingfrom",
        )
    assert excinfo.value.detail == "missing_from"

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=generate_lowercase_ulid(),
            kind="located_in",
            idempotency_key="link-missingto",
        )
    assert excinfo.value.detail == "missing_to"
    assert _counts(env.writer) == counts


def test_link_rejects_cross_project_pair(env) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    ref_a, _ = _seed_two_references(env, project_id=project_a.id, prefix="a")
    ref_b, _ = _seed_two_references(env, project_id=project_b.id, prefix="b")
    counts = _counts(env.writer)

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project_a.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind="associated_with",
            idempotency_key="link-cross",
        )
    assert excinfo.value.detail == "foreign_to"

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project_b.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind="associated_with",
            idempotency_key="link-cross2",
        )
    assert excinfo.value.detail == "foreign_from"
    assert _counts(env.writer) == counts


def test_link_rejects_archived_endpoints(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    _archive_reference(
        env, project_id=project.id, reference_id=ref_b.id, idempotency_key="arch-b"
    )
    counts = _counts(env.writer)

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind="belongs_to",
            idempotency_key="link-archto",
        )
    assert excinfo.value.detail == "archived_to"

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_b.id,
            to_reference_id=ref_a.id,
            kind="belongs_to",
            idempotency_key="link-archfrom",
        )
    assert excinfo.value.detail == "archived_from"
    assert _counts(env.writer) == counts


def test_link_rejects_bad_kind_and_metadata(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind="friend_of",
            idempotency_key="link-badkind",
        )
    assert excinfo.value.detail == "bad_kind"

    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind="belongs_to",
            metadata="not-an-object",
            idempotency_key="link-badmeta",
        )
    assert excinfo.value.detail == "bad_metadata"
    assert _counts(env.writer) == counts


def test_link_rejects_directional_duplicate(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    counts = _counts(env.writer)

    _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="wears",
        idempotency_key="link-dup-1",
    )
    with pytest.raises(ReferenceLinkError) as excinfo:
        _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind="wears",
            idempotency_key="link-dup-2",
        )
    assert excinfo.value.detail == "duplicate"
    assert _counts(env.writer) == (
        counts[0],
        counts[1],
        counts[2] + 1,
        counts[3] + 1,
        counts[4] + 1,
        counts[5],
        counts[6],
        counts[7],
    )


# ---------------------------------------------------------------------------
# link: heads, events, receipts, atomicity
# ---------------------------------------------------------------------------


def test_link_bounded_result_heads_events_and_receipt(env) -> None:
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    stream_a = f"{ref_a.id}:{REFERENCE_STREAM_TYPE}"
    stream_b = f"{ref_b.id}:{REFERENCE_STREAM_TYPE}"
    assert _stream_row(env.writer, stream_a)["head_seq"] == 1

    linked = _link(
        env,
        project_id=project.id,
        from_reference_id=ref_a.id,
        to_reference_id=ref_b.id,
        kind="located_in",
        metadata={"region": "north"},
        idempotency_key="link-heads",
    )
    # Bounded result: both affected ids plus kind/metadata/timestamp/head.
    assert linked.to_dict() == {
        "from_reference_id": ref_a.id,
        "to_reference_id": ref_b.id,
        "kind": "located_in",
        "metadata": {"region": "north"},
        "created_at": TS,
        "event_head_seq": 2,
    }

    # The from stream advanced; the to stream is untouched.
    assert _stream_row(env.writer, stream_a)["head_seq"] == 2
    assert _stream_row(env.writer, stream_b)["head_seq"] == 1

    # One reference.linked event carrying both affected reference ids.
    events = _event_rows(env.writer, stream_a)
    assert [e["kind"] for e in events] == ["reference.created", REFERENCE_LINKED_EVENT_KIND]
    data = json.loads(events[-1]["payload_json"])["data"]
    assert data == {
        "from_reference_id": ref_a.id,
        "to_reference_id": ref_b.id,
        "kind": "located_in",
        "metadata": {"region": "north"},
    }

    # One complete receipt keyed on the frozen link command kind.
    receipt = _receipt_row(env.writer, project.id, "link-heads")
    assert receipt["command_kind"] == REFERENCE_LINK_COMMAND_KIND
    assert receipt["primary_stream_id"] == stream_a
    assert receipt["resulting_stream_seq"] == 2
    assert json.loads(receipt["result_json"]) == linked.to_dict()


def test_link_statement_boundary_atomicity(tmp_path, standard_registry) -> None:
    """Representative crash mid-link leaves old-or-complete state."""
    root = tmp_path / "link-crash"
    root.mkdir()
    env2 = _fresh_namespace(root, standard_registry)
    try:
        project = _create_project(env2, project_id="crash-proj")
        ref_a, ref_b = _seed_two_references(env2, project_id=project.id)
        counts_before = _counts(env2.writer)

        # Crash after the reference_links INSERT: the whole command rolls
        # back (no row, no event, no receipt).
        outcome = _crash_run(
            env2.writer,
            kind=None,
            sql_sub="INSERT INTO reference_links",
            fn=lambda u: env2.reference_repo.link(
                u,
                project_id=project.id,
                from_reference_id=ref_a.id,
                to_reference_id=ref_b.id,
                kind="related_to",
                idempotency_key="link-crash-k",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        assert _counts(env2.writer) == counts_before

        # Crash at commit: old-or-complete (never a half-committed edge).
        outcome = _crash_run(
            env2.writer,
            kind="commit",
            sql_sub=None,
            fn=lambda u: env2.reference_repo.link(
                u,
                project_id=project.id,
                from_reference_id=ref_a.id,
                to_reference_id=ref_b.id,
                kind="related_to",
                idempotency_key="link-crash-k2",
                created_at=TS2,
            ),
        )
        assert outcome == "crashed"
        after = _counts(env2.writer)
        complete = (
            counts_before[0],
            counts_before[1],
            counts_before[2] + 1,
            counts_before[3] + 1,
            counts_before[4] + 1,
            counts_before[5],
            counts_before[6],
            counts_before[7],
        )
        assert after in (counts_before, complete)
    finally:
        env2.writer.close()


def test_all_five_link_kinds_are_frozen(env) -> None:
    """The five frozen kinds all round-trip through the link command."""
    project = _create_project(env)
    ref_a, ref_b = _seed_two_references(env, project_id=project.id)
    for index, kind in enumerate(REFERENCE_LINK_KINDS):
        result = _link(
            env,
            project_id=project.id,
            from_reference_id=ref_a.id,
            to_reference_id=ref_b.id,
            kind=kind,
            idempotency_key=f"link-kind-{index}",
        )
        assert result.kind == kind
    assert len(_link_rows(env.writer)) == len(REFERENCE_LINK_KINDS)
