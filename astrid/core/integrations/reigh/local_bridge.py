"""Pure helpers for the Astrid local read bridge."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.foundation.project_paths import (
    project_dir,
    resolve_projects_root,
    sources_dir,
    validate_project_slug,
)
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.paths import (
    find_timeline_by_event_stream_id,
    find_timeline_by_slug,
    load_assembly_json_with_repair,
    load_display_json_with_repair,
    timeline_dir,
    timelines_dir,
    validate_timeline_slug,
    validate_timeline_ulid,
)
from astrid.core.timeline.projection import regenerate_projection

from .event_construction import asset_registry_to_events, config_to_events

BRIDGE_CONFIG_VERSION = 1
BRIDGE_SOURCES_VERSION = 1
BRIDGE_AUDIO_PROXY_PROFILE_VERSION = "aac-m4a-stereo-48000-128k-v1"
BRIDGE_AUDIO_PROXY_FILENAME = "audio.m4a"
BRIDGE_VIDEO_PROXY_PROFILE_VERSION = "h264-mp4-720p-yuv420p-crf23-veryfast-v1"
BRIDGE_VIDEO_PROXY_FILENAME = "preview-720p.mp4"
_BRIDGE_CANONICAL_TOP_KEYS = ("tracks", "clips", "theme", "theme_overrides")
_AUDIO_PROXY_LOCK = threading.Lock()
_VIDEO_PROXY_LOCK = threading.Lock()
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
    source_id: str | None = None
    source_version: str | None = None


@dataclass(frozen=True)
class BridgeAudioProxyResult:
    source_id: str
    source_version: str | None
    status: str
    profile_version: str
    output: str | None = None
    output_path: Path | None = None
    error: str | None = None


@dataclass(frozen=True)
class BridgeVideoProxyResult:
    source_id: str
    source_version: str | None
    status: str
    profile_version: str
    output: str | None = None
    output_path: Path | None = None
    error: str | None = None


BridgeSubprocessRunner = Callable[[Sequence[str]], Any]


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
    project_payload = _read_project_payload(projects_root / slug / "project.json")

    found_ulid: str | None = None
    if _looks_like_uuid(timeline):
        found = find_timeline_by_event_stream_id(slug, timeline, root=projects_root)
        if found is not None:
            found_ulid = found[0]
        else:
            timelines_root = timelines_dir(slug, root=projects_root)
            if timelines_root.is_dir():
                for timeline_home in sorted(timelines_root.iterdir(), key=lambda item: item.name):
                    if not timeline_home.is_dir():
                        continue
                    if _load_canonical_timeline_id(timeline_home, timeline_home.name) == timeline:
                        found_ulid = timeline_home.name
                        break
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
    fallback_record = _load_bridge_timeline_record(
        slug,
        found_ulid,
        project_payload=project_payload,
        root=projects_root,
    )
    return fallback_record


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

    config = _load_bridge_config(record.timeline_home)
    if not isinstance(config, dict):
        return None

    return _bridge_timeline_payload(
        record,
        config=config,
        registry=load_bridge_registry(project_slug, record.timeline_id, root=root),
    )


def list_bridge_checkpoints(
    project_slug: str,
    timeline: str,
    *,
    root: str | Path | None = None,
    limit: int = 50,
) -> list[dict[str, Any]] | None:
    """Project config-bearing timeline events into Reigh editor checkpoints."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    backend = LocalFsBackend(
        timeline_id=record.timeline_id,
        timeline_home=record.timeline_home,
    )
    events = backend.read_events()
    checkpoints: list[dict[str, Any]] = []
    for version, event in enumerate(events, start=1):
        payload = event.payload.to_json_obj() if hasattr(event.payload, "to_json_obj") else event.payload
        if not isinstance(payload, dict):
            continue
        config = payload.get("config")
        if not isinstance(config, dict):
            continue
        checkpoints.append({
            "id": event.event_id,
            "timelineId": record.timeline_id,
            "config": config,
            "createdAt": event.ts,
            "triggerType": "manual",
            "label": f"v{version} {event.kind}",
            "editsSinceLastCheckpoint": 0,
            "event": event.to_json_obj(),
        })
    return list(reversed(checkpoints))[:max(limit, 0)]


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

    backend = LocalFsBackend(
        timeline_id=record.timeline_id,
        timeline_home=record.timeline_home,
    )
    head = backend.head()
    # The Reigh editor sends a superset config with render-only top-level keys
    # such as "output"; Astrid's canonical TimelineConfig must not persist them.
    canonical_config = {
        key: config[key]
        for key in _BRIDGE_CANONICAL_TOP_KEYS
        if key in config
    }
    batch = config_to_events(
        canonical_config,
        None,
        record.timeline_id,
        head.last_hash,
        head.version + 1,
        REIGH_LOCAL_EDITOR_ACTOR,
        "editor_save",
        expected_version=head.version,
    )
    backend.append_prebuilt_events(
        record.timeline_id,
        [item.event for item in batch.events],
        expected_version=head.version,
    )
    regenerated = regenerate_projection(
        record.timeline_id,
        backend,
        timeline_home=record.timeline_home,
    )
    return _bridge_timeline_payload(
        record,
        config=regenerated,
        registry=load_bridge_registry(project_slug, record.timeline_id, root=root),
        config_version=backend.head().version,
    )


