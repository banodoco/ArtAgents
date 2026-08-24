"""Live-contract regressions for portable ``external_local`` backups."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.backup.operations import (
    BackupError,
    RestoreValidationError,
    create_backup,
    restore_backup,
)
from astrid.core import doctor


def _seed_external(root: Path, *sources: Path) -> tuple[str, ...]:
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="project"
        )
        assert project.ok, project.error
        media_ids: list[str] = []
        for index, source in enumerate(sources):
            imported = app.media_service.import_file(
                project="demo",
                path=source,
                realm="external_local",
                idempotency_key=f"media-{index}",
            )
            assert imported.ok, imported.error
            media_ids.append(str(imported.data["id"]))
        return tuple(media_ids)


def test_external_backup_is_self_contained_and_deduplicated(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_a = tmp_path / "original-a.bin"
    source_b = tmp_path / "original-b.bin"
    source_a.write_bytes(b"same external bytes")
    source_b.write_bytes(source_a.read_bytes())
    media_id, duplicate_media_id = _seed_external(source_root, source_a, source_b)
    assert media_id == duplicate_media_id

    backup = tmp_path / "backup"
    created = create_backup(projects_root=source_root, dest_path=backup)
    payload = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
    assert created.external_media_files == 1
    assert created.external_dependencies == 2
    assert payload["external"]["mode"] == "self_contained"
    assert len(payload["external"]["files"]) == 2
    snapshots = [
        path
        for path in (backup / "media").rglob("*")
        if path.is_file()
    ]
    assert len(snapshots) == 1

    restored = restore_backup(backup, projects_root=target_root)
    assert restored.restored_external_files == 1
    assert restored.rebased_external_locators == 2
    source_a.unlink()
    source_b.unlink()

    checks = {check.name: check for check in doctor.run_checks(projects_root=target_root)}
    assert checks["media_paths"].status == "ok"
    assert all(check.status == "ok" for check in checks.values())

    with sqlite3.connect(target_root / ".astrid" / "astrid.sqlite3") as conn:
        rows = conn.execute(
            "SELECT m.id, m.content_hash, l.locator, m.metadata_json "
            "FROM media AS m JOIN media_locations AS l ON l.media_id = m.id "
            "WHERE l.realm = 'external_local' ORDER BY l.id"
        ).fetchall()
    assert [row[0] for row in rows] == [media_id, media_id]
    assert rows[0][2] != str(source_a)
    assert all(Path(row[2]).is_file() for row in rows)
    provenance = json.loads(rows[0][3])["backup_provenance"]["external_local"]
    assert {entry["original_locator"] for entry in provenance} == {
        str(source_a),
        str(source_b),
    }


def test_external_backup_missing_or_mutated_source_is_not_published(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = tmp_path / "original.bin"
    source.write_bytes(b"original")
    _seed_external(root, source)
    backup = tmp_path / "backup"

    source.unlink()
    with pytest.raises(BackupError, match="unavailable"):
        create_backup(projects_root=root, dest_path=backup)
    assert not backup.exists()

    source.write_bytes(b"mutated")
    with pytest.raises(BackupError, match="changed"):
        create_backup(projects_root=root, dest_path=backup)
    assert not backup.exists()


def test_external_snapshot_corruption_is_rejected_before_force_restore(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source = tmp_path / "original.bin"
    source.write_bytes(b"portable")
    _seed_external(source_root, source)
    backup = tmp_path / "backup"
    create_backup(projects_root=source_root, dest_path=backup)

    # Give the target an unrelated live project so --force has a real swap
    # boundary to protect; corrupt the backup bytes before restore.
    with compose_standard_application(projects_root=target_root) as app:
        created = app.projects_service.create(
            slug="keep", name="Keep", idempotency_key="keep"
        )
        assert created.ok, created.error
    snapshot = next(
        path
        for path in (backup / "media" / "external").rglob("*")
        if path.is_file()
    )
    snapshot.write_bytes(b"wrong bytes")
    with pytest.raises(RestoreValidationError, match="integrity verification"):
        restore_backup(backup, projects_root=target_root, allow_overwrite=True)

    with compose_standard_application(projects_root=target_root) as app:
        projects = app.projects_service.list()
        assert projects.ok, projects.error
        assert [project["slug"] for project in projects.data] == ["keep"]
