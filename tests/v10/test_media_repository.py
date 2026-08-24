"""Media repository tests: atomic receipt-first prepared import (m2 plan step 4, T5).

T5 scope proves the media vertical's import root before locations/relations
extend it:

- one prepared import atomically commits the ``media`` read model, the
  ``media_locations`` projection, the ``core.media`` stream (created on first
  import, reused on dedupe), the ``core.media.imported`` event (hash-chained
  from genesis), both heads, and one complete receipt inside the caller's
  unit of work;
- project-scoped content-hash dedupe: two paths with identical bytes in one
  project produce one media row (and one location each), while the same
  digest in another project produces its own media row;
- receipt-first replay returns the stored result with zero new rows, and a
  changed digest under the same key fails before any mutation;
- managed publication lands at the exact frozen sharded path, ``external_local``
  is explicit and publishes nothing, and typed validation/not-found/conflict
  errors reject bad input before SQL.

T6 extends this file with replay/dedupe edge assertions and the
transaction-free show/list reads.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from astrid.core.events.service import payload_event_hash
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import (
    PreparedMedia,
    managed_media_path,
    prepare_external_local,
    prepare_media_file,
    staging_path,
)
from astrid.core.receipts import ReceiptMismatchError, request_hash
from astrid.core.repositories import (
    MediaAlreadyExistsError,
    MediaConflictError,
    MediaLocationReadModel,
    MediaNotFoundError,
    MediaReadModel,
    MediaRelateReadModel,
    MediaRelationError,
    MediaRelationReadModel,
    MediaRepositoryError,
    MediaValidationError,
)
from astrid.core.repositories.media import (
    CORE_MEDIA_IMPORT_COMMAND_KIND,
    CORE_MEDIA_IMPORTED_EVENT_KIND,
    CORE_MEDIA_LOCATION_REPLACED_EVENT_KIND,
    CORE_MEDIA_RELATE_COMMAND_KIND,
    CORE_MEDIA_RELATED_EVENT_KIND,
    CORE_MEDIA_REPLACE_LOCATION_COMMAND_KIND,
    CORE_MEDIA_STREAM_TYPE,
    CORE_MEDIA_VERIFIED_EVENT_KIND,
    CORE_MEDIA_VERIFY_COMMAND_KIND,
    EXTERNAL_LOCAL_REALM,
    MANAGED_LOCAL_REALM,
    MediaFingerprint,
    MediaLocationNotFoundError,
    MediaVerificationError,
    prepare_media_fingerprint,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-16T00:00:00.000000+00:00"
TS2 = "2026-08-16T01:00:00.000000+00:00"

_UUID4_HEX_RE = re.compile(r"^[0-9a-f]{32}$")

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


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


def _import(
    env,
    *,
    project_id: str,
    prepared: PreparedMedia,
    idempotency_key: str,
    media_id: str | None = None,
    **overrides,
):
    args = {
        "project_id": project_id,
        "prepared": prepared,
        "idempotency_key": idempotency_key,
        "media_id": media_id or generate_lowercase_ulid(),
        "created_at": TS,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.media_repo.import_prepared(u, **args))


def _counts(writer: DatabaseWriter) -> tuple[int, int, int, int, int]:
    """(projects, media, media_locations, events, command_receipts) counts."""
    return writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM projects")[0],
            session.query_one("SELECT count(*) FROM media")[0],
            session.query_one("SELECT count(*) FROM media_locations")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )


def _media_row(writer: DatabaseWriter, media_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM media WHERE id = ?", (media_id,)
        )
    )


def _location_rows(writer: DatabaseWriter, media_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT id, media_id, realm, locator, verified_at, created_at "
            "FROM media_locations WHERE media_id = ? ORDER BY created_at ASC, id ASC",
            (media_id,),
        )
    )


def _stream_row(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM event_streams WHERE id = ?", (stream_id,)
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


def _event_rows(writer: DatabaseWriter, stream_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        )
    )


# ---------------------------------------------------------------------------
# Atomic import state
# ---------------------------------------------------------------------------


def test_import_creates_atomic_media_state(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "in/shot.png", PNG_BYTES)
    prepared = prepare_media_file(source, root=media_env.projects_root / "in")

    counts_before = _counts(media_env.writer)
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="import-k-1",
    )
    counts_after = _counts(media_env.writer)
    # media +1, media_locations +1, events +1, receipts +1; the project row
    # already exists (its event_head_seq advances instead).
    assert counts_after == (
        counts_before[0],
        counts_before[1] + 1,
        counts_before[2] + 1,
        counts_before[3] + 1,
        counts_before[4] + 1,
    )

    row = _media_row(media_env.writer, media.id)
    assert row is not None
    assert row["project_id"] == project.id
    assert row["media_kind"] == "image"
    assert row["mime_type"] == "image/png"
    assert row["byte_size"] == len(PNG_BYTES)
    assert row["content_hash"] == prepared.digest
    assert json.loads(row["metadata_json"]) == {
        "rel_path": "shot.png",
        "probe": {
            "byte_size": len(PNG_BYTES),
            "extension": ".png",
            "is_empty": False,
        },
    }

    # The managed bytes landed at the exact frozen sharded path.
    managed = managed_media_path(media_env.projects_root, prepared.digest)
    assert managed.read_bytes() == PNG_BYTES
    assert managed.parent.name == prepared.digest[2:4]
    assert managed.parent.parent.name == prepared.digest[:2]

    locations = _location_rows(media_env.writer, media.id)
    assert len(locations) == 1
    assert locations[0]["realm"] == MANAGED_LOCAL_REALM
    assert locations[0]["locator"] == str(managed)
    assert locations[0]["verified_at"] == TS

    stream = _stream_row(media_env.writer, f"{media.id}:{CORE_MEDIA_STREAM_TYPE}")
    assert stream["stream_type"] == CORE_MEDIA_STREAM_TYPE
    assert stream["aggregate_id"] == media.id
    assert stream["head_seq"] == 1

    project_row = media_env.writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project.id,)
        )
    )
    assert project_row["event_head_seq"] == 2  # project.created + media.imported


def test_managed_import_rejects_noncanonical_locator_before_publication(media_env) -> None:
    """A managed row must always point at its digest-derived CAS object."""
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "in/noncanonical.png", PNG_BYTES)
    prepared = prepare_media_file(source, root=media_env.projects_root / "in")
    before = _counts(media_env.writer)

    with pytest.raises(MediaValidationError, match="digest-derived managed path"):
        _import(
            media_env,
            project_id=project.id,
            prepared=prepared,
            idempotency_key="managed-noncanonical-k",
            locator=str(media_env.projects_root / "elsewhere" / "asset.png"),
        )

    assert _counts(media_env.writer) == before
    assert not managed_media_path(media_env.projects_root, prepared.digest).exists()


def test_imported_event_is_registered_and_hash_chained(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"bytes"), root=media_env.projects_root / "in"
    )
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="import-event-k",
    )
    stream_id = f"{media.id}:{CORE_MEDIA_STREAM_TYPE}"
    events = _event_rows(media_env.writer, stream_id)
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == CORE_MEDIA_IMPORTED_EVENT_KIND
    assert event["subject_type"] == "media"
    assert event["subject_id"] == media.id
    assert event["project_seq"] == 2
    assert event["seq"] == 1
    payload = json.loads(event["payload_json"])
    integrity = payload["_integrity"]
    assert integrity["previous_event_hash"] is None
    assert payload_event_hash(payload) == integrity["event_hash"]
    data = payload["data"]
    assert data["media_id"] == media.id
    assert data["content_hash"] == prepared.digest
    assert data["media_kind"] == "other"  # .bin derives application/octet-stream
    assert data["realm"] == MANAGED_LOCAL_REALM
    assert data["locator"] == str(managed_media_path(media_env.projects_root, prepared.digest))
    assert data["reused"] is False
    assert json.loads(event["changes_json"]) == [
        "media_id",
        "content_hash",
        "media_kind",
        "mime_type",
        "byte_size",
        "realm",
        "locator",
    ]


def test_receipt_contents_are_complete(media_env) -> None:
    project = _create_project(media_env)
    media_id = generate_lowercase_ulid()
    key = "import-receipt-k"
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"receipt bytes"),
        root=media_env.projects_root / "in",
    )
    _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key=key,
        media_id=media_id,
    )
    receipt = _receipt_row(media_env.writer, project.id, key)
    assert receipt is not None
    assert receipt["command_kind"] == CORE_MEDIA_IMPORT_COMMAND_KIND
    expected_hash = request_hash(
        CORE_MEDIA_IMPORT_COMMAND_KIND,
        {
            "media_id": media_id,
            "content_hash": prepared.digest,
            "media_kind": prepared.media_kind,
            "mime_type": prepared.mime_type,
            "byte_size": prepared.byte_size,
            "realm": MANAGED_LOCAL_REALM,
            "locator": str(managed_media_path(media_env.projects_root, prepared.digest)),
        },
    )
    assert receipt["request_hash"] == expected_hash
    assert receipt["primary_stream_id"] == f"{media_id}:{CORE_MEDIA_STREAM_TYPE}"
    assert receipt["resulting_stream_seq"] == 1
    assert receipt["first_project_seq"] == 2
    assert receipt["last_project_seq"] == 2
    event_ids = json.loads(receipt["event_ids_json"])
    assert len(event_ids) == 1
    assert _UUID4_HEX_RE.fullmatch(event_ids[0]) is not None
    result = json.loads(receipt["result_json"])
    assert result["id"] == media_id
    assert result["content_hash"] == prepared.digest
    assert result["locations"][0]["realm"] == MANAGED_LOCAL_REALM


# ---------------------------------------------------------------------------
# Project-scoped byte dedupe (SD2)
# ---------------------------------------------------------------------------


def test_two_paths_identical_bytes_produce_one_media_row(media_env) -> None:
    project = _create_project(media_env)
    first_source = _write(media_env.projects_root, "a/one.png", PNG_BYTES)
    second_source = _write(media_env.projects_root, "b/two/nested.png", PNG_BYTES)
    first = prepare_media_file(first_source, root=media_env.projects_root / "a")
    second = prepare_media_file(second_source, root=media_env.projects_root / "b/two")
    assert first.digest == second.digest

    media_one = _import(
        media_env, project_id=project.id, prepared=first, idempotency_key="dedupe-k-1"
    )
    media_two = _import(
        media_env, project_id=project.id, prepared=second, idempotency_key="dedupe-k-2"
    )
    # One media row (the dedupe reuses the first row's id) and one managed
    # location (the managed locator is digest-derived); the stream is
    # reused, not duplicated.
    assert media_two.id == media_one.id
    assert _counts(media_env.writer)[1] == 1  # media rows
    locations = _location_rows(media_env.writer, media_one.id)
    assert len(locations) == 1
    assert locations[0]["locator"] == str(
        managed_media_path(media_env.projects_root, first.digest)
    )
    stream = _stream_row(media_env.writer, f"{media_one.id}:{CORE_MEDIA_STREAM_TYPE}")
    assert stream["head_seq"] == 2  # one imported event per import command
    events = _event_rows(media_env.writer, f"{media_one.id}:{CORE_MEDIA_STREAM_TYPE}")
    assert [e["seq"] for e in events] == [1, 2]
    # The second publication reuses the verified managed digest.
    assert json.loads(events[1]["payload_json"])["data"]["reused"] is True
    # The redundant staging quarantine was drained.
    assert not (
        staging_path(media_env.projects_root, events[1]["txn_id"]) / "b/two/nested.png"
    ).exists()


def test_external_dedupe_two_paths_one_media_row_two_locations(media_env) -> None:
    project = _create_project(media_env)
    first_source = _write(media_env.projects_root, "ext/one.bin", b"identical")
    second_source = _write(media_env.projects_root, "ext/two.bin", b"identical")
    first = prepare_external_local(first_source, root=media_env.projects_root / "ext")
    second = prepare_external_local(second_source, root=media_env.projects_root / "ext")
    assert first.digest == second.digest

    _import(
        media_env,
        project_id=project.id,
        prepared=first,
        idempotency_key="ext-dedupe-k-1",
        realm=EXTERNAL_LOCAL_REALM,
    )
    _import(
        media_env,
        project_id=project.id,
        prepared=second,
        idempotency_key="ext-dedupe-k-2",
        realm=EXTERNAL_LOCAL_REALM,
    )
    # One media row, two distinct external locations (one per path).
    assert _counts(media_env.writer)[1] == 1
    rows = media_env.media_repo.list(media_env.writer, project.id)
    assert len(rows[0].locations) == 2
    assert {loc.locator for loc in rows[0].locations} == {
        str(first_source),
        str(second_source),
    }


def test_dedupe_is_scoped_to_project(media_env) -> None:
    project_a = _create_project(media_env, slug="alpha")
    project_b = _create_project(media_env, slug="beta")
    prepared = prepare_media_file(
        _write(media_env.projects_root, "shared.bin", b"same bytes"),
        root=media_env.projects_root,
    )
    media_a = _import(
        media_env, project_id=project_a.id, prepared=prepared, idempotency_key="p-a-k"
    )
    media_b = _import(
        media_env, project_id=project_b.id, prepared=prepared, idempotency_key="p-b-k"
    )
    # Same digest, different project: two media rows (dedupe is project-scoped).
    assert media_a.id != media_b.id
    assert media_a.project_id == project_a.id
    assert media_b.project_id == project_b.id
    assert _counts(media_env.writer)[1] == 2


def test_exact_duplicate_location_is_typed_conflict(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "same.bin", b"conflict bytes")
    prepared = prepare_external_local(source, root=media_env.projects_root)
    _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="c-k-1",
        realm=EXTERNAL_LOCAL_REALM,
    )
    counts = _counts(media_env.writer)
    # Same project, same digest, same external (realm, locator) under a new
    # key: the media row and location already exist — a typed conflict, zero
    # mutation. (A managed dedupe is not a conflict: its locator is
    # digest-derived and shares the existing location.)
    with pytest.raises(MediaConflictError) as excinfo:
        _import(
            media_env,
            project_id=project.id,
            prepared=prepared,
            idempotency_key="c-k-2",
            realm=EXTERNAL_LOCAL_REALM,
        )
    assert excinfo.value.reason == "duplicate_location"
    assert _counts(media_env.writer) == counts


# ---------------------------------------------------------------------------
# Replay and mismatch (receipt-first)
# ---------------------------------------------------------------------------


def test_identical_replay_returns_stored_result_with_zero_new_rows(media_env) -> None:
    project = _create_project(media_env)
    media_id = generate_lowercase_ulid()
    key = "import-replay-k"
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"replay bytes"),
        root=media_env.projects_root / "in",
    )
    first = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key=key,
        media_id=media_id,
    )
    counts_after_first = _counts(media_env.writer)
    second = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key=key,
        media_id=media_id,
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(media_env.writer) == counts_after_first


def test_mismatch_fails_before_any_mutation(media_env) -> None:
    project = _create_project(media_env)
    media_id = generate_lowercase_ulid()
    key = "import-mismatch-k"
    original = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"original"),
        root=media_env.projects_root / "in",
    )
    _import(
        media_env,
        project_id=project.id,
        prepared=original,
        idempotency_key=key,
        media_id=media_id,
    )
    counts = _counts(media_env.writer)
    changed = prepare_media_file(
        _write(media_env.projects_root, "in/b.bin", b"changed bytes"),
        root=media_env.projects_root / "in",
    )
    with pytest.raises(ReceiptMismatchError):
        _import(
            media_env,
            project_id=project.id,
            prepared=changed,
            idempotency_key=key,
            media_id=media_id,
        )
    assert _counts(media_env.writer) == counts
    # The stored media row is unchanged.
    row = _media_row(media_env.writer, media_id)
    assert row["content_hash"] == original.digest


# ---------------------------------------------------------------------------
# Explicit external_local
# ---------------------------------------------------------------------------


def test_external_local_import_is_explicit_and_publishes_nothing(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "ext/shot.png", PNG_BYTES)
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")

    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="external-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    # No managed bytes were published for the external realm.
    assert not managed_media_path(media_env.projects_root, prepared.digest).exists()
    locations = _location_rows(media_env.writer, media.id)
    assert len(locations) == 1
    assert locations[0]["realm"] == EXTERNAL_LOCAL_REALM
    assert locations[0]["locator"] == str(source)
    assert locations[0]["verified_at"] is None
    # The event carries the external realm and no reused flag.
    event = _event_rows(media_env.writer, f"{media.id}:{CORE_MEDIA_STREAM_TYPE}")[0]
    data = json.loads(event["payload_json"])["data"]
    assert data["realm"] == EXTERNAL_LOCAL_REALM
    assert "reused" not in data


# ---------------------------------------------------------------------------
# Typed validation
# ---------------------------------------------------------------------------


def test_validation_rejects_malformed_imports(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "ok.bin", b"ok"), root=media_env.projects_root
    )

    def do_import(**overrides):
        args = {
            "project_id": project.id,
            "prepared": prepared,
            "idempotency_key": "v-k",
            "media_id": generate_lowercase_ulid(),
            "created_at": TS,
        }
        args.update(overrides)
        return UnitOfWork(media_env.writer).run(
            lambda u: media_env.media_repo.import_prepared(u, **args)
        )

    with pytest.raises(MediaValidationError):
        do_import(project_id="")
    with pytest.raises(MediaValidationError):
        do_import(prepared="not-a-prepared-record")
    with pytest.raises(MediaValidationError):
        do_import(idempotency_key="")
    with pytest.raises(MediaValidationError):
        do_import(actor_kind="scheduler")
    with pytest.raises(MediaConflictError):
        do_import(realm="s3")
    with pytest.raises(MediaValidationError):
        _import(
            media_env,
            project_id=generate_lowercase_ulid(),
            prepared=prepared,
            idempotency_key="v-unknown-project",
        )


def test_error_family_is_repository_typed(media_env) -> None:
    project = _create_project(media_env)
    with pytest.raises(MediaRepositoryError):
        _import(
            media_env,
            project_id=project.id,
            prepared="nope",
            idempotency_key="family-k",
        )


def test_duplicate_media_id_rejected(media_env) -> None:
    project = _create_project(media_env)
    media_id = generate_lowercase_ulid()
    first = prepare_media_file(
        _write(media_env.projects_root, "a.bin", b"first bytes"),
        root=media_env.projects_root,
    )
    second = prepare_media_file(
        _write(media_env.projects_root, "b.bin", b"second bytes"),
        root=media_env.projects_root,
    )
    _import(
        media_env,
        project_id=project.id,
        prepared=first,
        idempotency_key="dup-k-1",
        media_id=media_id,
    )
    counts = _counts(media_env.writer)
    with pytest.raises(MediaAlreadyExistsError):
        _import(
            media_env,
            project_id=project.id,
            prepared=second,
            idempotency_key="dup-k-2",
            media_id=media_id,
        )
    assert _counts(media_env.writer) == counts


# ---------------------------------------------------------------------------
# Frozen read models and transaction-free reads
# ---------------------------------------------------------------------------


def test_media_read_model_frozen_roundtrip(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"round trip"),
        root=media_env.projects_root / "in",
    )
    media = _import(
        media_env, project_id=project.id, prepared=prepared, idempotency_key="rt-k"
    )
    rebuilt = MediaReadModel.from_mapping(media.to_dict())
    assert rebuilt == media
    assert rebuilt.content_hash == prepared.digest
    assert rebuilt.media_kind == "other"  # .bin derives application/octet-stream
    assert len(rebuilt.locations) == 1
    location = rebuilt.locations[0]
    assert MediaLocationReadModel.from_mapping(location.to_dict()) == location
    assert location.realm == MANAGED_LOCAL_REALM


def test_show_returns_media_with_ordered_locations(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"show me"),
        root=media_env.projects_root / "in",
    )
    media = _import(
        media_env, project_id=project.id, prepared=prepared, idempotency_key="show-k"
    )
    shown = media_env.media_repo.show(media_env.writer, media.id)
    assert shown == media
    assert len(shown.locations) == 1
    with pytest.raises(MediaNotFoundError):
        media_env.media_repo.show(media_env.writer, generate_lowercase_ulid())


def test_list_is_project_scoped_and_ordered(media_env) -> None:
    project_a = _create_project(media_env, slug="alpha")
    project_b = _create_project(media_env, slug="beta")
    first = prepare_media_file(
        _write(media_env.projects_root, "a.bin", b"alpha first"),
        root=media_env.projects_root,
    )
    second = prepare_media_file(
        _write(media_env.projects_root, "b.bin", b"alpha second"),
        root=media_env.projects_root,
    )
    other = prepare_media_file(
        _write(media_env.projects_root, "c.bin", b"beta bytes"),
        root=media_env.projects_root,
    )
    _import(media_env, project_id=project_a.id, prepared=first, idempotency_key="l-a-1")
    _import(media_env, project_id=project_b.id, prepared=other, idempotency_key="l-b-1")
    _import(media_env, project_id=project_a.id, prepared=second, idempotency_key="l-a-2")

    rows = media_env.media_repo.list(media_env.writer, project_a.id)
    assert [row.content_hash for row in rows] == [first.digest, second.digest]
    assert all(row.project_id == project_a.id for row in rows)
    assert media_env.media_repo.list(media_env.writer, project_b.id)[0].content_hash == other.digest
    assert media_env.media_repo.list(media_env.writer, generate_lowercase_ulid()) == []


# ---------------------------------------------------------------------------
# Location replacement (m2 plan step 5, T7)
# ---------------------------------------------------------------------------


def _replace(
    env,
    *,
    project_id: str,
    media_id: str,
    idempotency_key: str,
    realm: str,
    locator: str,
    **overrides,
):
    """Run one replace_location command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "media_id": media_id,
        "idempotency_key": idempotency_key,
        "realm": realm,
        "locator": locator,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(
        lambda u: env.media_repo.replace_location(u, **args)
    )


