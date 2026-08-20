"""Backup and restore operations for the managed Astrid database and media tree.

(m6 sprint plan, Phase 1.) This module is the operational ``backup`` family's
file/DB-level surface. It never opens the single-writer queue and never imports
a repository; it works directly over the one SQLite file and the managed-media
digest tree, exactly like ``serve`` and ``doctor``.

Layout (SD2, frozen by the plan): a backup is a directory containing

- ``astrid.sqlite3`` — a consistent online snapshot taken via
  ``sqlite3.Connection.backup``;
- ``media/`` — the managed-media copy (``.astrid/media/sha256`` digest tree),
  excluding ``.staging``/``cache``/``logs``/``packs`` and any ``.env``/secret
  files;
- ``backup.json`` — envelope metadata (version, created_at, pack migration
  state, media file count, sqlite page count).

Both :func:`create_backup` and :func:`restore_backup` acquire the
process-lifetime :class:`~astrid.core.store.ownership.DatabaseOwnerLock` beside
the live database so a backup/restore never races a second writer (SD3-m4
single-writer rule, kept through m6).

Restore is staged and validated read-only before any live byte is touched: the
backup is staged under ``.astrid/.restore-staging/``, validated with
``PRAGMA quick_check`` + ``PRAGMA foreign_key_check`` + a schema-version probe
against the current standard registry, and only then atomically swapped into
place. A corrupt/incompatible backup raises :class:`RestoreValidationError`
and leaves the live database and media tree untouched.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.migrations.runner import (
    MigrationError,
    probe_database,
    read_schema_migrations,
)
from astrid.core.store.ownership import DatabaseOwnerLock

BACKUP_FORMAT_VERSION = 1
"""Backup envelope format version written into ``backup.json``."""

BACKUP_DATABASE_NAME = "astrid.sqlite3"
"""The database file name inside a backup directory."""

BACKUP_MEDIA_DIR = "media"
"""The managed-media copy directory name inside a backup directory."""

BACKUP_METADATA_NAME = "backup.json"
"""The envelope metadata file name inside a backup directory."""

RESTORE_STAGING_DIR = ".restore-staging"
"""The staging root under ``.astrid`` used by :func:`restore_backup`."""

MANAGED_DIR_NAME = ".astrid"
"""The managed-data directory name under the projects root."""

MEDIA_DIR_NAME = "media"
"""The managed-media tree name under ``.astrid``."""

# ---------------------------------------------------------------------------
# Exclusion rules (SD2): the managed-media copy never carries staging, caches,
# logs, pack outputs, or secrets.
# ---------------------------------------------------------------------------

_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".staging",
        "cache",
        "logs",
        "packs",
        ".git",
        "__pycache__",
        RESTORE_STAGING_DIR,
    }
)
"""Directory names pruned from the media copy walk."""

_SECRET_NAME_MARKERS = (
    "secret",
    "credential",
    "credentials",
    "token",
    "password",
    "apikey",
    "api_key",
    "private_key",
    "access_key",
    "auth_token",
    "client_secret",
)
"""Substrings that mark a file name as secret-bearing."""

_SECRET_FILE_SUFFIXES = (".key", ".pem", ".p12", ".pfx", ".jks", ".crt")
"""File suffixes that mark a file as credential material."""


class BackupError(RuntimeError):
    """Base error for backup/restore operations."""


class RestoreValidationError(BackupError):
    """Raised when a staged restore fails read-only validation.

    The live database and media tree are left untouched when this error is
    raised: validation happens on the staged copy, before any swap.
    """


@dataclass(frozen=True, slots=True)
class BackupResult:
    """Outcome of :func:`create_backup` (also the ``backup.json`` shape)."""

    dest_path: Path
    created_at: str
    packs: tuple[tuple[str, int, str, str], ...]  # (pack, version, name, checksum)
    media_files: int
    sqlite_pages: int

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe envelope written as ``backup.json``."""
        return {
            "version": BACKUP_FORMAT_VERSION,
            "created_at": self.created_at,
            "packs": [
                {"pack": pack, "version": version, "name": name, "checksum": checksum}
                for pack, version, name, checksum in self.packs
            ],
            "media_files": self.media_files,
            "sqlite_pages": self.sqlite_pages,
        }


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Outcome of :func:`restore_backup`."""

    projects_root: Path
    database_path: Path
    restored_media_files: int
    restored_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "projects_root": str(self.projects_root),
            "database_path": str(self.database_path),
            "restored_media_files": self.restored_media_files,
            "restored_at": self.restored_at,
        }


# ---------------------------------------------------------------------------
# Exclusion helpers
# ---------------------------------------------------------------------------


def _is_secret_name(name: str) -> bool:
    """Return True when *name* is a ``.env`` or otherwise secret-bearing file."""
    lowered = name.lower()
    if lowered == ".env" or lowered.startswith(".env.") or lowered.endswith(".env"):
        return True
    if any(marker in lowered for marker in _SECRET_NAME_MARKERS):
        return True
    return lowered.endswith(_SECRET_FILE_SUFFIXES)


def _is_excluded_file(name: str) -> bool:
    return _is_secret_name(name)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_backup_dest(projects_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return projects_root / MANAGED_DIR_NAME / "backups" / f"backup-{stamp}"


def _read_migration_state(conn: sqlite3.Connection) -> tuple[tuple[str, int, str, str], ...]:
    """Read the applied migration rows (pack, version, name, checksum)."""
    rows = read_schema_migrations(conn)
    return tuple((row.pack, row.version, row.name, row.checksum) for row in rows)


def _online_backup(
    db_path: Path, dest_db: Path
) -> tuple[tuple[tuple[str, int, str, str], ...], int]:
    """Take a consistent online snapshot of *db_path* into *dest_db*.

    Uses ``sqlite3.Connection.backup`` (the online backup API), which reads a
    transactionally consistent snapshot without blocking the source writer.
    The snapshot is written to a sibling temp file and atomically moved into
    place so an idempotent re-backup never observes a half-written file.
    """
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, isolation_level=None)
    try:
        packs = _read_migration_state(source)
        sqlite_pages = int(source.execute("PRAGMA page_count").fetchone()[0])
        dest_db.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{BACKUP_DATABASE_NAME}.", suffix=".tmp", dir=dest_db.parent
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            destination = sqlite3.connect(str(tmp_path))
            try:
                source.backup(destination)
            finally:
                destination.close()
            os.replace(tmp_path, dest_db)
        finally:
            tmp_path.unlink(missing_ok=True)
        return packs, sqlite_pages
    finally:
        source.close()


def _copy_media_tree(projects_root: Path, dest_media: Path) -> int:
    """Copy the managed-media digest tree into *dest_media*, excluding secrets.

    Walks ``.astrid/media`` top-down and prunes ``.staging``/``cache``/``logs``/
    ``packs`` directories plus any ``.env``/secret file. Returns the number of
    files copied. A missing media tree copies nothing (a fresh project has no
    managed bytes yet).
    """
    source_media = projects_root / MANAGED_DIR_NAME / MEDIA_DIR_NAME
    if not source_media.is_dir():
        return 0
    count = 0
    for dirpath, dirnames, filenames in os.walk(source_media):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDED_DIR_NAMES)
        for name in sorted(filenames):
            if _is_excluded_file(name):
                continue
            source_file = Path(dirpath) / name
            relative = source_file.relative_to(source_media)
            dest_file = dest_media / relative
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, dest_file)
            count += 1
    return count


def _validate_backup_layout(backup: Path) -> None:
    if not backup.is_dir():
        raise RestoreValidationError(f"backup path is not a directory: {backup}")
    if not (backup / BACKUP_DATABASE_NAME).is_file():
        raise RestoreValidationError(
            f"backup is missing {BACKUP_DATABASE_NAME}: {backup}"
        )
    if not (backup / BACKUP_METADATA_NAME).is_file():
        raise RestoreValidationError(
            f"backup is missing {BACKUP_METADATA_NAME}: {backup}"
        )


def _count_files(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.rglob("*") if _.is_file())


# ---------------------------------------------------------------------------
# create_backup
# ---------------------------------------------------------------------------


def create_backup(
    projects_root: str | Path | None = None,
    dest_path: str | Path | None = None,
) -> BackupResult:
    """Create a consistent backup of the managed database and media tree.

    Resolves the projects root, derives ``${root}/.astrid/astrid.sqlite3``,
    acquires the exclusive-owner lock, takes an online SQLite snapshot, copies
    the managed media digest tree (excluding staging/cache/logs/packs and any
    ``.env``/secret file), and writes the ``backup.json`` envelope. An
    idempotent re-run over the same ``dest_path`` overwrites the previous
    backup cleanly.
    """
    root = resolve_projects_root(projects_root)
    db_path = derive_database_path(root)
    if not db_path.is_file():
        raise BackupError(f"no database to back up: {db_path}")
    dest = (
        Path(dest_path)
        if dest_path is not None
        else _default_backup_dest(root)
    )
    dest.mkdir(parents=True, exist_ok=True)
    dest_db = dest / BACKUP_DATABASE_NAME
    dest_media = dest / BACKUP_MEDIA_DIR
    dest_meta = dest / BACKUP_METADATA_NAME

    lock = DatabaseOwnerLock(db_path)
    try:
        try:
            packs, sqlite_pages = _online_backup(db_path, dest_db)
        except sqlite3.Error as exc:
            raise BackupError(f"SQLite online backup failed: {exc}") from exc

        media_files = _copy_media_tree(root, dest_media)

        created_at = _utc_now()
        result = BackupResult(
            dest_path=dest,
            created_at=created_at,
            packs=packs,
            media_files=media_files,
            sqlite_pages=sqlite_pages,
        )
        write_json_atomic(dest_meta, result.to_dict())
    finally:
        lock.release()

    return result


# ---------------------------------------------------------------------------
# restore_backup
# ---------------------------------------------------------------------------


def _validate_staged_database(staged_db: Path) -> None:
    """Validate a staged database read-only; raise on any corruption/incompat.

    Checks, in order: ``PRAGMA quick_check`` (page-level integrity),
    ``PRAGMA foreign_key_check`` (referential integrity), and a schema-version
    probe against the current standard registry (too-new schema, name drift,
    checksum drift, or an unregistered pack). The staged file is opened
    ``mode=ro`` and never mutated.
    """
    try:
        conn = sqlite3.connect(
            f"file:{staged_db}?mode=ro", uri=True, isolation_level=None
        )
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            f"cannot open staged database read-only: {exc}"
        ) from exc
    try:
        try:
            quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        except sqlite3.Error as exc:
            raise RestoreValidationError(f"quick_check failed: {exc}") from exc
        if quick != "ok":
            raise RestoreValidationError(f"quick_check reported: {quick!r}")
        try:
            fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        except sqlite3.Error as exc:
            raise RestoreValidationError(f"foreign_key_check failed: {exc}") from exc
        if fk_rows:
            raise RestoreValidationError(
                f"foreign_key_check found {len(fk_rows)} violation(s)"
            )
    finally:
        conn.close()

    from astrid.core.schema_packs.standard import build_standard_registry

    registry = build_standard_registry()
    try:
        probe_database(staged_db, registry)
    except MigrationError as exc:
        raise RestoreValidationError(
            f"schema-version incompatibility: {exc}"
        ) from exc


def _atomic_swap(
    live_db: Path,
    live_media: Path,
    staged_db: Path,
    staged_media: Path,
) -> None:
    """Atomically replace the live database and media tree with staged copies.

    The live database (and any ``-wal``/``-shm`` siblings) and media tree are
    moved aside under ``.astrid/.restore-staging/`` before the staged copies
    are moved into place with ``os.replace`` (atomic on the same filesystem).
    On any failure the moved-aside state is rolled back; on success the
    previous state is discarded.
    """
    astrid_dir = live_db.parent
    staging_root = astrid_dir / RESTORE_STAGING_DIR
    staging_root.mkdir(parents=True, exist_ok=True)
    prev_dir = staging_root / f"previous-{uuid.uuid4().hex}"
    prev_dir.mkdir(parents=True, exist_ok=False)

    # A replaced database must not read stale WAL/SHM bytes from the old file.
    for suffix in ("-wal", "-shm"):
        Path(f"{live_db}{suffix}").unlink(missing_ok=True)

    had_db = live_db.exists()
    had_media = live_media.is_dir()
    moved_db = False
    moved_media = False
    try:
        if had_db:
            os.replace(live_db, prev_dir / BACKUP_DATABASE_NAME)
            moved_db = True
        if had_media:
            os.replace(live_media, prev_dir / BACKUP_MEDIA_DIR)
            moved_media = True
        os.replace(staged_db, live_db)
        if staged_media.is_dir():
            os.replace(staged_media, live_media)
    except BaseException:
        # Roll back anything already moved so live data is not lost.
        live_db.unlink(missing_ok=True)
        if moved_db:
            os.replace(prev_dir / BACKUP_DATABASE_NAME, live_db)
        if moved_media and (prev_dir / BACKUP_MEDIA_DIR).is_dir():
            if live_media.exists():
                shutil.rmtree(live_media, ignore_errors=True)
            os.replace(prev_dir / BACKUP_MEDIA_DIR, live_media)
        raise
    # Success: the previous live state is superseded and discarded.
    shutil.rmtree(prev_dir, ignore_errors=True)


def restore_backup(
    backup_path: str | Path,
    projects_root: str | Path | None = None,
) -> RestoreResult:
    """Restore a backup into the managed database and media tree atomically.

    Stages the backup under ``.astrid/.restore-staging/``, validates the staged
    database read-only (quick_check + foreign_key_check + schema-version), and
    only then swaps it into place. A corrupt or incompatible backup raises
    :class:`RestoreValidationError` and leaves live data untouched.
    """
    root = resolve_projects_root(projects_root)
    backup = Path(backup_path)
    _validate_backup_layout(backup)

    live_db = derive_database_path(root)
    live_media = root / MANAGED_DIR_NAME / MEDIA_DIR_NAME
    backup_media = backup / BACKUP_MEDIA_DIR
    restored_media_files = _count_files(backup_media)

    lock = DatabaseOwnerLock(live_db)
    try:
        astrid_dir = live_db.parent
        astrid_dir.mkdir(parents=True, exist_ok=True)
        staging_root = astrid_dir / RESTORE_STAGING_DIR
        staging_root.mkdir(parents=True, exist_ok=True)
        txn_dir = staging_root / uuid.uuid4().hex
        txn_dir.mkdir(parents=True, exist_ok=False)
        try:
            staged_db = txn_dir / BACKUP_DATABASE_NAME
            staged_media = txn_dir / BACKUP_MEDIA_DIR
            shutil.copy2(backup / BACKUP_DATABASE_NAME, staged_db)
            if backup_media.is_dir():
                shutil.copytree(backup_media, staged_media)
            _validate_staged_database(staged_db)
            _atomic_swap(live_db, live_media, staged_db, staged_media)
        finally:
            shutil.rmtree(txn_dir, ignore_errors=True)
    finally:
        lock.release()

    return RestoreResult(
        projects_root=root,
        database_path=live_db,
        restored_media_files=restored_media_files,
        restored_at=_utc_now(),
    )


__all__ = [
    "BACKUP_DATABASE_NAME",
    "BACKUP_FORMAT_VERSION",
    "BACKUP_MEDIA_DIR",
    "BACKUP_METADATA_NAME",
    "BackupError",
    "BackupResult",
    "RestoreResult",
    "RestoreValidationError",
    "create_backup",
    "restore_backup",
]