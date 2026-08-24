"""Read-only resolution of project-owned managed media.

Managed media identity is the content digest plus the owning kernel project.
Absolute locators are projections and can become stale after a portable
restore.  Consumers use this module to derive the current canonical locator
without rewriting immutable timeline events or receipt payloads.
"""

from __future__ import annotations

import copy
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.core.foundation.project_paths import (
    derive_database_path,
    resolve_projects_root,
)
from astrid.core.io.media_import import (
    managed_media_path,
    sha256_file_bytes,
    validate_digest,
)
from astrid.core.migrations.runner import read_only_uri


def _managed_locator_digest(value: object) -> str | None:
    """Return the digest encoded by one strict absolute CAS locator shape."""

    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        return None
    parts = path.parts
    if len(parts) < 6 or tuple(parts[-6:-3]) != (".astrid", "media", "sha256"):
        return None
    try:
        digest = validate_digest(parts[-1])
    except (TypeError, ValueError):
        return None
    if parts[-3] != digest[:2] or parts[-2] != digest[2:4]:
        return None
    return digest


def managed_locator_digest(value: object) -> str | None:
    """Return the digest encoded by an exact absolute managed CAS locator.

    This is intentionally only a syntactic identity hint.  Callers must pass
    the returned digest through :func:`resolve_owned_managed_media` before
    acquiring bytes; the kernel ownership row and current byte hash remain the
    authorization boundary.
    """

    return _managed_locator_digest(value)


def resolve_owned_managed_media(
    *,
    projects_root: str | Path,
    project_ref: str,
    content_hash: str,
    requested_path: str | Path | None = None,
) -> Path | None:
    """Return the verified current CAS locator for one project/digest.

    Resolution fails closed unless the kernel has an exact ``managed_local``
    row for the project and digest, its locator equals this root's canonical
    digest path, and the bytes still hash to the recorded digest.  When
    ``requested_path`` is supplied it must already name that current locator;
    callers use the omitted form to rebase a stale locator by content identity.
    """

    try:
        digest = validate_digest(content_hash)
    except (TypeError, ValueError):
        return None
    root = resolve_projects_root(projects_root)
    database = derive_database_path(root)
    if not database.is_file():
        return None
    canonical = managed_media_path(root, digest).resolve(strict=False)
    if requested_path is not None:
        try:
            requested = Path(requested_path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            return None
        if requested != canonical:
            return None

    try:
        conn = sqlite3.connect(read_only_uri(database), uri=True)
    except sqlite3.Error:
        return None
    try:
        rows = conn.execute(
            "SELECT l.locator FROM media_locations AS l "
            "JOIN media AS m ON m.id = l.media_id "
            "JOIN projects AS p ON p.id = m.project_id "
            "WHERE (p.slug = ? OR p.id = ?) AND m.content_hash = ? "
            "AND l.realm = 'managed_local' ORDER BY l.id",
            (project_ref, project_ref, digest),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()

    if not rows:
        return None
    try:
        locators = {
            Path(str(row[0])).expanduser().resolve(strict=False) for row in rows
        }
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    if locators != {canonical}:
        return None
    if canonical.is_symlink() or not canonical.is_file():
        return None
    try:
        if sha256_file_bytes(canonical) != digest:
            return None
    except OSError:
        return None
    return canonical


def rebase_timeline_registry_managed_assets(
    registry: Mapping[str, Any],
    *,
    projects_root: str | Path,
    project_ref: str,
) -> dict[str, Any]:
    """Return a derived registry with stale managed CAS locators refreshed.

    Only entries that use Astrid's complete absolute managed digest-tree shape
    are eligible.  An explicit registry hash must agree with the locator; when
    it is absent, the strict ``sha256/aa/bb/<digest>`` locator supplies the
    candidate digest.  The destination kernel row, canonical locator, regular
    file, and current bytes must still prove that digest before rebasing.  The
    returned copy changes no kernel row, timeline event, history snapshot, or
    command receipt.
    """

    rebased = copy.deepcopy(dict(registry))
    raw_assets = rebased.get("assets", rebased)
    if not isinstance(raw_assets, dict):
        return rebased
    for entry in raw_assets.values():
        if not isinstance(entry, dict):
            continue
        locator_digest = _managed_locator_digest(entry.get("file"))
        if locator_digest is None:
            continue
        recorded_digest = (
            entry.get("content_sha256") or entry.get("sha256") or entry.get("hash")
        )
        if recorded_digest is not None:
            try:
                valid_digest = validate_digest(recorded_digest)
            except (TypeError, ValueError):
                continue
            if valid_digest != locator_digest:
                continue
        else:
            valid_digest = locator_digest
        resolved = resolve_owned_managed_media(
            projects_root=projects_root,
            project_ref=project_ref,
            content_hash=valid_digest,
        )
        if resolved is not None:
            entry["file"] = str(resolved)
    return rebased


__all__ = [
    "managed_locator_digest",
    "rebase_timeline_registry_managed_assets",
    "resolve_owned_managed_media",
]
