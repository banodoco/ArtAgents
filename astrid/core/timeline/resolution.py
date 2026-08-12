"""Asset normalization and integrity classification for timeline snapshots.

This module is deliberately independent of :mod:`astrid.core.timeline.snapshot`
(R4): it consumes a raw registry mapping (``{"assets": {...}}`` or
``{"assets": [...]}``) plus a project root and produces one
:class:`AssetIntegrity` classification per asset.

The single base for local asset resolution is **``project_root/sources``** —
the same base R4's media-hash resolution anchors on, and the only local file
key it reads is ``file`` (again matching R4).  Absolute refs, project-relative
``sources/...`` refs (with either slash style), and sources-relative refs must
all land beneath that directory or they are rejected.

Classification rules (in priority order):

1. **Thumbnail-only** — if the asset key contains ``"thumbnail"`` or the
   derived role is ``thumbnail_only``, the state is ``thumbnail_only`` and no
   hash is required.
2. **Remote** — an http/https/data (or any other non-empty scheme) reference
   with no usable local file is ``remote``; media is never fetched.
3. **Containment** — a local reference must resolve beneath
   ``project_root/sources``.  A path that escapes ``project_root`` is
   ``unsupported`` ("path escapes project root"); one that stays inside
   ``project_root`` but outside ``sources`` is ``unsupported`` ("path outside
   sources"); a symlink inside ``sources`` that resolves outside ``sources``
   is ``unsupported`` ("symlink escapes sources") unless its real target
   still lands inside ``sources``, in which case it is allowed.
4. **Missing** — a contained local path whose file does not exist is
   ``missing`` (this takes precedence over hash concerns).
5. **Hash** — for an existing contained file: if the entry records an expected
   sha256 (``content_sha256``/``sha256``/``hash``), the observed digest of the
   file bytes decides ``verified_original`` vs ``hash_mismatch``; if no
   expected hash is recorded the state is ``hash_unrecorded`` — a hash computed
   now does not retroactively verify an unrecorded one.

A remote URL next to a local file never wins: the local file is preferred and
the URL is ignored (no fallback, no fetch).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

_READ_CHUNK = 1024 * 1024

#: Registry entry keys that may carry an expected content hash (first wins).
_HASH_KEYS = ("content_sha256", "sha256", "hash")
#: Registry entry key that may carry a local file reference (R4 parity: only
#: ``file`` is read — the same key R4's media-hash resolution consumes).
_LOCAL_PATH_KEYS = ("file",)
#: Registry entry keys that may carry a remote URL (no local file fallback).
_URL_KEYS = ("url", "sourceUrl", "remoteUrl")
#: Registry entry keys that may carry a thumbnail URL.
_THUMBNAIL_URL_KEYS = ("thumbnailUrl", "thumbnail_url")
#: Entry keys that may carry an explicit role/kind marker.
_ROLE_KEYS = ("role", "kind")
#: Registry entry keys carrying source provenance (real registry shape).
_SOURCE_ID_KEY = "sourceId"
_SOURCE_VERSION_KEY = "sourceVersion"

_ROLE_ALIASES = {
    "timeline_media": "timeline_media",
    "generation_reference": "generation_reference",
    "generation_output": "generation_output",
    "thumbnail_only": "thumbnail_only",
    "rendered_sample": "rendered_sample",
    "thumbnail": "thumbnail_only",
    "proxy": "thumbnail_only",
    "render-output": "rendered_sample",
    "render_output": "rendered_sample",
}

#: URI schemes treated as remote (never fetched, never treated as local paths).
_REMOTE_SCHEMES = frozenset({"http", "https", "data", "file", "ftp", "s3"})


@dataclass(frozen=True)
class AssetIntegrity:
    """One immutable integrity classification for a single registry asset."""

    asset_key: str
    role: str
    state: str
    expected_sha256: str | None
    observed_sha256: str | None
    path: str | None
    reason: str
    source_id: str | None
    source_version: str | None


def _sha256_file(path: Path) -> str:
    """Raw hex SHA-256 of *path* using 1 MB chunked reads (stdlib only)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_uri(value: str) -> str | None:
    """Return the scheme if *value* looks like a URI, else None."""
    scheme = urlparse(value).scheme
    if scheme:
        return scheme
    return None


def _expected_hash(entry: dict[str, Any]) -> str | None:
    for key in _HASH_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _local_ref(entry: dict[str, Any]) -> str | None:
    for key in _LOCAL_PATH_KEYS:
        value = entry.get(key)
        if isinstance(value, (str, Path)) and str(value).strip():
            return str(value).strip()
    return None