def test_replace_external_location_changes_locator_and_keeps_identity(
    media_env,
) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "ext/one.bin", b"replace me")
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="replace-import-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    new_locator = str(media_env.projects_root / "ext" / "moved.bin")

    counts_before = _counts(media_env.writer)
    replaced = _replace(
        media_env,
        project_id=project.id,
        media_id=media.id,
        idempotency_key="replace-k",
        realm=EXTERNAL_LOCAL_REALM,
        locator=new_locator,
    )
    counts_after = _counts(media_env.writer)
    # Only the event and receipt rows grow; media and locations are stable.
    assert counts_after == (
        counts_before[0],
        counts_before[1],
        counts_before[2],
        counts_before[3] + 1,
        counts_before[4] + 1,
    )

    # Identity is untouched: same media id, digest, and derived facts.
    assert replaced.id == media.id
    assert replaced.content_hash == prepared.digest
    assert replaced.media_kind == media.media_kind
    assert replaced.byte_size == media.byte_size
    row = _media_row(media_env.writer, media.id)
    assert row["content_hash"] == prepared.digest
    assert row["created_at"] == TS  # the media row never changes

    # Only the locator projection changed (external: never verified).
    locations = _location_rows(media_env.writer, media.id)
    assert len(locations) == 1
    assert locations[0]["locator"] == new_locator
    assert locations[0]["verified_at"] is None
    assert locations[0]["created_at"] == TS
    assert replaced.locations[0].locator == new_locator
    assert replaced.locations[0].verified_at is None


