"""Pure helpers for the Astrid local read bridge."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import threading
from dataclasses import dataclass
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

from .event_construction import (
    config_to_events,
    construct_reigh_timeline_events,
)

BRIDGE_CONFIG_VERSION = 1

# Per-timeline save locks. The bridge server is threaded: a save must be
# atomic across head-read → CAS append → projection → registry.json sidecar,
# otherwise a concurrent append can land between steps and the response pairs
# a newer version with an older registry (or an older sidecar overwrites a
# newer one).  Locks are keyed by the CANONICAL timeline home path so saves
# of the same timeline through different aliases (slug / ULID / canonical
# UUID) serialize on ONE lock.
_SAVE_LOCKS: dict[str, threading.Lock] = {}
_SAVE_LOCKS_GUARD = threading.Lock()


def _bridge_save_lock(timeline_home: str | Path) -> threading.Lock:
    """Return the per-timeline lock serializing bridge save/registry writes."""
    key = os.path.abspath(os.fspath(timeline_home))
    with _SAVE_LOCKS_GUARD:
        lock = _SAVE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SAVE_LOCKS[key] = lock
        return lock

BRIDGE_SOURCES_VERSION = 1
BRIDGE_AUDIO_PROXY_PROFILE_VERSION = "aac-m4a-stereo-48000-128k-v1"
BRIDGE_VIDEO_PROXY_PROFILE_VERSION = "h264-mp4-720p-yuv420p-crf23-veryfast-v1"
_BRIDGE_CANONICAL_TOP_KEYS = (
    "tracks",
    "clips",
    "theme",
    "theme_overrides",
    "app",
    "pinnedShotGroups",
    "generation_defaults",
)
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
    """Return ``{"slug", "name"}`` rows for every readable bridge project.

    Sorted by slug. Projects whose ``project.json`` is unreadable or malformed
    are skipped (via ``list_bridge_project_dirs``); a missing/blank ``name``
    falls back to the slug.
    """
    rows: list[dict[str, str]] = []
    for project_path in list_bridge_project_dirs(root=root):
        payload = _read_project_payload(project_path / "project.json")
        slug = project_path.name
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            name = slug
        rows.append({"slug": slug, "name": name})
    return sorted(rows, key=lambda row: row["slug"])


def list_bridge_timelines(
    project_slug: str,
    *,
    root: str | Path | None = None,
) -> list[BridgeTimelineRecord]:
    """Return bridge timeline records for a project, sorted by timeline dir name.

    Identity resolution mirrors ``find_bridge_timeline``/``_load_bridge_timeline_record``:
    ``slug``/``name`` come from ``display.json``, ``timeline_id`` comes from
    ``assembly.identity.json`` (falling back to the ULID), and ``is_default``
    compares ``project.json``'s ``default_timeline_id`` against the ULID and the
    canonical timeline id. Timelines with an unreadable display payload are skipped.
    """
    projects_root = resolve_bridge_projects_root(root=root)
    slug = validate_project_slug(project_slug)
    project_payload = _read_project_payload(projects_root / slug / "project.json")
    default_timeline_id = project_payload.get("default_timeline_id")
    timelines_root = timelines_dir(slug, root=projects_root)
    if not timelines_root.is_dir():
        return []

    records: list[BridgeTimelineRecord] = []
    for child in sorted(timelines_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        timeline_ulid = child.name
        timeline_home = timelines_root / timeline_ulid
        try:
            raw_display = load_display_json_with_repair(timeline_home)
        except Exception:
            raw_display = None
        timeline_slug = raw_display.get("slug") if isinstance(raw_display, dict) else None
        timeline_name = raw_display.get("name") if isinstance(raw_display, dict) else None
        if not isinstance(timeline_slug, str) or not isinstance(timeline_name, str):
            continue
        timeline_id = _load_canonical_timeline_id(timeline_home, timeline_ulid)
        records.append(
            BridgeTimelineRecord(
                project_slug=slug,
                timeline_ulid=timeline_ulid,
                timeline_id=timeline_id,
                slug=timeline_slug,
                name=timeline_name,
                is_default=(
                    default_timeline_id == timeline_ulid
                    or default_timeline_id == timeline_id
                ),
                timeline_home=timeline_home,
            )
        )
    return records






def _load_canonical_timeline_id(timeline_home: Path, timeline_ulid: str) -> str:
    """Resolve the canonical timeline id — kernel-first (H2).

    For marked (SQLite-authority) timelines the authoritative id is derived
    from the directory ULID via the backfill marker/kernel binding FIRST;
    the identity sidecar is consulted ONLY for unbackfilled legacy dirs.
    """
    # Kernel-first authoritative resolution
    try:
        from pathlib import Path as _P

        from astrid.core.foundation.project_paths import resolve_projects_root as _rr_lb
        from astrid.core.timeline.authority import (
            is_backfilled_timeline,
            resolve_authoritative_timeline_id,
        )
        _th = _P(timeline_home)
        _pr_lb = None
        try:
            # Derive projects_root from timeline_home layout
            _cand = _th.parent.parent.parent
            if _cand.is_dir():
                _pr_lb = _cand
            else:
                _pr_lb = _rr_lb(None)
        except Exception:
            _pr_lb = _rr_lb(None)
        _auth = resolve_authoritative_timeline_id(_th, _pr_lb)
        if isinstance(_auth, str) and _auth:
            try:
                if is_backfilled_timeline(_auth, _pr_lb):
                    return _auth
            except Exception:
                pass
            # Not backfilled but auth exists (legacy sidecar fallback) — return it
            return _auth
    except Exception:
        pass
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

    # Build the row directly (like the removed list route) so a malformed dir
    # name never passes through timeline_dir()'s strict ULID validation before
    # we know the identity sidecar resolves it. Fall back to the record load.
    timeline_home = timelines_dir(slug, root=projects_root) / found_ulid
    raw_display = load_display_json_with_repair(timeline_home)
    if isinstance(raw_display, dict):
        timeline_slug = raw_display.get("slug")
        timeline_name = raw_display.get("name")
        if isinstance(timeline_slug, str) and isinstance(timeline_name, str):
            default_timeline_id = project_payload.get("default_timeline_id")
            return BridgeTimelineRecord(
                project_slug=slug,
                timeline_ulid=found_ulid,
                timeline_id=_load_canonical_timeline_id(timeline_home, found_ulid),
                slug=timeline_slug,
                name=timeline_name,
                is_default=(default_timeline_id == found_ulid or default_timeline_id == _load_canonical_timeline_id(timeline_home, found_ulid)),
                timeline_home=timeline_home,
            )
    return _load_bridge_timeline_record(
        slug,
        found_ulid,
        project_payload=project_payload,
        root=projects_root,
    )


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
        registry=_load_bridge_registry_for_record(record, root=root),
    )




def save_bridge_timeline(
        project_slug: str,
        timeline: str,
        config: dict[str, Any],
        *,
        registry: dict | None = None,
        expected_version: int | None = None,
        root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Append one editor-save event batch and reload bridge payload.

    When *registry* is provided the config and registry events are appended
    in a single atomic ``append_prebuilt_events`` call so that both succeed or
    both fail together.  *expected_version* enables CAS guards across the
    bridge save/registry endpoints; when ``None`` the current head version is
    used (backward-compatible default).
    """
    # Resolve the canonical timeline BEFORE acquiring the lock so the lock
    # keys by canonical timeline path (not the caller's alias).  Nothing to
    # serialize when the timeline does not exist.
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    with _bridge_save_lock(record.timeline_home):
        backend = LocalFsBackend(
            timeline_id=record.timeline_id,
            timeline_home=record.timeline_home,
        )
        # ``backend.head()`` is crash-reconciled: it adopts any orphaned
        # tail (fsynced append whose head write did not survive) and
        # truncates torn bytes BEFORE returning, so this head is the
        # POST-adoption state the append will actually persist from.
        # Constructing the batch from it keeps tail_hash/version consistent
        # with the retry append (complete-orphan recovery, MUST-FIX 3b).
        head = backend.head()

        # NEVER substitute a caller-supplied expected_version with a fresh read.
        cas_version: int = head.version if expected_version is None else expected_version

        # The Reigh editor sends a superset config. Persist canonical editor and
        # extension state (tracks, clips, theme, theme_overrides, app — extension
        # project-data — plus pinnedShotGroups / generation_defaults); explicitly
        # derived render state such as "output" is re-materialized by Astrid and
        # must not be persisted.
        canonical_config = {
            key: config[key]
            for key in _BRIDGE_CANONICAL_TOP_KEYS
            if key in config
        }

        if registry is not None:
            # Combined batch: config event + registry event in one atomic append.
            # ``current_config`` is only needed for registry-only construction;
            # passing None is safe because ``config`` is supplied.
            batch = construct_reigh_timeline_events(
                timeline_id=record.timeline_id,
                tail_hash=head.last_hash,
                next_event_version=head.version + 1,
                actor=REIGH_LOCAL_EDITOR_ACTOR,
                source="editor_save",
                config=canonical_config,
                asset_registry=registry,
                current_config=None,
                expected_version=cas_version,
            )
            backend.append_prebuilt_events(
                record.timeline_id,
                [item.event for item in batch.events],
                expected_version=cas_version,
            )
            regenerated = regenerate_projection(
                record.timeline_id,
                backend,
                timeline_home=record.timeline_home,
                batch_events=[item.event for item in batch.events],
            )
            # Persist the projected registry sidecar from the combined batch.
            write_json_atomic(
                record.timeline_home / "registry.json",
                batch.projected_asset_registry or {"assets": {}},
            )
            return _bridge_timeline_payload(
                record,
                config=regenerated,
                registry=batch.projected_asset_registry or {"assets": {}},
                config_version=backend.head().version,
            )
        else:
            # Config-only batch (backward-compatible path).
            batch = config_to_events(
                canonical_config,
                None,
                record.timeline_id,
                head.last_hash,
                head.version + 1,
                REIGH_LOCAL_EDITOR_ACTOR,
                "editor_save",
                expected_version=cas_version,
            )
            backend.append_prebuilt_events(
                record.timeline_id,
                [item.event for item in batch.events],
                expected_version=cas_version,
            )
            regenerated = regenerate_projection(
                record.timeline_id,
                backend,
                timeline_home=record.timeline_home,
                batch_events=[item.event for item in batch.events],
            )
            return _bridge_timeline_payload(
                record,
                config=regenerated,
                registry=_load_bridge_registry_for_record(record, root=root),
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


REGISTRY_REPLACED_EVENT_KIND = "timeline.asset_registry_replaced"


def _registry_from_event_stream(record: BridgeTimelineRecord) -> dict[str, Any] | None:
    """Recover the asset registry from the canonical event stream.

    ``registry.json`` is a recoverable sidecar of the timeline event log (see
    asset-library-design.md, "latest registry event → registry.json sidecar
    repair"). When the sidecar is missing, replay the most recent
    ``timeline.asset_registry_replaced`` event instead of falling back to the
    unsafe flat-file heuristic (which can map macOS ``.DS_Store`` junk onto
    every media asset when real sources live in per-source directories).
    """
    event_path = record.timeline_home / "assembly.jsonl"
    try:
        lines = event_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("kind") != REGISTRY_REPLACED_EVENT_KIND:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        registry = payload.get("registry")
        if isinstance(registry, dict) and isinstance(registry.get("assets"), dict):
            return {"assets": dict(registry["assets"])}
    return None


def _registry_from_sqlite(record: BridgeTimelineRecord, *, root: str | Path | None = None) -> dict[str, Any] | None:
    """Recover registry for a backfilled timeline from kernel SQLite (single authority)."""
    try:
        projects_root = resolve_projects_root(root)
        import sqlite3

        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _derive_db
        db_path = _derive_db(projects_root)
        if not db_path.is_file():
            return None
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT asset_registry_json FROM timelines WHERE id = ?", (record.timeline_id,)).fetchone()
            if row is not None and row["asset_registry_json"]:
                import json as _json
                try:
                    payload = _json.loads(row["asset_registry_json"])
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    if isinstance(payload.get("assets"), dict):
                        return {"assets": dict(payload["assets"])}
                    # repository stores INNER assets map (canonical_json(dict(assets)))
                    return {"assets": dict(payload)}
            # Fallback: scan latest registry-bearing event
            sid = f"{record.timeline_id}:timeline.timeline"
            erow = conn.execute("SELECT payload_json FROM events WHERE stream_id = ? AND kind IN ('timeline.asset_registry_replaced','timeline.saved','timeline.config_replaced') ORDER BY seq DESC LIMIT 1", (sid,)).fetchone()
            if erow is not None:
                from astrid.core.receipts.canonical import parse_json as _parse
                try:
                    obj = _parse(erow["payload_json"])
                except Exception:
                    obj = None
                if isinstance(obj, dict):
                    data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
                    reg = data.get("registry") if isinstance(data, dict) else None
                    if isinstance(reg, dict) and isinstance(reg.get("assets"), dict):
                        return {"assets": dict(reg["assets"])}
                    if isinstance(reg, dict):
                        return {"assets": dict(reg)}
        finally:
            conn.close()
    except (OSError, RuntimeError, ValueError):
        raise
    except Exception:
        return None
    return None


def _registry_from_legacy_assets(record: BridgeTimelineRecord) -> dict[str, Any] | None:
    """Legacy fallback: the pre-bridge ``assets.json`` sidecar written by
    project-migration tooling (its entries carry absolute source paths)."""
    payload = _read_registry_payload(record.timeline_home / "assets.json")
    assets = payload.get("assets")
    if isinstance(assets, dict):
        return {"assets": dict(assets)}
    return None


def _is_record_backfilled(record: BridgeTimelineRecord, *, root: str | Path | None = None) -> bool:
    """Check backfill marker for this timeline; fail closed on unreadable marker."""
    import importlib as _il

    from astrid.core.foundation.project_paths import resolve_projects_root as _resolve_root
    _bf_mod = _il.import_module("astrid.packs.timeline.backfill")
    BackfillError = _bf_mod.BackfillError  # type: ignore[attr-defined]
    read_backfill_state = _bf_mod.read_backfill_state  # type: ignore[attr-defined]

    try:
        projects_root = _resolve_root(root)
        state = read_backfill_state(projects_root)
    except BackfillError as exc:
        raise RuntimeError(f"backfill authority marker is unreadable: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"backfill authority marker is unreadable: {exc}") from exc
    return record.timeline_id in state

def _ensure_bridge_registry(
    record: BridgeTimelineRecord,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return the registry payload, recovering and persisting it when the
    sidecar is missing.

    Backfilled timelines recover registry from SQLite exclusively (single
    authority). Marker read failure is a typed failure, never a silent legacy
    fallback. Un-backfilled timelines keep the legacy recovery order:
    event stream → assets.json → source derivation.
    """
    # Marker-gated: backfilled timelines read registry from SQLite exclusively.
    try:
        backfilled = _is_record_backfilled(record, root=root)
    except Exception as exc:
        raise RuntimeError(f"backfill marker failure for {record.timeline_id}: {exc}") from exc
    if backfilled:
        recovered = _registry_from_sqlite(record, root=root)
        if recovered is not None:
            write_json_atomic(record.timeline_home / "registry.json", recovered)
            return recovered
        empty: dict[str, Any] = {"assets": {}}
        write_json_atomic(record.timeline_home / "registry.json", empty)
        return empty
    raw = _read_registry_payload(record.timeline_home / "registry.json")
    if "assets" in raw:
        return raw
    # Legacy un-backfilled path only: stale JSONL / assets.json / source derivation.
    recovered = _registry_from_event_stream(record)
    if recovered is None:
        recovered = _registry_from_legacy_assets(record)
    if recovered is not None:
        write_json_atomic(record.timeline_home / "registry.json", recovered)
        return recovered
    return _derive_registry_from_sources(record, root=root)

def _bridge_asset_resolvable_from_record(
    record: BridgeTimelineRecord,
    entry: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> bool:
    """Return whether one normalized registry entry resolves to media.

    Record-scoped variant of the existence check inside
    :func:`resolve_bridge_asset`, used by the registry normalization loop so
    per-asset validation does not re-run the (expensive) timeline lookup.
    """
    file_value = entry.get("file")
    if not isinstance(file_value, str) or not file_value.strip():
        return False
    file_value = file_value.strip()
    if _is_http_url(file_value):
        return True
    normalized = _normalize_bridge_local_asset_reference(record.project_slug, file_value, root=root)
    if normalized is None:
        return False
    local_path, _normalized_file = normalized
    return local_path.exists()


def _load_bridge_registry_for_record(
    record: BridgeTimelineRecord,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Normalize the registry for an already-resolved timeline record.

    The GET hot path previously re-ran ``find_bridge_timeline`` (full event
    replay + display repair) once for the registry and once more per asset
    (measured: 6 full resolutions for a 5-asset timeline).  Threading the
    record through keeps it to a single resolution.
    """
    raw = _ensure_bridge_registry(record, root=root)
    raw = _sync_bridge_sources(record, raw, root=root)
    assets = raw.get("assets")
    if not isinstance(assets, dict):
        return {"assets": {}}

    normalized_assets: dict[str, dict[str, Any]] = {}
    for asset_key, entry in sorted(assets.items()):
        if not isinstance(asset_key, str) or not isinstance(entry, dict):
            continue
        if not _bridge_asset_resolvable_from_record(record, entry, root=root):
            continue
        normalized_assets[asset_key] = dict(entry)
    return {"assets": normalized_assets}


def load_bridge_registry(
    project_slug: str,
    timeline: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Return a normalized registry payload for bridge-visible assets only.

    Assets are recovered from the event stream (or legacy sidecar) before the
    source-file heuristic runs, so projects whose real sources live in
    per-source directories are not mapped onto stray flat files.
    """
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return {"assets": {}}
    return _load_bridge_registry_for_record(record, root=root)


def resolve_bridge_asset(
    project_slug: str,
    timeline: str,
    asset_key: str,
    *,
    root: str | Path | None = None,
    sync_sources: bool = True,
) -> BridgeResolvedAsset | None:
    """Resolve one registry asset without reading the media bytes into memory.

    When *sync_sources* is False, the registry is read (and derived if missing)
    but the sources.json sync/write step is skipped. This is appropriate for
    read-only hot-paths such as byte-range media serving where the sync side
    effects are unnecessary on every chunk request.
    """
    record = find_bridge_timeline(project_slug, timeline, root=root)
    if record is None:
        return None

    registry = _ensure_bridge_registry(record, root=root)
    if sync_sources:
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
    source_files = sorted(
        path for path in sources_root.iterdir()
        if path.is_file() and not path.name.startswith(".")
    ) if sources_root.is_dir() else []
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
