"""Executable shot SDK service tests (m4 plan step 16, task T17).

Proves ``astrid.sdk.shots.ShotsService`` exposes repository-backed,
envelope-shaped ``list``/``show``/``create``/``add_item``/``remove_item``/
``reorder`` over the shots pack repository:

- the five-key envelope shape with the committed nine-key receipt on
  mutations and a null receipt on pure reads;
- deterministic shot and item ids derived from the idempotency key, so an
  identical retry replays with zero new rows and a changed request under the
  same key returns ``idempotency_mismatch`` before any mutation;
- ``add_item`` preserves exact-media order and the ``0 .. count`` position
  domain; out-of-range positions and foreign media are rejected before any
  write;
- ``remove_item`` deletes only the ``shot_items`` row (kernel media is
  preserved) and renormalizes the remaining order;
- ``reorder`` accepts exactly one whole-shot permutation and rejects
  omissions/duplicates/extras before any write;
- cross-project and missing shots are typed ``not_found``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.io.media_import import prepare_media_file
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import build_standard_registry
from astrid.packs.shots.repository import (
    SHOT_ADD_ITEM_COMMAND_KIND,
    SHOT_CREATE_COMMAND_KIND,
    ShotRepository,
)
from astrid.sdk.contracts import derive_stable_id
from astrid.sdk.shots import ShotsService

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
    """A fresh standard writer, repositories, and shot service."""
    registry = build_standard_registry()
    writer = DatabaseWriter(tmp_path / "shots.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        media = MediaRepository(
            events=events, receipts=receipts, projects_root=tmp_path
        )
        shots = ShotRepository(events=events, receipts=receipts)
        yield SimpleNamespace(
            service=ShotsService(writer, projects, shots, receipts),
            writer=writer,
            projects=projects,
            media=media,
            shots=shots,
            root=tmp_path,
        )
    finally:
        writer.close()


def _create_project(env: SimpleNamespace, slug: str = "pilot") -> str:
    project_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.projects.create(
            u,
            slug=slug,
            name=slug.title(),
            settings={},
            idempotency_key=f"create-{slug}-k",
            project_id=project_id,
        )
    )
    return project_id


_IMPORT_SEQ = 0


def _import_media(
    env: SimpleNamespace,
    project_id: str,
    *,
    data: bytes | None = None,
) -> str:
    global _IMPORT_SEQ
    _IMPORT_SEQ += 1
    # Media is content-addressed: distinct bytes guarantee a distinct media
    # row, so callers importing several media in one test never collide.
    content = data if data is not None else PNG_BYTES + str(_IMPORT_SEQ).encode()
    path = env.root / f"media-{generate_lowercase_ulid()}.png"
    path.write_bytes(content)
    prepared = prepare_media_file(path)
    media_id = generate_lowercase_ulid()
    UnitOfWork(env.writer).run(
        lambda u: env.media.import_prepared(
            u,
            project_id=project_id,
            prepared=prepared,
            idempotency_key=f"import-{media_id}",
            media_id=media_id,
            realm="external_local",
        )
    )
    return media_id


def _shot_count(env: SimpleNamespace) -> int:
    return env.writer.submit(lambda s: s.query_one("SELECT COUNT(*) FROM shots")[0])


def _media_count(env: SimpleNamespace) -> int:
    return env.writer.submit(lambda s: s.query_one("SELECT COUNT(*) FROM media")[0])


def _create_shot(
    env: SimpleNamespace,
    project: str,
    *,
    name: str = "Opening",
    idempotency_key: str | None = None,
):
    return env.service.create(
        project=project, name=name, idempotency_key=idempotency_key
    )


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_create_envelope_has_exactly_five_keys(env: SimpleNamespace) -> None:
    project = _create_project(env)
    result = _create_shot(env, project)
    assert result.ok is True
    assert set(result.as_dict().keys()) == ENVELOPE_KEYS
    assert result.error is None
    assert result.receipt is not None
    assert set(result.receipt.as_dict().keys()) == RECEIPT_KEYS
    assert result.receipt.command_kind == SHOT_CREATE_COMMAND_KIND


def test_read_envelopes_carry_null_receipt(env: SimpleNamespace) -> None:
    project = _create_project(env)
    created = _create_shot(env, project)
    shot_id = created.data["id"]
    for result in (env.service.list(project), env.service.show(project, shot_id)):
        assert result.ok is True
        assert result.receipt is None
        assert result.idempotency_key == ""


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic ids
# ---------------------------------------------------------------------------


def test_create_derives_deterministic_id_from_key(env: SimpleNamespace) -> None:
    project = _create_project(env)
    expected = derive_stable_id(
        command_kind=SHOT_CREATE_COMMAND_KIND,
        scope=project,
        idempotency_key="k-deterministic",
        ordinal=0,
    )
    result = _create_shot(
        env, project, idempotency_key="k-deterministic"
    )
    assert result.ok is True
    assert result.data["id"] == expected


def test_identical_retry_replays_with_zero_new_rows(env: SimpleNamespace) -> None:
    project = _create_project(env)
    first = _create_shot(env, project, idempotency_key="k1")
    assert first.ok is True
    first_receipt_id = first.receipt.receipt_id
    assert _shot_count(env) == 1

    second = _create_shot(env, project, idempotency_key="k1")
    assert second.ok is True
    assert second.data["id"] == first.data["id"]
    assert second.receipt.receipt_id == first_receipt_id
    assert _shot_count(env) == 1


def test_mismatch_returns_idempotency_mismatch_before_mutation(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    first = _create_shot(env, project, idempotency_key="k1")
    assert first.ok is True

    changed = _create_shot(env, project, name="Changed", idempotency_key="k1")
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert _shot_count(env) == 1


# ---------------------------------------------------------------------------
# add_item: position domain and exact-media ordering
# ---------------------------------------------------------------------------


def test_add_item_keeps_exact_normalized_order(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    shot_id = _create_shot(env, project).data["id"]

    first = env.service.add_item(
        project, shot_id, media_id=media_a, position=0, idempotency_key="add-a"
    )
    assert first.ok is True
    assert first.data["item_ids"] == [first.data["item"]["id"]]

    second = env.service.add_item(
        project, shot_id, media_id=media_b, position=1, idempotency_key="add-b"
    )
    assert second.ok is True
    assert second.data["item_ids"] == [
        first.data["item"]["id"],
        second.data["item"]["id"],
    ]

    shown = env.service.show(project, shot_id)
    assert shown.ok is True
    assert [i["media_id"] for i in shown.data["items"]] == [media_a, media_b]
    assert [i["position"] for i in shown.data["items"]] == [0, 1]


def test_add_item_derives_deterministic_item_id(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    shot_id = _create_shot(env, project).data["id"]
    expected = derive_stable_id(
        command_kind=SHOT_ADD_ITEM_COMMAND_KIND,
        scope=project,
        idempotency_key="add-deterministic",
        ordinal=0,
    )
    result = env.service.add_item(
        project,
        shot_id,
        media_id=media_id,
        position=0,
        idempotency_key="add-deterministic",
    )
    assert result.ok is True
    assert result.data["item"]["id"] == expected


def test_add_item_out_of_range_position_rejected(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_id = _import_media(env, project)
    shot_id = _create_shot(env, project).data["id"]

    result = env.service.add_item(
        project, shot_id, media_id=media_id, position=4, idempotency_key="bad"
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"

    shown = env.service.show(project, shot_id)
    assert shown.ok is True
    assert shown.data["items"] == []


def test_add_item_foreign_media_returns_validation_error(
    env: SimpleNamespace,
) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    media_id = _import_media(env, project_a)
    shot_id = _create_shot(env, project_b).data["id"]

    result = env.service.add_item(
        project_b, shot_id, media_id=media_id, position=0, idempotency_key="x"
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"


# ---------------------------------------------------------------------------
# remove_item: media preserved, order renormalized
# ---------------------------------------------------------------------------


def test_remove_item_preserves_media_and_renormalizes(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    shot_id = _create_shot(env, project).data["id"]
    env.service.add_item(
        project, shot_id, media_id=media_a, position=0, idempotency_key="add-a"
    )
    added_b = env.service.add_item(
        project, shot_id, media_id=media_b, position=1, idempotency_key="add-b"
    )
    item_b_id = added_b.data["item"]["id"]
    media_before = _media_count(env)

    removed = env.service.remove_item(
        project, shot_id, item_b_id, idempotency_key="remove-b"
    )
    assert removed.ok is True
    assert removed.receipt is not None
    # The removed item's media identity is carried by the receipt result.
    assert removed.data["item"]["media_id"] == media_b
    # Kernel media rows and bytes are preserved.
    assert _media_count(env) == media_before

    shown = env.service.show(project, shot_id)
    assert shown.ok is True
    assert [i["media_id"] for i in shown.data["items"]] == [media_a]
    assert [i["position"] for i in shown.data["items"]] == [0]


# ---------------------------------------------------------------------------
# reorder: exact whole-shot permutation
# ---------------------------------------------------------------------------


def test_reorder_accepts_exact_permutation(env: SimpleNamespace) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    shot_id = _create_shot(env, project).data["id"]
    item_a = env.service.add_item(
        project, shot_id, media_id=media_a, position=0, idempotency_key="add-a"
    ).data["item"]["id"]
    item_b = env.service.add_item(
        project, shot_id, media_id=media_b, position=1, idempotency_key="add-b"
    ).data["item"]["id"]

    reordered = env.service.reorder(
        project, shot_id, [item_b, item_a], idempotency_key="reorder-1"
    )
    assert reordered.ok is True
    assert reordered.receipt is not None
    assert reordered.data["item_ids"] == [item_b, item_a]
    assert reordered.data["media_ids"] == [media_b, media_a]

    shown = env.service.show(project, shot_id)
    assert shown.ok is True
    assert [i["media_id"] for i in shown.data["items"]] == [media_b, media_a]


def test_reorder_rejects_non_permutation_before_any_write(
    env: SimpleNamespace,
) -> None:
    project = _create_project(env)
    media_a = _import_media(env, project)
    media_b = _import_media(env, project)
    media_c = _import_media(env, project)
    shot_id = _create_shot(env, project).data["id"]
    item_a = env.service.add_item(
        project, shot_id, media_id=media_a, position=0, idempotency_key="add-a"
    ).data["item"]["id"]
    item_b = env.service.add_item(
        project, shot_id, media_id=media_b, position=1, idempotency_key="add-b"
    ).data["item"]["id"]
    env.service.add_item(
        project, shot_id, media_id=media_c, position=2, idempotency_key="add-c"
    )

    before = env.service.show(project, shot_id).data["items"]
    for bad_ids in (
        [item_b, item_a],  # omission
        [item_b, item_b, item_a],  # duplicate
        [item_b, item_a, "nonexistent"],  # extra
    ):
        result = env.service.reorder(
            project, shot_id, bad_ids, idempotency_key=f"bad-{len(bad_ids)}"
        )
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "validation_error"

    after = env.service.show(project, shot_id).data["items"]
    assert [i["id"] for i in after] == [i["id"] for i in before]


# ---------------------------------------------------------------------------
# list / show and not-found
# ---------------------------------------------------------------------------


def test_list_and_show_round_trip(env: SimpleNamespace) -> None:
    project = _create_project(env)
    created = _create_shot(env, project)
    shot_id = created.data["id"]

    listed = env.service.list(project)
    assert listed.ok is True
    assert [row["id"] for row in listed.data] == [shot_id]

    shown = env.service.show(project, shot_id)
    assert shown.ok is True
    assert shown.data["id"] == shot_id


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    project = _create_project(env)
    result = env.service.show(project, "missing-shot")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_show_cross_project_returns_not_found(env: SimpleNamespace) -> None:
    project_a = _create_project(env, slug="alpha")
    project_b = _create_project(env, slug="beta")
    created = _create_shot(env, project_a)

    result = env.service.show(project_b, created.data["id"])
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"
