"""Public T06/T07 contract tests for ShotsService text bindings."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

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


def test_positive_head_friendly_and_exact_set_replay_share_canonical_receipt(
    tmp_path: Path,
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        first = app.shots_service.set_text_binding(
            project_id, shot_ref="Opening", kind="transcript", text=b"same",
            expected_head=0, idempotency_key="canonical-set",
        )
        changed = app.shots_service.set_text_binding(
            project_id, shot_ref="Opening", kind="transcript", text=b"changed",
            expected_head=1, idempotency_key="canonical-positive-set",
        )
        replay = app.shots_service.set_text_binding(
            project_id, binding_id=first.data["binding"]["binding_id"], text=b"changed",
            expected_head=1, idempotency_key="canonical-positive-set",
        )
        assert changed.ok and replay.ok
        assert replay.as_dict() == changed.as_dict()
        assert replay.receipt.request_hash == changed.receipt.request_hash
        assert replay.data["binding"]["binding_id"] != shot_id


@pytest.mark.parametrize("existing", [True, False])
def test_exact_binding_id_head_zero_is_rejected_before_uow(
    tmp_path: Path, monkeypatch, existing: bool
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, _shot_id = _seed(app)
        binding_id = "missing-binding-id"
        if existing:
            created = app.shots_service.set_text_binding(
                project_id, shot_ref="Opening", kind="transcript", text=b"stable",
                expected_head=0, idempotency_key="head-zero-setup",
            )
            binding_id = created.data["binding"]["binding_id"]
        before = app.writer.submit(
            lambda session: session.query_one(
                "SELECT (SELECT COUNT(*) FROM events), "
                "(SELECT COUNT(*) FROM command_receipts), "
                "(SELECT COUNT(*) FROM shot_text_bindings)"
            )
        )
        calls = 0
        original_run = __import__("astrid.sdk.shots", fromlist=["UnitOfWork"]).UnitOfWork.run

        def counted(self, callback):
            nonlocal calls
            calls += 1
            return original_run(self, callback)

        monkeypatch.setattr("astrid.sdk.shots.UnitOfWork.run", counted)
        result = app.shots_service.set_text_binding(
            project_id, binding_id=binding_id, text=b"rejected",
            expected_head=0, idempotency_key=f"head-zero-{existing}",
        )
        after = app.writer.submit(
            lambda session: session.query_one(
                "SELECT (SELECT COUNT(*) FROM events), "
                "(SELECT COUNT(*) FROM command_receipts), "
                "(SELECT COUNT(*) FROM shot_text_bindings)"
            )
        )
        assert result.ok is False
        assert result.error.code == "validation_error"
        assert result.error.details["reason"] == "expected_head"
        assert calls == 0
        assert tuple(after) == tuple(before)


def test_friendly_and_exact_rebind_replay_share_canonical_receipt(tmp_path: Path) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, _shot_id = _seed(app)
        first = app.shots_service.set_text_binding(
            project_id, shot_ref="Opening", kind="transcript", text=b"first",
            expected_head=0, idempotency_key="canonical-first",
        )
        second = app.shots_service.set_text_binding(
            project_id, binding_id=first.data["binding"]["binding_id"], text=b"second",
            expected_head=1, idempotency_key="canonical-second",
        )
        friendly = app.shots_service.rebind_text_binding(
            project_id, shot_ref="Opening", kind="transcript",
            media_id=first.data["binding"]["media_id"], expected_head=2,
            idempotency_key="canonical-rebind",
        )
        exact = app.shots_service.rebind_text_binding(
            project_id, binding_id=first.data["binding"]["binding_id"],
            media_id=first.data["binding"]["media_id"], expected_head=2,
            idempotency_key="canonical-rebind",
        )
        assert friendly.ok and exact.ok
        assert exact.as_dict() == friendly.as_dict()
        assert exact.receipt.request_hash == friendly.receipt.request_hash
        assert second.data["binding"]["media_id"] != first.data["binding"]["media_id"]


def test_invalid_utf8_is_public_detail_and_opens_no_uow_or_temp(tmp_path: Path, monkeypatch) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, _shot_id = _seed(app)
        calls = 0
        original_run = __import__("astrid.sdk.shots", fromlist=["UnitOfWork"]).UnitOfWork.run

        def counted(self, callback):
            nonlocal calls
            calls += 1
            return original_run(self, callback)

        monkeypatch.setattr("astrid.sdk.shots.UnitOfWork.run", counted)
        temp_root = Path(tempfile.gettempdir())
        before = set(temp_root.glob(".astrid-shot-text-*.txt"))
        result = app.shots_service.set_text_binding(
            project_id, shot_ref="Opening", kind="transcript", text=b"\xff",
            expected_head=0, idempotency_key="invalid",
        )
        after = set(temp_root.glob(".astrid-shot-text-*.txt"))
        assert result.error.code == "validation_error"
        assert result.error.details["reason"] == "invalid_utf8"
        assert calls == 0
        assert after == before


def _sdk_persisted_binding_snapshot(app, *, project_id: str, binding_id: str) -> dict[str, object]:
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

    return app.writer.submit(capture)


def test_malformed_bound_hash_is_public_integrity_zero_write_and_no_temp(
    tmp_path: Path, monkeypatch
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        created = app.shots_service.set_text_binding(
            project_id,
            shot_ref=shot_id,
            kind="transcript",
            text=b"stable",
            expected_head=0,
            idempotency_key="malformed-hash-create",
        )
        binding_id = created.data["binding"]["binding_id"]
        media_id = created.data["binding"]["media_id"]
        app.writer.submit(
            lambda s: s.execute(
                "UPDATE media SET content_hash = ? WHERE id = ?",
                ("malformed", media_id),
            )
        )
        before = _sdk_persisted_binding_snapshot(
            app, project_id=project_id, binding_id=binding_id
        )
        temp_root = Path(tempfile.gettempdir())
        temp_before = set(temp_root.glob(".astrid-shot-text-*.txt"))
        materialize_calls = 0

        def forbidden_materialization(*args, **kwargs):
            nonlocal materialize_calls
            materialize_calls += 1
            raise AssertionError("malformed current hash must fail before materialization")

        monkeypatch.setattr(app.text_bindings, "materialize_absent_text", forbidden_materialization)
        monkeypatch.setattr(
            tempfile,
            "NamedTemporaryFile",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("malformed current hash must create no temp")
            ),
        )
        result = app.shots_service.set_text_binding(
            project_id,
            binding_id=binding_id,
            text=b"next",
            expected_head=1,
            idempotency_key="malformed-hash-set",
        )
        after = _sdk_persisted_binding_snapshot(
            app, project_id=project_id, binding_id=binding_id
        )
        assert result.ok is False
        assert result.error.code == "integrity_error"
        assert result.error.code != "internal_error"
        assert result.error.details == {
            "entity": "text_binding_media",
            "reason": "managed_hash_mismatch",
        }
        assert result.receipt is None
        assert after == before
        assert materialize_calls == 0
        assert set(temp_root.glob(".astrid-shot-text-*.txt")) == temp_before


def test_canonical_managed_symlink_is_public_integrity_zero_write_and_no_temp(
    tmp_path: Path, monkeypatch
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        created = app.shots_service.set_text_binding(
            project_id, shot_ref=shot_id, kind="transcript", text=b"stable",
            expected_head=0, idempotency_key="symlink-create",
        )
        binding_id = created.data["binding"]["binding_id"]
        media_id = created.data["binding"]["media_id"]
        from astrid.core.io.media_import import managed_media_path

        canonical = managed_media_path(tmp_path, created.data["binding"]["content_hash"])
        target = tmp_path / "same-byte-target.txt"
        target.write_bytes(b"stable")
        canonical.unlink()
        canonical.symlink_to(target)
        before = _sdk_persisted_binding_snapshot(app, project_id=project_id, binding_id=binding_id)
        temp_root = Path(tempfile.gettempdir())
        temp_before = set(temp_root.glob(".astrid-shot-text-*.txt"))
        materialize_calls = 0

        def forbidden_materialization(*args, **kwargs):
            nonlocal materialize_calls
            materialize_calls += 1
            raise AssertionError("symlinked current media must fail before materialization")

        monkeypatch.setattr(app.text_bindings, "materialize_absent_text", forbidden_materialization)
        monkeypatch.setattr(
            tempfile,
            "NamedTemporaryFile",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("symlinked current media must create no temp")
            ),
        )
        result = app.shots_service.set_text_binding(
            project_id, binding_id=binding_id, text=b"next", expected_head=1,
            idempotency_key="symlink-set",
        )
        after = _sdk_persisted_binding_snapshot(app, project_id=project_id, binding_id=binding_id)
        assert result.ok is False
        assert result.error.code == "integrity_error"
        assert result.error.code != "internal_error"
        assert result.error.details == {
            "entity": "text_binding_media",
            "reason": "managed_file_symlink",
        }
        assert result.receipt is None
        assert after == before
        assert materialize_calls == 0
        assert set(temp_root.glob(".astrid-shot-text-*.txt")) == temp_before
        assert media_id == created.data["binding"]["media_id"]


def test_stored_managed_locator_symlink_is_public_integrity_zero_write_and_no_temp(
    tmp_path: Path, monkeypatch
) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, shot_id = _seed(app)
        created = app.shots_service.set_text_binding(
            project_id, shot_ref=shot_id, kind="transcript", text=b"stable",
            expected_head=0, idempotency_key="locator-symlink-create",
        )
        binding_id = created.data["binding"]["binding_id"]
        media_id = created.data["binding"]["media_id"]
        from astrid.core.io.media_import import managed_media_path

        canonical = managed_media_path(tmp_path, created.data["binding"]["content_hash"])
        alias = tmp_path / "managed-locator-alias.txt"
        alias.symlink_to(canonical)
        app.writer.submit(
            lambda s: s.execute(
                "UPDATE media_locations SET locator = ? WHERE media_id = ? AND realm = 'managed_local'",
                (str(alias), media_id),
            )
        )
        before = _sdk_persisted_binding_snapshot(app, project_id=project_id, binding_id=binding_id)
        temp_root = Path(tempfile.gettempdir())
        temp_before = set(temp_root.glob(".astrid-shot-text-*.txt"))
        materialize_calls = 0

        def forbidden_materialization(*args, **kwargs):
            nonlocal materialize_calls
            materialize_calls += 1
            raise AssertionError("symlinked stored locator must fail before materialization")

        monkeypatch.setattr(app.text_bindings, "materialize_absent_text", forbidden_materialization)
        monkeypatch.setattr(
            tempfile,
            "NamedTemporaryFile",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("symlinked stored locator must create no temp")
            ),
        )
        result = app.shots_service.set_text_binding(
            project_id, binding_id=binding_id, text=b"next", expected_head=1,
            idempotency_key="locator-symlink-set",
        )
        after = _sdk_persisted_binding_snapshot(app, project_id=project_id, binding_id=binding_id)
        assert result.ok is False
        assert result.error.code == "integrity_error"
        assert result.error.details == {
            "entity": "text_binding_media",
            "reason": "managed_file_symlink",
        }
        assert result.receipt is None
        assert after == before
        assert materialize_calls == 0
        assert set(temp_root.glob(".astrid-shot-text-*.txt")) == temp_before


def test_sdk_freezes_once_and_passes_immutable_bytes_into_uow(tmp_path: Path, monkeypatch) -> None:
    with compose_standard_application(projects_root=tmp_path) as app:
        project_id, _shot_id = _seed(app)
        import astrid.packs.shots.text_bindings as bindings_module
        import astrid.sdk.shots as shots_module
        calls = 0
        original_freeze = shots_module.freeze_text_bytes

        def counted(value):
            nonlocal calls
            calls += 1
            return original_freeze(value)

        monkeypatch.setattr(shots_module, "freeze_text_bytes", counted)
        monkeypatch.setattr(
            bindings_module, "freeze_text_bytes",
            lambda value: (_ for _ in ()).throw(AssertionError("in-UoW freeze")),
        )
        result = app.shots_service.set_text_binding(
            project_id, shot_ref="Opening", kind="transcript", text=b"frozen",
            expected_head=0, idempotency_key="freeze-once",
        )
        assert result.ok
        assert calls == 1
