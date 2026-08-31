"""Runtime-managed media identity classification for timeline snapshots.

Live Astrid accepts media by the neutral runtime's project-scoped object id and
verified content digest. URLs, local paths, CAS locators, path fingerprints,
and legacy path-backed realms are migration-only concepts and are deliberately
not represented by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from astrid.core.io.media_import import validate_digest

_HASH_KEYS = ("digest", "content_sha256", "sha256", "hash")
_ROLE_KEYS = ("role", "kind")
_URL_KEYS = ("url", "sourceUrl", "remoteUrl", "file")
_THUMBNAIL_URL_KEYS = ("thumbnailUrl", "thumbnail_url")
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


@dataclass(frozen=True)
class AssetIntegrity:
    asset_key: str
    role: str
    state: str
    expected_sha256: str | None
    observed_sha256: str | None
    reason: str
    source_id: str | None
    source_version: str | None


def _expected_hash(entry: Mapping[str, Any]) -> str | None:
    for key in _HASH_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().removeprefix("sha256:")
    return None


def _derive_role(key: str, entry: Mapping[str, Any], roles: set[str] | None, default: str) -> str:
    if "thumbnail" in key.lower():
        return "thumbnail_only"
    if roles:
        return "thumbnail_only" if "thumbnail_only" in roles else next(iter(roles))
    for field in _ROLE_KEYS:
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return _ROLE_ALIASES.get(value.strip().lower(), "unknown")
    return default


def _runtime_rows(runtime_client: Any | None, project_ref: str, media_snapshot: Any | None) -> list[Mapping[str, Any]]:
    rows: Any = media_snapshot
    if rows is None:
        if runtime_client is None:
            return []
        try:
            result = runtime_client.media.list(project_ref)
            rows = result.data if result.ok else []
        except Exception:  # noqa: BLE001 - a runtime read failure is fail-closed
            return []
    if isinstance(rows, Mapping):
        rows = rows.get("items", rows.get("media", rows.get(project_ref, rows)))
    if isinstance(rows, Mapping):
        rows = [{"object_id": key, **value} for key, value in rows.items() if isinstance(value, Mapping)]
    if not isinstance(rows, (list, tuple, set)):
        return []
    scoped: list[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        scope = row.get("project_ref") or row.get("project_slug")
        if scope is not None and str(scope) != project_ref:
            continue
        scoped.append(row)
    return scoped


def _admitted_digest(entry: Mapping[str, Any], *, project_ref: str, runtime_client: Any | None, media_snapshot: Any | None) -> str | None:
    object_id = entry.get("object_id") or entry.get("media_id")
    if not isinstance(object_id, str) or not object_id.strip():
        return None
    expected = _expected_hash(entry)
    for row in _runtime_rows(runtime_client, project_ref, media_snapshot):
        if str(row.get("object_id") or row.get("media_id") or row.get("id")) != object_id:
            continue
        raw = row.get("digest") or row.get("content_hash") or row.get("content_sha256") or row.get("sha256")
        if not isinstance(raw, str):
            return None
        try:
            digest = validate_digest(raw.removeprefix("sha256:"))
        except (TypeError, ValueError):
            return None
        if expected is not None:
            try:
                if validate_digest(expected) != digest:
                    return None
            except (TypeError, ValueError):
                return None
        return digest
    return None


def classify_asset(
    asset_key: str,
    registry_entry: Any,
    *,
    project_ref: str,
    roles: set[str] | None = None,
    default_role: str = "timeline_media",
    runtime_client: Any | None = None,
    media_snapshot: Any | None = None,
) -> AssetIntegrity:
    """Classify one registry entry without opening any filesystem media path."""
    key = str(asset_key)
    entry = registry_entry if isinstance(registry_entry, Mapping) else {}
    role = _derive_role(key, entry, roles, default_role)
    expected = _expected_hash(entry)
    source_id = (
        entry.get("object_id")
        or entry.get("media_id")
        or (entry.get("sourceId") if isinstance(entry.get("sourceId"), str) else None)
    )
    source_version = entry.get("sourceVersion") if isinstance(entry.get("sourceVersion"), str) else None
    forbidden = next((field for field in (*_URL_KEYS, *_THUMBNAIL_URL_KEYS, "path", "source_path", "locator", "realm") if field in entry), None)
    if forbidden is not None:
        return AssetIntegrity(key, role, "unsupported", expected, None, "media locators are retired; use a runtime-managed object id and digest", source_id, source_version)
    if role == "thumbnail_only" and not (entry.get("object_id") or entry.get("media_id")):
        return AssetIntegrity(key, role, "thumbnail_only", None, None, "thumbnail-only asset — no object bytes required", source_id, source_version)
    object_id = entry.get("object_id") or entry.get("media_id")
    if not isinstance(object_id, str) or not object_id.strip():
        return AssetIntegrity(key, role, "missing", expected, None, "runtime-managed object_id is required", source_id, source_version)
    digest = _admitted_digest(entry, project_ref=project_ref, runtime_client=runtime_client, media_snapshot=media_snapshot)
    if digest is None:
        return AssetIntegrity(key, role, "unsupported", expected, None, "object is not admitted by the selected project runtime", source_id, source_version)
    return AssetIntegrity(key, role, "verified_original", digest, digest, "runtime-managed object digest is admitted for this project", source_id, source_version)


def _iter_registry_assets(registry: Mapping[str, Any]) -> Iterable[tuple[str, Any]]:
    assets = registry.get("assets", registry) if "assets" in registry else registry
    if isinstance(assets, Mapping):
        yield from ((str(key), value) for key, value in assets.items())
    elif isinstance(assets, list):
        for index, value in enumerate(assets):
            yield str(value.get("asset_key") or value.get("key") or f"asset-{index}") if isinstance(value, Mapping) else f"asset-{index}", value
    else:
        raise ValueError("registry assets must be an object or list")


def classify_registry(registry: Mapping[str, Any], *, project_ref: str, default_role: str = "timeline_media", runtime_client: Any | None = None, media_snapshot: Any | None = None) -> dict[str, AssetIntegrity]:
    return {key: classify_asset(key, entry, project_ref=project_ref, default_role=default_role, runtime_client=runtime_client, media_snapshot=media_snapshot) for key, entry in _iter_registry_assets(registry)}


__all__ = ["AssetIntegrity", "classify_asset", "classify_registry"]
