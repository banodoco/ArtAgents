"""Read-only resolution of project-owned managed media.

Managed media identity is the content digest plus the owning kernel project.
Absolute locators are projections and can become stale after a portable
restore.  Consumers use this module to derive the current canonical locator
without rewriting immutable timeline events or receipt payloads.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from astrid.core.io.media_import import (
    managed_media_path,
    sha256_file_bytes,
    validate_digest,
)


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
    acquiring bytes; runtime project admission and the current byte hash
    remain the authorization boundary.
    """

    return _managed_locator_digest(value)


def resolve_owned_managed_media(
    *,
    projects_root: str | Path,
    project_ref: str,
    content_hash: str,
    requested_path: str | Path | None = None,
    runtime_client: Any | None = None,
    media_snapshot: Any | None = None,
) -> Path | None:
    """Return the verified current CAS locator for one project/digest.

    Resolution fails closed unless the workspace runtime's project-scoped
    managed-object read surface admits the digest.  The runtime response may
    also carry a managed locator; when it does, it must equal this root's
    canonical digest path.  The canonical path must be a regular non-symlink
    file whose bytes still hash to the admitted digest.  ``media_snapshot``
    is an already-admitted runtime response and is useful for child-process
    consumers; when omitted, ``runtime_client.media.list(project_ref)`` is
    read.  There is deliberately no local SQLite fallback.  When
    ``requested_path`` is supplied it must already name that current locator;
    callers use the omitted form to rebase a stale locator by content identity.
    """

    try:
        digest = validate_digest(content_hash)
    except (TypeError, ValueError):
        return None
    root = Path(projects_root).expanduser().resolve()
    canonical = managed_media_path(root, digest).resolve(strict=False)
    if requested_path is not None:
        try:
            requested = Path(requested_path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            return None
        if requested != canonical:
            return None

    rows = _runtime_media_rows(
        project_ref=project_ref,
        runtime_client=runtime_client,
        media_snapshot=media_snapshot,
    )
    admitted = [row for row in rows if row.digest == digest]
    if not admitted:
        return None
    # A generated runtime object normally has no filesystem locator: the
    # local CAS path is a deterministic child materialization of its digest.
    # If the admitted response does expose locations, enforce the old exact
    # managed_local-location contract against those projections.
    has_managed_locator = any(row.has_managed_locator for row in admitted)
    locators = {locator for row in admitted for locator in row.managed_locators}
    if has_managed_locator and locators != {canonical}:
        return None
    if canonical.is_symlink() or not canonical.is_file():
        return None
    try:
        if sha256_file_bytes(canonical) != digest:
            return None
    except OSError:
        return None
    return canonical


class _RuntimeMediaRow:
    """Small normalized read model for generated/runtime media responses."""

    __slots__ = (
        "media_id",
        "digest",
        "mime_type",
        "has_managed_locator",
        "managed_locators",
    )

    def __init__(
        self,
        *,
        media_id: str | None,
        digest: str,
        mime_type: str | None,
        has_managed_locator: bool,
        managed_locators: set[Path],
    ) -> None:
        self.media_id = media_id
        self.digest = digest
        self.mime_type = mime_type
        self.has_managed_locator = has_managed_locator
        self.managed_locators = managed_locators


def _value(row: Any, *keys: str) -> Any:
    if isinstance(row, Mapping):
        for key in keys:
            if key in row:
                return row[key]
        return None
    for key in keys:
        try:
            value = getattr(row, key)
        except AttributeError:
            continue
        return value
    return None


def _digest_from_runtime_row(row: Any) -> str | None:
    raw = _value(row, "content_hash", "content_sha256", "sha256", "digest", "object_id")
    if not isinstance(raw, str):
        return None
    try:
        return validate_digest(raw.removeprefix("sha256:"))
    except (TypeError, ValueError):
        return None


def _managed_locators_from_runtime_row(row: Any) -> tuple[bool, set[Path]]:
    """Extract optional managed-local projections without trusting them."""

    raw_locations = _value(row, "locations", "media_locations")
    if raw_locations is None:
        raw_locations = [row] if _value(row, "locator") is not None else []
    if isinstance(raw_locations, Mapping):
        raw_locations = [raw_locations]
    if not isinstance(raw_locations, (list, tuple, set)):
        return False, set()
    result: set[Path] = set()
    has_managed_locator = False
    for location in raw_locations:
        realm = _value(location, "realm")
        locator = _value(location, "locator", "path")
        if realm not in (None, "managed_local"):
            continue
        if not isinstance(locator, str):
            if realm == "managed_local":
                return True, set()
            continue
        has_managed_locator = True
        if not locator.strip():
            return True, set()
        try:
            result.add(Path(locator).expanduser().resolve(strict=False))
        except (OSError, RuntimeError, TypeError, ValueError):
            return True, set()
    return has_managed_locator, result


def _runtime_media_rows(
    *,
    project_ref: str,
    runtime_client: Any | None,
    media_snapshot: Any | None,
) -> tuple[_RuntimeMediaRow, ...]:
    """Read only project-scoped runtime media facts; never consult local DB."""

    raw_rows = media_snapshot
    if raw_rows is None and runtime_client is not None:
        try:
            media = getattr(runtime_client, "media", None)
            if media is not None and callable(getattr(media, "list", None)):
                result = media.list(project_ref)
                raw_rows = result.data if getattr(result, "ok", True) else None
            elif callable(getattr(runtime_client, "list_project_objects", None)):
                raw_rows = runtime_client.list_project_objects(project_ref)
        except Exception:  # noqa: BLE001 - runtime read failures fail closed here
            return ()
    if isinstance(raw_rows, Mapping):
        raw_rows = raw_rows.get("items", raw_rows.get("media", raw_rows))
    if isinstance(raw_rows, Mapping):
        # A snapshot keyed by media id is a convenient admitted child shape.
        raw_rows = [
            {"media_id": key, **value} if isinstance(value, Mapping) else value
            for key, value in raw_rows.items()
        ]
    if not isinstance(raw_rows, (list, tuple, set)):
        return ()
    normalized: list[_RuntimeMediaRow] = []
    for raw in raw_rows:
        digest = _digest_from_runtime_row(raw)
        if digest is None:
            continue
        media_id = _value(raw, "media_id", "id", "object_id")
        has_managed_locator, managed_locators = _managed_locators_from_runtime_row(raw)
        normalized.append(
            _RuntimeMediaRow(
                media_id=str(media_id) if isinstance(media_id, str) and media_id else None,
                digest=digest,
                mime_type=(
                    str(mime)
                    if isinstance(
                        (mime := _value(raw, "mime_type", "media_type", "type")), str
                    )
                    and mime.strip()
                    else None
                ),
                has_managed_locator=has_managed_locator,
                managed_locators=managed_locators,
            )
        )
    return tuple(normalized)


def _resolve_owned_managed_media_id(
    *,
    projects_root: str | Path,
    project_ref: str,
    media_id: object,
    recorded_digest: object = None,
    runtime_client: Any | None = None,
    media_snapshot: Any | None = None,
) -> tuple[Path, str, str] | None:
    """Resolve one project-owned media ID to verified CAS path/hash/MIME."""

    if not isinstance(media_id, str) or not media_id.strip():
        return None
    root = Path(projects_root).expanduser().resolve()
    rows = _runtime_media_rows(
        project_ref=project_ref,
        runtime_client=runtime_client,
        media_snapshot=media_snapshot,
    )
    matching = [row for row in rows if row.media_id == media_id]
    if not matching:
        return None
    try:
        digest = validate_digest(matching[0].digest)
    except (TypeError, ValueError):
        return None
    if recorded_digest is not None:
        try:
            if validate_digest(recorded_digest) != digest:
                return None
        except (TypeError, ValueError):
            return None
    resolved = resolve_owned_managed_media(
        projects_root=root,
        project_ref=project_ref,
        content_hash=digest,
        runtime_client=runtime_client,
        media_snapshot=media_snapshot,
    )
    mime_type = matching[0].mime_type
    if resolved is None or not isinstance(mime_type, str) or not mime_type.strip():
        return None
    return resolved, digest, mime_type


def rebase_timeline_registry_managed_assets(
    registry: Mapping[str, Any],
    *,
    projects_root: str | Path,
    project_ref: str,
    runtime_client: Any | None = None,
    media_snapshot: Any | None = None,
) -> dict[str, Any]:
    """Return a derived registry with stale managed CAS locators refreshed.

    Entries may identify managed bytes either by Astrid's complete absolute
    digest-tree shape or by a project-owned runtime ``media_id`` when no file
    locator is supplied. An explicit registry hash must agree with the locator
    or runtime media admission; when it is absent, the strict
    ``sha256/aa/bb/<digest>`` locator or admitted runtime media row supplies
    the candidate digest. The destination runtime admission, canonical
    locator, regular file, and current bytes must still prove that digest
    before rebasing. The returned copy changes no runtime row,
    timeline event, history snapshot, or command receipt. Explicit non-managed
    file locators are left untouched.
    """

    rebased = copy.deepcopy(dict(registry))
    raw_assets = rebased.get("assets", rebased)
    if not isinstance(raw_assets, dict):
        return rebased
    for entry in raw_assets.values():
        if not isinstance(entry, dict):
            continue
        recorded_digest = (
            entry.get("content_sha256") or entry.get("sha256") or entry.get("hash")
        )
        raw_file = entry.get("file")
        locator_digest = _managed_locator_digest(raw_file)
        if locator_digest is None:
            if isinstance(raw_file, str) and raw_file.strip():
                continue
            resolved_by_id = _resolve_owned_managed_media_id(
                projects_root=projects_root,
                project_ref=project_ref,
                media_id=entry.get("media_id"),
                recorded_digest=recorded_digest,
                runtime_client=runtime_client,
                media_snapshot=media_snapshot,
            )
            if resolved_by_id is not None:
                resolved, digest, mime_type = resolved_by_id
                entry["file"] = str(resolved)
                entry.setdefault("content_sha256", digest)
                entry.setdefault("type", mime_type)
            continue
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
            runtime_client=runtime_client,
            media_snapshot=media_snapshot,
        )
        if resolved is not None:
            entry["file"] = str(resolved)
    return rebased


__all__ = [
    "managed_locator_digest",
    "rebase_timeline_registry_managed_assets",
    "resolve_owned_managed_media",
]