def test_replace_managed_location_refreshes_verified_at(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"managed bytes"),
        root=media_env.projects_root / "in",
    )
    media = _import(
        media_env, project_id=project.id, prepared=prepared, idempotency_key="m-import-k"
    )
    canonical = str(managed_media_path(media_env.projects_root, prepared.digest))

    counts_before = _counts(media_env.writer)
    replaced = _replace(
        media_env,
        project_id=project.id,
        media_id=media.id,
        idempotency_key="m-replace-k",
        realm=MANAGED_LOCAL_REALM,
        locator=canonical,
    )
    counts_after = _counts(media_env.writer)
    # A managed replacement is a verified refresh: no new location row.
    assert counts_after == (
        counts_before[0],
        counts_before[1],
        counts_before[2],
        counts_before[3] + 1,
        counts_before[4] + 1,
    )
    locations = _location_rows(media_env.writer, media.id)
    assert len(locations) == 1
    assert locations[0]["locator"] == canonical
    assert locations[0]["verified_at"] == TS2  # re-stamped at replacement
    assert replaced.locations[0].locator == canonical
    assert replaced.locations[0].verified_at == TS2


def test_replace_location_rejects_foreign_project_and_unknown_media(
    media_env,
) -> None:
    project_a = _create_project(media_env, slug="alpha")
    project_b = _create_project(media_env, slug="beta")
    source = _write(media_env.projects_root, "ext/a.bin", b"ownership")
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")
    media = _import(
        media_env,
        project_id=project_a.id,
        prepared=prepared,
        idempotency_key="own-import-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    counts = _counts(media_env.writer)

    # The media belongs to project A; project B cannot see or replace it.
    with pytest.raises(MediaNotFoundError):
        _replace(
            media_env,
            project_id=project_b.id,
            media_id=media.id,
            idempotency_key="own-foreign-k",
            realm=EXTERNAL_LOCAL_REALM,
            locator="/tmp/elsewhere.bin",
        )
    # Unknown media ids are indistinguishable from foreign ones.
    with pytest.raises(MediaNotFoundError):
        _replace(
            media_env,
            project_id=project_a.id,
            media_id=generate_lowercase_ulid(),
            idempotency_key="own-unknown-k",
            realm=EXTERNAL_LOCAL_REALM,
            locator="/tmp/elsewhere.bin",
        )
    assert _counts(media_env.writer) == counts


def test_replace_location_managed_requires_canonical_path(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"canonical"),
        root=media_env.projects_root / "in",
    )
    media = _import(
        media_env, project_id=project.id, prepared=prepared, idempotency_key="c-import-k"
    )
    counts = _counts(media_env.writer)
    with pytest.raises(MediaValidationError):
        _replace(
            media_env,
            project_id=project.id,
            media_id=media.id,
            idempotency_key="c-bad-k",
            realm=MANAGED_LOCAL_REALM,
            locator="/tmp/not-the-managed-tree.bin",
        )
    # remote is not replaceable in m2 (only the local realms).
    with pytest.raises(MediaValidationError):
        _replace(
            media_env,
            project_id=project.id,
            media_id=media.id,
            idempotency_key="c-remote-k",
            realm="remote",
            locator="https://example.invalid/a.bin",
        )
    with pytest.raises(MediaValidationError):
        _replace(
            media_env,
            project_id=project.id,
            media_id=media.id,
            idempotency_key="c-empty-k",
            realm=EXTERNAL_LOCAL_REALM,
            locator="",
        )
    assert _counts(media_env.writer) == counts