def save_bridge_registry(
    project_slug: str,
    timeline: str,
    registry: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Append one registry replacement event, refresh projections, and persist the sidecar."""
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    backend = LocalFsBackend(
        timeline_id=record.timeline_id,
        timeline_home=record.timeline_home,
    )
    current_config = _load_bridge_config(record.timeline_home)
    head = backend.head()
    batch = asset_registry_to_events(
        registry,
        current_config,
        record.timeline_id,
        head.last_hash,
        head.version + 1,
        REIGH_LOCAL_EDITOR_ACTOR,
        "editor_save",
        expected_version=head.version,
    )
    backend.append_prebuilt_events(
        record.timeline_id,
        [item.event for item in batch.events],
        expected_version=head.version,
    )
    regenerate_projection(
        record.timeline_id,
        backend,
        timeline_home=record.timeline_home,
    )
    write_json_atomic(
        record.timeline_home / "registry.json",
        batch.projected_asset_registry or {"assets": {}},
    )
    return batch.projected_asset_registry or {"assets": {}}


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
    if "assets" not in raw:
        raw = _derive_registry_from_sources(record, root=root)
    raw = _sync_bridge_sources(record, raw, root=root)
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
    if "assets" not in registry:
        registry = _derive_registry_from_sources(record, root=root)
    registry = _sync_bridge_sources(record, registry, root=root)
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
            source_id=_coerce_non_empty_str(entry.get("sourceId")),
            source_version=_coerce_non_empty_str(entry.get("sourceVersion")),
        )

    normalized_local = _normalize_bridge_local_asset_reference(project_slug, file_value, root=root)
    if normalized_local is None:
        return None
    local_path, _normalized_file = normalized_local

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
        source_id=_coerce_non_empty_str(entry.get("sourceId")),
        source_version=_coerce_non_empty_str(entry.get("sourceVersion")),
    )


def get_bridge_audio_proxy_status(
    project_slug: str,
    source_id: str,
    *,
    root: str | Path | None = None,
) -> BridgeAudioProxyResult | None:
    """Return persisted audio proxy status for one project source."""
    source_entry = _load_source_entry(project_slug, source_id, root=root)
    if source_entry is None:
        return None
    return _audio_proxy_result_from_source(project_slug, source_id, source_entry, root=root)


def ensure_bridge_audio_proxy(
    project_slug: str,
    source_id: str,
    *,
    root: str | Path | None = None,
    runner: BridgeSubprocessRunner | None = None,
    background: bool = True,
) -> BridgeAudioProxyResult | None:
    """Ensure the current source version has an AAC ``.m4a`` audio proxy.

    By default the function records a queued state and starts a daemon worker.
    Tests and maintenance scripts can pass ``background=False`` plus an
    injectable runner to perform deterministic synchronous generation.
    """
    source_entry = _load_source_entry(project_slug, source_id, root=root)
    if source_entry is None:
        return None

    current = _audio_proxy_result_from_source(project_slug, source_id, source_entry, root=root)
    if _is_current_audio_proxy_ready(current):
        return current

    projects_root = resolve_bridge_projects_root(root=root)
    source_version = _coerce_non_empty_str(source_entry.get("sourceVersion"))
    if source_version is None:
        updated = _write_audio_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="sourceVersion is missing",
            root=projects_root,
        )
        return _audio_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    file_value = _coerce_non_empty_str(source_entry.get("file"))
    normalized = _normalize_bridge_local_asset_reference(project_slug, file_value or "", root=projects_root)
    if file_value is None or normalized is None:
        updated = _write_audio_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="source file is missing or outside the project sources directory",
            root=projects_root,
        )
        return _audio_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    source_path, normalized_file = normalized
    if not source_path.is_file():
        updated = _write_audio_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="source file does not exist",
            root=projects_root,
        )
        return _audio_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    if not _is_video_backed_source(source_entry, normalized_file):
        updated = _write_audio_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="source is not a video-backed local source",
            root=projects_root,
        )
        return _audio_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    output_path = _audio_proxy_output_path(project_slug, source_id, source_version, root=projects_root)
    if output_path.is_file():
        updated = _write_audio_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="ready",
            output_path=output_path,
            error=None,
            root=projects_root,
        )
        return _audio_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    queued = _write_audio_proxy_metadata(
        project_slug,
        source_id,
        source_entry,
        status="queued",
        output_path=output_path,
        error=None,
        root=projects_root,
    )

    if background:
        worker = threading.Thread(
            target=_generate_bridge_audio_proxy_worker,
            args=(project_slug, source_id, source_version, source_path, output_path),
            kwargs={"root": projects_root, "runner": runner},
            daemon=True,
        )
        worker.start()
        return _audio_proxy_result_from_source(project_slug, source_id, queued, root=projects_root)

    _generate_bridge_audio_proxy_worker(
        project_slug,
        source_id,
        source_version,
        source_path,
        output_path,
        root=projects_root,
        runner=runner,
    )
    return get_bridge_audio_proxy_status(project_slug, source_id, root=projects_root)


def get_bridge_video_proxy_status(
    project_slug: str,
    source_id: str,
    *,
    root: str | Path | None = None,
) -> BridgeVideoProxyResult | None:
    """Return persisted video proxy status for one project source."""
    source_entry = _load_source_entry(project_slug, source_id, root=root)
    if source_entry is None:
        return None
    return _video_proxy_result_from_source(project_slug, source_id, source_entry, root=root)


def ensure_bridge_video_proxy(
    project_slug: str,
    source_id: str,
    *,
    root: str | Path | None = None,
    runner: BridgeSubprocessRunner | None = None,
    background: bool = True,
) -> BridgeVideoProxyResult | None:
    """Ensure the current source version has an H.264 ``.mp4`` video proxy.

    By default the function records a queued state and starts a daemon worker.
    Tests and maintenance scripts can pass ``background=False`` plus an
    injectable runner to perform deterministic synchronous generation.
    """
    source_entry = _load_source_entry(project_slug, source_id, root=root)
    if source_entry is None:
        return None

    current = _video_proxy_result_from_source(project_slug, source_id, source_entry, root=root)
    if _is_current_video_proxy_ready(current):
        return current

    projects_root = resolve_bridge_projects_root(root=root)
    source_version = _coerce_non_empty_str(source_entry.get("sourceVersion"))
    if source_version is None:
        updated = _write_video_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="sourceVersion is missing",
            root=projects_root,
        )
        return _video_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    file_value = _coerce_non_empty_str(source_entry.get("file"))
    normalized = _normalize_bridge_local_asset_reference(project_slug, file_value or "", root=projects_root)
    if file_value is None or normalized is None:
        updated = _write_video_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="source file is missing or outside the project sources directory",
            root=projects_root,
        )
        return _video_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    source_path, normalized_file = normalized
    if not source_path.is_file():
        updated = _write_video_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="source file does not exist",
            root=projects_root,
        )
        return _video_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    if not _is_video_backed_source(source_entry, normalized_file):
        updated = _write_video_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="failed",
            error="source is not a video-backed local source",
            root=projects_root,
        )
        return _video_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    output_path = _video_proxy_output_path(project_slug, source_id, source_version, root=projects_root)
    if (
        current.status in {"queued", "generating"}
        and current.profile_version == BRIDGE_VIDEO_PROXY_PROFILE_VERSION
        and current.output_path is not None
        and current.output_path == output_path
    ):
        return current

    if output_path.is_file():
        updated = _write_video_proxy_metadata(
            project_slug,
            source_id,
            source_entry,
            status="ready",
            output_path=output_path,
            error=None,
            root=projects_root,
        )
        return _video_proxy_result_from_source(project_slug, source_id, updated, root=projects_root)

    queued = _write_video_proxy_metadata(
        project_slug,
        source_id,
        source_entry,
        status="queued",
        output_path=output_path,
        error=None,
        root=projects_root,
    )

    if background:
        worker = threading.Thread(
            target=_generate_bridge_video_proxy_worker,
            args=(project_slug, source_id, source_version, source_path, output_path),
            kwargs={"root": projects_root, "runner": runner},
            daemon=True,
        )
        worker.start()
        return _video_proxy_result_from_source(project_slug, source_id, queued, root=projects_root)

    _generate_bridge_video_proxy_worker(
        project_slug,
        source_id,
        source_version,
        source_path,
        output_path,
        root=projects_root,
        runner=runner,
    )
    return get_bridge_video_proxy_status(project_slug, source_id, root=projects_root)


def _video_proxy_result_from_source(
    project_slug: str,
    source_id: str,
    source_entry: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> BridgeVideoProxyResult:
    source_version = _coerce_non_empty_str(source_entry.get("sourceVersion"))
    video_proxy = source_entry.get("videoProxy")
    proxy_meta = video_proxy if isinstance(video_proxy, dict) else {}
    status = _coerce_non_empty_str(proxy_meta.get("status")) or "missing"
    profile_version = _coerce_non_empty_str(proxy_meta.get("profileVersion")) or BRIDGE_VIDEO_PROXY_PROFILE_VERSION
    output = _coerce_non_empty_str(proxy_meta.get("output"))
    output_path = _resolve_video_proxy_output(project_slug, output, root=root) if output else None
    return BridgeVideoProxyResult(
        source_id=source_id,
        source_version=source_version,
        status=status,
        profile_version=profile_version,
        output=output,
        output_path=output_path,
        error=_coerce_non_empty_str(proxy_meta.get("error")),
    )


def _proxy_output_matches_source_version(output_path: Path | None, source_version: str | None) -> bool:
    if output_path is None or source_version is None:
        return False
    return output_path.parent.name == source_version


def _is_current_audio_proxy_ready(result: BridgeAudioProxyResult) -> bool:
    return (
        result.status == "ready"
        and result.output_path is not None
        and result.output_path.is_file()
        and _proxy_output_matches_source_version(result.output_path, result.source_version)
    )


def _is_current_video_proxy_ready(result: BridgeVideoProxyResult) -> bool:
    return (
        result.status == "ready"
        and result.output_path is not None
        and result.output_path.is_file()
        and _proxy_output_matches_source_version(result.output_path, result.source_version)
    )


def _write_video_proxy_metadata(
    project_slug: str,
    source_id: str,
    source_entry: dict[str, Any],
    *,
    status: str,
    root: str | Path | None = None,
    output_path: Path | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    projects_root = resolve_bridge_projects_root(root=root)
    with _VIDEO_PROXY_LOCK:
        payload = load_bridge_sources(project_slug, root=projects_root)
        sources = payload.get("sources")
        next_sources = dict(sources) if isinstance(sources, dict) else {}
        current_entry = next_sources.get(source_id)
        next_entry = dict(current_entry) if isinstance(current_entry, dict) else dict(source_entry)
        prior_proxy = next_entry.get("videoProxy")
        proxy_meta = dict(prior_proxy) if isinstance(prior_proxy, dict) else {}

        now = _utc_now_iso()
        if "createdAt" not in proxy_meta:
            proxy_meta["createdAt"] = now
        proxy_meta["updatedAt"] = now
        proxy_meta["status"] = status
        proxy_meta["profileVersion"] = BRIDGE_VIDEO_PROXY_PROFILE_VERSION
        if output_path is not None:
            proxy_meta["output"] = _project_relative_video_proxy_output(project_slug, output_path, root=projects_root)
        if error:
            proxy_meta["error"] = error
        else:
            proxy_meta.pop("error", None)

        next_entry["videoProxy"] = proxy_meta
        next_sources[source_id] = next_entry
        save_bridge_sources(project_slug, {"sources": next_sources}, root=projects_root)
        return next_entry


def _public_video_proxy_metadata(video_proxy: dict[str, Any]) -> dict[str, Any]:
    public = {
        "status": video_proxy.get("status", "missing"),
        "profileVersion": video_proxy.get("profileVersion", BRIDGE_VIDEO_PROXY_PROFILE_VERSION),
        "output": video_proxy.get("output"),
        "updatedAt": video_proxy.get("updatedAt"),
    }
    if video_proxy.get("error") is not None:
        public["error"] = video_proxy.get("error")
    if video_proxy.get("createdAt") is not None:
        public["createdAt"] = video_proxy.get("createdAt")
    return public


def _generate_bridge_video_proxy_worker(
    project_slug: str,
    source_id: str,
    source_version: str,
    source_path: Path,
    output_path: Path,
    *,
    root: str | Path | None = None,
    runner: BridgeSubprocessRunner | None = None,
) -> None:
    projects_root = resolve_bridge_projects_root(root=root)
    source_entry = _load_source_entry(project_slug, source_id, root=projects_root)
    if source_entry is None:
        return

    if _coerce_non_empty_str(source_entry.get("sourceVersion")) != source_version:
        return

    _write_video_proxy_metadata(
        project_slug,
        source_id,
        source_entry,
        status="generating",
        output_path=output_path,
        error=None,
        root=projects_root,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(f".{output_path.stem}.tmp{output_path.suffix}")
    if temp_output.exists():
        temp_output.unlink()
    command = _build_ffmpeg_video_proxy_command(source_path, temp_output)

    try:
        _run_video_proxy_command(command, runner=runner)
        if temp_output.is_file():
            temp_output.replace(output_path)
        elif not output_path.is_file():
            raise FileNotFoundError(f"ffmpeg did not create {temp_output}")
    except Exception as exc:
        if temp_output.exists():
            temp_output.unlink()
        latest_entry = _load_source_entry(project_slug, source_id, root=projects_root) or source_entry
        _write_video_proxy_metadata(
            project_slug,
            source_id,
            latest_entry,
            status="failed",
            output_path=output_path,
            error=str(exc),
            root=projects_root,
        )
        return

    latest_entry = _load_source_entry(project_slug, source_id, root=projects_root) or source_entry
    _write_video_proxy_metadata(
        project_slug,
        source_id,
        latest_entry,
        status="ready",
        output_path=output_path,
        error=None,
        root=projects_root,
    )


def _build_ffmpeg_video_proxy_command(source_path: Path, output_path: Path) -> list[str]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    return [
        ffmpeg,
        "-y",
        "-i",
        str(source_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
        "-crf",
        "23",
        "-preset",
        "veryfast",
        "-an",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _run_video_proxy_command(command: Sequence[str], *, runner: BridgeSubprocessRunner | None) -> None:
    if runner is not None:
        runner(command)
        return
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _video_proxy_output_path(
    project_slug: str,
    source_id: str,
    source_version: str,
    *,
    root: str | Path | None = None,
) -> Path:
    return (
        project_dir(project_slug, root=resolve_bridge_projects_root(root=root))
        / "proxies"
        / source_id
        / source_version
        / BRIDGE_VIDEO_PROXY_FILENAME
    )


def _project_relative_video_proxy_output(
    project_slug: str,
    output_path: Path,
    *,
    root: str | Path | None = None,
) -> str:
    project_root = project_dir(project_slug, root=resolve_bridge_projects_root(root=root)).resolve()
    return output_path.resolve().relative_to(project_root).as_posix()


def _resolve_video_proxy_output(
    project_slug: str,
    output: str,
    *,
    root: str | Path | None = None,
) -> Path | None:
    project_root = project_dir(project_slug, root=resolve_bridge_projects_root(root=root)).resolve()
    candidate = (project_root / output).resolve()
    proxies_root = (project_root / "proxies").resolve()
    if not _is_path_within_root(candidate, proxies_root):
        return None
    return candidate


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


def _read_sources_payload(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_bridge_sources(
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the project-level ``sources.json`` payload for *project_slug*.

    The returned dict always contains ``version`` (int) and ``sources``
    (dict of ``sourceId`` → source entry).
    """
    projects_root = resolve_bridge_projects_root(root=root)
    slug = validate_project_slug(project_slug)
    sources_path = project_dir(slug, root=projects_root) / "sources.json"
    payload = _read_sources_payload(sources_path)
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        return {"version": BRIDGE_SOURCES_VERSION, "sources": {}}
    return {
        "version": payload.get("version", BRIDGE_SOURCES_VERSION),
        "sources": dict(sorted(sources.items())),
    }


def save_bridge_sources(
    project_slug: str,
    sources: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Atomically persist a sources payload for *project_slug*.

    *sources* must be a dict with an optional ``"sources"`` key containing
    the per-source entries.  The payload is validated, normalized, and
    written via :func:`write_json_atomic`.
    """
    projects_root = resolve_bridge_projects_root(root=root)
    slug = validate_project_slug(project_slug)
    project_dir_path = project_dir(slug, root=projects_root)
    project_dir_path.mkdir(parents=True, exist_ok=True)

    sources_data = sources.get("sources")
    normalized_sources = dict(sources_data) if isinstance(sources_data, dict) else {}

    validated: dict[str, dict[str, Any]] = {}
    for source_id, entry in sorted(normalized_sources.items()):
        if not isinstance(source_id, str) or not isinstance(entry, dict):
            continue
        validated[source_id] = dict(entry)

    payload: dict[str, Any] = {
        "version": BRIDGE_SOURCES_VERSION,
        "sources": dict(sorted(validated.items())),
    }

    write_json_atomic(project_dir_path / "sources.json", payload)
    return payload


def _build_source_summary(source_entry: dict[str, Any], source_id: str) -> dict[str, Any]:
    """Produce a compact API-facing summary for a single source entry."""
    asset_ids = source_entry.get("assetIds")
    asset_count = len(asset_ids) if isinstance(asset_ids, dict) else 0
    summary = {
        "sourceId": source_id,
        "sourceVersion": source_entry.get("sourceVersion"),
        "origin": source_entry.get("origin", "local"),
        "file": source_entry.get("file"),
        "assetCount": asset_count,
        "sizeBytes": source_entry.get("sizeBytes"),
    }
    audio_proxy = source_entry.get("audioProxy")
    if isinstance(audio_proxy, dict):
        summary["audioProxy"] = _public_audio_proxy_metadata(audio_proxy)
    video_proxy = source_entry.get("videoProxy")
    if isinstance(video_proxy, dict):
        summary["videoProxy"] = _public_video_proxy_metadata(video_proxy)
    return summary


def _load_source_entry(
    project_slug: str,
    source_id: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    payload = load_bridge_sources(project_slug, root=root)
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        return None
    entry = sources.get(source_id)
    return dict(entry) if isinstance(entry, dict) else None


def _audio_proxy_result_from_source(
    project_slug: str,
    source_id: str,
    source_entry: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> BridgeAudioProxyResult:
    source_version = _coerce_non_empty_str(source_entry.get("sourceVersion"))
    audio_proxy = source_entry.get("audioProxy")
    proxy_meta = audio_proxy if isinstance(audio_proxy, dict) else {}
    status = _coerce_non_empty_str(proxy_meta.get("status")) or "missing"
    profile_version = _coerce_non_empty_str(proxy_meta.get("profileVersion")) or BRIDGE_AUDIO_PROXY_PROFILE_VERSION
    output = _coerce_non_empty_str(proxy_meta.get("output"))
    output_path = _resolve_audio_proxy_output(project_slug, output, root=root) if output else None
    return BridgeAudioProxyResult(
        source_id=source_id,
        source_version=source_version,
        status=status,
        profile_version=profile_version,
        output=output,
        output_path=output_path,
        error=_coerce_non_empty_str(proxy_meta.get("error")),
    )


def _write_audio_proxy_metadata(
    project_slug: str,
    source_id: str,
    source_entry: dict[str, Any],
    *,
    status: str,
    root: str | Path | None = None,
    output_path: Path | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    projects_root = resolve_bridge_projects_root(root=root)
    with _AUDIO_PROXY_LOCK:
        payload = load_bridge_sources(project_slug, root=projects_root)
        sources = payload.get("sources")
        next_sources = dict(sources) if isinstance(sources, dict) else {}
        current_entry = next_sources.get(source_id)
        next_entry = dict(current_entry) if isinstance(current_entry, dict) else dict(source_entry)
        prior_proxy = next_entry.get("audioProxy")
        proxy_meta = dict(prior_proxy) if isinstance(prior_proxy, dict) else {}

        now = _utc_now_iso()
        if "createdAt" not in proxy_meta:
            proxy_meta["createdAt"] = now
        proxy_meta["updatedAt"] = now
        proxy_meta["status"] = status
        proxy_meta["profileVersion"] = BRIDGE_AUDIO_PROXY_PROFILE_VERSION
        if output_path is not None:
            proxy_meta["output"] = _project_relative_audio_proxy_output(project_slug, output_path, root=projects_root)
        if error:
            proxy_meta["error"] = error
        else:
            proxy_meta.pop("error", None)

        next_entry["audioProxy"] = proxy_meta
        next_sources[source_id] = next_entry
        save_bridge_sources(project_slug, {"sources": next_sources}, root=projects_root)
        return next_entry


def _public_audio_proxy_metadata(audio_proxy: dict[str, Any]) -> dict[str, Any]:
    public = {
        "status": audio_proxy.get("status", "missing"),
        "profileVersion": audio_proxy.get("profileVersion", BRIDGE_AUDIO_PROXY_PROFILE_VERSION),
        "output": audio_proxy.get("output"),
        "updatedAt": audio_proxy.get("updatedAt"),
    }
    if audio_proxy.get("error") is not None:
        public["error"] = audio_proxy.get("error")
    if audio_proxy.get("createdAt") is not None:
        public["createdAt"] = audio_proxy.get("createdAt")
    return public


def _generate_bridge_audio_proxy_worker(
    project_slug: str,
    source_id: str,
    source_version: str,
    source_path: Path,
    output_path: Path,
    *,
    root: str | Path | None = None,
    runner: BridgeSubprocessRunner | None = None,
) -> None:
    projects_root = resolve_bridge_projects_root(root=root)
    source_entry = _load_source_entry(project_slug, source_id, root=projects_root)
    if source_entry is None:
        return

    if _coerce_non_empty_str(source_entry.get("sourceVersion")) != source_version:
        return

    _write_audio_proxy_metadata(
        project_slug,
        source_id,
        source_entry,
        status="generating",
        output_path=output_path,
        error=None,
        root=projects_root,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(f".{output_path.stem}.tmp{output_path.suffix}")
    if temp_output.exists():
        temp_output.unlink()
    command = _build_ffmpeg_audio_proxy_command(source_path, temp_output)

    try:
        _run_audio_proxy_command(command, runner=runner)
        if temp_output.is_file():
            temp_output.replace(output_path)
        elif not output_path.is_file():
            raise FileNotFoundError(f"ffmpeg did not create {temp_output}")
    except Exception as exc:
        if temp_output.exists():
            temp_output.unlink()
        latest_entry = _load_source_entry(project_slug, source_id, root=projects_root) or source_entry
        _write_audio_proxy_metadata(
            project_slug,
            source_id,
            latest_entry,
            status="failed",
            output_path=output_path,
            error=str(exc),
            root=projects_root,
        )
        return

    latest_entry = _load_source_entry(project_slug, source_id, root=projects_root) or source_entry
    _write_audio_proxy_metadata(
        project_slug,
        source_id,
        latest_entry,
        status="ready",
        output_path=output_path,
        error=None,
        root=projects_root,
    )


def _build_ffmpeg_audio_proxy_command(source_path: Path, output_path: Path) -> list[str]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    return [
        ffmpeg,
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _run_audio_proxy_command(command: Sequence[str], *, runner: BridgeSubprocessRunner | None) -> None:
    if runner is not None:
        runner(command)
        return
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _audio_proxy_output_path(
    project_slug: str,
    source_id: str,
    source_version: str,
    *,
    root: str | Path | None = None,
) -> Path:
    return (
        project_dir(project_slug, root=resolve_bridge_projects_root(root=root))
        / "proxies"
        / source_id
        / source_version
        / BRIDGE_AUDIO_PROXY_FILENAME
    )


def _project_relative_audio_proxy_output(
    project_slug: str,
    output_path: Path,
    *,
    root: str | Path | None = None,
) -> str:
    project_root = project_dir(project_slug, root=resolve_bridge_projects_root(root=root)).resolve()
    return output_path.resolve().relative_to(project_root).as_posix()


def _resolve_audio_proxy_output(
    project_slug: str,
    output: str,
    *,
    root: str | Path | None = None,
) -> Path | None:
    project_root = project_dir(project_slug, root=resolve_bridge_projects_root(root=root)).resolve()
    candidate = (project_root / output).resolve()
    proxies_root = (project_root / "proxies").resolve()
    if not _is_path_within_root(candidate, proxies_root):
        return None
    return candidate


def _is_video_backed_source(source_entry: dict[str, Any], normalized_file: str) -> bool:
    media_type = _coerce_non_empty_str(source_entry.get("type"))
    if media_type is None:
        media_type, _encoding = mimetypes.guess_type(normalized_file)
    if media_type and media_type.startswith("video/"):
        return True
    return Path(normalized_file).suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_bridge_config(timeline_home: Path) -> dict[str, Any] | None:
    config = load_assembly_json_with_repair(timeline_home)
    if isinstance(config, dict):
        return config

    assembly_file = timeline_home / "assembly.json"
    try:
        payload = read_json(assembly_file)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _derive_registry_from_sources(
    record: BridgeTimelineRecord,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    config = _load_bridge_config(record.timeline_home)
    if not isinstance(config, dict):
        return {"assets": {}}

    asset_keys = sorted({
        clip.get("asset")
        for clip in config.get("clips", [])
        if isinstance(clip, dict)
        and clip.get("clipType") == "media"
        and isinstance(clip.get("asset"), str)
        and clip.get("asset")
    })
    if not asset_keys:
        return {"assets": {}}

    sources_root = sources_dir(record.project_slug, root=resolve_bridge_projects_root(root=root))
    source_files = sorted(path for path in sources_root.iterdir() if path.is_file()) if sources_root.is_dir() else []
    if not source_files:
        return {"assets": {}}

    assets: dict[str, dict[str, Any]] = {}
    if len(source_files) == 1:
        for asset_key in asset_keys:
            assets[asset_key] = _derived_registry_entry(source_files[0])
        return {"assets": assets}

    source_by_stem = {path.stem: path for path in source_files}
    source_by_name = {path.name: path for path in source_files}
    for asset_key in asset_keys:
        matched = source_by_name.get(asset_key) or source_by_stem.get(asset_key)
        if matched is not None:
            assets[asset_key] = _derived_registry_entry(matched)
    return {"assets": assets}


def _derived_registry_entry(source_file: Path) -> dict[str, Any]:
    mime_type, _encoding = mimetypes.guess_type(source_file.name)
    entry: dict[str, Any] = {"file": source_file.name}
    if mime_type:
        entry["type"] = mime_type
    return entry


def _sync_bridge_sources(
    record: BridgeTimelineRecord,
    registry: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    assets = registry.get("assets")
    if not isinstance(assets, dict):
        return {"assets": {}}

    projects_root = resolve_bridge_projects_root(root=root)
    sources_payload = _read_sources_payload(project_dir(record.project_slug, root=projects_root) / "sources.json")
    existing_sources = sources_payload.get("sources")
    normalized_sources = dict(existing_sources) if isinstance(existing_sources, dict) else {}

    synced_assets: dict[str, dict[str, Any]] = {}
    touched_source_ids: set[str] = set()
    source_asset_ids: dict[str, set[str]] = {}

    for asset_key, entry in sorted(assets.items()):
        if not isinstance(asset_key, str) or not isinstance(entry, dict):
            continue

        next_entry = dict(entry)
        file_value = next_entry.get("file")
        if not isinstance(file_value, str) or not file_value.strip():
            synced_assets[asset_key] = next_entry
            continue

        file_value = file_value.strip()
        if _is_http_url(file_value):
            synced_assets[asset_key] = next_entry
            continue

        normalized_local = _normalize_bridge_local_asset_reference(record.project_slug, file_value, root=projects_root)
        if normalized_local is None:
            synced_assets[asset_key] = next_entry
            continue

        local_path, normalized_file = normalized_local
        stat = _safe_stat(local_path)
        source_id = _derive_local_source_id(normalized_file)
        source_version = _derive_local_source_version(
            normalized_file,
            size_bytes=stat.st_size if stat is not None else None,
            mtime_ns=stat.st_mtime_ns if stat is not None else None,
            content_sha256=_coerce_non_empty_str(next_entry.get("content_sha256")),
            audio_proxy_profile_version=BRIDGE_AUDIO_PROXY_PROFILE_VERSION,
            video_proxy_profile_version=BRIDGE_VIDEO_PROXY_PROFILE_VERSION,
        )
        next_entry["file"] = normalized_file
        next_entry["sourceId"] = source_id
        next_entry["sourceVersion"] = source_version
        synced_assets[asset_key] = next_entry
        touched_source_ids.add(source_id)
        source_asset_ids.setdefault(source_id, set()).add(asset_key)

        merged_source = _merge_synced_source_entry(
            normalized_sources.get(source_id),
            source_id=source_id,
            source_version=source_version,
            normalized_file=normalized_file,
            asset_key=asset_key,
            size_bytes=stat.st_size if stat is not None else None,
            mtime_ns=stat.st_mtime_ns if stat is not None else None,
            content_sha256=_coerce_non_empty_str(next_entry.get("content_sha256")),
        )
        normalized_sources[source_id] = merged_source

    next_sources: dict[str, dict[str, Any]] = {}
    for source_id, source_entry in sorted(normalized_sources.items()):
        if not isinstance(source_entry, dict):
            continue
        active_asset_ids = source_asset_ids.get(source_id)
        is_local_source = source_id.startswith("local:") or source_entry.get("origin") == "local"
        if not active_asset_ids:
            if is_local_source or source_id in touched_source_ids:
                continue
            next_sources[source_id] = dict(source_entry)
            continue

        next_sources[source_id] = {
            **source_entry,
            "assetIds": {
                asset_key: True
                for asset_key in sorted(active_asset_ids)
                if asset_key in synced_assets
            },
        }

    write_json_atomic(
        project_dir(record.project_slug, root=projects_root) / "sources.json",
        {
            "version": BRIDGE_SOURCES_VERSION,
            "sources": next_sources,
        },
    )
    return {"assets": synced_assets}


def _merge_synced_source_entry(
    existing: Any,
    *,
    source_id: str,
    source_version: str,
    normalized_file: str,
    asset_key: str,
    size_bytes: int | None,
    mtime_ns: int | None,
    content_sha256: str | None,
) -> dict[str, Any]:
    base = dict(existing) if isinstance(existing, dict) else {}
    asset_ids = base.get("assetIds")
    next_asset_ids = dict(asset_ids) if isinstance(asset_ids, dict) else {}
    next_asset_ids[asset_key] = True

    merged = {
        **base,
        "sourceId": source_id,
        "sourceVersion": source_version,
        "origin": "local",
        "file": normalized_file,
        "assetIds": {
            key: next_asset_ids[key]
            for key in sorted(next_asset_ids)
        },
        "audioProxyProfileVersion": BRIDGE_AUDIO_PROXY_PROFILE_VERSION,
        "videoProxyProfileVersion": BRIDGE_VIDEO_PROXY_PROFILE_VERSION,
    }
    if size_bytes is not None:
        merged["sizeBytes"] = size_bytes
    if mtime_ns is not None:
        merged["mtimeNs"] = mtime_ns
    if content_sha256:
        merged["content_sha256"] = content_sha256
    else:
        merged.pop("content_sha256", None)
    return merged


def _load_bridge_timeline_record(
    project_slug: str,
    timeline_ulid: str,
    *,
    project_payload: dict[str, Any],
    root: str | Path | None = None,
) -> BridgeTimelineRecord | None:
    timeline_home = timeline_dir(project_slug, timeline_ulid, root=root)
    raw_display = _read_display_payload(timeline_home / "display.json")
    timeline_slug = raw_display.get("slug")
    timeline_name = raw_display.get("name")
    if not isinstance(timeline_slug, str) or not isinstance(timeline_name, str):
        return None
    timeline_id = _load_canonical_timeline_id(timeline_home, timeline_ulid)
    default_timeline_id = project_payload.get("default_timeline_id")
    return BridgeTimelineRecord(
        project_slug=project_slug,
        timeline_ulid=timeline_ulid,
        timeline_id=timeline_id,
        slug=timeline_slug,
        name=timeline_name,
        is_default=(default_timeline_id == timeline_ulid or default_timeline_id == timeline_id),
        timeline_home=timeline_home,
    )


def _read_display_payload(path: Path) -> dict[str, Any]:
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
    normalized = _normalize_bridge_local_asset_reference(project_slug, file_value, root=root)
    if normalized is None:
        return None
    return normalized[0]


def _normalize_bridge_local_asset_reference(
    project_slug: str,
    file_value: str,
    *,
    root: str | Path | None = None,
) -> tuple[Path, str] | None:
    projects_root = resolve_bridge_projects_root(root=root)
    sources_root = sources_dir(project_slug, root=projects_root).resolve()

    candidate = Path(file_value.strip()).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (sources_root / candidate).resolve()
    if not _is_path_within_root(resolved, sources_root):
        return None
    normalized_file = resolved.relative_to(sources_root).as_posix()
    return resolved, normalized_file


def _derive_local_source_id(normalized_file: str) -> str:
    return f"local:{hashlib.sha256(normalized_file.encode('utf-8')).hexdigest()}"


def _derive_local_source_version(
    normalized_file: str,
    *,
    size_bytes: int | None,
    mtime_ns: int | None,
    content_sha256: str | None,
    audio_proxy_profile_version: str,
    video_proxy_profile_version: str | None = None,
) -> str:
    fingerprint = "|".join((
        normalized_file,
        str(size_bytes if size_bytes is not None else ""),
        str(mtime_ns if mtime_ns is not None else ""),
        content_sha256 or "",
        audio_proxy_profile_version,
        video_proxy_profile_version or "",
    ))
    return f"local-v1:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()}"


def _safe_stat(path: Path) -> Any | None:
    try:
        return path.stat()
    except OSError:
        return None


def _coerce_non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None


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
