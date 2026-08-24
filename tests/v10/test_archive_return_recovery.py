"""Regression coverage for the live two-session archive/return failure."""

from __future__ import annotations

from pathlib import Path

from astrid.application import compose_standard_application

TINY_PNG = (
    Path(__file__).parents[1] / "packs" / "builtin" / "generate_image" / "fixtures" / "tiny.png"
)


def _data(result):
    assert result.ok is True, result.as_dict()
    return result.data


def test_timeline_archive_is_discoverable_and_repeat_unarchive_is_noop(
    tmp_path: Path,
) -> None:
    with compose_standard_application(tmp_path) as app:
        _data(app.projects_service.create(slug="return-later", name="Return Later"))
        created = _data(
            app.timelines_service.create(
                project="return-later",
                slug="primary",
                name="Primary",
                config={"paused_note": "return later"},
                set_default=True,
            )
        )
        timeline_id = created["timeline_id"]

        _data(app.timelines_service.archive("return-later", "primary"))
        assert _data(app.timelines_service.list("return-later")) == []
        inclusive = _data(app.timelines_service.list("return-later", include_archived=True))
        assert len(inclusive) == 1
        assert inclusive[0]["timeline_id"] == timeline_id
        assert inclusive[0]["slug"] == "primary"
        assert inclusive[0]["archived_at"] is not None

        restored = app.timelines_service.unarchive("return-later", "primary")
        assert _data(restored)["changed"] is True
        assert restored.receipt is not None
        repeated = app.timelines_service.unarchive("return-later", "primary")
        assert _data(repeated)["changed"] is False
        assert repeated.receipt is None
        assert repeated.data["config_version"] == restored.data["config_version"]

        shown = _data(app.timelines_service.show("return-later", "primary"))
        assert shown["timeline_id"] == timeline_id
        assert shown["config"] == {"paused_note": "return later"}
        saved = _data(
            app.timelines_service.save(
                "return-later",
                "primary",
                config={"paused_note": "resumed"},
                registry={"assets": {}},
                expected_version=shown["config_version"],
            )
        )
        assert saved["timeline_id"] == timeline_id
        assert len(_data(app.timelines_service.list("return-later"))) == 1


def test_reference_unarchive_by_unique_name_preserves_identity_and_media(
    tmp_path: Path,
) -> None:
    with compose_standard_application(tmp_path) as app:
        _data(app.projects_service.create(slug="return-later", name="Return Later"))
        media = _data(app.media_service.import_file(project="return-later", path=TINY_PNG))
        reference = _data(
            app.references_service.create(
                project="return-later",
                kind="character",
                name="Seed",
                media_id=media["id"],
            )
        )
        reference_id = reference["id"]
        media_reference_id = reference["media"][0]["id"]

        _data(app.references_service.archive("return-later", reference_id))
        inclusive = _data(app.references_service.list("return-later", include_archived=True))
        assert inclusive[0]["name"] == "Seed"
        assert inclusive[0]["archived_at"] is not None

        restored = app.references_service.unarchive("return-later", "Seed")
        assert _data(restored)["changed"] is True
        repeated = app.references_service.unarchive("return-later", "Seed")
        assert _data(repeated)["changed"] is False
        assert repeated.receipt is None

        shown = _data(app.references_service.show("return-later", reference_id))
        assert shown["id"] == reference_id
        assert shown["archived_at"] is None
        assert shown["media"][0]["id"] == media_reference_id
        assert shown["media"][0]["media_id"] == media["id"]
        assert len(_data(app.references_service.list("return-later"))) == 1
        assert len(_data(app.media_service.list("return-later"))) == 1


def test_reference_recovery_name_fails_closed_when_ambiguous(tmp_path: Path) -> None:
    with compose_standard_application(tmp_path) as app:
        _data(app.projects_service.create(slug="demo", name="Demo"))
        media = _data(app.media_service.import_file(project="demo", path=TINY_PNG))
        ids = []
        for key in ("seed-one", "seed-two"):
            reference = _data(
                app.references_service.create(
                    project="demo",
                    kind="character",
                    name="Seed",
                    media_id=media["id"],
                    idempotency_key=key,
                )
            )
            ids.append(reference["id"])
            _data(app.references_service.archive("demo", reference["id"]))

        result = app.references_service.unarchive("demo", "Seed")
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "validation_error"
        assert sorted(result.error.details["candidate_ids"]) == sorted(ids)
        assert _data(app.references_service.list("demo")) == []