def test_replace_location_missing_realm_is_typed_error(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"only managed"),
        root=media_env.projects_root / "in",
    )
    media = _import(
        media_env, project_id=project.id, prepared=prepared, idempotency_key="mr-import-k"
    )
    counts = _counts(media_env.writer)
    # The media was imported managed only: no external location to replace.
    with pytest.raises(MediaLocationNotFoundError) as excinfo:
        _replace(
            media_env,
            project_id=project.id,
            media_id=media.id,
            idempotency_key="mr-missing-k",
            realm=EXTERNAL_LOCAL_REALM,
            locator="/tmp/external.bin",
        )
    assert excinfo.value.realm == EXTERNAL_LOCAL_REALM
    assert _counts(media_env.writer) == counts


def test_replace_location_ambiguous_realm_is_typed_conflict(media_env) -> None:
    project = _create_project(media_env)
    first_source = _write(media_env.projects_root, "ext/a.bin", b"same bytes")
    second_source = _write(media_env.projects_root, "ext/b.bin", b"same bytes")
    first = prepare_external_local(first_source, root=media_env.projects_root / "ext")
    second = prepare_external_local(second_source, root=media_env.projects_root / "ext")
    media = _import(
        media_env,
        project_id=project.id,
        prepared=first,
        idempotency_key="amb-import-1",
        realm=EXTERNAL_LOCAL_REALM,
    )
    _import(
        media_env,
        project_id=project.id,
        prepared=second,
        idempotency_key="amb-import-2",
        realm=EXTERNAL_LOCAL_REALM,
    )
    assert len(_location_rows(media_env.writer, media.id)) == 2
    counts = _counts(media_env.writer)
    with pytest.raises(MediaConflictError) as excinfo:
        _replace(
            media_env,
            project_id=project.id,
            media_id=media.id,
            idempotency_key="amb-replace-k",
            realm=EXTERNAL_LOCAL_REALM,
            locator="/tmp/moved.bin",
        )
    assert excinfo.value.reason == "multiple_locations"
    assert _counts(media_env.writer) == counts


def test_replace_location_replay_and_mismatch(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "ext/a.bin", b"replay replace")
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="rp-import-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    locator_a = str(media_env.projects_root / "ext" / "moved-a.bin")
    locator_b = str(media_env.projects_root / "ext" / "moved-b.bin")
    key = "rp-replace-k"

    first = _replace(
        media_env,
        project_id=project.id,
        media_id=media.id,
        idempotency_key=key,
        realm=EXTERNAL_LOCAL_REALM,
        locator=locator_a,
    )
    counts_after_first = _counts(media_env.writer)
    # Identical retry: exact replay, zero new rows.
    second = _replace(
        media_env,
        project_id=project.id,
        media_id=media.id,
        idempotency_key=key,
        realm=EXTERNAL_LOCAL_REALM,
        locator=locator_a,
    )
    assert second == first
    assert second.to_dict() == first.to_dict()
    assert _counts(media_env.writer) == counts_after_first
    assert _location_rows(media_env.writer, media.id)[0]["locator"] == locator_a

    # Same key with a different locator: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _replace(
            media_env,
            project_id=project.id,
            media_id=media.id,
            idempotency_key=key,
            realm=EXTERNAL_LOCAL_REALM,
            locator=locator_b,
        )
    assert _counts(media_env.writer) == counts_after_first
    assert _location_rows(media_env.writer, media.id)[0]["locator"] == locator_a


def test_replace_location_event_is_registered_and_hash_chained(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "ext/a.bin", b"chain me")
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="ch-import-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    stream_id = f"{media.id}:{CORE_MEDIA_STREAM_TYPE}"
    imported_event = _event_rows(media_env.writer, stream_id)[0]
    imported_hash = json.loads(imported_event["payload_json"])["_integrity"]["event_hash"]
    new_locator = str(media_env.projects_root / "moved.bin")

    _replace(
        media_env,
        project_id=project.id,
        media_id=media.id,
        idempotency_key="ch-replace-k",
        realm=EXTERNAL_LOCAL_REALM,
        locator=new_locator,
    )

    events = _event_rows(media_env.writer, stream_id)
    assert len(events) == 2
    event = events[1]
    assert event["kind"] == CORE_MEDIA_LOCATION_REPLACED_EVENT_KIND
    assert event["subject_type"] == "media"
    assert event["subject_id"] == media.id
    assert event["seq"] == 2
    assert event["project_seq"] == 3  # project.created, imported, replaced
    payload = json.loads(event["payload_json"])
    integrity = payload["_integrity"]
    assert integrity["previous_event_hash"] == imported_hash
    assert payload_event_hash(payload) == integrity["event_hash"]
    data = payload["data"]
    assert data["media_id"] == media.id
    assert data["content_hash"] == prepared.digest
    assert data["realm"] == EXTERNAL_LOCAL_REALM
    assert data["locator"] == new_locator
    assert data["previous_locator"] == str(source)
    assert data["verified_at"] is None

    # Stream and project heads advanced exactly once.
    stream = _stream_row(media_env.writer, stream_id)
    assert stream["head_seq"] == 2
    project_row = media_env.writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project.id,)
        )
    )
    assert project_row["event_head_seq"] == 3

    # One complete receipt with the exact project sequence and event id.
    receipt = _receipt_row(media_env.writer, project.id, "ch-replace-k")
    assert receipt is not None
    assert receipt["command_kind"] == CORE_MEDIA_REPLACE_LOCATION_COMMAND_KIND
    assert receipt["first_project_seq"] == 3
    assert receipt["last_project_seq"] == 3
    assert receipt["resulting_stream_seq"] == 2
    event_ids = json.loads(receipt["event_ids_json"])
    assert event_ids == [event["event_id"]]
    result = json.loads(receipt["result_json"])
    assert result["id"] == media.id
    assert result["content_hash"] == prepared.digest
    assert result["locations"][0]["locator"] == new_locator
    expected_hash = request_hash(
        CORE_MEDIA_REPLACE_LOCATION_COMMAND_KIND,
        {
            "media_id": media.id,
            "realm": EXTERNAL_LOCAL_REALM,
            "locator": new_locator,
        },
    )
    assert receipt["request_hash"] == expected_hash


