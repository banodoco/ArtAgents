"""Focused B1 conformance for the shot text-binding kernel."""

from __future__ import annotations

import hashlib
import os
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
    result = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"Hello\n", expected_head=0, idempotency_key="binding-key",
        )
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
        UnitOfWork(text_env["writer"]).run(
            lambda u, slot=slot, key=key: text_env["bindings"].set(
                u, project_id=project.id, shot_ref=shot.id, kind="prompt", slot=slot,
                text=key.encode(), expected_head=0, idempotency_key=key,
            )
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
    result = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"stable", expected_head=0, idempotency_key="integrity-key",
        )
    )
    path = managed_media_path(text_env["root"], result.binding.content_hash)
    path.write_bytes(b"changed")
    with pytest.raises(ShotTextBindingIntegrityError) as exc_info:
        text_env["bindings"].show(
            text_env["writer"], project_id=project.id, binding_id=result.binding.binding_id
        )
    assert exc_info.value.detail == "managed_size_mismatch"


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
    created = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"stable", expected_head=0, idempotency_key="authority-key",
        )
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
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, binding_id=binding_id, text=b"next",
                expected_head=1, idempotency_key="authority-fail",
            )
        )
    assert exc_info.value.detail == "binding_shot_project_mismatch"
    after = text_env["writer"].submit(
        lambda s: s.query_one(
            "SELECT (SELECT COUNT(*) FROM events), (SELECT COUNT(*) FROM command_receipts), "
            "(SELECT head_seq FROM event_streams WHERE id = ?)", (stream_id,)
        )
    )
    assert tuple(after) == tuple(before)


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
    created = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"stable", expected_head=0, idempotency_key=f"{column}-key",
        )
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
    result = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"prepared", expected_head=0, idempotency_key="prepared-key",
        )
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
    result = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"reused", expected_head=0, idempotency_key="reuse-binding",
        )
    )
    assert result.binding.media_id == media.id
    assert result.binding.mime_type == "text/markdown"


def test_direct_repository_path_never_calls_prepare_media_file(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    monkeypatch.setattr("astrid.packs.shots.text_bindings.prepare_media_file", pytest.fail, raising=False)
    result = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"no-probe", expected_head=0, idempotency_key="no-probe-key",
        )
    )
    assert result.changed


def _binding_counts(env) -> tuple[int, int, int, int]:
    row = env["writer"].submit(
        lambda s: s.query_one(
            "SELECT (SELECT COUNT(*) FROM events), (SELECT COUNT(*) FROM media), "
            "(SELECT COUNT(*) FROM shot_text_bindings), (SELECT COUNT(*) FROM command_receipts)"
        )
    )
    return tuple(row)


def test_event_append_fingerprint_fence_rolls_back_set_current_race(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"old", expected_head=0, idempotency_key="race-old",
        )
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
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, binding_id=created.binding.binding_id,
                text=b"new", expected_head=1, idempotency_key="race-current",
            )
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
    created = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"old", expected_head=0, idempotency_key="desired-old",
        )
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
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, binding_id=created.binding.binding_id,
                text=b"desired", expected_head=1, idempotency_key="race-desired",
            )
        )
    assert _binding_counts(text_env) == before
    path.write_bytes(b"desired")
    assert text_env["bindings"].show(
        text_env["writer"], project_id=project.id, binding_id=created.binding.binding_id
    ).media_id == created.binding.media_id


def test_event_append_fingerprint_fence_rolls_back_rebind_race(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"old", expected_head=0, idempotency_key="rebind-old",
        )
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
def test_injected_binding_failures_roll_back_all_rows_and_clean_temp(
    text_env, monkeypatch, failure: str
) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    before = _binding_counts(text_env)
    observed: list[Path] = []
    original_prepare = text_env["bindings"]._prepared_media

    def prepared(frozen):
        value, path = original_prepare(frozen)
        observed.append(path)
        return value, path

    monkeypatch.setattr(text_env["bindings"], "_prepared_media", prepared)
    if failure == "materialize":
        def fail_materialize(*args, **kwargs):
            raise RuntimeError("injected materialization failure")
        monkeypatch.setattr(text_env["bindings"]._media, "materialize_prepared", fail_materialize)
    elif failure == "event":
        original_append = text_env["bindings"]._events.append
        def failing_append(uow, **kwargs):
            if kwargs["event_kind"] == "shot.text_binding.created":
                raise RuntimeError("injected binding event failure")
            return original_append(uow, **kwargs)
        monkeypatch.setattr(text_env["bindings"]._events, "append", failing_append)
    else:
        def fail_receipt(*args, **kwargs):
            raise RuntimeError("injected receipt failure")
        monkeypatch.setattr(text_env["bindings"]._receipts, "record", fail_receipt)
    with pytest.raises((AssertionError, RuntimeError)):
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, shot_ref=shot.id, kind="transcript",
                text=f"failure-{failure}".encode(), expected_head=0,
                idempotency_key=f"failure-{failure}",
            )
        )
    assert _binding_counts(text_env) == before
    assert observed and all(not path.exists() for path in observed)


def test_replay_stale_and_noop_never_prepare_temp(text_env, monkeypatch) -> None:
    project = _create_project(text_env)
    shot = _create_shot(text_env, project.id)
    created = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, shot_ref=shot.id, kind="transcript",
            text=b"one", expected_head=0, idempotency_key="first",
        )
    )
    changed = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"two", expected_head=1, idempotency_key="second",
        )
    )
    monkeypatch.setattr(text_env["bindings"], "_prepared_media", pytest.fail)
    replay = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"two", expected_head=1, idempotency_key="second",
        )
    )
    assert replay.binding == changed.binding
    with pytest.raises(Exception, match="expected head"):
        UnitOfWork(text_env["writer"]).run(
            lambda u: text_env["bindings"].set(
                u, project_id=project.id, binding_id=created.binding.binding_id,
                text=b"three", expected_head=1, idempotency_key="stale",
            )
        )
    no_op = UnitOfWork(text_env["writer"]).run(
        lambda u: text_env["bindings"].set(
            u, project_id=project.id, binding_id=created.binding.binding_id,
            text=b"two", expected_head=2, idempotency_key="no-op",
        )
    )
    assert no_op.changed is False
