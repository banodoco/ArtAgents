"""Public T06/T07 contract tests for ShotsService text bindings."""

from __future__ import annotations

from pathlib import Path

from astrid.application import compose_standard_application
from astrid.core.store.uow import UnitOfWork
from astrid.packs.shots.repository import ShotRepository
from astrid.packs.shots.text_bindings import ShotTextBindingRepository


ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}
BINDING_KEYS = {
    "binding_id",
    "project_id",
    "shot_id",
    "kind",
    "slot",
    "media_id",
    "event_stream_id",
    "head",
    "content_hash",
    "mime_type",
    "byte_size",
    "created_at",
    "updated_at",
}
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


def _seed(app) -> tuple[str, str]:
    project = UnitOfWork(app.writer).run(
        lambda uow: app.projects.create(
            uow,
            slug="sdk-text",
            name="SDK Text",
            settings={},
            idempotency_key="sdk-text-project",
        )
    )
    shot = UnitOfWork(app.writer).run(
        lambda uow: app.shots.create(
            uow,
            project_id=project.id,
            name="Opening",
            idempotency_key="sdk-text-shot",
        )
    )
    return project.id, shot.id


def test_standard_composition_exposes_one_shared_text_repository(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        assert isinstance(app.text_bindings, ShotTextBindingRepository)
        assert app.shot_text_bindings is app.text_bindings
        assert isinstance(app.shots, ShotRepository)
        assert app.shots_service._text_bindings is app.text_bindings
        assert app.shots_service._media is app.media
        assert app.shots_service._writer is app.writer


def test_set_returns_frozen_binding_envelope_and_receipt(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        result = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="transcript",
            text=b"hello\n",
            expected_head=0,
            idempotency_key="set-one",
        )

        assert set(result.as_dict()) == ENVELOPE_KEYS
        assert result.ok is True
        assert result.idempotency_key == "set-one"
        assert result.data["changed"] is True
        assert set(result.data["binding"]) == BINDING_KEYS
        assert "timeline_id" not in result.data["binding"]
        assert result.data["binding"]["head"] == 1
        assert result.data["binding"]["mime_type"] == "text/plain"
        assert result.receipt is not None
        assert set(result.receipt.as_dict()) == RECEIPT_KEYS
        assert result.receipt.command_kind == "shot.text_binding.set"
        assert len(result.receipt.event_ids) == 2
        assert result.receipt.result == result.data


def test_replay_precedes_cas_and_changed_key_is_rejected(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        first = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="prompt",
            text=b"one",
            expected_head=0,
            idempotency_key="replay-key",
        )
        replay = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="prompt",
            text=b"one",
            expected_head=0,
            idempotency_key="replay-key",
        )
        assert replay.as_dict() == first.as_dict()

        mismatch = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="prompt",
            text=b"different",
            expected_head=0,
            idempotency_key="replay-key",
        )
        assert mismatch.ok is False
        assert mismatch.error.code == "idempotency_mismatch"
        assert mismatch.receipt is None


def test_noop_does_not_consume_key_and_then_changed_work_records_receipt(
    tmp_path: Path,
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        created = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="voiceover_script",
            text=b"same",
            expected_head=0,
            idempotency_key="create-key",
        )
        no_op = app.shots_service.set_text_binding(
            project_id,
            binding_id=created.data["binding"]["binding_id"],
            text=b"same",
            expected_head=1,
            idempotency_key="reusable-key",
        )
        assert no_op.ok is True
        assert no_op.data["changed"] is False
        assert no_op.receipt is None
        assert no_op.idempotency_key == "reusable-key"

        changed = app.shots_service.set_text_binding(
            project_id,
            binding_id=created.data["binding"]["binding_id"],
            text=b"changed",
            expected_head=1,
            idempotency_key="reusable-key",
        )
        assert changed.ok is True
        assert changed.data["changed"] is True
        assert changed.data["binding"]["head"] == 2
        assert changed.receipt is not None


def test_rebind_uses_existing_media_and_has_public_result_shape(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        first = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="transcript",
            text=b"first",
            expected_head=0,
            idempotency_key="first-key",
        )
        second = app.shots_service.set_text_binding(
            project_id,
            binding_id=first.data["binding"]["binding_id"],
            text=b"second",
            expected_head=1,
            idempotency_key="second-key",
        )
        rebound = app.shots_service.rebind_text_binding(
            project_id,
            binding_id=first.data["binding"]["binding_id"],
            media_id=first.data["binding"]["media_id"],
            expected_head=2,
            idempotency_key="rebind-key",
        )
        assert rebound.ok is True
        assert rebound.data["changed"] is True
        assert rebound.data["binding"]["media_id"] == first.data["binding"]["media_id"]
        assert rebound.data["binding"]["head"] == 3
        assert rebound.receipt is not None
        assert rebound.receipt.command_kind == "shot.text_binding.rebind"
        assert len(rebound.receipt.event_ids) == 1

        replay = app.shots_service.rebind_text_binding(
            project_id,
            binding_id=first.data["binding"]["binding_id"],
            media_id=first.data["binding"]["media_id"],
            expected_head=2,
            idempotency_key="rebind-key",
        )
        assert replay.as_dict() == rebound.as_dict()
        assert second.data["binding"]["media_id"] != first.data["binding"]["media_id"]


def test_list_supports_friendly_and_exact_modes(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        created = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="prompt",
            slot="regen-glitch",
            text=b"alternate",
            expected_head=0,
            idempotency_key="alternate-key",
        )
        friendly = app.shots_service.list_text_bindings(
            project_id, shot_ref="Opening", kind="prompt"
        )
        exact = app.shots_service.list_text_bindings(
            project_id, binding_ids=[created.data["binding"]["binding_id"]]
        )
        assert friendly.ok and exact.ok
        assert friendly.receipt is None and friendly.idempotency_key == ""
        assert exact.data == friendly.data
        assert exact.data[0]["slot"] == "regen-glitch"
