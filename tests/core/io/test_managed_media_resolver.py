from __future__ import annotations

import hashlib
from pathlib import Path

from astrid.application import compose_standard_application
from astrid.core.backup import create_backup, restore_backup
from astrid.core.io.managed_media_resolver import (
    rebase_timeline_registry_managed_assets,
    resolve_owned_managed_media,
)


def _seed_managed(root: Path) -> tuple[str, str]:
    payload = b"portable managed timeline asset"
    source = root / "frame.png"
    root.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="project"
        )
        assert project.ok, project.error
        media = app.media_service.import_file(
            project="demo", path=source, idempotency_key="media"
        )
        assert media.ok, media.error
        return (
            str(media.data["locations"][0]["locator"]),
            hashlib.sha256(payload).hexdigest(),
        )


def test_stale_timeline_managed_locator_is_derived_after_restore(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    restored_root = tmp_path / "restored"
    old_locator, digest = _seed_managed(source_root)
    backup = tmp_path / "backup"
    create_backup(projects_root=source_root, dest_path=backup)
    restore_backup(backup, projects_root=restored_root)

    derived = rebase_timeline_registry_managed_assets(
        {
            "assets": {
                "frame": {
                    "file": old_locator,
                    "content_sha256": digest,
                    "type": "image/png",
                }
            }
        },
        projects_root=restored_root,
        project_ref="demo",
    )
    current = Path(derived["assets"]["frame"]["file"])

    assert current != Path(old_locator)
    assert current.is_file()
    assert current.read_bytes() == b"portable managed timeline asset"
    assert resolve_owned_managed_media(
        projects_root=restored_root,
        project_ref="demo",
        content_hash=digest,
        requested_path=current,
    ) == current.resolve()


def test_stale_timeline_managed_locator_without_registry_hash_is_derived(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    restored_root = tmp_path / "restored"
    old_locator, _digest = _seed_managed(source_root)
    backup = tmp_path / "backup"
    create_backup(projects_root=source_root, dest_path=backup)
    restore_backup(backup, projects_root=restored_root)

    derived = rebase_timeline_registry_managed_assets(
        {"assets": {"frame": {"file": old_locator, "type": "image/png"}}},
        projects_root=restored_root,
        project_ref="demo",
    )
    current = Path(derived["assets"]["frame"]["file"])

    assert current != Path(old_locator)
    assert current.is_file()
    assert current.read_bytes() == b"portable managed timeline asset"


def test_hashless_rebase_rejects_malformed_or_unowned_managed_shapes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    _old_locator, digest = _seed_managed(root)
    malformed = tmp_path / ".astrid" / "media" / "sha256" / "xx" / "yy" / digest
    shaped = tmp_path / ".astrid" / "media" / "sha256" / digest[:2] / digest[2:4] / digest

    malformed_registry = {"assets": {"frame": {"file": str(malformed)}}}
    assert rebase_timeline_registry_managed_assets(
        malformed_registry,
        projects_root=root,
        project_ref="demo",
    ) == malformed_registry

    unowned_registry = {"assets": {"frame": {"file": str(shaped)}}}
    assert rebase_timeline_registry_managed_assets(
        unowned_registry,
        projects_root=root,
        project_ref="another-project",
    ) == unowned_registry


def test_hashless_rebase_fails_closed_when_current_managed_bytes_changed(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    restored_root = tmp_path / "restored"
    old_locator, digest = _seed_managed(source_root)
    backup = tmp_path / "backup"
    create_backup(projects_root=source_root, dest_path=backup)
    restore_backup(backup, projects_root=restored_root)
    current = (
        restored_root
        / ".astrid"
        / "media"
        / "sha256"
        / digest[:2]
        / digest[2:4]
        / digest
    )
    current.write_bytes(b"tampered")
    registry = {"assets": {"frame": {"file": old_locator}}}

    assert rebase_timeline_registry_managed_assets(
        registry,
        projects_root=restored_root,
        project_ref="demo",
    ) == registry


def test_registry_rebase_fails_closed_for_non_managed_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _old_locator, digest = _seed_managed(root)
    foreign = tmp_path / "foreign" / digest
    registry = {"assets": {"frame": {"file": str(foreign), "content_sha256": digest}}}

    assert rebase_timeline_registry_managed_assets(
        registry,
        projects_root=root,
        project_ref="demo",
    ) == registry


def test_media_id_derives_verified_locator_hash_and_type_without_event_mutation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    payload = b"project-owned managed bytes"
    source = tmp_path / "frame.png"
    source.write_bytes(payload)
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="project"
        )
        assert project.ok, project.error
        imported = app.media_service.import_file(
            project="demo", path=source, idempotency_key="media"
        )
        assert imported.ok, imported.error
        media_id = imported.data["id"]
        digest = imported.data["content_hash"]

    registry = {
        "assets": {
            "frame": {
                "media_id": media_id,
                "content_sha256": digest,
            }
        }
    }
    derived = rebase_timeline_registry_managed_assets(
        registry,
        projects_root=root,
        project_ref="demo",
    )

    assert "file" not in registry["assets"]["frame"]
    assert Path(derived["assets"]["frame"]["file"]).read_bytes() == payload
    assert derived["assets"]["frame"]["content_sha256"] == digest
    assert derived["assets"]["frame"]["type"].startswith("image/")


def test_media_id_resolution_rejects_foreign_project_and_hash_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "root"
    source = tmp_path / "frame.png"
    source.write_bytes(b"project-owned managed bytes")
    with compose_standard_application(projects_root=root) as app:
        for slug in ("owner", "other"):
            project = app.projects_service.create(
                slug=slug, name=slug, idempotency_key=f"project:{slug}"
            )
            assert project.ok, project.error
        imported = app.media_service.import_file(
            project="owner", path=source, idempotency_key="media"
        )
        assert imported.ok, imported.error
        media_id = imported.data["id"]

    foreign = {"assets": {"frame": {"media_id": media_id}}}
    assert rebase_timeline_registry_managed_assets(
        foreign,
        projects_root=root,
        project_ref="other",
    ) == foreign

    mismatch = {
        "assets": {
            "frame": {
                "media_id": media_id,
                "content_sha256": "0" * 64,
            }
        }
    }
    assert rebase_timeline_registry_managed_assets(
        mismatch,
        projects_root=root,
        project_ref="owner",
    ) == mismatch
