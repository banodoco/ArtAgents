"""Focused B1 conformance for the shot text-binding kernel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import managed_media_path, prepare_media_file
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


def _create_project(env):
    return UnitOfWork(env["writer"]).run(
        lambda u: env["projects"].create(
            u, slug="pilot", name="Pilot", settings={},
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