def _remote_ref(entry: dict[str, Any]) -> str | None:
    for key in _URL_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _thumbnail_ref(entry: dict[str, Any]) -> str | None:
    for key in _THUMBNAIL_URL_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _source_id(entry: dict[str, Any]) -> str | None:
    value = entry.get(_SOURCE_ID_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _source_version(entry: dict[str, Any]) -> str | None:
    value = entry.get(_SOURCE_VERSION_KEY)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _derive_role(
    asset_key: str,
    entry: dict[str, Any],
    roles: set[str] | None,
    default_role: str,
) -> str:
    if "thumbnail" in asset_key.lower():
        return "thumbnail_only"
    if roles:
        if "thumbnail_only" in roles:
            return "thumbnail_only"
        if len(roles) == 1:
            return next(iter(roles))
        return default_role
    for key in _ROLE_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return _ROLE_ALIASES.get(value.strip().lower(), "unknown")
    return default_role


def _resolve_asset_local_path_contained_with_reason(
    asset_file: str,
    *,
    project_root: Path,
) -> tuple[Path | None, str | None]:
    """Implement the shared local-path contract and retain R5's reason."""

    if not isinstance(asset_file, str) or not asset_file.strip():
        return None, "no-local-ref"
    ref = asset_file.strip()
    candidate = Path(ref).expanduser()
    # On Windows a drive-qualified path has a urlparse scheme (for example
    # ``C:``), so absolute-path detection must win over URI detection.
    if not candidate.is_absolute() and _is_uri(ref) is not None:
        return None, "remote"
    try:
        root = project_root.resolve()
        sources_root = (root / "sources").resolve()
    except (OSError, RuntimeError):
        return None, "escape"
    if not sources_root.is_relative_to(root):
        return None, "escape"

    if candidate.is_absolute():
        lexical = Path(os.path.abspath(candidate))
    else:
        # Treat both slash styles as asset-path separators so the contract is
        # stable when a registry written on one platform is read on another.
        normalized_ref = ref.replace("\\", "/")
        if normalized_ref.startswith("sources/"):
            normalized_ref = normalized_ref[len("sources/") :]
        lexical = Path(os.path.abspath(sources_root / Path(normalized_ref)))

    try:
        resolved = lexical.resolve()
    except (OSError, RuntimeError):
        return None, "symlink-escape"
    if lexical.is_relative_to(sources_root):
        if resolved.is_relative_to(sources_root):
            return resolved, None
        # A symlink inside sources resolved outside sources.
        return None, "symlink-escape"
    if resolved.is_relative_to(sources_root):
        # e.g. a symlinked parent that still lands inside sources: allowed.
        return resolved, None
    if resolved.is_relative_to(root):
        return None, "outside-sources"
    return None, "escape"


def resolve_asset_local_path_contained(
    asset_file: str,
    *,
    project_root: Path,
) -> Path | None:
    """Return the normalized contained path, without requiring existence.

    This is the containment half of :func:`resolve_asset_local_path`.  It
    returns ``None`` only when the reference is empty, remote, or escapes the
    real ``project_root/sources`` tree.  A contained missing path is returned
    so callers such as :func:`classify_asset` can report ``missing`` rather
    than ``unsupported``.
    """

    path, failure = _resolve_asset_local_path_contained_with_reason(
        asset_file,
        project_root=project_root,
    )
    return path if failure is None else None


def resolve_asset_local_path(
    asset_file: str,
    *,
    project_root: Path,
) -> Path | None:
    """Resolve one existing local asset under ``project_root/sources``.

    This is the single normalization contract shared by R4 and R5:

    1. The anchor is always ``project_root / "sources"``.
    2. A relative ref starting with ``sources/`` or ``sources\\`` has that
       one prefix stripped before it is joined to the anchor.
    3. Every other relative ref is joined directly to the anchor.
    4. An absolute ref is accepted only when its resolved path is beneath the
       anchor; otherwise ``None`` is returned.
    5. Real paths are checked against the real anchor, so ``..`` and symlink
       escapes return ``None`` (as do remote URI references).
    6. A path is returned only when the referenced file exists; contained
       missing or non-file paths return ``None``.  Use
       :func:`resolve_asset_local_path_contained` when a caller must
       distinguish missing from unsupported.
    """

    path = resolve_asset_local_path_contained(
        asset_file,
        project_root=project_root,
    )
    if path is None:
        return None
    try:
        return path if path.is_file() else None
    except OSError:
        return None


def _resolve_local_path(
    entry: dict[str, Any],
    project_root: Path,
) -> tuple[Path | None, str | None]:
    """Resolve a registry entry while retaining R5's failure classification."""

    ref = _local_ref(entry)
    if ref is None:
        return None, "no-local-ref"
    return _resolve_asset_local_path_contained_with_reason(
        ref,
        project_root=project_root,
    )


def _metadata_suffix(entry: dict[str, Any]) -> str:
    parts: list[str] = []
    duration = entry.get("duration")
    if isinstance(duration, (int, float)) and not isinstance(duration, bool):
        parts.append(f"duration={duration}")
    asset_type = entry.get("type")
    if isinstance(asset_type, str) and asset_type.strip():
        parts.append(f"type={asset_type.strip()}")
    resolution = entry.get("resolution")
    if isinstance(resolution, str) and resolution.strip():
        parts.append(f"resolution={resolution.strip()}")
    return "; " + "; ".join(parts) if parts else ""


def classify_asset(
    asset_key: str,
    registry_entry: Any,
    *,
    project_root: Path,
    roles: set[str] | None = None,
    default_role: str = "timeline_media",
) -> AssetIntegrity:
    """Classify a single registry entry into an :class:`AssetIntegrity`.

    Parameters
    ----------
    asset_key:
        Registry key identifying the asset.
    registry_entry:
        The registry entry dict (any non-dict is treated as empty).
    project_root:
        Root directory whose ``sources`` subdirectory anchors all local file
        references; a reference must resolve beneath ``project_root/sources``
        to be classified as a local asset.
    roles:
        Optional explicit role set (takes precedence over entry fields).
    default_role:
        Role used when neither *roles* nor entry fields decide.
    """
    key = str(asset_key)
    entry = registry_entry if isinstance(registry_entry, dict) else {}
    role = _derive_role(key, entry, roles, default_role)
    source_id = _source_id(entry)
    source_version = _source_version(entry)

    # Rule 1: thumbnail-only assets require no hash and are never substituted.
    if role == "thumbnail_only":
        path, failure = _resolve_local_path(entry, project_root)
        reason = "thumbnail-only asset — no hash required"
        if path is not None:
            reason += f" (local file: {path})"
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="thumbnail_only",
            expected_sha256=None,
            observed_sha256=None,
            path=str(path) if path is not None else None,
            reason=reason,
            source_id=source_id,
            source_version=source_version,
        )

    path, failure = _resolve_local_path(entry, project_root)

    # Rule 2: remote references are never fetched.
    if failure == "remote":
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="remote",
            expected_sha256=_expected_hash(entry),
            observed_sha256=None,
            path=None,
            reason=f"remote source — no fetch (scheme: {_is_uri(_local_ref(entry) or '')})",
            source_id=source_id,
            source_version=source_version,
        )

    # Rule 3: escaping paths are unsupported, never normalized.
    if failure == "escape":
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="unsupported",
            expected_sha256=_expected_hash(entry),
            observed_sha256=None,
            path=None,
            reason=f"path escapes project root: {_local_ref(entry)!r}",
            source_id=source_id,
            source_version=source_version,
        )

    # Rule 3: inside project_root but outside sources -> unsupported.
    if failure == "outside-sources":
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="unsupported",
            expected_sha256=_expected_hash(entry),
            observed_sha256=None,
            path=None,
            reason=f"path outside sources: {_local_ref(entry)!r}",
            source_id=source_id,
            source_version=source_version,
        )

    # Rule 3: a symlink inside sources resolving outside sources.
    if failure == "symlink-escape":
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="unsupported",
            expected_sha256=_expected_hash(entry),
            observed_sha256=None,
            path=None,
            reason=f"symlink escapes sources: {_local_ref(entry)!r}",
            source_id=source_id,
            source_version=source_version,
        )

    # No local file reference at all.
    if failure == "no-local-ref":
        remote = _remote_ref(entry)
        if remote is not None:
            return AssetIntegrity(
                asset_key=key,
                role=role,
                state="remote",
                expected_sha256=_expected_hash(entry),
                observed_sha256=None,
                path=None,
                reason=f"remote source — no fetch (scheme: {_is_uri(remote)})",
                source_id=source_id,
                source_version=source_version,
            )
        if _thumbnail_ref(entry) is not None:
            return AssetIntegrity(
                asset_key=key,
                role=role,
                state="thumbnail_only",
                expected_sha256=None,
                observed_sha256=None,
                path=None,
                reason="only thumbnailUrl present — treated as thumbnail-only, no hash required",
                source_id=source_id,
                source_version=source_version,
            )
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="missing",
            expected_sha256=_expected_hash(entry),
            observed_sha256=None,
            path=None,
            reason="no local file reference in registry entry",
            source_id=source_id,
            source_version=source_version,
        )

    # Rule 4: contained path that is missing or is not a regular file.
    if not path.is_file():
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="missing",
            expected_sha256=_expected_hash(entry),
            observed_sha256=None,
            path=str(path),
            reason=f"file not found or not a regular file: {path}",
            source_id=source_id,
            source_version=source_version,
        )

    # Rule 5: hash verification for existing contained files.
    expected = _expected_hash(entry)
    if expected is None:
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="hash_unrecorded",
            expected_sha256=None,
            observed_sha256=None,
            path=str(path),
            reason=(
                "no expected sha256 recorded in registry entry"
                f" (file exists but a current hash does not verify it){_metadata_suffix(entry)}"
            ),
            source_id=source_id,
            source_version=source_version,
        )
    try:
        observed = _sha256_file(path)
    except OSError as exc:  # e.g. permission denied, is-a-directory
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="missing",
            expected_sha256=expected,
            observed_sha256=None,
            path=str(path),
            reason=f"file not readable: {exc}",
            source_id=source_id,
            source_version=source_version,
        )
    if observed == expected:
        return AssetIntegrity(
            asset_key=key,
            role=role,
            state="verified_original",
            expected_sha256=expected,
            observed_sha256=observed,
            path=str(path),
            reason="observed sha256 matches expected sha256",
            source_id=source_id,
            source_version=source_version,
        )
    return AssetIntegrity(
        asset_key=key,
        role=role,
        state="hash_mismatch",
        expected_sha256=expected,
        observed_sha256=observed,
        path=str(path),
        reason=f"observed sha256 {observed} != expected {expected}",
        source_id=source_id,
        source_version=source_version,
    )