# ---------------------------------------------------------------------------
# Media relations (m2 plan step 5, T8)
# ---------------------------------------------------------------------------


def _import_three(env, *, project_id: str):
    """Import three distinct media files and return their read models."""
    models = []
    for name, data in (
        ("a.bin", b"relation bytes a"),
        ("b.bin", b"relation bytes b"),
        ("c.bin", b"relation bytes c"),
    ):
        source = _write(env.projects_root, f"rel/{name}", data)
        prepared = prepare_media_file(source, root=env.projects_root / "rel")
        models.append(
            _import(
                env,
                project_id=project_id,
                prepared=prepared,
                idempotency_key=f"rel-import-{name}",
            )
        )
    return models


def _relate(
    env,
    *,
    project_id: str,
    relations,
    idempotency_key: str,
    **overrides,
):
    """Run one relate command inside its own unit of work."""
    args = {
        "project_id": project_id,
        "relations": relations,
        "idempotency_key": idempotency_key,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.media_repo.relate(u, **args))


def _relation_rows(writer: DatabaseWriter, project_id: str):
    return writer.submit(
        lambda session: session.query(
            "SELECT r.from_media_id, r.to_media_id, r.kind, r.ordinal, "
            "r.metadata_json, r.created_at FROM media_relations r "
            "JOIN media m ON m.id = r.from_media_id "
            "WHERE m.project_id = ? "
            "ORDER BY r.ordinal ASC, r.from_media_id ASC, "
            "r.to_media_id ASC, r.kind ASC",
            (project_id,),
        )
    )


def test_relate_materializes_relations_in_ordinal_order_atomically(media_env) -> None:
    project = _create_project(media_env)
    first, second, third = _import_three(media_env, project_id=project.id)
    counts_before = _counts(media_env.writer)

    # Scrambled ordinals: materialization must follow ordinal order, not
    # caller order.
    result = _relate(
        media_env,
        project_id=project.id,
        idempotency_key="relate-k-1",
        relations=[
            {
                "from_media_id": first.id,
                "to_media_id": third.id,
                "kind": "derived_from",
                "ordinal": 2,
                "metadata": {"pass": 2},
            },
            {
                "from_media_id": second.id,
                "to_media_id": first.id,
                "kind": "variant_of",
                "ordinal": 0,
            },
            {
                "from_media_id": first.id,
                "to_media_id": second.id,
                "kind": "uses_as_input",
                "ordinal": 1,
            },
        ],
    )
    counts_after = _counts(media_env.writer)
    # media +0, locations +0, relations +3 (not counted by _counts), events
    # +3, receipts +1.
    assert counts_after == (
        counts_before[0],
        counts_before[1],
        counts_before[2],
        counts_before[3] + 3,
        counts_before[4] + 1,
    )

    # Projection rows materialize in ordinal order with exact metadata.
    rows = _relation_rows(media_env.writer, project.id)
    assert [(r["ordinal"], r["kind"]) for r in rows] == [
        (0, "variant_of"),
        (1, "uses_as_input"),
        (2, "derived_from"),
    ]
    assert rows[0]["from_media_id"] == second.id and rows[0]["to_media_id"] == first.id
    assert rows[1]["from_media_id"] == first.id and rows[1]["to_media_id"] == second.id
    assert rows[2]["from_media_id"] == first.id and rows[2]["to_media_id"] == third.id
    assert json.loads(rows[2]["metadata_json"]) == {"pass": 2}
    assert rows[0]["created_at"] == TS2

    # The read model mirrors the projection rows in ordinal order.
    assert [r.ordinal for r in result.relations] == [0, 1, 2]
    assert result.relations[0].kind == "variant_of"
    assert result.relations[0].metadata == {}
    rebuilt = MediaRelateReadModel.from_mapping(result.to_dict())
    assert rebuilt == result

    # One core.media.related event per edge, in ordinal order, on each
    # from-media's stream; project sequences are contiguous.
    events = _event_rows(media_env.writer, f"{first.id}:{CORE_MEDIA_STREAM_TYPE}")
    assert [e["kind"] for e in events] == [
        CORE_MEDIA_IMPORTED_EVENT_KIND,
        CORE_MEDIA_RELATED_EVENT_KIND,
        CORE_MEDIA_RELATED_EVENT_KIND,
    ]
    assert [e["seq"] for e in events] == [1, 2, 3]
    variant_events = _event_rows(
        media_env.writer, f"{second.id}:{CORE_MEDIA_STREAM_TYPE}"
    )
    assert variant_events[-1]["kind"] == CORE_MEDIA_RELATED_EVENT_KIND
    assert variant_events[-1]["seq"] == 2

    related = events[1:]
    assert [json.loads(e["payload_json"])["data"]["ordinal"] for e in related] == [1, 2]
    assert related[0]["project_seq"] + 1 == related[1]["project_seq"]
    # Hash chain: each related event chains from its stream's previous tail.
    for event in related:
        payload = json.loads(event["payload_json"])
        assert payload_event_hash(payload) == payload["_integrity"]["event_hash"]
    assert (
        json.loads(related[0]["payload_json"])["_integrity"]["previous_event_hash"]
        is not None
    )
    assert json.loads(related[1]["payload_json"])["data"]["metadata"] == {"pass": 2}

    # All three relate events, in ordinal (project-seq) order, one per edge.
    all_related = media_env.writer.submit(
        lambda session: session.query(
            "SELECT * FROM events WHERE kind = ? ORDER BY project_seq ASC",
            (CORE_MEDIA_RELATED_EVENT_KIND,),
        )
    )
    assert len(all_related) == 3
    assert [json.loads(e["payload_json"])["data"]["ordinal"] for e in all_related] == [
        0,
        1,
        2,
    ]
    assert [e["project_seq"] for e in all_related] == list(
        range(all_related[0]["project_seq"], all_related[0]["project_seq"] + 3)
    )
    assert all_related[0]["stream_id"] == f"{second.id}:{CORE_MEDIA_STREAM_TYPE}"
    assert all_related[1]["stream_id"] == f"{first.id}:{CORE_MEDIA_STREAM_TYPE}"
    assert all_related[2]["stream_id"] == f"{first.id}:{CORE_MEDIA_STREAM_TYPE}"
    # The variant edge event carries its full edge payload.
    variant_payload = json.loads(all_related[0]["payload_json"])["data"]
    assert variant_payload["from_media_id"] == second.id
    assert variant_payload["to_media_id"] == first.id
    assert variant_payload["kind"] == "variant_of"

    # Both affected media streams' heads and the project head advanced.
    assert _stream_row(media_env.writer, f"{first.id}:{CORE_MEDIA_STREAM_TYPE}")["head_seq"] == 3
    assert _stream_row(media_env.writer, f"{second.id}:{CORE_MEDIA_STREAM_TYPE}")["head_seq"] == 2
    assert _stream_row(media_env.writer, f"{third.id}:{CORE_MEDIA_STREAM_TYPE}")["head_seq"] == 1
    project_row = media_env.writer.submit(
        lambda session: session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project.id,)
        )
    )
    # project.created + 3 imports + 3 relates = 7 events.
    assert project_row["event_head_seq"] == 7

    # The one complete receipt spans the whole event range with the exact
    # ordered event ids and the primary stream's resulting head.
    receipt = _receipt_row(media_env.writer, project.id, "relate-k-1")
    assert receipt["command_kind"] == CORE_MEDIA_RELATE_COMMAND_KIND
    assert receipt["first_project_seq"] == all_related[0]["project_seq"]
    assert receipt["last_project_seq"] == all_related[-1]["project_seq"]
    # Primary stream = the first relation's from-media stream (second); its
    # head advanced from 1 (import) to 2 (the variant_of event).
    assert receipt["primary_stream_id"] == f"{second.id}:{CORE_MEDIA_STREAM_TYPE}"
    assert receipt["resulting_stream_seq"] == 2
    event_ids = json.loads(receipt["event_ids_json"])
    assert event_ids == [e["event_id"] for e in all_related]
    assert _UUID4_HEX_RE.fullmatch(event_ids[0]) is not None
    stored_result = json.loads(receipt["result_json"])
    assert MediaRelateReadModel.from_mapping(stored_result) == result
    expected_hash = request_hash(
        CORE_MEDIA_RELATE_COMMAND_KIND,
        {
            "relations": [
                {
                    "from_media_id": second.id,
                    "to_media_id": first.id,
                    "kind": "variant_of",
                    "ordinal": 0,
                    "metadata": {},
                },
                {
                    "from_media_id": first.id,
                    "to_media_id": second.id,
                    "kind": "uses_as_input",
                    "ordinal": 1,
                    "metadata": {},
                },
                {
                    "from_media_id": first.id,
                    "to_media_id": third.id,
                    "kind": "derived_from",
                    "ordinal": 2,
                    "metadata": {"pass": 2},
                },
            ]
        },
    )
    assert receipt["request_hash"] == expected_hash


