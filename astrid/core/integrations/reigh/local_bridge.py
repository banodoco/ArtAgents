"""Pure helpers for the Astrid local read bridge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json
from astrid.core.foundation.project_paths import (
    project_dir,
    resolve_projects_root,
    sources_dir,
    validate_project_slug,
)
from astrid.core.timeline.paths import (
    find_timeline_by_event_stream_id,
    find_timeline_by_slug,
    load_display_json_with_repair,
    load_assembly_json_with_repair,
    timeline_dir,
    timelines_dir,
    validate_timeline_slug,
    validate_timeline_ulid,
)
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.events.schema.payloads.config import TimelineConfigReplacedPayload
from astrid.core.timeline.projection import regenerate_projection

BRIDGE_CONFIG_VERSION = 1
REIGH_LOCAL_EDITOR_ACTOR = TimelineActor(
    type="human",
    id="reigh-app:local-editor",
    display="Reigh local editor",
)


@dataclass(frozen=True)
class BridgeTimelineRecord:
    project_slug: str
    timeline_ulid: str
    timeline_id: str
    slug: str
    name: str
    is_default: bool
    timeline_home: Path


@dataclass(frozen=True)
class BridgeResolvedAsset:
    asset_key: str
    entry: dict[str, Any]
    source_kind: str
    local_path: Path | None = None
    url: str | None = None
    size_bytes: int | None = None


def resolve_bridge_projects_root(root: str | Path | None = None) -> Path:
    """Resolve the bridge projects root using Astrid's standard precedence."""
    return resolve_projects_root(root=root)