def resolve_asset_path(
    asset_key: str,
    registry_entry: Any,
    *,
    project_root: Path,
) -> Path | None:
    """Return the contained absolute local path for *registry_entry*, or None.

    None is returned for remote references, escaping paths, paths outside
    ``project_root/sources``, symlink escapes, and entries with no local file
    reference.  File existence is deliberately not checked here; use
    :func:`classify_asset` for existence/hash classification.
    """
    entry = registry_entry if isinstance(registry_entry, dict) else {}
    ref = _local_ref(entry)
    if ref is None:
        return None
    return resolve_asset_local_path_contained(ref, project_root=project_root)


def _iter_registry_assets(
    registry: dict[str, Any],
) -> Iterable[tuple[str, Any]]:
    """Yield ``(asset_key, entry)`` pairs from either supported registry shape."""
    if not isinstance(registry, dict):
        raise ValueError(f"registry must be a dict, got {type(registry).__name__}")
    assets = registry.get("assets", registry) if "assets" in registry else registry
    if isinstance(assets, dict):
        for key, entry in assets.items():
            yield str(key), entry
        return
    if isinstance(assets, list):
        for index, item in enumerate(assets):
            if not isinstance(item, dict):
                yield f"asset-{index}", item
                continue
            key = item.get("asset_key") or item.get("key") or item.get("id")
            if key is None and len(item) == 1:
                (candidate_key, candidate_entry) = next(iter(item.items()))
                if isinstance(candidate_entry, dict):
                    yield str(candidate_key), candidate_entry
                    continue
            yield str(key) if key is not None else f"asset-{index}", item
        return
    raise ValueError(f"registry['assets'] must be a dict or list, got {type(assets).__name__}")


def classify_registry(
    registry: dict[str, Any],
    *,
    project_root: Path,
    default_role: str = "timeline_media",
) -> dict[str, AssetIntegrity]:
    """Classify every asset in *registry* (``{"assets": {...}}`` or ``[...]``)."""
    return {
        key: classify_asset(
            key,
            entry,
            project_root=project_root,
            default_role=default_role,
        )
        for key, entry in _iter_registry_assets(registry)
    }


__all__ = [
    "AssetIntegrity",
    "classify_asset",
    "classify_registry",
    "resolve_asset_local_path",
    "resolve_asset_local_path_contained",
    "resolve_asset_path",
]