def test_relate_rejects_unknown_kind_before_sql(media_env) -> None:
    project = _create_project(media_env)
    first, second, _ = _import_three(media_env, project_id=project.id)
    counts = _counts(media_env.writer)
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-kind-k",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": second.id,
                    "kind": "sibling",
                    "ordinal": 0,
                }
            ],
        )
    assert excinfo.value.reason == "kind"
    assert _counts(media_env.writer) == counts
    assert _relation_rows(media_env.writer, project.id) == []


def test_relate_rejects_self_link_before_sql(media_env) -> None:
    project = _create_project(media_env)
    first, _, _ = _import_three(media_env, project_id=project.id)
    counts = _counts(media_env.writer)
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-self-k",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": first.id,
                    "kind": "uses_as_input",
                    "ordinal": 0,
                }
            ],
        )
    assert excinfo.value.reason == "self"
    assert _counts(media_env.writer) == counts
    assert _relation_rows(media_env.writer, project.id) == []


def test_relate_rejects_cross_project_and_unknown_endpoints(media_env) -> None:
    project_a = _create_project(media_env, slug="alpha")
    project_b = _create_project(media_env, slug="beta")
    first, second, _ = _import_three(media_env, project_id=project_a.id)
    foreign, _, _ = _import_three(media_env, project_id=project_b.id)
    counts = _counts(media_env.writer)

    # A foreign endpoint is indistinguishable from an unknown one.
    with pytest.raises(MediaNotFoundError):
        _relate(
            media_env,
            project_id=project_a.id,
            idempotency_key="relate-foreign-k",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": foreign.id,
                    "kind": "derived_from",
                    "ordinal": 0,
                }
            ],
        )
    with pytest.raises(MediaNotFoundError):
        _relate(
            media_env,
            project_id=project_a.id,
            idempotency_key="relate-unknown-k",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": generate_lowercase_ulid(),
                    "kind": "derived_from",
                    "ordinal": 0,
                }
            ],
        )
    assert _counts(media_env.writer) == counts
    assert _relation_rows(media_env.writer, project_a.id) == []
    assert _relation_rows(media_env.writer, project_b.id) == []


def test_relate_rejects_duplicate_edges_before_sql(media_env) -> None:
    project = _create_project(media_env)
    first, second, _ = _import_three(media_env, project_id=project.id)
    counts = _counts(media_env.writer)

    # The same edge declared twice in one command.
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-dup-in-k",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": second.id,
                    "kind": "derived_from",
                    "ordinal": 0,
                },
                {
                    "from_media_id": first.id,
                    "to_media_id": second.id,
                    "kind": "derived_from",
                    "ordinal": 0,
                },
            ],
        )
    assert excinfo.value.reason == "duplicate"
    assert _counts(media_env.writer) == counts
    assert _relation_rows(media_env.writer, project.id) == []

    # A committed edge re-requested under a new key.
    _relate(
        media_env,
        project_id=project.id,
        idempotency_key="relate-ok-k",
        relations=[
            {
                "from_media_id": first.id,
                "to_media_id": second.id,
                "kind": "derived_from",
                "ordinal": 0,
            }
        ],
    )
    counts = _counts(media_env.writer)
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-dup-existing-k",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": second.id,
                    "kind": "derived_from",
                    "ordinal": 0,
                }
            ],
        )
    assert excinfo.value.reason == "duplicate"
    assert _counts(media_env.writer) == counts
    assert len(_relation_rows(media_env.writer, project.id)) == 1


def test_relate_enforces_one_variant_parent(media_env) -> None:
    project = _create_project(media_env)
    first, second, third = _import_three(media_env, project_id=project.id)

    # second variant_of first is the one parent for second.
    _relate(
        media_env,
        project_id=project.id,
        idempotency_key="relate-parent-1",
        relations=[
            {
                "from_media_id": second.id,
                "to_media_id": first.id,
                "kind": "variant_of",
                "ordinal": 0,
            }
        ],
    )
    counts = _counts(media_env.writer)
    # A second variant_of parent for the same from-media is rejected, even
    # though the unique index would also reject it at commit.
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-parent-2",
            relations=[
                {
                    "from_media_id": second.id,
                    "to_media_id": third.id,
                    "kind": "variant_of",
                    "ordinal": 1,
                }
            ],
        )
    assert excinfo.value.reason == "single_parent"
    assert _counts(media_env.writer) == counts
    assert len(_relation_rows(media_env.writer, project.id)) == 1

    # Two variant_of edges from the same media in one command: rejected.
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-parent-3",
            relations=[
                {
                    "from_media_id": third.id,
                    "to_media_id": first.id,
                    "kind": "variant_of",
                    "ordinal": 0,
                },
                {
                    "from_media_id": third.id,
                    "to_media_id": second.id,
                    "kind": "variant_of",
                    "ordinal": 1,
                },
            ],
        )
    assert excinfo.value.reason == "single_parent"
    assert len(_relation_rows(media_env.writer, project.id)) == 1


def test_relate_rejects_variant_cycles(media_env) -> None:
    project = _create_project(media_env)
    first, second, third = _import_three(media_env, project_id=project.id)

    # Chain: third variant_of second, second variant_of first (acyclic).
    _relate(
        media_env,
        project_id=project.id,
        idempotency_key="relate-chain-1",
        relations=[
            {
                "from_media_id": third.id,
                "to_media_id": second.id,
                "kind": "variant_of",
                "ordinal": 0,
            },
            {
                "from_media_id": second.id,
                "to_media_id": first.id,
                "kind": "variant_of",
                "ordinal": 0,
            },
        ],
    )
    counts = _counts(media_env.writer)
    # Closing the cycle (first variant_of third) is rejected before SQL.
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-cycle-1",
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": third.id,
                    "kind": "variant_of",
                    "ordinal": 0,
                }
            ],
        )
    assert excinfo.value.reason == "cycle"
    assert _counts(media_env.writer) == counts
    assert len(_relation_rows(media_env.writer, project.id)) == 2

    # A two-edge cycle entirely inside one command is also rejected (the
    # chain above already gave first/second/third parents, so use fresh
    # media for the in-command cycle).
    fresh_a = _import(
        media_env,
        project_id=project.id,
        prepared=prepare_media_file(
            _write(media_env.projects_root, "rel/cycle-a.bin", b"cycle a"),
            root=media_env.projects_root / "rel",
        ),
        idempotency_key="rel-import-cycle-a",
    )
    fresh_b = _import(
        media_env,
        project_id=project.id,
        prepared=prepare_media_file(
            _write(media_env.projects_root, "rel/cycle-b.bin", b"cycle b"),
            root=media_env.projects_root / "rel",
        ),
        idempotency_key="rel-import-cycle-b",
    )
    with pytest.raises(MediaRelationError) as excinfo:
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key="relate-cycle-2",
            relations=[
                {
                    "from_media_id": fresh_a.id,
                    "to_media_id": fresh_b.id,
                    "kind": "variant_of",
                    "ordinal": 0,
                },
                {
                    "from_media_id": fresh_b.id,
                    "to_media_id": fresh_a.id,
                    "kind": "variant_of",
                    "ordinal": 1,
                },
            ],
        )
    assert excinfo.value.reason == "cycle"
    assert len(_relation_rows(media_env.writer, project.id)) == 2


