"""Backup/restore round-trip and failure-mode tests (m6 sprint plan, Phase 1).

Covers the operational ``backup`` family contract:

- round-trip: create a backup, destroy the live data, restore, and reopen with
  matching project rows and managed media bytes;
- corruption detection: restore rejects a quick_check-corrupted backup and a
  foreign-key-violating backup **without mutating** live data;
- exclusion: the managed-media copy drops ``.env``/secret files and
  ``.staging``/``cache``/``logs``/``packs`` directories;
- idempotent overwrite: re-backing up to the same destination replaces it;
- envelope metadata shape: ``backup.json`` carries version/created_at/packs/
  media_files/sqlite_pages;
- CLI dispatch: ``backup create --json`` emits valid JSON and ``backup
  restore <missing>`` exits non-zero.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.backup import (
    RestoreValidationError,
    create_backup,
    restore_backup,
)
from astrid.core.backup import cli as backup_cli
from astrid.core.backup.operations import recover_backup_publication

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _seed_project(root: Path) -> None:
    """Create one demo project plus one managed media file under *root*."""
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        media_path = root / "shot.png"
        media_path.write_bytes(_PNG_BYTES)
        media = app.media_service.import_file(
            project="demo", path=media_path, idempotency_key="m1"
        )
        assert media.ok, media.error


def _destroy_live_data(root: Path) -> None:
    """Remove the live database and managed media tree (simulating a loss)."""
    db_path = root / ".astrid" / "astrid.sqlite3"
    db_path.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    shutil.rmtree(root / ".astrid" / "media", ignore_errors=True)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_backup_restore_round_trip(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    db_path = tmp_path / ".astrid" / "astrid.sqlite3"
    sha256_tree = tmp_path / ".astrid" / "media" / "sha256"
    assert db_path.is_file()
    assert sha256_tree.is_dir()

    dest = tmp_path / "backup"
    result = create_backup(projects_root=tmp_path, dest_path=dest)
    assert result.media_files >= 1
    assert (dest / "astrid.sqlite3").is_file()
    assert (dest / "backup.json").is_file()
    assert (dest / "media").is_dir()

    _destroy_live_data(tmp_path)
    assert not db_path.exists()

    restored = restore_backup(dest, projects_root=tmp_path)
    assert restored.database_path == db_path
    assert db_path.is_file()

    with compose_standard_application(projects_root=tmp_path) as app:
        with app.writer.read_only_connection() as conn:
            project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert project_count == 1
    assert any(p.is_file() for p in sha256_tree.rglob("*"))


# ---------------------------------------------------------------------------
# Corruption detection (no live mutation)
# ---------------------------------------------------------------------------


def test_restore_rejects_corrupt_backup_without_mutating_live(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)

    # Corrupt the backup database bytes.
    (dest / "astrid.sqlite3").write_bytes(b"not a sqlite database")

    live_db = tmp_path / ".astrid" / "astrid.sqlite3"
    before = live_db.read_bytes()
    with pytest.raises(RestoreValidationError):
        restore_backup(dest, projects_root=tmp_path, allow_overwrite=True)
    assert live_db.read_bytes() == before


@pytest.mark.parametrize("allow_overwrite", [False, True])
def test_restore_rejects_malformed_backup_metadata_without_mutating_live(
    tmp_path: Path, allow_overwrite: bool
) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)
    (dest / "backup.json").write_text("{ not json", encoding="utf-8")

    live_db = tmp_path / ".astrid" / "astrid.sqlite3"
    live_media = tmp_path / ".astrid" / "media"
    before_db = live_db.read_bytes()
    before_media = {
        path.relative_to(live_media): path.read_bytes()
        for path in live_media.rglob("*")
        if path.is_file()
    }

    with pytest.raises(RestoreValidationError, match="invalid backup metadata"):
        restore_backup(
            dest,
            projects_root=tmp_path,
            allow_overwrite=allow_overwrite,
        )

    assert live_db.read_bytes() == before_db
    assert {
        path.relative_to(live_media): path.read_bytes()
        for path in live_media.rglob("*")
        if path.is_file()
    } == before_media


@pytest.mark.parametrize("allow_overwrite", [False, True])
def test_restore_rejects_future_backup_metadata_without_mutating_live(
    tmp_path: Path, allow_overwrite: bool
) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)
    (dest / "backup.json").write_text('{"version": 999}\n', encoding="utf-8")

    live_db = tmp_path / ".astrid" / "astrid.sqlite3"
    live_media = tmp_path / ".astrid" / "media"
    before_db = live_db.read_bytes()
    before_media = {
        path.relative_to(live_media): path.read_bytes()
        for path in live_media.rglob("*")
        if path.is_file()
    }

    with pytest.raises(
        RestoreValidationError, match="unsupported backup metadata version"
    ):
        restore_backup(
            dest,
            projects_root=tmp_path,
            allow_overwrite=allow_overwrite,
        )

    assert live_db.read_bytes() == before_db
    assert {
        path.relative_to(live_media): path.read_bytes()
        for path in live_media.rglob("*")
        if path.is_file()
    } == before_media


def test_restore_rejects_foreign_key_violation_without_mutating_live(
    tmp_path: Path,
) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)

    # Introduce a dangling foreign-key reference into the backup database.
    backup_db = dest / "astrid.sqlite3"
    conn = sqlite3.connect(str(backup_db))
    try:
        conn.execute(
            "INSERT INTO media_locations (id, media_id, realm, locator, created_at)"
            " VALUES ('loc-corrupt', 'nonexistent-media', 'managed_local',"
            " 'sha256:deadbeef', '2026-01-01T00:00:00Z')"
        )
        conn.commit()
    finally:
        conn.close()

    live_db = tmp_path / ".astrid" / "astrid.sqlite3"
    before = live_db.read_bytes()
    with pytest.raises(RestoreValidationError, match="foreign_key_check"):
        restore_backup(dest, projects_root=tmp_path, allow_overwrite=True)
    assert live_db.read_bytes() == before


def test_restore_refuses_to_overwrite_live_data_by_default(
    tmp_path: Path,
) -> None:
    """A restore into a root that already holds data is refused, untouched."""
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)

    live_db = tmp_path / ".astrid" / "astrid.sqlite3"
    before = live_db.read_bytes()
    with pytest.raises(RestoreValidationError, match="allow_overwrite"):
        restore_backup(dest, projects_root=tmp_path)
    assert live_db.read_bytes() == before


def test_restore_allow_overwrite_replaces_live_data(tmp_path: Path) -> None:
    """With allow_overwrite=True the restore deliberately replaces live data."""
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)

    # Mutate live state past the backup point: one extra project row.
    with compose_standard_application(projects_root=tmp_path) as app:
        extra = app.projects_service.create(
            slug="extra", name="Extra", idempotency_key="p2"
        )
        assert extra.ok, extra.error

    restored = restore_backup(dest, projects_root=tmp_path, allow_overwrite=True)
    assert restored.database_path.is_file()
    with compose_standard_application(projects_root=tmp_path) as app:
        with app.writer.read_only_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert count == 1


def test_cli_restore_requires_force_over_live_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI refuses over live data without --force and succeeds with it."""
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)

    code = backup_cli.main(
        ["restore", str(dest), "--projects-root", str(tmp_path), "--json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False

    code = backup_cli.main(
        [
            "restore",
            str(dest),
            "--projects-root",
            str(tmp_path),
            "--force",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True


# ---------------------------------------------------------------------------
# Media / secret exclusion
# ---------------------------------------------------------------------------


def test_backup_excludes_env_and_secret_files_and_staging(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    media_root = tmp_path / ".astrid" / "media"

    (media_root / ".env").write_text("ASTRID_TEST_SECRET=supersecret\n", encoding="utf-8")
    (media_root / "my_secret.txt").write_text("password=topsecret\n", encoding="utf-8")
    (media_root / ".staging" / "txn" / "junk.bin").parent.mkdir(parents=True, exist_ok=True)
    (media_root / ".staging" / "txn" / "junk.bin").write_bytes(b"junk")
    (media_root / "cache").mkdir(exist_ok=True)
    (media_root / "cache" / "cached.bin").write_bytes(b"cache")

    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)
    dest_media = dest / "media"

    copied_names = {p.name for p in dest_media.rglob("*") if p.is_file()}
    assert ".env" not in copied_names
    assert "my_secret.txt" not in copied_names

    blob = b"".join(p.read_bytes() for p in dest_media.rglob("*") if p.is_file())
    assert b"supersecret" not in blob
    assert b"topsecret" not in blob

    path_parts = {part for p in dest_media.rglob("*") for part in p.parts}
    assert ".staging" not in path_parts
    assert "cache" not in path_parts


# ---------------------------------------------------------------------------
# Idempotent overwrite and envelope shape
# ---------------------------------------------------------------------------


def test_backup_overwrite_is_idempotent(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    first = create_backup(projects_root=tmp_path, dest_path=dest)
    assert first.media_files >= 1

    second = create_backup(projects_root=tmp_path, dest_path=dest)
    assert second.media_files >= first.media_files
    assert (dest / "backup.json").is_file()

    conn = sqlite3.connect(f"file:{dest / 'astrid.sqlite3'}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_backup_publication_crash_matrix_recovers_old_or_complete_destination(
    tmp_path: Path,
) -> None:
    """Every publication hard-death boundary reopens and restores safely."""
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)
    runtime_log = tmp_path / "backup-runtime.log"
    repo_root = Path(__file__).resolve().parents[2]
    child = (
        "import sys; from pathlib import Path; "
        "from astrid.core.backup.operations import create_backup; "
        "create_backup(projects_root=Path(sys.argv[1]), dest_path=Path(sys.argv[2]))"
    )

    for boundary in (
        "staged_complete",
        "previous_moved",
        "destination_published",
        "previous_cleaned",
    ):
        runtime_log.write_text("", encoding="utf-8")
        child_env = os.environ.copy()
        child_env["ASTRID_BACKUP_KILL_BOUNDARY"] = boundary
        child_env["ASTRID_BACKUP_RUNTIME_LOG"] = str(runtime_log)
        child_env["PYTHONPATH"] = str(repo_root)
        completed = subprocess.run(
            [sys.executable, "-c", child, str(tmp_path), str(dest)],
            cwd=repo_root,
            env=child_env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 77, completed.stderr
        records = [
            json.loads(line)
            for line in runtime_log.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert records and records[-1]["boundary"] == boundary

        recover_backup_publication(dest)
        marker = dest.parent / f".{dest.name}.publication.json"
        assert not marker.exists()
        assert (dest / "astrid.sqlite3").is_file()
        assert (dest / "backup.json").is_file()
        assert (dest / "media").is_dir()
        assert not list(dest.parent.glob(f".{dest.name}.staging-*"))
        assert not list(dest.parent.glob(f".{dest.name}.previous-*"))
        with sqlite3.connect(f"file:{dest / 'astrid.sqlite3'}?mode=ro", uri=True) as conn:
            assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"

        _destroy_live_data(tmp_path)
        restore_backup(dest, projects_root=tmp_path)
        with compose_standard_application(projects_root=tmp_path) as app:
            with app.writer.read_only_connection() as conn:
                assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_backup_envelope_metadata_shape(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    result = create_backup(projects_root=tmp_path, dest_path=dest)

    payload = json.loads((dest / "backup.json").read_text(encoding="utf-8"))
    assert set(payload) == {"version", "created_at", "packs", "media_files", "sqlite_pages"}
    assert payload["version"] == 1
    assert isinstance(payload["created_at"], str) and payload["created_at"]
    assert isinstance(payload["packs"], list) and payload["packs"]
    packs = {entry["pack"]: entry for entry in payload["packs"]}
    assert "core" in packs
    assert packs["core"]["version"] == 1
    assert payload["media_files"] == result.media_files
    assert payload["sqlite_pages"] == result.sqlite_pages


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------


def test_cli_create_json_valid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_project(tmp_path)
    dest = tmp_path / "backup"
    code = backup_cli.main(
        ["create", "--out", str(dest), "--projects-root", str(tmp_path), "--json"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["version"] == 1
    assert (dest / "astrid.sqlite3").is_file()


def test_cli_restore_missing_path_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = backup_cli.main(["restore", str(tmp_path / "does-not-exist")])
    assert code != 0
    assert capsys.readouterr().err
