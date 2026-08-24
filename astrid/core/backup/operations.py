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

import json
import hashlib
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
from astrid.core.io.media_import import (
    managed_media_path,
    sha256_file_bytes,
    validate_digest,
)
from astrid.core.project.workspace import materialize_project_workspace
from astrid.core.migrations.runner import (
    MigrationError,
    probe_database,
    read_only_uri,
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

BACKUP_PUBLICATION_SCHEMA = "astrid.backup_publication.v1"
"""Durable marker schema for an interrupted backup-directory publish."""

BACKUP_PUBLICATION_BOUNDARIES = (
    "staged_complete",
    "previous_moved",
    "destination_published",
    "previous_cleaned",
)
"""Observable hard-death boundaries used by the backup crash matrix."""

RESTORE_STAGING_DIR = ".restore-staging"
"""The staging root under ``.astrid`` used by :func:`restore_backup`."""

RESTORE_JOURNAL_SCHEMA = "astrid.restore_journal.v1"
"""Durable marker schema for an interrupted database/media restore."""

RESTORE_JOURNAL_NAME = "restore-journal.json"
"""The journal name inside one restore transaction directory."""

RESTORE_SWAP_BOUNDARIES = (
    "database_moved",
    "media_moved",
    "database_published",
    "media_published",
)
"""Observable hard-death boundaries used by the restore crash matrix."""

# Keep a descriptive alias for callers that use the recovery terminology.
RESTORE_RECOVERY_BOUNDARIES = RESTORE_SWAP_BOUNDARIES
"""Alias for :data:`RESTORE_SWAP_BOUNDARIES`."""

_RESTORE_KILL_ENV = "ASTRID_RESTORE_KILL_BOUNDARY"
_RESTORE_RUNTIME_LOG_ENV = "ASTRID_RESTORE_RUNTIME_LOG"
_RESTORE_PHASES = frozenset(
    {
        "prepared",
        "database_moved",
        "media_moved",
        "database_published",
        "media_published",
    }
)
_RESTORE_DATABASE_SIDECARS = ("-wal", "-shm")

MANAGED_DIR_NAME = ".astrid"
"""The managed-data directory name under the projects root."""

MEDIA_DIR_NAME = "media"
"""The managed-media tree name under ``.astrid``."""

EXTERNAL_MEDIA_DIR_NAME = "external"
"""Backup-owned bytes for reference-in-place ``external_local`` media."""

EXTERNAL_MEDIA_TREE_NAME = "sha256"
"""Digest tree below :data:`EXTERNAL_MEDIA_DIR_NAME`."""

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
class _ExternalDependency:
    """One external-local locator captured in a self-contained backup."""

    location_id: str
    media_id: str
    original_locator: str
    content_hash: str
    byte_size: int
    media_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "location_id": self.location_id,
            "media_id": self.media_id,
            "original_locator": self.original_locator,
            "content_hash": self.content_hash,
            "byte_size": self.byte_size,
            "media_path": self.media_path,
        }


@dataclass(frozen=True, slots=True)
class BackupResult:
    """Outcome of :func:`create_backup` (also the ``backup.json`` shape)."""

    dest_path: Path
    created_at: str
    packs: tuple[tuple[str, int, str, str], ...]  # (pack, version, name, checksum)
    media_files: int
    sqlite_pages: int
    external_media_files: int = 0
    external_dependencies: int = 0
    external_dependencies_unresolved: int = 0
    external_manifest: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe envelope written as ``backup.json``."""
        payload: dict[str, object] = {
            "version": BACKUP_FORMAT_VERSION,
            "created_at": self.created_at,
            "packs": [
                {"pack": pack, "version": version, "name": name, "checksum": checksum}
                for pack, version, name, checksum in self.packs
            ],
            "media_files": self.media_files,
            "sqlite_pages": self.sqlite_pages,
        }
        # Keep the original v1 envelope unchanged for backups with no
        # reference-in-place media.  The additive section is emitted only
        # when it carries useful external dependency evidence.
        if self.external_dependencies or self.external_media_files:
            payload.update(
                {
                    "external_media_files": self.external_media_files,
                    "external_dependencies": self.external_dependencies,
                    "external_dependencies_unresolved": self.external_dependencies_unresolved,
                    "external": {
                        "mode": "self_contained",
                        "files": list(self.external_manifest),
                    },
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Outcome of :func:`restore_backup`."""

    projects_root: Path
    database_path: Path
    restored_media_files: int
    rebased_media_locators: int
    restored_at: str
    restored_project_workspaces: int = 0
    restored_external_files: int = 0
    rebased_external_locators: int = 0
    unresolved_external_locators: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "projects_root": str(self.projects_root),
            "database_path": str(self.database_path),
            "restored_media_files": self.restored_media_files,
            "rebased_media_locators": self.rebased_media_locators,
            "restored_project_workspaces": self.restored_project_workspaces,
            "restored_external_files": self.restored_external_files,
            "rebased_external_locators": self.rebased_external_locators,
            "unresolved_external_locators": self.unresolved_external_locators,
            "restored_at": self.restored_at,
        }