def test_relate_replay_and_mismatch(media_env) -> None:
    project = _create_project(media_env)
    first, second, _ = _import_three(media_env, project_id=project.id)
    relations = [
        {
            "from_media_id": first.id,
            "to_media_id": second.id,
            "kind": "derived_from",
            "ordinal": 0,
            "metadata": {"note": "replay"},
        }
    ]
    key = "relate-replay-k"
    first_result = _relate(
        media_env, project_id=project.id, relations=relations, idempotency_key=key
    )
    counts = _counts(media_env.writer)

    # Identical retry: exact replay, zero new rows.
    second_result = _relate(
        media_env, project_id=project.id, relations=relations, idempotency_key=key
    )
    assert second_result == first_result
    assert second_result.to_dict() == first_result.to_dict()
    assert _counts(media_env.writer) == counts
    assert len(_relation_rows(media_env.writer, project.id)) == 1

    # Same key with a different relation set: mismatch before any mutation.
    with pytest.raises(ReceiptMismatchError):
        _relate(
            media_env,
            project_id=project.id,
            idempotency_key=key,
            relations=[
                {
                    "from_media_id": first.id,
                    "to_media_id": second.id,
                    "kind": "uses_as_input",
                    "ordinal": 0,
                }
            ],
        )
    assert _counts(media_env.writer) == counts
    assert len(_relation_rows(media_env.writer, project.id)) == 1
    assert _relation_rows(media_env.writer, project.id)[0]["kind"] == "derived_from"


def test_relate_read_model_roundtrip_and_validation(media_env) -> None:
    relation = MediaRelationReadModel(
        from_media_id="m1",
        to_media_id="m2",
        kind="mask_for",
        ordinal=3,
        metadata={"alpha": 1},
        created_at=TS,
    )
    assert MediaRelationReadModel.from_mapping(relation.to_dict()) == relation
    with pytest.raises(MediaValidationError):
        MediaRelationReadModel(
            from_media_id="m1",
            to_media_id="m1",
            kind="mask_for",
            ordinal=0,
            metadata={},
            created_at=TS,
        )
    with pytest.raises(MediaValidationError):
        MediaRelationReadModel(
            from_media_id="m1",
            to_media_id="m2",
            kind="sibling",
            ordinal=0,
            metadata={},
            created_at=TS,
        )
    with pytest.raises(MediaValidationError):
        _relate(
            media_env,
            project_id=generate_lowercase_ulid(),
            idempotency_key="relate-empty-k",
            relations=[],
        )


# ---------------------------------------------------------------------------
# Project-scoped media resolution (m4 plan step 9, task T10)
# ---------------------------------------------------------------------------


def test_resolve_media_by_id_within_project_returns_canonical_id(media_env) -> None:
    project = _create_project(media_env)
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"resolve by id"),
        root=media_env.projects_root / "in",
    )
    media = _import(
        media_env, project_id=project.id, prepared=prepared, idempotency_key="r-id-k"
    )

    resolved = media_env.writer.submit(
        lambda session: media_env.media_repo.resolve_media(
            session, project_id=project.id, media_id=media.id
        )
    )
    assert resolved == media.id


def test_resolve_media_by_id_cross_project_is_not_found(media_env) -> None:
    project_a = _create_project(media_env, slug="alpha")
    project_b = _create_project(media_env, slug="beta")
    prepared = prepare_media_file(
        _write(media_env.projects_root, "in/a.bin", b"foreign id"),
        root=media_env.projects_root / "in",
    )
    media_a = _import(
        media_env, project_id=project_a.id, prepared=prepared, idempotency_key="r-fid-k"
    )

    # A media id from another project is indistinguishable from unknown.
    with pytest.raises(MediaNotFoundError) as excinfo:
        media_env.writer.submit(
            lambda session: media_env.media_repo.resolve_media(
                session, project_id=project_b.id, media_id=media_a.id
            )
        )
    assert excinfo.value.media_id == media_a.id


def test_resolve_media_by_locator_alias_within_project(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "ext/a.bin", b"locator alias")
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="r-loc-k",
        realm=EXTERNAL_LOCAL_REALM,
    )

    resolved = media_env.writer.submit(
        lambda session: media_env.media_repo.resolve_media(
            session,
            project_id=project.id,
            realm=EXTERNAL_LOCAL_REALM,
            locator=str(source),
        )
    )
    assert resolved == media.id


