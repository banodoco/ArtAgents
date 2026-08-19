"""Executable media SDK service tests (m4 plan step 11, task T12).

Proves ``astrid.sdk.media.MediaService`` exposes repository-backed,
envelope-shaped ``import_file``/``import_directory``/``list``/``show``/
``verify``/``relocate``/``relate`` over the kernel
:class:`~astrid.core.repositories.media.MediaRepository`:

- the five-key envelope shape with the committed nine-key receipt on
  mutations and a null receipt on pure reads;
- deterministic media ids derived from the idempotency key, so an identical
  retry replays with zero new rows and a changed request under the same key
  returns ``idempotency_mismatch`` before any mutation;
- directory import walks files in deterministic sorted order, derives child
  keys, and returns one media read model plus one receipt per file;
- project-scoped ``show``/``verify``/``relocate`` (a cross-project media id
  is a typed ``not_found``);
- ``verify`` hashes the selected local location outside the transaction and
  a mutated location changes zero rows;
- ``relate`` accepts only the five frozen kinds and delegates the
  self-edge/duplicate/cycle rules (no invented direction matrix).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.media import (
    CORE_MEDIA_IMPORT_COMMAND_KIND,
    MEDIA_RELATION_KINDS,
    MediaRepository,
)
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import derive_stable_id
from astrid.sdk.media import MediaService

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}
RECEIPT_KEYS = {
    "receipt_id",
    "command_kind",
    "idempotency_key",
    "request_hash",
    "project_id",
    "project_seq",
    "event_ids",
    "result",
    "created_at",
}

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def env(tmp_path: Path):
    """A fresh kernel writer, project/media repositories, and media service."""
    registry = core_only_registry()
    writer = DatabaseWriter(tmp_path / "media.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        media = MediaRepository(
            events=events, receipts=receipts, projects_root=tmp_path
        )
        yield SimpleNamespace(
            service=MediaService(writer, projects, media, receipts),
            writer=writer,
            root=tmp_path,
        )
    finally:
        writer.close()


def _write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _create_project(env: SimpleNamespace, slug: str = "pilot") -> str:
    project_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.service._projects.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"create-{slug}-k",
            project_id=project_id,
        )
    )
    return project_id


def _media_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM media")[0]
    )


def _event_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM events")[0]
    )


def _import_one(
    env: SimpleNamespace,
    project: str,
    *,
    path: Path,
    realm: str = "managed_local",
    idempotency_key: str | None = None,
):
    return env.service.import_file(
        project=project, path=path, realm=realm, idempotency_key=idempotency_key
    )


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_import_envelope_has_exactly_five_keys(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    result = _import_one(env, project, path=path)
    assert result.ok is True
    assert set(result.as_dict().keys()) == ENVELOPE_KEYS
    assert result.receipt is not None
    assert set(result.receipt.as_dict().keys()) == RECEIPT_KEYS
    assert result.receipt.command_kind == CORE_MEDIA_IMPORT_COMMAND_KIND


def test_read_envelopes_carry_null_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project, path=path)
    media_id = created.data["id"]
    for result in (env.service.list(project), env.service.show(project, media_id)):
        assert result.ok is True
        assert result.receipt is None
        assert result.idempotency_key == ""


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic ids
# ---------------------------------------------------------------------------


def test_import_derives_deterministic_id_from_key(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    expected = derive_stable_id(
        command_kind=CORE_MEDIA_IMPORT_COMMAND_KIND,
        scope=project,
        idempotency_key="k-deterministic",
        ordinal=0,
    )
    result = _import_one(
        env, project, path=path, idempotency_key="k-deterministic"
    )
    assert result.ok is True
    assert result.data["id"] == expected


def test_identical_retry_replays_with_zero_new_rows(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    first = _import_one(env, project, path=path, idempotency_key="k1")
    assert first.ok is True
    first_receipt_id = first.receipt.receipt_id
    assert _media_count(env) == 1

    second = _import_one(env, project, path=path, idempotency_key="k1")
    assert second.ok is True
    assert second.data["id"] == first.data["id"]
    assert second.receipt.receipt_id == first_receipt_id
    assert _media_count(env) == 1


def test_mismatch_returns_idempotency_mismatch_before_mutation(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    first_path = _write(env.root, "in/a.png", PNG_BYTES)
    first = _import_one(env, project, path=first_path, idempotency_key="k1")
    assert first.ok is True

    second_path = _write(env.root, "in/b.png", PNG_BYTES + b"x")
    changed = _import_one(env, project, path=second_path, idempotency_key="k1")
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert _media_count(env) == 1


# ---------------------------------------------------------------------------
# Directory import: sorted, child-keyed, per-file receipts
# ---------------------------------------------------------------------------


def test_directory_import_is_sorted_child_keyed_with_per_file_receipts(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    directory = env.root / "dir"
    _write(directory, "zeta.txt", b"z")
    _write(directory, "alpha.txt", b"a")
    _write(directory, "sub/beta.txt", b"b")
    result = env.service.import_directory(project=project, directory=directory)
    assert result.ok is True
    assert result.receipt is None
    assert [entry["path"] for entry in result.data] == [
        "alpha.txt",
        "zeta.txt",
        "sub/beta.txt",
    ]
    for index, entry in enumerate(result.data):
        assert entry["receipt"] is not None
        assert entry["idempotency_key"] == f"{result.idempotency_key}#{index}"
        assert entry["media"]["id"]
    assert _media_count(env) == 3


def test_directory_import_replay_returns_same_entries_zero_new_rows(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    directory = env.root / "dir"
    _write(directory, "a.txt", b"aa")
    _write(directory, "b.txt", b"bb")

    first = env.service.import_directory(
        project=project, directory=directory, idempotency_key="dir-k"
    )
    assert first.ok is True
    count_after_first = _media_count(env)

    second = env.service.import_directory(
        project=project, directory=directory, idempotency_key="dir-k"
    )
    assert second.ok is True
    assert [e["path"] for e in second.data] == [e["path"] for e in first.data]
    assert [e["idempotency_key"] for e in second.data] == [
        e["idempotency_key"] for e in first.data
    ]
    assert [e["media"]["id"] for e in second.data] == [
        e["media"]["id"] for e in first.data
    ]
    assert _media_count(env) == count_after_first


# ---------------------------------------------------------------------------
# List and show with project scoping
# ---------------------------------------------------------------------------


def test_list_and_show_round_trip(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project, path=path)
    media_id = created.data["id"]

    listed = env.service.list(project)
    assert listed.ok is True
    assert [row["id"] for row in listed.data] == [media_id]

    shown = env.service.show(project, media_id)
    assert shown.ok is True
    assert shown.data == created.data


def test_show_cross_project_returns_not_found(env: SimpleNamespace) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project_a, path=path)

    result = env.service.show(project_b, created.data["id"])
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    project = _create_project(env)
    result = env.service.show(project, "missing-media")
    assert result.ok is False
    assert result.error.code == "not_found"


# ---------------------------------------------------------------------------
# Verify: project-scoped, byte identity, replay
# ---------------------------------------------------------------------------


def test_verify_stamps_verified_at_and_returns_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project, path=path, realm="external_local")
    media_id = created.data["id"]

    result = env.service.verify(
        project, media_id, realm="external_local", idempotency_key="v1"
    )
    assert result.ok is True
    assert result.receipt is not None
    locations = result.data["locations"]
    assert [loc for loc in locations if loc["realm"] == "external_local"][
        0
    ]["verified_at"] is not None


def test_verify_mutated_bytes_changes_zero_rows(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project, path=path, realm="external_local")
    media_id = created.data["id"]

    before_events = _event_count(env)
    path.write_bytes(b"tampered bytes")
    result = env.service.verify(
        project, media_id, realm="external_local", idempotency_key="v-tamper"
    )
    assert result.ok is False
    assert _event_count(env) == before_events


def test_verify_replay_returns_same_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project, path=path, realm="external_local")
    media_id = created.data["id"]

    first = env.service.verify(
        project, media_id, realm="external_local", idempotency_key="v-replay"
    )
    assert first.ok is True
    second = env.service.verify(
        project, media_id, realm="external_local", idempotency_key="v-replay"
    )
    assert second.ok is True
    assert second.receipt.receipt_id == first.receipt.receipt_id


def test_verify_cross_project_returns_not_found(env: SimpleNamespace) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project_a, path=path, realm="external_local")

    result = env.service.verify(
        project_b, created.data["id"], realm="external_local"
    )
    assert result.ok is False
    assert result.error.code == "not_found"


# ---------------------------------------------------------------------------
# Relocate and relate
# ---------------------------------------------------------------------------


def test_relocate_replaces_location_identity_unchanged(env: SimpleNamespace) -> None:
    project = _create_project(env)
    path = _write(env.root, "in/shot.png", PNG_BYTES)
    created = _import_one(env, project, path=path, realm="external_local")
    media_id = created.data["id"]
    original_hash = created.data["content_hash"]

    new_path = _write(env.root, "elsewhere/shot.png", PNG_BYTES)
    result = env.service.relocate(
        project,
        media_id,
        realm="external_local",
        locator=str(new_path),
        idempotency_key="relocate-1",
    )
    assert result.ok is True
    assert result.receipt is not None
    assert result.data["content_hash"] == original_hash


def test_relate_accepts_frozen_kind_and_delegates_rules(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    a = _write(env.root, "in/a.png", PNG_BYTES)
    b = _write(env.root, "in/b.png", PNG_BYTES + b"x")
    media_a = _import_one(env, project, path=a).data["id"]
    media_b = _import_one(env, project, path=b).data["id"]

    ok = env.service.relate(
        project,
        relations=[
            {
                "from_media_id": media_a,
                "to_media_id": media_b,
                "kind": "derived_from",
            }
        ],
        idempotency_key="relate-1",
    )
    assert ok.ok is True
    assert ok.receipt is not None
    assert ok.data["relations"][0]["kind"] == "derived_from"


def test_relate_rejects_non_frozen_kind(env: SimpleNamespace) -> None:
    project = _create_project(env)
    a = _write(env.root, "in/a.png", PNG_BYTES)
    b = _write(env.root, "in/b.png", PNG_BYTES + b"x")
    media_a = _import_one(env, project, path=a).data["id"]
    media_b = _import_one(env, project, path=b).data["id"]

    result = env.service.relate(
        project,
        relations=[
            {
                "from_media_id": media_a,
                "to_media_id": media_b,
                "kind": "not_a_kind",
            }
        ],
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"


def test_relate_rejects_self_edge(env: SimpleNamespace) -> None:
    project = _create_project(env)
    a = _write(env.root, "in/a.png", PNG_BYTES)
    media_a = _import_one(env, project, path=a).data["id"]

    result = env.service.relate(
        project,
        relations=[
            {"from_media_id": media_a, "to_media_id": media_a, "kind": "variant_of"}
        ],
    )
    assert result.ok is False
    assert result.error.code == "validation_error"


def test_frozen_relation_kinds_are_exactly_five() -> None:
    assert MEDIA_RELATION_KINDS == (
        "derived_from",
        "variant_of",
        "uses_as_input",
        "mask_for",
        "audio_for",
    )
