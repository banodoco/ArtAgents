"""Focused B1 conformance for the shot text-binding kernel."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import managed_media_path, prepare_media_file
from astrid.core.receipts.canonical import request_hash
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs.shots.repository import ShotRepository
from astrid.packs.shots.text_bindings import (
    MAX_SHOT_TEXT_BYTES,
    SHOT_TEXT_BINDING_STREAM_TYPE,
    TEXT_BINDING_KINDS,
    ShotTextBindingAmbiguousError,
    ShotTextBindingIntegrityError,
    ShotTextBindingRepository,
    ShotTextBindingValidationError,
    derive_text_binding_id,
    derive_text_binding_stream_id,
    freeze_text_bytes,
)

TS = "2026-08-31T00:00:00.000000+00:00"


@pytest.fixture
def text_env(tmp_path: Path, standard_registry):
    writer = DatabaseWriter(tmp_path / "text.sqlite3", standard_registry)
    events = EventAppendService(standard_registry)
    receipts = ReceiptService()
    try:
        yield {
            "writer": writer,
            "root": tmp_path,
            "projects": ProjectRepository(events=events, receipts=receipts),
            "media": MediaRepository(events=events, receipts=receipts, projects_root=tmp_path),
            "shots": ShotRepository(events=events, receipts=receipts),
            "bindings": ShotTextBindingRepository(
                events=events, receipts=receipts,
                media=MediaRepository(events=events, receipts=receipts, projects_root=tmp_path),
                projects_root=tmp_path,
            ),
        }
    finally:
        writer.close()


def _create_project(env, *, slug: str = "pilot"):
    return UnitOfWork(env["writer"]).run(
        lambda u: env["projects"].create(
            u, slug=slug, name=slug.title(), settings={},
            idempotency_key="project-key", project_id=generate_lowercase_ulid(), created_at=TS,
        )
    )


def _create_shot(env, project_id: str, *, name: str = "Opening"):
    return UnitOfWork(env["writer"]).run(
        lambda u: env["shots"].create(
            u, project_id=project_id, name=name,
            idempotency_key=f"shot-{name}", shot_id=generate_lowercase_ulid(), created_at=TS,
        )
    )


def _import_text(env, project_id: str, data: bytes, *, key: str = "media-key"):
    source = env["root"] / f"{key}.txt"
    source.write_bytes(data)
    prepared = prepare_media_file(source)
    return UnitOfWork(env["writer"]).run(
        lambda u: env["media"].import_prepared(
            u, project_id=project_id, prepared=prepared,
            idempotency_key=key, media_id=generate_lowercase_ulid(), created_at=TS,
        )
    )


def _set_binding(env, *, text: bytes, **kwargs):
    """Freeze caller bytes before opening the repository unit of work."""
    frozen = freeze_text_bytes(text)
    return UnitOfWork(env["writer"]).run(
        lambda u: env["bindings"].set(u, frozen=frozen, **kwargs)
    )


def test_identity_vectors_are_natural_and_key_independent() -> None:
    base = dict(project_id="project", shot_id="shot", kind="prompt", slot=None)
    first = derive_text_binding_id(**base)
    assert first == derive_text_binding_id(**base)
    assert first != derive_text_binding_id(**{**base, "project_id": "other"})
    assert first != derive_text_binding_id(**{**base, "shot_id": "other"})
    assert first != derive_text_binding_id(**{**base, "kind": "transcript"})
    assert first != derive_text_binding_id(**{**base, "slot": "regen-glitch"})
    assert first == derive_text_binding_id(**{**base, "slot": None})
    assert derive_text_binding_stream_id(first) == f"{first}:{SHOT_TEXT_BINDING_STREAM_TYPE}"


def test_kinds_slots_and_caller_bytes_are_closed_and_bounded() -> None:
    assert TEXT_BINDING_KINDS == ("prompt", "voiceover_script", "transcript")
    empty = freeze_text_bytes(b"")
    assert empty.byte_size == 0
    assert empty.digest == hashlib.sha256(b"").hexdigest()
    assert freeze_text_bytes("unicode".encode()).value == b"unicode"
    with pytest.raises(Exception, match="UTF-8"):
        freeze_text_bytes(b"\xff")
    with pytest.raises(Exception, match="exceeds"):
        freeze_text_bytes(b"x" * (MAX_SHOT_TEXT_BYTES + 1))


def test_media_read_is_project_scoped_and_has_no_relations(text_env) -> None:
    project = _create_project(text_env)
    media = _import_text(text_env, project.id, b"hello")
    found = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["media"].read_project_media(u, project_id=project.id, media_id=media.id)
    )
    assert found is not None
    assert found.id == media.id
    assert found.relations == ()
    assert [location.realm for location in found.locations] == ["managed_local"]
    assert UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["media"].read_project_media(u, project_id="foreign", media_id=media.id)
    ) is None
    assert UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["media"].read_project_media(
            u, project_id=project.id, content_hash=media.content_hash
        )
    ).id == media.id


def test_binding_set_creates_natural_projection_and_stream(text_env) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    result = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"Hello\n", expected_head=0, idempotency_key="binding-key",
    )
    assert result.changed is True
    assert result.binding.binding_id == derive_text_binding_id(
        project_id=project.id, shot_id=shot.id, kind="transcript", slot=None
    )
    assert result.binding.head == 1
    assert result.binding.mime_type == "text/plain"
    assert result.binding.byte_size == 6
    assert result.binding.event_stream_id == derive_text_binding_stream_id(result.binding.binding_id)
    stream = text_env["writer"].submit(
        lambda session: session.query_one(
            "SELECT stream_type, aggregate_id, head_seq FROM event_streams WHERE id = ?",
            (result.binding.event_stream_id,),
        )
    )
    assert tuple(stream) == ("shot.text_binding", result.binding.binding_id, 1)
    listed = text_env["bindings"].list(
        text_env["writer"], project_id=project.id, shot_ref=shot.id, kind="transcript"
    )
    assert [binding.binding_id for binding in listed] == [result.binding.binding_id]


def test_binding_friendly_omitted_slot_is_wildcard_for_existing_target(text_env) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    for slot, key in (("regen-glitch", "one"), ("variant", "two")):
        _set_binding(
            text_env, project_id=project.id, shot_ref=shot.id, kind="prompt", slot=slot,
            text=key.encode(), expected_head=0, idempotency_key=key,
        )
    with pytest.raises(ShotTextBindingAmbiguousError) as exc_info:
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"]._resolve_binding(
                u, project_id=project.id, shot_ref=shot.id, kind="prompt"
            )
        )
    assert {candidate["slot"] for candidate in exc_info.value.candidates} == {
        "regen-glitch", "variant"
    }


def test_bound_media_corruption_is_integrity_failure(text_env) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    result = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"stable", expected_head=0, idempotency_key="integrity-key",
    )
    path = managed_media_path(text_env["root"], result.binding.content_hash)
    path.write_bytes(b"changed")
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        text_env["bindings"].show(
            text_env["writer"], project_id=project.id, binding_id=result.binding.binding_id
        )
    assert exc_info.value.detail == "managed_size_mismatch"


def _persisted_binding_snapshot(env, *, project_id: str, binding_id: str) -> dict[str, object]:
    def capture(session):
        return {
            "binding_pointer_timestamp": tuple(
                session.query_one(
                    "SELECT media_id, updated_at FROM shot_text_bindings WHERE id = ?",
                    (binding_id,),
                )
            ),
            "project_heads": tuple(
                tuple(row)
                for row in session.query(
                    "SELECT id, event_head_seq FROM projects WHERE id = ?",
                    (project_id,),
                )
            ),
            "stream_heads": tuple(
                tuple(row)
                for row in session.query(
                    "SELECT id, head_seq FROM event_streams "
                    "WHERE project_id = ? ORDER BY id",
                    (project_id,),
                )
            ),
            "events": tuple(
                tuple(row)
                for row in session.query(
                    "SELECT * FROM events WHERE project_id = ? "
                    "ORDER BY project_seq, event_id",
                    (project_id,),
                )
            ),
            "receipts": tuple(
                tuple(row)
                for row in session.query(
                    "SELECT * FROM command_receipts WHERE project_id = ? "
                    "ORDER BY idempotency_key",
                    (project_id,),
                )
            ),
            "media": tuple(
                tuple(row)
                for row in session.query(
                    "SELECT * FROM media WHERE project_id = ? ORDER BY id",
                    (project_id,),
                )
            ),
            "media_locations": tuple(
                tuple(row)
                for row in session.query(
                    "SELECT ml.* FROM media_locations ml "
                    "JOIN media m ON m.id = ml.media_id "
                    "WHERE m.project_id = ? ORDER BY ml.media_id, ml.realm, ml.locator",
                    (project_id,),
                )
            ),
        }

    return env["writer"].submit(capture)


def test_malformed_bound_hash_is_typed_zero_write_and_no_temp(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"stable", expected_head=0, idempotency_key="malformed-hash-create",
    )
    media_id = created.binding.media_id
    text_env["writer"].submit(
        lambda s: s.execute(
            "UPDATE media SET content_hash = ? WHERE id = ?",
            ("malformed", media_id),
        )
    )
    before = _persisted_binding_snapshot(
        text_env, project_id=project.id, binding_id=created.binding.binding_id
    )
    temp_root = Path(tempfile.gettempdir())
    temp_before = set(temp_root.glob(".astrid-shot-text-*.txt"))
    materialize_calls = 0

    def forbidden_materialization(*args, **kwargs):
        nonlocal materialize_calls
        materialize_calls += 1
        raise AssertionError("malformed current hash must fail before materialization")

    monkeypatch.setattr(text_env["bindings"], "materialize_absent_text", forbidden_materialization)
    monkeypatch.setattr(
        tempfile,
        "NamedTemporaryFile",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("malformed current hash must create no temp")
        ),
    )
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        _set_binding(
            text_env, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"next", expected_head=1, idempotency_key="malformed-hash-set",
        )
    after = _persisted_binding_snapshot(
        text_env, project_id=project.id, binding_id=created.binding.binding_id
    )
    assert exc_info.value.detail == "managed_hash_mismatch"
    assert exc_info.value.media_id == media_id
    assert after == before
    assert materialize_calls == 0
    assert set(temp_root.glob(".astrid-shot-text-*.txt")) == temp_before


def test_canonical_request_hash_vectors_include_binding_stream_and_desired_hash() -> None:
    set_facts = {
        "project_id": "project", "shot_id": "shot", "kind": "transcript",
        "slot": None, "binding_id": "binding",
        "event_stream_id": "binding:shot.text_binding", "expected_head": 0,
        "desired_content_hash": "a" * 64,
    }
    rebind_facts = {
        "project_id": "project", "binding_id": "binding",
        "event_stream_id": "binding:shot.text_binding", "expected_head": 3,
        "desired_media_id": "media", "desired_content_hash": "b" * 64,
    }
    assert request_hash("shot.text_binding.set", set_facts) == (
        "cef56c8632f75d5754e4f3d97dd37daf09a44aa47c3bdf5de8504231d3698b63"
    )
    assert request_hash("shot.text_binding.rebind", rebind_facts) == (
        "6513b83971ed2d3f0855a4b5ad2a45658079ecb993dca8300be5a8dda25efd22"
    )
    rebind_facts["desired_content_hash"] = "c" * 64
    assert request_hash("shot.text_binding.rebind", rebind_facts) == (
        "55560a285541ba359be21ec638bf61e4ea8d57d9a09a0d91145bbb38011994bb"
    )


def test_authority_corruption_is_rejected_before_any_write(text_env) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"stable", expected_head=0, idempotency_key="authority-key",
    )
    binding_id = created.binding.binding_id
    stream_id = created.binding.event_stream_id
    foreign_project = _create_project(text_env, slug="foreign")
    other_shot = _create_shot(text_env, foreign_project.id, name="Other")
    before = text_env["writer"].submit(
        lambda s: s.query_one(
            "SELECT (SELECT COUNT(*) FROM events), (SELECT COUNT(*) FROM command_receipts), "
            "(SELECT head_seq FROM event_streams WHERE id = ?)", (stream_id,)
        )
    )
    text_env["writer"].submit(
        lambda s: s.execute("UPDATE shot_text_bindings SET shot_id = ? WHERE id = ?", (other_shot.id, binding_id))
    )
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        _set_binding(
            text_env, project_id=project.id, binding_id=binding_id, text=b"next",
            expected_head=1, idempotency_key="authority-fail",
        )
    assert exc_info.value.detail == "binding_shot_project_mismatch"
    after = text_env["writer"].submit(
        lambda s: s.query_one(
            "SELECT (SELECT COUNT(*) FROM events), (SELECT COUNT(*) FROM command_receipts), "
            "(SELECT head_seq FROM event_streams WHERE id = ?)", (stream_id,)
        )
    )
    assert tuple(after) == tuple(before)


@pytest.mark.parametrize("selector", ["exact", "friendly"])
@pytest.mark.parametrize(
    ("column", "value", "detail"),
    [
        ("project_id", "foreign-project", "binding_stream_project_mismatch"),
        ("stream_type", "wrong.stream", "binding_stream_type_mismatch"),
        ("aggregate_id", "wrong-aggregate", "binding_stream_aggregate_mismatch"),
    ],
)
def test_corrupt_stream_authority_is_zero_write_for_exact_and_friendly_set(
    text_env, selector: str, column: str, value: str, detail: str
) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"stable", expected_head=0, idempotency_key=f"stream-{column}",
    )
    stream_id = created.binding.event_stream_id
    if column == "project_id":
        value = _create_project(
            text_env, slug=f"foreign-stream-{selector}"
        ).id
    text_env["writer"].submit(
        lambda s: s.execute(
            f"UPDATE event_streams SET {column} = ? WHERE id = ?",
            (value, stream_id),
        )
    )
    before = text_env["writer"].submit(
        lambda s: s.query_one(
            "SELECT b.media_id, b.updated_at, s.head_seq, "
            "(SELECT COUNT(*) FROM events), "
            "(SELECT COUNT(*) FROM command_receipts), "
            "(SELECT COUNT(*) FROM media) "
            "FROM shot_text_bindings b JOIN event_streams s "
            "ON s.id = b.event_stream_id WHERE b.id = ?",
            (created.binding.binding_id,),
        )
    )
    request = {
        "project_id": project.id,
        "frozen": freeze_text_bytes(b"next"),
        "expected_head": 1,
        "idempotency_key": f"stream-corrupt-{selector}-{column}",
    }
    if selector == "exact":
        request["binding_id"] = created.binding.binding_id
    else:
        request.update({"shot_ref": shot.id, "kind": "transcript"})
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(u, **request)
        )
    after = text_env["writer"].submit(
        lambda s: s.query_one(
            "SELECT b.media_id, b.updated_at, s.head_seq, "
            "(SELECT COUNT(*) FROM events), "
            "(SELECT COUNT(*) FROM command_receipts), "
            "(SELECT COUNT(*) FROM media) "
            "FROM shot_text_bindings b JOIN event_streams s "
            "ON s.id = b.event_stream_id WHERE b.id = ?",
            (created.binding.binding_id,),
        )
    )
    assert exc_info.value.detail == detail
    assert tuple(after) == tuple(before)


def test_receipt_replay_checks_before_full_stream_authority(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"stable", expected_head=0, idempotency_key="replay-create",
    )
    changed = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"changed", expected_head=1, idempotency_key="replay-changed",
    )
    text_env["writer"].submit(
        lambda s: s.execute(
            "UPDATE event_streams SET stream_type = ? WHERE id = ?",
            ("wrong.stream", created.binding.event_stream_id),
        )
    )
    monkeypatch.setattr(
        text_env["bindings"], "_validate_binding_authority",
        lambda *args, **kwargs: pytest.fail("replay performed full authority validation"),
    )
    replay = _set_binding(
        text_env, project_id=project.id, binding_id=created.binding.binding_id,
        text=b"changed", expected_head=1, idempotency_key="replay-changed",
    )
    assert replay.binding == changed.binding


@pytest.mark.parametrize(
    ("column", "value", "detail"),
    [
        ("kind", "prompt", "binding_natural_tuple_mismatch"),
        ("event_stream_id", "wrong-stream", "binding_stream_id_mismatch"),
    ],
)
def test_natural_and_stream_identity_corruption_is_typed(
    text_env, column: str, value: str, detail: str
) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"stable", expected_head=0, idempotency_key=f"{column}-key",
    )
    binding_id = created.binding.binding_id
    if column == "event_stream_id":
        text_env["writer"].submit(
            lambda s: s.execute(
                "INSERT INTO event_streams "
                "(id, project_id, stream_type, aggregate_id, head_seq, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                ("wrong-stream", project.id, SHOT_TEXT_BINDING_STREAM_TYPE, "wrong", TS),
            )
        )
    text_env["writer"].submit(
        lambda s: s.execute(
            f"UPDATE shot_text_bindings SET {column} = ? WHERE id = ?",
            (value, binding_id),
        )
    )
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        text_env["bindings"].show(
            text_env["writer"], project_id=project.id, binding_id=binding_id
        )
    assert exc_info.value.detail == detail


def test_prepared_materialization_uses_one_0600_temp_and_cleans_it(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    observed: list[dict[str, object]] = []
    original = text_env["bindings"]._prepared_media

    def wrapped(frozen):
        prepared, path = original(frozen)
        observed.append({"path": str(path), "mode": oct(os.stat(path).st_mode & 0o777), "digest": prepared.digest})
        return prepared, path

    monkeypatch.setattr(text_env["bindings"], "_prepared_media", wrapped)
    result = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"prepared", expected_head=0, idempotency_key="prepared-key",
    )
    assert len(observed) == 1
    assert observed[0]["mode"] == "0o600"
    assert not Path(str(observed[0]["path"])).exists()
    assert observed[0]["digest"] == result.binding.content_hash


def test_existing_digest_reuses_mime_and_never_prepares_temp(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    source = text_env["root"] / "existing.md"
    source.write_bytes(b"reused")
    prepared = prepare_media_file(source)
    media = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["media"].import_prepared(
            u, project_id=project.id, prepared=prepared,
            idempotency_key="existing-md", media_id=generate_lowercase_ulid(), created_at=TS,
        )
    )
    monkeypatch.setattr(text_env["bindings"], "_prepared_media", pytest.fail)
    result = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"reused", expected_head=0, idempotency_key="reuse-binding",
    )
    assert result.binding.media_id == media.id
    assert result.binding.mime_type == "text/markdown"


def test_direct_repository_path_never_calls_prepare_media_file(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    monkeypatch.setattr("astrid.packs.shots.text_bindings.prepare_media_file", pytest.fail, raising=False)
    frozen = freeze_text_bytes(b"no-probe")
    monkeypatch.setattr("astrid.packs.shots.text_bindings.freeze_text_bytes", pytest.fail)
    result = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            frozen=frozen, expected_head=0, idempotency_key="no-probe-key",
        )
    )
    assert result.changed


def test_direct_repository_rejects_raw_bytes_before_any_write(text_env) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    before = _binding_counts(text_env)
    with pytest.raises(ShotTextBindingValidationError, match="frozen text bytes"):
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, shot_ref=shot.id, kind="transcript",
                frozen=b"raw", expected_head=0, idempotency_key="raw-key",
            )
        )
    assert _binding_counts(text_env) == before


def _binding_counts(env) -> tuple[int, int, int, int]:
    row = env["writer"].submit(
        lambda s: s.query_one(
            "SELECT (SELECT COUNT(*) FROM events), (SELECT COUNT(*) FROM media), "
            "(SELECT COUNT(*) FROM shot_text_bindings), (SELECT COUNT(*) FROM command_receipts)"
        )
    )
    return tuple(row)


def _binding_authority_snapshot(
    env, *, project_id: str, binding_id: str, desired_digest: str,
    desired_locator: str, binding_key: str, media_key: str,
) -> dict[str, object]:
    def capture(session):
        project = session.query_one(
            "SELECT event_head_seq FROM projects WHERE id = ?", (project_id,)
        )
        streams = session.query(
            "SELECT id, project_id, stream_type, aggregate_id, head_seq "
            "FROM event_streams WHERE project_id = ? ORDER BY id",
            (project_id,),
        )
        events = session.query(
            "SELECT * FROM events WHERE project_id = ? AND idempotency_key IN (?, ?) "
            "ORDER BY project_seq, event_id",
            (project_id, binding_key, media_key),
        )
        event_summary = session.query_one(
            "SELECT COUNT(*), MAX(project_seq) FROM events WHERE project_id = ?",
            (project_id,),
        )
        per_stream = session.query(
            "SELECT stream_id, MAX(seq) FROM events WHERE project_id = ? "
            "GROUP BY stream_id ORDER BY stream_id",
            (project_id,),
        )
        media_summary = session.query_one(
            "SELECT "
            "(SELECT COUNT(*) FROM media WHERE project_id = ?), "
            "(SELECT COUNT(*) FROM media WHERE project_id = ? AND content_hash = ?), "
            "(SELECT COUNT(*) FROM media_locations ml JOIN media m ON m.id = ml.media_id "
            " WHERE m.project_id = ?), "
            "(SELECT COUNT(*) FROM media_locations ml JOIN media m ON m.id = ml.media_id "
            " WHERE m.project_id = ? AND ml.realm = 'managed_local' AND ml.locator = ?) "
            "",
            (
                project_id, project_id, desired_digest, project_id,
                project_id, desired_locator,
            ),
        )
        binding = session.query_one(
            "SELECT * FROM shot_text_bindings WHERE id = ?", (binding_id,)
        )
        receipts = session.query_one(
            "SELECT "
            "(SELECT COUNT(*) FROM command_receipts WHERE project_id = ?), "
            "(SELECT COUNT(*) FROM command_receipts "
            " WHERE project_id = ? AND idempotency_key = ?) "
            "",
            (project_id, project_id, binding_key),
        )
        return {
            "project_event_head_seq": int(project["event_head_seq"]),
            "event_streams": {
                "count": len(streams),
                "rows": tuple(tuple(row) for row in streams),
            },
            "events": {
                "count": int(event_summary[0]),
                "max_project_seq": event_summary[1],
                "per_stream_max_seq": tuple(tuple(row) for row in per_stream),
                "key_rows": tuple(tuple(row) for row in events),
            },
            "media": {
                "count": int(media_summary[0]),
                "desired_digest_count": int(media_summary[1]),
                "media_locations_count": int(media_summary[2]),
                "canonical_desired_locator_count": int(media_summary[3]),
            },
            "shot_text_bindings": {
                "count": int(
                    session.query_one(
                        "SELECT COUNT(*) FROM shot_text_bindings WHERE project_id = ?",
                        (project_id,),
                    )[0]
                ),
                "prospective_target": (
                    {
                        "exists": True,
                        "row": tuple(binding),
                        "media_id": binding["media_id"],
                        "updated_at": binding["updated_at"],
                        "event_stream_id": binding["event_stream_id"],
                    }
                    if binding is not None
                    else {
                        "exists": False,
                        "row": None,
                        "media_id": None,
                        "updated_at": None,
                        "event_stream_id": None,
                    }
                ),
            },
            "command_receipts": {
                "count": int(receipts[0]),
                "top_level_key_count": int(receipts[1]),
            },
        }

    return env["writer"].submit(capture)


def test_event_append_fingerprint_fence_rolls_back_set_current_race(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"old", expected_head=0, idempotency_key="race-old",
    )
    path = managed_media_path(text_env["root"], created.binding.content_hash)
    before = _binding_counts(text_env)
    original = text_env["bindings"]._events.append

    def append(uow, **kwargs):
        event = original(uow, **kwargs)
        if kwargs["event_kind"] == "shot.text_binding.rebound":
            path.write_bytes(b"raced-current")
        return event

    monkeypatch.setattr(text_env["bindings"]._events, "append", append)
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        _set_binding(
            text_env, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"new", expected_head=1, idempotency_key="race-current",
        )
    assert exc_info.value.detail == "managed_file_mutated"
    assert _binding_counts(text_env) == before
    path.write_bytes(b"old")
    assert text_env["bindings"].show(
        text_env["writer"], project_id=project.id, binding_id=created.binding.binding_id
    ).head == 1


def test_event_append_fingerprint_fence_rolls_back_set_desired_race(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"old", expected_head=0, idempotency_key="desired-old",
    )
    desired = _import_text(text_env, project.id, b"desired", key="desired-media")
    path = managed_media_path(text_env["root"], desired.content_hash)
    before = _binding_counts(text_env)
    original = text_env["bindings"]._events.append

    def append(uow, **kwargs):
        event = original(uow, **kwargs)
        if kwargs["event_kind"] == "shot.text_binding.rebound":
            path.write_bytes(b"raced-desired")
        return event

    monkeypatch.setattr(text_env["bindings"]._events, "append", append)
    with pytest.raises(ShotTextBindingIntegrityError, match="managed_file_mutated"):
        _set_binding(
            text_env, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"desired", expected_head=1, idempotency_key="race-desired",
        )
    assert _binding_counts(text_env) == before
    path.write_bytes(b"desired")
    assert text_env["bindings"].show(
        text_env["writer"], project_id=project.id, binding_id=created.binding.binding_id
    ).media_id == created.binding.media_id


def test_event_append_fingerprint_fence_rolls_back_rebind_race(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"old", expected_head=0, idempotency_key="rebind-old",
    )
    desired = _import_text(text_env, project.id, b"desired", key="rebind-media")
    path = managed_media_path(text_env["root"], desired.content_hash)
    before = _binding_counts(text_env)
    original = text_env["bindings"]._events.append

    def append(uow, **kwargs):
        event = original(uow, **kwargs)
        if kwargs["event_kind"] == "shot.text_binding.rebound":
            path.write_bytes(b"raced-rebind")
        return event

    monkeypatch.setattr(text_env["bindings"]._events, "append", append)
    with pytest.raises(ShotTextBindingIntegrityError, match="managed_file_mutated"):
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].rebind(
                u, project_id=project.id, binding_id=created.binding.binding_id,
                media_id=desired.id, expected_head=1, idempotency_key="race-rebind",
            )
        )
    assert _binding_counts(text_env) == before
    path.write_bytes(b"desired")


@pytest.mark.parametrize("failure", ["materialize", "event", "receipt"])
def test_injected_binding_failures_roll_back_complete_authority_and_clean_temp(
    text_env, monkeypatch, failure: str
) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    frozen = freeze_text_bytes(f"failure-{failure}".encode())
    binding_key = f"failure-{failure}"
    binding_id = derive_text_binding_id(
        project_id=project.id, shot_id=shot.id, kind="transcript", slot=None
    )
    media_key = f"{binding_key}:media:{frozen.digest}"
    snapshot_args = {
        "project_id": project.id,
        "binding_id": binding_id,
        "desired_digest": frozen.digest,
        "desired_locator": str(managed_media_path(text_env["root"], frozen.digest)),
        "binding_key": binding_key,
        "media_key": media_key,
    }
    before = _binding_authority_snapshot(text_env, **snapshot_args)
    counters = {
        "materialize_prepared": {"attempted": 0, "committed": 0},
        "core_media_event_append": {"attempted": 0, "committed": 0},
        "binding_event_append": {"attempted": 0, "committed": 0},
        "receipt_record": {"attempted": 0, "committed": 0},
        "uow": {"attempted": 0, "committed": 0, "rollback": 0},
        "temp_creation": {"attempted": 0, "committed": 0},
        "temp_0600": {"attempted": 0, "committed": 0},
        "temp_cleanup": {"attempted": 0, "committed": 0},
    }
    observed: list[Path] = []
    original_prepare = text_env["bindings"]._prepared_media

    def prepared(value):
        counters["temp_creation"]["attempted"] += 1
        prepared_value, path = original_prepare(value)
        observed.append(path)
        counters["temp_creation"]["committed"] += 1
        counters["temp_0600"]["attempted"] += 1
        if (os.stat(path).st_mode & 0o777) == 0o600:
            counters["temp_0600"]["committed"] += 1
        return prepared_value, path

    monkeypatch.setattr(text_env["bindings"], "_prepared_media", prepared)
    media = text_env["bindings"]._media
    original_materialize = media.materialize_prepared
    if failure == "materialize":
        def materialize_target(*args, **kwargs):
            raise RuntimeError("injected materialization failure")
    else:
        materialize_target = original_materialize

    def counting_materialize(*args, **kwargs):
        counters["materialize_prepared"]["attempted"] += 1
        return materialize_target(*args, **kwargs)

    monkeypatch.setattr(media, "materialize_prepared", counting_materialize)
    original_append = text_env["bindings"]._events.append
    if failure == "event":
        def append_target(uow, **kwargs):
            if kwargs["event_kind"] == "shot.text_binding.created":
                raise RuntimeError("injected binding event failure")
            return original_append(uow, **kwargs)
    else:
        append_target = original_append

    def counting_append(uow, **kwargs):
        event_kind = kwargs["event_kind"]
        if event_kind == "core.media.imported":
            counter = counters["core_media_event_append"]
        elif event_kind == "shot.text_binding.created":
            counter = counters["binding_event_append"]
        else:
            return append_target(uow, **kwargs)
        counter["attempted"] += 1
        return append_target(uow, **kwargs)

    monkeypatch.setattr(text_env["bindings"]._events, "append", counting_append)
    original_record = text_env["bindings"]._receipts.record
    if failure == "receipt":
        def record_target(*args, **kwargs):
            raise RuntimeError("injected receipt failure")
    else:
        record_target = original_record

    def counting_record(*args, **kwargs):
        counters["receipt_record"]["attempted"] += 1
        return record_target(*args, **kwargs)

    monkeypatch.setattr(text_env["bindings"]._receipts, "record", counting_record)

    def on_statement(kind, _sql, _parameters):
        if kind == "begin_immediate":
            counters["uow"]["attempted"] += 1
        elif kind == "commit":
            counters["uow"]["committed"] += 1
            for name in (
                "materialize_prepared", "core_media_event_append",
                "binding_event_append", "receipt_record",
            ):
                counters[name]["committed"] = counters[name]["attempted"]
        elif kind == "rollback":
            counters["uow"]["rollback"] += 1
    with pytest.raises((AssertionError, RuntimeError)):
        UnitOfWork(text_env["writer"], on_statement=on_statement).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, shot_ref=shot.id, kind="transcript",
                frozen=frozen, expected_head=0, idempotency_key=binding_key,
            )
        )
    counters["temp_cleanup"]["attempted"] = len(observed)
    counters["temp_cleanup"]["committed"] = sum(
        not path.exists() for path in observed
    )
    assert _binding_authority_snapshot(text_env, **snapshot_args) == before
    assert counters["uow"] == {"attempted": 1, "committed": 0, "rollback": 1}
    assert counters["materialize_prepared"] == {"attempted": 1, "committed": 0}
    assert counters["core_media_event_append"] == {
        "attempted": int(failure != "materialize"), "committed": 0
    }
    assert counters["binding_event_append"] == {
        "attempted": int(failure in ("event", "receipt")), "committed": 0
    }
    assert counters["receipt_record"] == {
        "attempted": int(failure == "receipt"), "committed": 0
    }
    assert counters["temp_creation"] == {"attempted": 1, "committed": 1}
    assert counters["temp_0600"] == {"attempted": 1, "committed": 1}
    assert counters["temp_cleanup"] == {"attempted": 1, "committed": 1}


def test_replay_stale_and_noop_never_prepare_temp(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = _set_binding(
        text_env, project_id=project.id, shot_ref=shot.id, kind="transcript",
        text=b"one", expected_head=0, idempotency_key="first",
    )
    changed = _set_binding(
        text_env, project_id=project.id, binding_id=created.binding.binding_id,
        text=b"two", expected_head=1, idempotency_key="second",
    )
    monkeypatch.setattr(text_env["bindings"], "_prepared_media", pytest.fail)
    replay = _set_binding(
        text_env, project_id=project.id, binding_id=created.binding.binding_id,
        text=b"two", expected_head=1, idempotency_key="second",
    )
    assert replay.binding == changed.binding
    with pytest.raises(Exception, match="expected head"):
        _set_binding(
            text_env, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"three", expected_head=1, idempotency_key="stale",
        )
    no_op = _set_binding(
        text_env, project_id=project.id, binding_id=created.binding.binding_id,
        text=b"two", expected_head=2, idempotency_key="no-op",
    )
    assert no_op.changed is False