def test_resolve_media_by_locator_alias_cross_project_is_not_found(media_env) -> None:
    """A locator alias is never globally unique; resolution is project-scoped.

    This is the CF-0E82 regression: the locator lookup must join
    ``media_locations`` to ``media`` and require ``media.project_id`` to
    equal the route project. The same locator existing in another project
    must never resolve here (and a foreign-only locator is not_found).
    """
    project_a = _create_project(media_env, slug="alpha")
    project_b = _create_project(media_env, slug="beta")
    source = _write(media_env.projects_root, "ext/shared.bin", b"shared locator")
    prepared = prepare_external_local(source, root=media_env.projects_root / "ext")
    media_a = _import(
        media_env,
        project_id=project_a.id,
        prepared=prepared,
        idempotency_key="r-shared-a-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    media_b = _import(
        media_env,
        project_id=project_b.id,
        prepared=prepared,
        idempotency_key="r-shared-b-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    assert media_a.id != media_b.id

    # The same locator resolves to each project's own media row.
    resolved_a = media_env.writer.submit(
        lambda session: media_env.media_repo.resolve_media(
            session,
            project_id=project_a.id,
            realm=EXTERNAL_LOCAL_REALM,
            locator=str(source),
        )
    )
    assert resolved_a == media_a.id
    resolved_b = media_env.writer.submit(
        lambda session: media_env.media_repo.resolve_media(
            session,
            project_id=project_b.id,
            realm=EXTERNAL_LOCAL_REALM,
            locator=str(source),
        )
    )
    assert resolved_b == media_b.id

    # A locator that exists only in another project is not_found here.
    foreign_source = _write(media_env.projects_root, "ext/foreign.bin", b"foreign")
    foreign_prepared = prepare_external_local(
        foreign_source, root=media_env.projects_root / "ext"
    )
    _import(
        media_env,
        project_id=project_a.id,
        prepared=foreign_prepared,
        idempotency_key="r-foreign-k",
        realm=EXTERNAL_LOCAL_REALM,
    )
    with pytest.raises(MediaNotFoundError):
        media_env.writer.submit(
            lambda session: media_env.media_repo.resolve_media(
                session,
                project_id=project_b.id,
                realm=EXTERNAL_LOCAL_REALM,
                locator=str(foreign_source),
            )
        )


def test_resolve_media_requires_exactly_one_form(media_env) -> None:
    project = _create_project(media_env)

    with pytest.raises(MediaValidationError):
        media_env.writer.submit(
            lambda session: media_env.media_repo.resolve_media(
                session, project_id=project.id
            )
        )
    with pytest.raises(MediaValidationError):
        media_env.writer.submit(
            lambda session: media_env.media_repo.resolve_media(
                session,
                project_id=project.id,
                media_id=generate_lowercase_ulid(),
                realm=EXTERNAL_LOCAL_REALM,
                locator="/tmp/x.bin",
            )
        )
    # A locator alias requires both realm and locator.
    with pytest.raises(MediaValidationError):
        media_env.writer.submit(
            lambda session: media_env.media_repo.resolve_media(
                session, project_id=project.id, realm=EXTERNAL_LOCAL_REALM
            )
        )


# ---------------------------------------------------------------------------
# Stable verification (m4 plan step 10)
# ---------------------------------------------------------------------------


def _verify(
    env,
    *,
    project_id: str,
    media_id: str,
    realm: str,
    idempotency_key: str,
    fingerprint: MediaFingerprint,
    **overrides,
):
    args = {
        "project_id": project_id,
        "media_id": media_id,
        "realm": realm,
        "idempotency_key": idempotency_key,
        "fingerprint": fingerprint,
        "created_at": TS2,
    }
    args.update(overrides)
    return UnitOfWork(env.writer).run(lambda u: env.media_repo.verify(u, **args))


def _managed_media(env, *, key: str = "import-k-1"):
    """Import one managed PNG and return ``(project, media)``."""
    project = _create_project(env)
    source = _write(env.projects_root, "in/shot.png", PNG_BYTES)
    prepared = prepare_media_file(source, root=env.projects_root / "in")
    media = _import(env, project_id=project.id, prepared=prepared, idempotency_key=key)
    return project, media


def test_verify_stamps_location_appends_event_and_writes_receipt(media_env) -> None:
    project, media = _managed_media(media_env)
    media_id = media.id
    locator = media.locations[0].locator

    fingerprint = prepare_media_fingerprint(locator)
    before = _counts(media_env.writer)

    result = _verify(
        media_env,
        project_id=project.id,
        media_id=media_id,
        realm=MANAGED_LOCAL_REALM,
        idempotency_key="verify-k-1",
        fingerprint=fingerprint,
    )

    # Exactly one new event and one new receipt; no new media/location rows.
    after = _counts(media_env.writer)
    assert (after[1], after[2]) == (before[1], before[2])
    assert after[3] == before[3] + 1
    assert after[4] == before[4] + 1

    # The location's verification stamp advanced to the command instant.
    loc_rows = _location_rows(media_env.writer, media_id)
    assert len(loc_rows) == 1
    assert loc_rows[0]["verified_at"] == TS2

    # The returned read model carries the refreshed stamp.
    assert result.locations[0].verified_at == TS2

    # The verified event landed on the media stream in order.
    stream_id = f"{media_id}:{CORE_MEDIA_STREAM_TYPE}"
    events = _event_rows(media_env.writer, stream_id)
    assert [str(row["kind"]) for row in events] == [
        CORE_MEDIA_IMPORTED_EVENT_KIND,
        CORE_MEDIA_VERIFIED_EVENT_KIND,
    ]
    # Both heads advanced exactly one.
    stream = _stream_row(media_env.writer, stream_id)
    assert int(stream["head_seq"]) == 2

    # The receipt is keyed on the verify command kind.
    receipt = _receipt_row(media_env.writer, project.id, "verify-k-1")
    assert receipt["command_kind"] == CORE_MEDIA_VERIFY_COMMAND_KIND


def test_verify_mutated_bytes_cause_zero_mutation(media_env) -> None:
    project, media = _managed_media(media_env)
    locator = media.locations[0].locator

    # Prepare the fingerprint, then mutate the bytes (size change).
    fingerprint = prepare_media_fingerprint(locator)
    Path(locator).write_bytes(PNG_BYTES + b"mutated")
    before = _counts(media_env.writer)

    with pytest.raises(MediaVerificationError):
        _verify(
            media_env,
            project_id=project.id,
            media_id=media.id,
            realm=MANAGED_LOCAL_REALM,
            idempotency_key="verify-k-1",
            fingerprint=fingerprint,
        )

    # Zero mutation: no new event, head, projection, or receipt change, and
    # the location stamp stays at the import instant (TS), not the command.
    assert _counts(media_env.writer) == before
    loc_rows = _location_rows(media_env.writer, media.id)
    assert loc_rows[0]["verified_at"] == TS


def test_verify_same_size_replacement_detected_by_rehash(media_env) -> None:
    project, media = _managed_media(media_env)
    locator = media.locations[0].locator

    fingerprint = prepare_media_fingerprint(locator)
    # Replace with same-size, different bytes, then restore the mtime so only
    # the content re-hash can detect the change (the TOCTOU race).
    replacement = b"\x89PNG\r\n\x1a\n" + b"\x01" * 16
    assert len(replacement) == len(PNG_BYTES)
    path = Path(locator)
    path.write_bytes(replacement)
    os.utime(path, ns=(path.stat().st_atime_ns, fingerprint.mtime_ns))
    before = _counts(media_env.writer)

    with pytest.raises(MediaVerificationError):
        _verify(
            media_env,
            project_id=project.id,
            media_id=media.id,
            realm=MANAGED_LOCAL_REALM,
            idempotency_key="verify-k-1",
            fingerprint=fingerprint,
        )

    assert _counts(media_env.writer) == before
    assert _location_rows(media_env.writer, media.id)[0]["verified_at"] == TS


def test_verify_missing_location_causes_zero_mutation(media_env) -> None:
    project, media = _managed_media(media_env)
    locator = media.locations[0].locator

    fingerprint = prepare_media_fingerprint(locator)
    Path(locator).unlink()
    before = _counts(media_env.writer)

    with pytest.raises(MediaNotFoundError):
        _verify(
            media_env,
            project_id=project.id,
            media_id=media.id,
            realm=MANAGED_LOCAL_REALM,
            idempotency_key="verify-k-1",
            fingerprint=fingerprint,
        )

    assert _counts(media_env.writer) == before
    assert _location_rows(media_env.writer, media.id)[0]["verified_at"] == TS


def test_verify_replays_and_mismatches(media_env) -> None:
    project, media = _managed_media(media_env)
    locator = media.locations[0].locator
    fingerprint = prepare_media_fingerprint(locator)

    first = _verify(
        media_env,
        project_id=project.id,
        media_id=media.id,
        realm=MANAGED_LOCAL_REALM,
        idempotency_key="verify-k-1",
        fingerprint=fingerprint,
    )

    # A second media with a different content hash, for the mismatch case.
    other_source = _write(media_env.projects_root, "in/other.png", PNG_BYTES + b"\x02")
    other_prepared = prepare_media_file(
        other_source, root=media_env.projects_root / "in"
    )
    other_media = _import(
        media_env,
        project_id=project.id,
        prepared=other_prepared,
        idempotency_key="import-other",
    )
    other_fingerprint = prepare_media_fingerprint(other_media.locations[0].locator)
    counts = _counts(media_env.writer)

    # An identical retry replays the stored result with zero new rows.
    replayed = _verify(
        media_env,
        project_id=project.id,
        media_id=media.id,
        realm=MANAGED_LOCAL_REALM,
        idempotency_key="verify-k-1",
        fingerprint=fingerprint,
    )
    assert replayed == first
    assert _counts(media_env.writer) == counts

    # A changed request under the same key mismatches before any mutation:
    # a different media (a different content hash) is different canonical
    # input, even though its bytes verify fine.
    with pytest.raises(ReceiptMismatchError):
        _verify(
            media_env,
            project_id=project.id,
            media_id=other_media.id,
            realm=MANAGED_LOCAL_REALM,
            idempotency_key="verify-k-1",
            fingerprint=other_fingerprint,
        )
    assert _counts(media_env.writer) == counts


def test_verify_cross_project_media_returns_not_found(media_env) -> None:
    project_a, media = _managed_media(media_env, key="import-a")
    project_b = _create_project(media_env, slug="other")
    locator = media.locations[0].locator
    fingerprint = prepare_media_fingerprint(locator)

    # A media id that belongs to another project is indistinguishable from an
    # unknown one (no existence leak across projects).
    with pytest.raises(MediaNotFoundError):
        _verify(
            media_env,
            project_id=project_b.id,
            media_id=media.id,
            realm=MANAGED_LOCAL_REALM,
            idempotency_key="verify-k-1",
            fingerprint=fingerprint,
        )


def test_verify_external_local_location(media_env) -> None:
    project = _create_project(media_env)
    source = _write(media_env.projects_root, "external/shot.png", PNG_BYTES)
    prepared = prepare_external_local(source)
    media = _import(
        media_env,
        project_id=project.id,
        prepared=prepared,
        idempotency_key="import-ext-1",
        realm=EXTERNAL_LOCAL_REALM,
    )
    locator = media.locations[0].locator
    assert media.locations[0].verified_at is None

    fingerprint = prepare_media_fingerprint(locator)
    result = _verify(
        media_env,
        project_id=project.id,
        media_id=media.id,
        realm=EXTERNAL_LOCAL_REALM,
        idempotency_key="verify-ext-1",
        fingerprint=fingerprint,
    )
    assert result.locations[0].verified_at == TS2


def test_verify_fingerprint_for_wrong_path_is_validation_error(media_env) -> None:
    project, media = _managed_media(media_env)

    # A fingerprint prepared from a different path must be rejected before any
    # mutation (the verify must target the location's actual locator).
    other = _write(media_env.projects_root, "elsewhere.bin", PNG_BYTES)
    fingerprint = prepare_media_fingerprint(other)
    before = _counts(media_env.writer)

    with pytest.raises(MediaValidationError):
        _verify(
            media_env,
            project_id=project.id,
            media_id=media.id,
            realm=MANAGED_LOCAL_REALM,
            idempotency_key="verify-k-1",
            fingerprint=fingerprint,
        )

    assert _counts(media_env.writer) == before
    assert _location_rows(media_env.writer, media.id)[0]["verified_at"] == TS