def list_bridge_project_dirs(root: str | Path | None = None) -> list[Path]:
    """Return sorted project directories that contain a readable ``project.json``."""
    projects_root = resolve_bridge_projects_root(root=root)
    if not projects_root.is_dir():
        return []

    result: list[Path] = []
    for child in sorted(projects_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or not (child / "project.json").is_file():
            continue
        try:
            payload = read_json(child / "project.json")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        result.append(child)
    return result


def list_bridge_projects(root: str | Path | None = None) -> list[dict[str, str]]:
    """Return sorted bridge-visible project metadata."""
    projects_root = resolve_bridge_projects_root(root=root)
    rows: list[dict[str, str]] = []
    for project_dir in list_bridge_project_dirs(projects_root):
        payload = read_json(project_dir / "project.json")
        rows.append({
            "slug": str(payload.get("slug") or project_dir.name),
            "name": str(payload.get("name") or payload.get("slug") or project_dir.name),
        })
    return rows


def list_bridge_timelines(
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> list[BridgeTimelineRecord]:
    """Return bridge timeline rows sorted by ULID."""
    projects_root = resolve_bridge_projects_root(root=root)
    slug = validate_project_slug(project_slug)
    project_payload = _read_project_payload(projects_root / slug / "project.json")
    default_timeline_id = project_payload.get("default_timeline_id")
    timelines_root = timelines_dir(slug, root=projects_root)
    rows: list[BridgeTimelineRecord] = []
    if not timelines_root.is_dir():
        return rows

    for timeline_home in sorted(timelines_root.iterdir(), key=lambda item: item.name):
        if not timeline_home.is_dir():
            continue
        raw_display = load_display_json_with_repair(timeline_home)
        if not isinstance(raw_display, dict):
            continue
        timeline_slug = raw_display.get("slug")
        timeline_name = raw_display.get("name")
        if not isinstance(timeline_slug, str) or not isinstance(timeline_name, str):
            continue
        ulid = timeline_home.name
        rows.append(
            BridgeTimelineRecord(
                project_slug=slug,
                timeline_ulid=ulid,
                timeline_id=_load_canonical_timeline_id(timeline_home, ulid),
                slug=timeline_slug,
                name=timeline_name,
                is_default=(default_timeline_id == ulid),
                timeline_home=timeline_home,
            )
        )
    return rows


def find_bridge_timeline(
    project_slug: str,
    timeline: str,
    *,
    root: str | Path | None = None,
) -> BridgeTimelineRecord | None:
    """Resolve a timeline by slug, ULID, or canonical UUID."""
    projects_root = resolve_bridge_projects_root(root=root)
    slug = validate_project_slug(project_slug)

    found_ulid: str | None = None
    if _looks_like_uuid(timeline):
        found = find_timeline_by_event_stream_id(slug, timeline, root=projects_root)
        if found is not None:
            found_ulid = found[0]
    else:
        try:
            found_ulid = validate_timeline_ulid(timeline)
            if not timeline_dir(slug, found_ulid, root=projects_root).is_dir():
                found_ulid = None
        except Exception:
            found_ulid = None

        if found_ulid is None:
            try:
                validate_timeline_slug(timeline)
            except Exception:
                return None
            found = find_timeline_by_slug(slug, timeline, root=projects_root)
            if found is not None:
                found_ulid = found[0]

    if found_ulid is None:
        return None

    for row in list_bridge_timelines(slug, root=projects_root):
        if row.timeline_ulid == found_ulid:
            return row
    return None


def load_bridge_timeline(
    project_slug: str,
    timeline: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Load repaired timeline config plus bridge identity metadata."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    config = load_assembly_json_with_repair(record.timeline_home)
    if not isinstance(config, dict):
        return None

    return _bridge_timeline_payload(
        record,
        config=config,
        registry=load_bridge_registry(project_slug, record.timeline_ulid, root=root),
    )


def save_bridge_timeline(
    project_slug: str,
    timeline: str,
    config: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Append one editor-save config replacement event and reload bridge payload."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    payload = TimelineConfigReplacedPayload(config=config, source="editor_save")
    backend = LocalFsBackend(
        timeline_id=record.timeline_id,
        timeline_home=record.timeline_home,
    )
    backend.append_event(
        record.timeline_id,
        "timeline.config_replaced",
        payload.to_json_obj(),
        actor=REIGH_LOCAL_EDITOR_ACTOR,
    )
    regenerated = regenerate_projection(
        record.timeline_id,
        backend,
        timeline_home=record.timeline_home,
    )
    return _bridge_timeline_payload(
        record,
        config=regenerated,
        registry=load_bridge_registry(project_slug, record.timeline_ulid, root=root),
        config_version=backend.head().version,
    )


def _bridge_timeline_payload(
    record: BridgeTimelineRecord,
    *,
    config: dict[str, Any],
    registry: dict[str, Any],
    config_version: int | None = None,
) -> dict[str, Any]:
    backend = LocalFsBackend(
        timeline_id=record.timeline_id,
        timeline_home=record.timeline_home,
    )
    version = backend.head().version if config_version is None else config_version
    return {
        "timeline_id": record.timeline_id,
        "timeline_ulid": record.timeline_ulid,
        "slug": record.slug,
        "name": record.name,
        "is_default": record.is_default,
        "config": config,
        "registry": registry,
        "config_version": version,
    }


def bridge_registry_path(
    project_slug: str,
    timeline: str,
    *,
    root: str | Path | None = None,
) -> Path | None:
    """Return the per-timeline registry sidecar path when the timeline exists."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None
    return record.timeline_home / "registry.json"


def load_bridge_registry(
    project_slug: str,
    timeline: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return a normalized registry payload for bridge-visible assets only."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return {"assets": {}}

    registry_path = record.timeline_home / "registry.json"
    raw = _read_registry_payload(registry_path)
    assets = raw.get("assets")
    if not isinstance(assets, dict):
        return {"assets": {}}

    normalized_assets: dict[str, dict[str, Any]] = {}
    for asset_key, entry in sorted(assets.items()):
        if not isinstance(asset_key, str) or not isinstance(entry, dict):
            continue
        if resolve_bridge_asset(project_slug, timeline, asset_key, root=root) is None:
            continue
        normalized_assets[asset_key] = dict(entry)
    return {"assets": normalized_assets}


def resolve_bridge_asset(
    project_slug: str,
    timeline: str,
    asset_key: str,
    *,
    root: str | Path | None = None,
) -> BridgeResolvedAsset | None:
    """Resolve one registry asset without reading the media bytes into memory."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    registry = _read_registry_payload(record.timeline_home / "registry.json")
    assets = registry.get("assets")
    if not isinstance(assets, dict):
        return None

    entry = assets.get(asset_key)
    if not isinstance(entry, dict):
        return None

    file_value = entry.get("file")
    if not isinstance(file_value, str) or not file_value.strip():
        return None

    file_value = file_value.strip()
    if _is_http_url(file_value):
        return BridgeResolvedAsset(
            asset_key=asset_key,
            entry=dict(entry),
            source_kind="http",
            url=file_value,
        )

    local_path = _resolve_bridge_local_asset_path(project_slug, file_value, root=root)
    if local_path is None:
        return None

    try:
        size_bytes = local_path.stat().st_size if local_path.exists() else None
    except OSError:
        size_bytes = None

    return BridgeResolvedAsset(
        asset_key=asset_key,
        entry=dict(entry),
        source_kind="local",
        local_path=local_path,
        size_bytes=size_bytes,
    )


def _load_canonical_timeline_id(timeline_home: Path, timeline_ulid: str) -> str:
    identity_path = timeline_home / "assembly.identity.json"
    if not identity_path.is_file():
        return timeline_ulid

    try:
        identity = read_json(identity_path)
    except Exception:
        return timeline_ulid

    if isinstance(identity, dict):
        timeline_id = identity.get("timeline_id")
        if isinstance(timeline_id, str) and timeline_id:
            return timeline_id
    return timeline_ulid


def _read_project_payload(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_registry_payload(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_bridge_local_asset_path(
    project_slug: str,
    file_value: str,
    *,
    root: str | Path | None = None,
) -> Path | None:
    projects_root = resolve_bridge_projects_root(root=root)
    sources_root = sources_dir(project_slug, root=projects_root).resolve()

    candidate = Path(file_value).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (sources_root / candidate).resolve()
    return resolved if _is_path_within_root(resolved, sources_root) else None


def _is_path_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    if len(parts) != 5:
        return False
    expected_lengths = (8, 4, 4, 4, 12)
    return all(len(part) == expected and all(ch in "0123456789abcdefABCDEF" for ch in part) for part, expected in zip(parts, expected_lengths))