@dataclass(frozen=True, slots=True)
class _RestoreJournal:
    """Validated paths and state read from one restore journal."""

    journal_path: Path
    transaction_dir: Path
    previous_dir: Path
    database_path: Path
    media_path: Path
    staged_database: Path
    staged_media: Path
    had_database: bool
    had_media: bool
    database_sidecars: tuple[str, ...]
    phase: str

    def payload(self, *, phase: str | None = None) -> dict[str, object]:
        """Return the complete JSON payload for an atomic journal update."""
        return {
            "schema": RESTORE_JOURNAL_SCHEMA,
            "transaction": str(self.transaction_dir.resolve()),
            "previous": str(self.previous_dir.resolve()),
            "database": str(self.database_path.resolve()),
            "media": str(self.media_path.resolve()),
            "staged_database": str(self.staged_database.resolve()),
            "staged_media": str(self.staged_media.resolve()),
            "had_database": self.had_database,
            "had_media": self.had_media,
            "database_sidecars": list(self.database_sidecars),
            "phase": phase if phase is not None else self.phase,
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
    source = sqlite3.connect(read_only_uri(db_path), uri=True, isolation_level=None)
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
                # The backup API copies the source header verbatim, which
                # carries journal_mode=WAL; a single-file WAL snapshot cannot
                # be opened read-only (its -shm index is missing), so restore
                # validation fails on it. Rewrite the header to DELETE mode so
                # the snapshot is a portable, self-contained single file.
                destination.execute("PRAGMA journal_mode=DELETE")
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


def _path_is_within(path: Path, directory: Path) -> bool:
    """Return whether *path* is below *directory* without following files."""
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _external_snapshot_path(media_root: Path, digest: str) -> Path:
    """Return the backup-owned digest path for one external byte snapshot."""
    valid = validate_digest(digest)
    return (
        media_root
        / EXTERNAL_MEDIA_DIR_NAME
        / EXTERNAL_MEDIA_TREE_NAME
        / valid[:2]
        / valid[2:4]
        / valid
    )


def _copy_external_media(
    staged_db: Path,
    *,
    dest_media: Path,
    backup_destination: Path,
) -> tuple[tuple[_ExternalDependency, ...], int]:
    """Snapshot every readable external-local dependency into the backup.

    External media is reference-in-place during normal editing, but a backup
    is expected to be portable.  We therefore verify each source against the
    recorded media digest, copy each digest once, and retain every original
    locator in the envelope.  A missing, symlinked, or mutated source fails
    before the staged backup can be published.
    """
    try:
        conn = sqlite3.connect(read_only_uri(staged_db), uri=True)
    except sqlite3.Error as exc:
        raise BackupError(f"cannot inspect external media for backup: {exc}") from exc

    dependencies: list[_ExternalDependency] = []
    copied: set[str] = set()
    try:
        try:
            rows = conn.execute(
                "SELECT l.id, l.media_id, l.locator, m.content_hash, m.byte_size "
                "FROM media_locations AS l JOIN media AS m ON m.id = l.media_id "
                "WHERE l.realm = 'external_local' ORDER BY l.id"
            ).fetchall()
        except sqlite3.Error as exc:
            raise BackupError(f"cannot inspect external media for backup: {exc}") from exc
    finally:
        conn.close()

    for location_id, media_id, locator, content_hash, byte_size in rows:
        digest = validate_digest(content_hash)
        source = Path(str(locator)).expanduser()
        if source.is_symlink() or not source.is_file():
            raise BackupError(
                "external_local backup dependency is unavailable: "
                f"media {media_id}, location {location_id}, source {source}; "
                "restore the external file or relocate it before backing up"
            )
        if _path_is_within(source, backup_destination):
            raise BackupError(
                "external_local backup dependency points inside the backup "
                f"destination ({source}); refusing to snapshot its own output"
            )
        try:
            source_hash = sha256_file_bytes(source)
        except OSError as exc:
            raise BackupError(
                f"cannot read external_local backup dependency {source}: {exc}"
            ) from exc
        if source_hash != digest:
            raise BackupError(
                "external_local backup dependency changed: "
                f"media {media_id}, location {location_id}, source {source}; "
                f"expected {digest}, found {source_hash}; no backup was published"
            )

        # If the managed digest tree already contains the exact bytes, point
        # the manifest at it. Otherwise materialize one external snapshot per
        # digest. This dedupes same-content external locations and across
        # managed/external realms without changing the source file.
        managed_candidate = dest_media / "sha256" / digest[:2] / digest[2:4] / digest
        if managed_candidate.is_file() and not managed_candidate.is_symlink():
            try:
                managed_valid = sha256_file_bytes(managed_candidate) == digest
            except OSError:
                managed_valid = False
        else:
            managed_valid = False
        if managed_valid:
            relative = managed_candidate.relative_to(dest_media).as_posix()
        else:
            target = _external_snapshot_path(dest_media, digest)
            relative = target.relative_to(dest_media).as_posix()
            if digest not in copied:
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_name = tempfile.mkstemp(
                    prefix=f".{digest}.", suffix=".tmp", dir=target.parent
                )
                os.close(fd)
                temp_target = Path(tmp_name)
                try:
                    shutil.copyfile(source, temp_target)
                    copied_hash = sha256_file_bytes(temp_target)
                    if copied_hash != digest:
                        raise BackupError(
                            "external_local backup dependency changed while copying: "
                            f"{source}; expected {digest}, found {copied_hash}; "
                            "no backup was published"
                        )
                    os.replace(temp_target, target)
                finally:
                    temp_target.unlink(missing_ok=True)
                copied.add(digest)

        dependencies.append(
            _ExternalDependency(
                location_id=str(location_id),
                media_id=str(media_id),
                original_locator=str(locator),
                content_hash=digest,
                byte_size=int(byte_size),
                media_path=relative,
            )
        )

    return tuple(dependencies), len({item.content_hash for item in dependencies})


# ---------------------------------------------------------------------------
# Recoverable backup publication
# ---------------------------------------------------------------------------


def _publication_marker_path(dest: Path) -> Path:
    """Return the sibling marker that journals publication of *dest*."""
    return dest.parent / f".{dest.name}.publication.json"


def _publication_runtime_log(boundary: str, *, marker: Path) -> None:
    """Record a boundary in the optional child-process runtime log."""
    log_path = os.environ.get("ASTRID_BACKUP_RUNTIME_LOG")
    if not log_path:
        return
    record = {
        "boundary": boundary,
        "marker": str(marker),
        "pid": os.getpid(),
    }
    with Path(log_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _publication_boundary(boundary: str, *, marker: Path) -> None:
    """Expose a durable publication boundary and optionally hard-kill.

    The environment hook is deliberately test-only and inert for normal
    callers.  The child exits with ``os._exit`` so neither Python cleanup nor
    the owner-lock release can mask the exact filesystem state under test.
    """
    if boundary not in BACKUP_PUBLICATION_BOUNDARIES:
        raise BackupError(f"unknown backup publication boundary: {boundary!r}")
    _publication_runtime_log(boundary, marker=marker)
    if os.environ.get("ASTRID_BACKUP_KILL_BOUNDARY") == boundary:
        os._exit(77)  # noqa: PLR1722 - intentional hard-death test seam


def _fsync_directory(path: Path) -> None:
    """Durably record a directory rename where the platform supports it."""
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    fd: int | None = None
    try:
        fd = os.open(path, flags)
        os.fsync(fd)
    except OSError:
        # The marker and directory swaps are still atomic on the supported
        # filesystem when directory fsync is unavailable (e.g. some tmpfs).
        pass
    finally:
        if fd is not None:
            os.close(fd)


def _remove_publication_path(path: Path) -> None:
    """Remove one journaled directory or file without following links."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _backup_artifact_complete(path: Path) -> bool:
    """Return whether *path* has the complete directory-level layout."""
    if not path.is_dir():
        return False
    if not (path / BACKUP_DATABASE_NAME).is_file():
        return False
    if not (path / BACKUP_METADATA_NAME).is_file():
        return False
    if not (path / BACKUP_MEDIA_DIR).is_dir():
        return False
    try:
        payload = json.loads(
            (path / BACKUP_METADATA_NAME).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("version") == BACKUP_FORMAT_VERSION


def _read_publication_marker(marker: Path, dest: Path) -> dict[str, object]:
    """Read and constrain a marker before using any journaled path."""
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"invalid backup publication marker: {marker}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != BACKUP_PUBLICATION_SCHEMA:
        raise BackupError(f"unsupported backup publication marker: {marker}")
    target = Path(str(payload.get("target", ""))).resolve()
    if target != dest.resolve():
        raise BackupError(f"backup publication marker targets {target}, not {dest}")
    parent = dest.parent.resolve()
    paths: dict[str, object] = {"target": target}
    for key in ("staging", "previous"):
        raw = payload.get(key)
        if raw is None:
            paths[key] = None
            continue
        value = Path(str(raw)).resolve()
        if value.parent != parent or value == target:
            raise BackupError(f"unsafe backup publication marker path: {value}")
        paths[key] = value
    phase = payload.get("phase")
    if phase not in {"staged", "previous_moved", "published"}:
        raise BackupError(f"invalid backup publication phase: {phase!r}")
    paths["phase"] = phase
    return paths


def _write_publication_marker(
    marker: Path,
    *,
    dest: Path,
    staging: Path,
    previous: Path | None,
    phase: str,
) -> None:
    """Atomically persist one backup publication journal state."""
    write_json_atomic(
        marker,
        {
            "schema": BACKUP_PUBLICATION_SCHEMA,
            "target": str(dest.resolve()),
            "staging": str(staging.resolve()),
            "previous": str(previous.resolve()) if previous is not None else None,
            "phase": phase,
        },
    )


def recover_backup_publication(dest_path: str | Path) -> None:
    """Recover one interrupted backup publication before it is reopened.

    A marker is the authority for an in-flight overwrite.  Recovery chooses a
    complete staged directory when available, otherwise restores the complete
    previous directory; it never accepts a partially populated destination.
    The operation is idempotent and is intentionally independent of SQLite.
    """
    dest = Path(dest_path)
    marker = _publication_marker_path(dest)
    if not marker.exists():
        return
    paths = _read_publication_marker(marker, dest)
    staging = paths["staging"]
    previous = paths["previous"]
    phase = paths["phase"]
    assert isinstance(staging, Path)
    assert previous is None or isinstance(previous, Path)

    target_complete = _backup_artifact_complete(dest)
    staging_complete = _backup_artifact_complete(staging)
    previous_complete = previous is not None and _backup_artifact_complete(previous)

    if phase == "staged":
        if target_complete:
            _remove_publication_path(staging)
        elif staging_complete and not dest.exists():
            os.replace(staging, dest)
        else:
            raise BackupError("backup publication has no complete old or new destination")
    elif phase == "previous_moved":
        if target_complete:
            _remove_publication_path(staging)
            if previous is not None:
                _remove_publication_path(previous)
        elif staging_complete:
            if dest.exists():
                _remove_publication_path(dest)
            os.replace(staging, dest)
            if previous is not None:
                _remove_publication_path(previous)
        elif previous_complete:
            if dest.exists():
                _remove_publication_path(dest)
            assert previous is not None
            os.replace(previous, dest)
            _remove_publication_path(staging)
        else:
            raise BackupError("backup publication has no complete old or new destination")
    else:  # published
        if target_complete:
            _remove_publication_path(staging)
            if previous is not None:
                _remove_publication_path(previous)
        elif staging_complete:
            if dest.exists():
                _remove_publication_path(dest)
            os.replace(staging, dest)
            if previous is not None:
                _remove_publication_path(previous)
        elif previous_complete:
            if dest.exists():
                _remove_publication_path(dest)
            assert previous is not None
            os.replace(previous, dest)
        else:
            raise BackupError("backup publication has no complete old or new destination")

    marker.unlink(missing_ok=True)
    _fsync_directory(dest.parent)


def _restore_is_file(path: Path) -> bool:
    """Return whether *path* is a regular, non-symlink file."""
    return path.is_file() and not path.is_symlink()


def _restore_is_dir(path: Path) -> bool:
    """Return whether *path* is a regular, non-symlink directory."""
    return path.is_dir() and not path.is_symlink()


def _remove_restore_path(path: Path) -> None:
    """Remove one restore-owned path without following a symlink."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _restore_runtime_log(boundary: str, *, journal: Path) -> None:
    """Record one restore boundary in the optional child-process log."""
    log_path = os.environ.get(_RESTORE_RUNTIME_LOG_ENV)
    if not log_path:
        return
    record = {"boundary": boundary, "journal": str(journal), "pid": os.getpid()}
    with Path(log_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _restore_boundary(boundary: str, *, journal: Path) -> None:
    """Expose one restore move and optionally hard-kill the child process."""
    if boundary not in RESTORE_SWAP_BOUNDARIES:
        raise BackupError(f"unknown restore swap boundary: {boundary!r}")
    _restore_runtime_log(boundary, journal=journal)
    if os.environ.get(_RESTORE_KILL_ENV) == boundary:
        os._exit(78)  # noqa: PLR1722 - intentional hard-death test seam


def _restore_path_from_payload(
    payload: dict[str, object], key: str, *, journal: Path
) -> Path:
    raw = payload.get(key)
    if not isinstance(raw, str) or not raw:
        raise BackupError(f"restore journal is missing {key}: {journal}")
    return Path(raw).resolve()


def _read_restore_journal(
    journal_path: str | Path,
    *,
    expected_database: str | Path | None = None,
) -> _RestoreJournal:
    """Read and constrain one restore journal before using its paths."""
    journal = Path(journal_path)
    if journal.is_symlink() or not journal.is_file():
        raise BackupError(f"restore journal is not a regular file: {journal}")
    try:
        payload = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"invalid restore journal: {journal}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != RESTORE_JOURNAL_SCHEMA:
        raise BackupError(f"unsupported restore journal: {journal}")

    transaction_dir = journal.parent.resolve()
    transaction = _restore_path_from_payload(payload, "transaction", journal=journal)
    previous_dir = _restore_path_from_payload(payload, "previous", journal=journal)
    database_path = _restore_path_from_payload(payload, "database", journal=journal)
    media_path = _restore_path_from_payload(payload, "media", journal=journal)
    staged_database = _restore_path_from_payload(
        payload, "staged_database", journal=journal
    )
    staged_media = _restore_path_from_payload(payload, "staged_media", journal=journal)

    if transaction != transaction_dir:
        raise BackupError(f"restore journal transaction escapes its directory: {journal}")
    if previous_dir != transaction_dir / "previous":
        raise BackupError(f"restore journal previous path is unsafe: {journal}")
    if staged_database != transaction_dir / BACKUP_DATABASE_NAME:
        raise BackupError(f"restore journal database stage is unsafe: {journal}")
    if staged_media != transaction_dir / BACKUP_MEDIA_DIR:
        raise BackupError(f"restore journal media stage is unsafe: {journal}")

    if expected_database is not None:
        expected_db = Path(expected_database).resolve()
        if database_path != expected_db:
            raise BackupError(
                f"restore journal targets {database_path}, not {expected_db}"
            )
        expected_media = expected_db.parent / MEDIA_DIR_NAME
        if media_path != expected_media:
            raise BackupError(f"restore journal media target is unsafe: {journal}")
    elif media_path != database_path.parent / MEDIA_DIR_NAME:
        raise BackupError(f"restore journal media target is unsafe: {journal}")

    had_database = payload.get("had_database")
    had_media = payload.get("had_media")
    if not isinstance(had_database, bool) or not isinstance(had_media, bool):
        raise BackupError(f"restore journal has invalid prior-state flags: {journal}")

    raw_sidecars = payload.get("database_sidecars")
    if not isinstance(raw_sidecars, list) or any(
        item not in _RESTORE_DATABASE_SIDECARS for item in raw_sidecars
    ):
        raise BackupError(f"restore journal has invalid database sidecars: {journal}")
    database_sidecars = tuple(dict.fromkeys(str(item) for item in raw_sidecars))
    phase = payload.get("phase")
    if phase not in _RESTORE_PHASES:
        raise BackupError(f"restore journal has invalid phase: {phase!r}")

    return _RestoreJournal(
        journal_path=journal,
        transaction_dir=transaction_dir,
        previous_dir=previous_dir,
        database_path=database_path,
        media_path=media_path,
        staged_database=staged_database,
        staged_media=staged_media,
        had_database=had_database,
        had_media=had_media,
        database_sidecars=database_sidecars,
        phase=str(phase),
    )


def _write_restore_journal(state: _RestoreJournal, *, phase: str) -> _RestoreJournal:
    """Atomically persist one restore phase and return the updated state."""
    if phase not in _RESTORE_PHASES:
        raise BackupError(f"unknown restore journal phase: {phase!r}")
    write_json_atomic(state.journal_path, state.payload(phase=phase))
    return _RestoreJournal(
        journal_path=state.journal_path,
        transaction_dir=state.transaction_dir,
        previous_dir=state.previous_dir,
        database_path=state.database_path,
        media_path=state.media_path,
        staged_database=state.staged_database,
        staged_media=state.staged_media,
        had_database=state.had_database,
        had_media=state.had_media,
        database_sidecars=state.database_sidecars,
        phase=phase,
    )


def _old_database_source(state: _RestoreJournal) -> Path | None:
    previous = state.previous_dir / BACKUP_DATABASE_NAME
    if _restore_is_file(previous):
        return previous
    if state.phase == "prepared" and _restore_is_file(state.database_path):
        return state.database_path
    return None


def _old_sidecar_source(state: _RestoreJournal, suffix: str) -> Path | None:
    previous = state.previous_dir / f"{BACKUP_DATABASE_NAME}{suffix}"
    if _restore_is_file(previous):
        return previous
    if state.phase == "prepared":
        live = Path(f"{state.database_path}{suffix}")
        if _restore_is_file(live):
            return live
    return None


def _old_media_source(state: _RestoreJournal) -> Path | None:
    previous = state.previous_dir / BACKUP_MEDIA_DIR
    if _restore_is_dir(previous):
        return previous
    if state.phase in {"prepared", "database_moved"} and _restore_is_dir(
        state.media_path
    ):
        return state.media_path
    return None


def _old_restore_available(state: _RestoreJournal) -> bool:
    """Return whether the journal still identifies a complete old state."""
    if state.had_database and _old_database_source(state) is None:
        return False
    if state.had_media and _old_media_source(state) is None:
        return False
    for suffix in state.database_sidecars:
        if _old_sidecar_source(state, suffix) is None:
            return False
    return True


def _new_restore_mode(state: _RestoreJournal) -> str | None:
    """Return the journal-authorized complete-new state, if one exists."""
    staged_complete = _restore_is_file(state.staged_database) and _restore_is_dir(
        state.staged_media
    )
    if staged_complete:
        return "staged"
    if (
        state.phase == "database_published"
        and _restore_is_file(state.database_path)
        and _restore_is_dir(state.staged_media)
    ):
        return "database_published"
    if (
        state.phase == "media_published"
        and _restore_is_file(state.database_path)
        and _restore_is_dir(state.media_path)
    ):
        return "published"
    return None


def _finish_restore_transaction(state: _RestoreJournal) -> None:
    """Remove journal-owned paths after an old or new state is selected."""
    _remove_restore_path(state.staged_database)
    _remove_restore_path(state.staged_media)
    _remove_restore_path(state.previous_dir)
    state.journal_path.unlink(missing_ok=True)
    try:
        state.transaction_dir.rmdir()
    except OSError:
        # An unrelated file in the transaction directory is not semantic
        # restore state. Leave it alone and let the next recovery ignore it.
        pass


def _restore_old_state(state: _RestoreJournal) -> None:
    """Restore the exact pre-restore database/media pair named by the journal."""
    if state.had_database:
        source = _old_database_source(state)
        if source is None:
            raise BackupError("restore journal lost the previous database")
        if source != state.database_path:
            _remove_restore_path(state.database_path)
            os.replace(source, state.database_path)
        expected_sidecars = set(state.database_sidecars)
        for suffix in _RESTORE_DATABASE_SIDECARS:
            target = Path(f"{state.database_path}{suffix}")
            source_sidecar = _old_sidecar_source(state, suffix)
            if suffix in expected_sidecars:
                if source_sidecar is None:
                    raise BackupError("restore journal lost a previous database sidecar")
                if source_sidecar != target:
                    _remove_restore_path(target)
                    os.replace(source_sidecar, target)
            else:
                _remove_restore_path(target)
    else:
        _remove_restore_path(state.database_path)
        for suffix in _RESTORE_DATABASE_SIDECARS:
            _remove_restore_path(Path(f"{state.database_path}{suffix}"))

    if state.had_media:
        source_media = _old_media_source(state)
        if source_media is None:
            raise BackupError("restore journal lost the previous media tree")
        if source_media != state.media_path:
            _remove_restore_path(state.media_path)
            os.replace(source_media, state.media_path)
    else:
        _remove_restore_path(state.media_path)

    _finish_restore_transaction(state)


def _restore_new_state(state: _RestoreJournal, mode: str) -> None:
    """Complete the journal-authorized replacement state."""
    if mode == "staged":
        _validate_staged_database(state.staged_database)
        _remove_restore_path(state.database_path)
        for suffix in _RESTORE_DATABASE_SIDECARS:
            _remove_restore_path(Path(f"{state.database_path}{suffix}"))
        os.replace(state.staged_database, state.database_path)
        state = _write_restore_journal(state, phase="database_published")
        _remove_restore_path(state.media_path)
        os.replace(state.staged_media, state.media_path)
        state = _write_restore_journal(state, phase="media_published")
    elif mode == "database_published":
        _validate_staged_database(state.database_path)
        _remove_restore_path(state.media_path)
        os.replace(state.staged_media, state.media_path)
        state = _write_restore_journal(state, phase="media_published")
    elif mode == "published":
        _validate_staged_database(state.database_path)
    else:
        raise BackupError(f"unknown complete restore mode: {mode!r}")
    _finish_restore_transaction(state)


def _recover_restore_transaction(
    journal_path: str | Path,
    *,
    expected_database: str | Path,
) -> None:
    """Resolve one interrupted restore using only its durable journal."""
    state = _read_restore_journal(
        journal_path, expected_database=expected_database
    )
    old_available = _old_restore_available(state)
    new_mode = _new_restore_mode(state)

    # Preserve an existing editable database when it is still available. A
    # fresh root has no old database, so it prefers a complete staged restore;
    # this avoids silently discarding the first restore on an empty project.
    if state.had_database and old_available:
        _restore_old_state(state)
    elif new_mode is not None:
        _restore_new_state(state, new_mode)
    elif old_available:
        _restore_old_state(state)
    else:
        raise BackupError(
            "restore journal has neither a complete previous nor replacement state"
        )


def recover_restore_staging(projects_root: str | Path | None = None) -> int:
    """Recover journaled restore transactions before opening a writer.

    Only a directory containing the exact :data:`RESTORE_JOURNAL_NAME` is a
    restore transaction. Arbitrary files and directories under
    ``.astrid/.restore-staging`` are ignored and never treated as semantic
    database or media state.
    """
    root = resolve_projects_root(projects_root)
    database_path = derive_database_path(root)
    staging_root = database_path.parent / RESTORE_STAGING_DIR
    if not _restore_is_dir(staging_root):
        return 0
    recovered = 0
    for transaction_dir in sorted(staging_root.iterdir(), key=lambda path: path.name):
        if transaction_dir.is_symlink() or not transaction_dir.is_dir():
            continue
        journal = transaction_dir / RESTORE_JOURNAL_NAME
        if journal.is_symlink() or not journal.is_file():
            continue
        _recover_restore_transaction(journal, expected_database=database_path)
        recovered += 1
    return recovered


def recover_interrupted_restore(projects_root: str | Path | None = None) -> int:
    """Compatibility-named entry point for startup restore recovery."""
    return recover_restore_staging(projects_root)


def recover_interrupted_restores(projects_root: str | Path | None = None) -> int:
    """Plural alias for :func:`recover_restore_staging`."""
    return recover_restore_staging(projects_root)


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
    if not _restore_is_dir(backup / BACKUP_MEDIA_DIR):
        raise RestoreValidationError(
            f"backup is missing {BACKUP_MEDIA_DIR}: {backup}"
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
    lock = DatabaseOwnerLock(db_path)
    try:
        # A prior hard-dead child may have left a complete staging directory,
        # a moved previous directory, or a published new directory. Resolve
        # that journal before creating another attempt so overwrite is
        # idempotent and never layers a new publication over mixed bytes.
        recover_backup_publication(dest)
        if dest.exists() and not dest.is_dir():
            raise BackupError(f"backup destination is not a directory: {dest}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        staging = dest.parent / f".{dest.name}.staging-{uuid.uuid4().hex}"
        previous = dest.parent / f".{dest.name}.previous-{uuid.uuid4().hex}"
        marker = _publication_marker_path(dest)
        staging.mkdir(parents=True, exist_ok=False)
        try:
            dest_db = staging / BACKUP_DATABASE_NAME
            dest_media = staging / BACKUP_MEDIA_DIR
            dest_meta = staging / BACKUP_METADATA_NAME
            try:
                packs, sqlite_pages = _online_backup(db_path, dest_db)
            except sqlite3.Error as exc:
                raise BackupError(f"SQLite online backup failed: {exc}") from exc

            # Keep an explicit empty media directory in the complete marker
            # state so recovery can distinguish a finished empty tree from a
            # child that died before the managed-media stage was materialized.
            dest_media.mkdir(parents=True, exist_ok=True)
            media_files = _copy_media_tree(root, dest_media)
            external_dependencies, external_media_files = _copy_external_media(
                dest_db,
                dest_media=dest_media,
                backup_destination=dest,
            )
            created_at = _utc_now()
            result = BackupResult(
                dest_path=dest,
                created_at=created_at,
                packs=packs,
                media_files=media_files,
                sqlite_pages=sqlite_pages,
                external_media_files=external_media_files,
                external_dependencies=len(external_dependencies),
                external_manifest=tuple(
                    item.to_dict() for item in external_dependencies
                ),
            )
            # The marker is written only after every database, managed-media,
            # and metadata byte is complete in the sibling staging directory.
            write_json_atomic(dest_meta, result.to_dict())
            _write_publication_marker(
                marker,
                dest=dest,
                staging=staging,
                previous=previous if dest.exists() else None,
                phase="staged",
            )
            _publication_boundary("staged_complete", marker=marker)

            if dest.exists():
                os.replace(dest, previous)
                _write_publication_marker(
                    marker,
                    dest=dest,
                    staging=staging,
                    previous=previous,
                    phase="previous_moved",
                )
                _fsync_directory(dest.parent)
                _publication_boundary("previous_moved", marker=marker)

            os.replace(staging, dest)
            _write_publication_marker(
                marker,
                dest=dest,
                staging=staging,
                previous=previous if previous.exists() else None,
                phase="published",
            )
            _fsync_directory(dest.parent)
            _publication_boundary("destination_published", marker=marker)

            if previous.exists():
                _remove_publication_path(previous)
            _fsync_directory(dest.parent)
            _publication_boundary("previous_cleaned", marker=marker)
            marker.unlink(missing_ok=True)
            _fsync_directory(dest.parent)
        except BaseException:
            # Ordinary failures retain the marker for the next invocation;
            # hard-death tests intentionally bypass this cleanup entirely.
            if not os.environ.get("ASTRID_BACKUP_KILL_BOUNDARY"):
                if staging.exists():
                    _remove_publication_path(staging)
                if previous.exists() and not dest.exists():
                    os.replace(previous, dest)
                marker.unlink(missing_ok=True)
            raise
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


def _normalize_staged_database_journal(staged_db: Path) -> None:
    """Ensure a staged DB can be opened read-only without WAL sidecars."""
    try:
        conn = sqlite3.connect(str(staged_db), isolation_level=None)
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            f"cannot normalize staged database journal mode: {exc}"
        ) from exc
    try:
        try:
            mode = conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        except sqlite3.Error as exc:
            raise RestoreValidationError(
                f"cannot normalize staged database journal mode: {exc}"
            ) from exc
        if str(mode).lower() != "delete":
            raise RestoreValidationError(
                f"staged database retained unsupported journal mode: {mode!r}"
            )
    finally:
        conn.close()
    for suffix in _RESTORE_DATABASE_SIDECARS:
        Path(f"{staged_db}{suffix}").unlink(missing_ok=True)


def _materialize_restored_project_workspaces(
    staged_db: Path,
    *,
    projects_root: Path,
) -> int:
    """Rebuild file-oriented project bindings from the staged kernel rows.

    The files are derived projections, so this reads only authoritative
    project rows/settings and never replays or edits an event.  ``plan.md`` is
    created only when absent; an existing human plan is preserved.  Existing
    binding extension fields are preserved while kernel identity/default
    fields are reconciled atomically.
    """

    try:
        conn = sqlite3.connect(read_only_uri(staged_db), uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            f"cannot inspect restored projects for workspace materialization: {exc}"
        ) from exc
    try:
        try:
            rows = conn.execute(
                "SELECT p.id, p.slug, p.name, p.settings_json, p.created_at, "
                "p.updated_at, json_extract(created.payload_json, "
                "'$.data.timeline_ulid') AS default_timeline_ulid "
                "FROM projects AS p "
                "LEFT JOIN timelines AS t ON t.id = "
                "json_extract(p.settings_json, '$.default_timeline_id') "
                "LEFT JOIN events AS created ON created.stream_id = t.event_stream_id "
                "AND created.kind = 'timeline.created' "
                "ORDER BY p.slug"
            ).fetchall()
        except sqlite3.Error as exc:
            raise RestoreValidationError(
                f"cannot inspect restored projects for workspace materialization: {exc}"
            ) from exc
    finally:
        conn.close()

    count = 0
    for row in rows:
        try:
            settings = json.loads(str(row["settings_json"]))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RestoreValidationError(
                f"restored project {row['slug']!r} has invalid settings JSON"
            ) from exc
        try:
            materialize_project_workspace(
                slug=str(row["slug"]),
                name=str(row["name"]),
                project_id=str(row["id"]),
                projects_root=projects_root,
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
                # Kernel defaults are UUID-backed settings.  The legacy file
                # schema accepts only its old uppercase filesystem ULID and is
                # not timeline authority; keep this derived sentinel null.
                default_timeline_id=None,
                reconcile_binding=True,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise RestoreValidationError(
                "cannot materialize restored project workspace "
                f"{row['slug']!r}: {exc}"
            ) from exc
        count += 1
    return count


def _rebase_staged_managed_media(
    staged_db: Path,
    *,
    projects_root: Path,
    staged_media: Path,
) -> int:
    """Rebase and verify every managed-local locator in a staged database.

    Managed media locators historically contain absolute paths.  A database
    snapshot can therefore carry a source-root path even when its bytes are
    copied into a different restore root.  The digest is the durable identity
    and defines the only valid managed path, so rewrite those projections in
    the staged copy before publication.  Every rewritten target is checked
    for regular-file status and byte identity while the live tree is still
    untouched; a failure leaves the transaction unpublished.
    """
    try:
        conn = sqlite3.connect(str(staged_db))
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            f"cannot open staged database for managed-media rebase: {exc}"
        ) from exc

    try:
        try:
            rows = conn.execute(
                "SELECT l.id, l.media_id, l.locator, m.content_hash "
                "FROM media_locations AS l "
                "JOIN media AS m ON m.id = l.media_id "
                "WHERE l.realm = 'managed_local' "
                "ORDER BY l.id"
            ).fetchall()
        except sqlite3.Error as exc:
            raise RestoreValidationError(
                f"cannot inspect staged managed-media locators: {exc}"
            ) from exc

        updates: list[tuple[str, str]] = []
        target_keys: set[tuple[str, str]] = set()
        for location_id, media_id, _old_locator, content_hash in rows:
            try:
                canonical = managed_media_path(projects_root, content_hash)
            except (TypeError, ValueError) as exc:
                raise RestoreValidationError(
                    "cannot rebase managed media location "
                    f"{location_id}: invalid content hash {content_hash!r}"
                ) from exc

            digest = str(content_hash)
            staged_file = staged_media / "sha256" / digest[:2] / digest[2:4] / digest
            if staged_file.is_symlink() or not staged_file.is_file():
                raise RestoreValidationError(
                    "managed media restore is incomplete: "
                    f"media {media_id} expects {staged_file}, but the copied "
                    "file is missing or is not a regular file; restore was not published"
                )
            try:
                actual_hash = sha256_file_bytes(staged_file)
            except OSError as exc:
                raise RestoreValidationError(
                    f"cannot verify copied managed media {staged_file}: {exc}"
                ) from exc
            if actual_hash != digest:
                raise RestoreValidationError(
                    "managed media restore failed integrity verification: "
                    f"{staged_file} hashes to {actual_hash}, expected {digest}; "
                    "restore was not published"
                )

            target_key = (str(media_id), str(canonical))
            if target_key in target_keys:
                raise RestoreValidationError(
                    "cannot rebase managed media locations: duplicate canonical "
                    f"target {canonical} for media {media_id}"
                )
            target_keys.add(target_key)
            if str(_old_locator) != str(canonical):
                updates.append((str(canonical), str(location_id)))

        if not updates:
            return 0
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "UPDATE media_locations SET locator = ? WHERE id = ?", updates
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise RestoreValidationError(
                "cannot persist managed-media locator rebase; "
                f"restore was not published: {exc}"
            ) from exc
        return len(updates)
    finally:
        conn.close()


def _read_external_manifest(backup: Path) -> tuple[_ExternalDependency, ...]:
    """Read and constrain the optional self-contained external section."""
    try:
        payload = json.loads(
            (backup / BACKUP_METADATA_NAME).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RestoreValidationError(f"invalid backup metadata: {backup}") from exc
    if not isinstance(payload, dict):
        raise RestoreValidationError(f"backup metadata is not an object: {backup}")
    section = payload.get("external")
    if section is None:
        return ()
    if not isinstance(section, dict) or section.get("mode") != "self_contained":
        raise RestoreValidationError(
            "backup external section is not a self-contained snapshot"
        )
    raw_files = section.get("files")
    if not isinstance(raw_files, list):
        raise RestoreValidationError("backup external section has no files list")

    result: list[_ExternalDependency] = []
    seen_locations: set[str] = set()
    media_root = (backup / BACKUP_MEDIA_DIR).resolve()
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise RestoreValidationError("backup external manifest entry is not an object")
        try:
            location_id = str(raw["location_id"])
            media_id = str(raw["media_id"])
            original_locator = str(raw["original_locator"])
            digest = validate_digest(raw["content_hash"])
            byte_size = int(raw["byte_size"])
            media_path = str(raw["media_path"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RestoreValidationError(
                "backup external manifest entry is incomplete"
            ) from exc
        if not location_id or not media_id or not original_locator or byte_size < 0:
            raise RestoreValidationError("backup external manifest entry has invalid identity")
        if location_id in seen_locations:
            raise RestoreValidationError(
                f"backup external manifest repeats location {location_id}"
            )
        seen_locations.add(location_id)
        relative = Path(media_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise RestoreValidationError(
                f"backup external manifest path escapes media tree: {media_path}"
            )
        staged_file = (media_root / relative).resolve()
        try:
            staged_file.relative_to(media_root)
        except ValueError as exc:
            raise RestoreValidationError(
                f"backup external manifest path escapes media tree: {media_path}"
            ) from exc
        if staged_file.is_symlink() or not staged_file.is_file():
            raise RestoreValidationError(
                "backup external snapshot is missing: "
                f"{media_path} for location {location_id}; restore was not published"
            )
        try:
            actual_size = staged_file.stat().st_size
            actual_hash = sha256_file_bytes(staged_file)
        except OSError as exc:
            raise RestoreValidationError(
                f"cannot verify backup external snapshot {staged_file}: {exc}"
            ) from exc
        if actual_size != byte_size or actual_hash != digest:
            raise RestoreValidationError(
                "backup external snapshot failed integrity verification: "
                f"{media_path} hashes to {actual_hash} ({actual_size} bytes), "
                f"expected {digest} ({byte_size} bytes); restore was not published"
            )
        result.append(
            _ExternalDependency(
                location_id=location_id,
                media_id=media_id,
                original_locator=original_locator,
                content_hash=digest,
                byte_size=byte_size,
                media_path=relative.as_posix(),
            )
        )
    return tuple(result)


def _rebase_staged_external_media(
    staged_db: Path,
    *,
    projects_root: Path,
    staged_media: Path,
    dependencies: tuple[_ExternalDependency, ...],
) -> tuple[int, int, int]:
    """Point restored external locations at verified backup-owned bytes.

    The source locator is retained in ``media.metadata_json`` as explicit
    backup provenance.  Distinct location rows that share one content digest
    receive hard-link aliases under ``external/locators``; the byte snapshot
    itself remains deduplicated and every update occurs before publication.
    """
    try:
        conn = sqlite3.connect(str(staged_db))
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            f"cannot open staged database for external-media rebase: {exc}"
        ) from exc
    try:
        try:
            rows = conn.execute(
                "SELECT l.id, l.media_id, l.locator, m.content_hash "
                "FROM media_locations AS l JOIN media AS m ON m.id = l.media_id "
                "WHERE l.realm = 'external_local' ORDER BY l.id"
            ).fetchall()
        except sqlite3.Error as exc:
            raise RestoreValidationError(
                f"cannot inspect staged external-media locators: {exc}"
            ) from exc

        row_by_location = {
            str(location_id): (str(media_id), str(locator), str(content_hash))
            for location_id, media_id, locator, content_hash in rows
        }
        dependency_by_location = {item.location_id: item for item in dependencies}
        unknown = sorted(set(dependency_by_location) - set(row_by_location))
        if unknown:
            raise RestoreValidationError(
                "backup external manifest references unknown location(s): "
                + ", ".join(unknown)
            )

        updates: list[tuple[str, str]] = []
        metadata_updates: dict[str, str] = {}
        metadata_cache: dict[str, dict[str, object]] = {}
        used_targets: dict[str, str] = {}
        rebased = 0
        restored_files = len({item.content_hash for item in dependencies})

        for item in dependencies:
            media_id, old_locator, db_digest = row_by_location[item.location_id]
            if media_id != item.media_id or db_digest != item.content_hash:
                raise RestoreValidationError(
                    "backup external manifest does not match staged media identity "
                    f"for location {item.location_id}; restore was not published"
                )
            source = staged_media / item.media_path
            if source.is_symlink() or not source.is_file():
                raise RestoreValidationError(
                    f"staged external snapshot is unavailable: {source}; "
                    "restore was not published"
                )
            target_relative = item.media_path
            prior_location = used_targets.get(target_relative)
            if prior_location is not None:
                # SQLite forbids two rows with the same (media, realm,
                # locator). Keep one deduplicated snapshot and make a stable
                # hard-link alias for the additional location row.
                alias_name = hashlib.sha256(
                    item.location_id.encode("utf-8")
                ).hexdigest()
                alias_relative = (
                    Path(EXTERNAL_MEDIA_DIR_NAME)
                    / "locators"
                    / alias_name
                )
                alias = staged_media / alias_relative
                alias.parent.mkdir(parents=True, exist_ok=True)
                if alias.exists() or alias.is_symlink():
                    if alias.is_symlink() or not alias.is_file():
                        raise RestoreValidationError(
                            f"external locator alias collision: {alias}"
                        )
                    if sha256_file_bytes(alias) != item.content_hash:
                        raise RestoreValidationError(
                            f"external locator alias has the wrong bytes: {alias}"
                        )
                else:
                    try:
                        os.link(source, alias)
                    except OSError as exc:
                        raise RestoreValidationError(
                            f"cannot create deduplicated external locator alias {alias}: {exc}"
                        ) from exc
                target_relative = alias_relative.as_posix()
                source = alias
            else:
                used_targets[target_relative] = item.location_id

            final_locator = str(
                (projects_root / MANAGED_DIR_NAME / MEDIA_DIR_NAME / target_relative).resolve()
            )
            if old_locator != final_locator:
                updates.append((final_locator, item.location_id))
                rebased += 1

            if item.media_id in metadata_cache:
                metadata = metadata_cache[item.media_id]
            else:
                try:
                    row = conn.execute(
                        "SELECT metadata_json FROM media WHERE id = ?", (item.media_id,)
                    ).fetchone()
                    raw_metadata = json.loads(row[0]) if row is not None else {}
                except (sqlite3.Error, TypeError, json.JSONDecodeError) as exc:
                    raise RestoreValidationError(
                        f"cannot preserve external locator provenance for media {item.media_id}"
                    ) from exc
                if isinstance(raw_metadata, dict):
                    metadata = raw_metadata
                else:
                    metadata = {"original_metadata": raw_metadata}
                metadata_cache[item.media_id] = metadata
            provenance = metadata.setdefault("backup_provenance", {})
            if not isinstance(provenance, dict):
                provenance = {"original_backup_provenance": provenance}
                metadata["backup_provenance"] = provenance
            records = provenance.setdefault("external_local", [])
            if not isinstance(records, list):
                records = []
                provenance["external_local"] = records
            record = {
                "location_id": item.location_id,
                "original_locator": item.original_locator,
                "content_hash": item.content_hash,
                "restored_locator": final_locator,
            }
            if not any(
                isinstance(existing, dict)
                and existing.get("location_id") == item.location_id
                for existing in records
            ):
                records.append(record)
            metadata_updates[item.media_id] = json.dumps(
                metadata, sort_keys=True, separators=(",", ":")
            )

        unresolved = len(set(row_by_location) - set(dependency_by_location))
        if updates or metadata_updates:
            try:
                conn.execute("BEGIN IMMEDIATE")
                if updates:
                    conn.executemany(
                        "UPDATE media_locations SET locator = ? WHERE id = ?", updates
                    )
                if metadata_updates:
                    conn.executemany(
                        "UPDATE media SET metadata_json = ? WHERE id = ?",
                        [(value, media_id) for media_id, value in metadata_updates.items()],
                    )
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                raise RestoreValidationError(
                    "cannot persist external-media locator rebase; restore was not published: "
                    f"{exc}"
                ) from exc
        return restored_files, rebased, unresolved
    finally:
        conn.close()


def _atomic_swap(
    live_db: Path,
    live_media: Path,
    staged_db: Path,
    staged_media: Path,
    *,
    journal_path: Path,
) -> None:
    """Publish staged database/media with a durable old-or-new journal.

    The journal is created before this function is called and is updated
    atomically after each database or media move. A hard-dead process therefore
    leaves enough authoritative state for :func:`recover_restore_staging` to
    select the complete prior pair or finish the complete replacement.
    """
    state = _read_restore_journal(journal_path, expected_database=live_db)
    if state.staged_database != staged_db or state.staged_media != staged_media:
        raise BackupError("restore journal staging paths do not match the swap")
    if not _restore_is_file(staged_db) or not _restore_is_dir(staged_media):
        raise BackupError("restore staging is incomplete before publication")

    # The journal owns the previous directory. Keeping it inside the
    # transaction makes arbitrary sibling files irrelevant to recovery.
    state.previous_dir.mkdir(parents=True, exist_ok=True)
    try:
        if state.had_database:
            os.replace(live_db, state.previous_dir / BACKUP_DATABASE_NAME)
            for suffix in state.database_sidecars:
                sidecar = Path(f"{live_db}{suffix}")
                if _restore_is_file(sidecar):
                    os.replace(
                        sidecar,
                        state.previous_dir / f"{BACKUP_DATABASE_NAME}{suffix}",
                    )
            state = _write_restore_journal(state, phase="database_moved")
            _restore_boundary("database_moved", journal=journal_path)
        if state.had_media:
            os.replace(live_media, state.previous_dir / BACKUP_MEDIA_DIR)
            state = _write_restore_journal(state, phase="media_moved")
            _restore_boundary("media_moved", journal=journal_path)

        # A replaced database must not read stale WAL/SHM bytes from the old
        # file. The old sidecars are already journaled in ``previous``.
        for suffix in _RESTORE_DATABASE_SIDECARS:
            _remove_restore_path(Path(f"{live_db}{suffix}"))
        os.replace(staged_db, live_db)
        state = _write_restore_journal(state, phase="database_published")
        _restore_boundary("database_published", journal=journal_path)
        _remove_restore_path(live_media)
        os.replace(staged_media, live_media)
        state = _write_restore_journal(state, phase="media_published")
        _restore_boundary("media_published", journal=journal_path)
    except BaseException:
        # A normal exception gets the same deterministic recovery as a fresh
        # process. Hard-death hooks use os._exit and never reach this block.
        try:
            _recover_restore_transaction(journal_path, expected_database=live_db)
        except BaseException:
            # Preserve the journal for the next standard composition if the
            # in-process rollback itself cannot complete.
            pass
        raise
    _finish_restore_transaction(state)


_LIVE_DATA_PROBE_TABLES = (
    "projects",
    "event_streams",
    "events",
    "media",
    "command_receipts",
)
"""Tables whose non-emptiness means the live database holds real content."""


def _live_database_holds_data(live_db: str | Path) -> bool:
    """Return True when an existing live database holds real content.

    An absent database is empty by definition. A present database counts as
    holding data when any content table has rows — i.e. anything beyond a
    freshly initialized root, whose tables are all empty. A present database
    that cannot be probed read-only (corrupt bytes, foreign schema, missing
    migration rows, unreadable WAL) **also** counts as holding data:
    restore must never silently discard bytes it cannot inspect.
    """
    path = Path(live_db)
    if not _restore_is_file(path):
        return False
    try:
        conn = sqlite3.connect(read_only_uri(path), uri=True)
    except sqlite3.Error:
        return True
    try:
        try:
            if not read_schema_migrations(conn):
                return True
        except sqlite3.Error:
            return True
        for table in _LIVE_DATA_PROBE_TABLES:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            except sqlite3.Error:
                return True
            if row is not None and int(row[0]) > 0:
                return True
        return False
    finally:
        conn.close()


def restore_backup(
    backup_path: str | Path,
    projects_root: str | Path | None = None,
    *,
    allow_overwrite: bool = False,
) -> RestoreResult:
    """Restore a backup into the managed database and media tree atomically.

    Stages the backup under ``.astrid/.restore-staging/``, validates the staged
    database read-only (quick_check + foreign_key_check + schema-version), and
    only then swaps it into place. A corrupt or incompatible backup raises
    :class:`RestoreValidationError` and leaves live data untouched.

    Safety default: when the target root already holds a live database with
    content, the restore refuses with :class:`RestoreValidationError` unless
    ``allow_overwrite=True`` (CLI ``--force``) is passed — a restore is a
    deliberate replacement of the live tree, never a silent overwrite.
    """
    root = resolve_projects_root(projects_root)
    backup = Path(backup_path)
    try:
        recover_backup_publication(backup)
    except BackupError as exc:
        raise RestoreValidationError(f"backup publication recovery failed: {exc}") from exc
    _validate_backup_layout(backup)

    live_db = derive_database_path(root)
    live_media = root / MANAGED_DIR_NAME / MEDIA_DIR_NAME
    backup_media = backup / BACKUP_MEDIA_DIR
    restored_media_files = _count_files(backup_media)
    rebased_media_locators = 0
    external_dependencies = _read_external_manifest(backup)
    restored_external_files = len({item.content_hash for item in external_dependencies})
    rebased_external_locators = 0
    unresolved_external_locators = 0
    restored_project_workspaces = 0

    lock = DatabaseOwnerLock(live_db)
    try:
        if not allow_overwrite and _live_database_holds_data(live_db):
            raise RestoreValidationError(
                f"refusing to restore over live data at {live_db}: the "
                "existing database already holds projects/events/media. "
                "Re-run with allow_overwrite=True (CLI: --force) to replace "
                "it deliberately."
            )
        try:
            recover_restore_staging(root)
        except BackupError as exc:
            raise RestoreValidationError(
                f"interrupted restore recovery failed: {exc}"
            ) from exc
        astrid_dir = live_db.parent
        astrid_dir.mkdir(parents=True, exist_ok=True)
        staging_root = astrid_dir / RESTORE_STAGING_DIR
        staging_root.mkdir(parents=True, exist_ok=True)
        txn_dir = staging_root / uuid.uuid4().hex
        txn_dir.mkdir(parents=True, exist_ok=False)
        journal_path = txn_dir / RESTORE_JOURNAL_NAME
        try:
            staged_db = txn_dir / BACKUP_DATABASE_NAME
            staged_media = txn_dir / BACKUP_MEDIA_DIR
            shutil.copy2(backup / BACKUP_DATABASE_NAME, staged_db)
            shutil.copytree(backup_media, staged_media)
            rebased_media_locators = _rebase_staged_managed_media(
                staged_db,
                projects_root=root,
                staged_media=staged_media,
            )
            (
                restored_external_files,
                rebased_external_locators,
                unresolved_external_locators,
            ) = _rebase_staged_external_media(
                staged_db,
                projects_root=root,
                staged_media=staged_media,
                dependencies=external_dependencies,
            )
            _normalize_staged_database_journal(staged_db)
            _validate_staged_database(staged_db)
            previous_dir = txn_dir / "previous"
            previous_dir.mkdir(parents=True, exist_ok=True)
            state = _RestoreJournal(
                journal_path=journal_path,
                transaction_dir=txn_dir,
                previous_dir=previous_dir,
                database_path=live_db,
                media_path=live_media,
                staged_database=staged_db,
                staged_media=staged_media,
                had_database=_restore_is_file(live_db),
                had_media=_restore_is_dir(live_media),
                database_sidecars=tuple(
                    suffix
                    for suffix in _RESTORE_DATABASE_SIDECARS
                    if _restore_is_file(Path(f"{live_db}{suffix}"))
                ),
                phase="prepared",
            )
            write_json_atomic(journal_path, state.payload())
            _atomic_swap(
                live_db,
                live_media,
                staged_db,
                staged_media,
                journal_path=journal_path,
            )
            # Project workspaces are derived from kernel rows, but they live
            # outside the journaled database/media pair.  Materialize them
            # only after that pair has published successfully so a validation
            # or swap failure never mutates the target workspace.  The helper
            # is idempotent: if the process is interrupted here, repeating the
            # same restore with ``--force`` safely reconciles the projections;
            # existing human-authored plan.md files are never overwritten.
            try:
                restored_project_workspaces = _materialize_restored_project_workspaces(
                    live_db,
                    projects_root=root,
                )
            except RestoreValidationError as exc:
                raise BackupError(
                    "database and media restore succeeded, but a derived project "
                    "workspace could not be reconciled; fix the reported filesystem "
                    "problem and repeat this same backup restore with --force: "
                    f"{exc}"
                ) from exc
        finally:
            # Hard-death tests bypass this finally. If an ordinary failure
            # recovered successfully (or staging validation failed before a
            # journal existed), remove the private transaction directory;
            # otherwise preserve the durable journal for startup recovery.
            if not journal_path.exists():
                shutil.rmtree(txn_dir, ignore_errors=True)
    finally:
        lock.release()

    return RestoreResult(
        projects_root=root,
        database_path=live_db,
        restored_media_files=restored_media_files,
        rebased_media_locators=rebased_media_locators,
        restored_project_workspaces=restored_project_workspaces,
        restored_external_files=restored_external_files,
        rebased_external_locators=rebased_external_locators,
        unresolved_external_locators=unresolved_external_locators,
        restored_at=_utc_now(),
    )


__all__ = [
    "BACKUP_DATABASE_NAME",
    "BACKUP_FORMAT_VERSION",
    "BACKUP_MEDIA_DIR",
    "BACKUP_METADATA_NAME",
    "BACKUP_PUBLICATION_BOUNDARIES",
    "BACKUP_PUBLICATION_SCHEMA",
    "RESTORE_JOURNAL_NAME",
    "RESTORE_JOURNAL_SCHEMA",
    "RESTORE_RECOVERY_BOUNDARIES",
    "RESTORE_SWAP_BOUNDARIES",
    "BackupError",
    "BackupResult",
    "RestoreResult",
    "RestoreValidationError",
    "create_backup",
    "recover_backup_publication",
    "recover_interrupted_restore",
    "recover_interrupted_restores",
    "recover_restore_staging",
    "restore_backup",
]
