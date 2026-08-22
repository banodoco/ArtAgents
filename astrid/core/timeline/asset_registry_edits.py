"""Asset registry sync primitives.

``sync_asset_registry`` reads a JSON manifest, resolves each entry to a
registered source (``source_id``) or a local file path under the project's
``sources/`` root, merges the mapped entries into the latest full registry,
and appends a ``timeline.asset_registry_replaced`` event (with CAS guard).

No automatic ffprobe; no implicit pruning of unrelated or missing entries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.contracts.errors import AstridError
from astrid.core.foundation.project_paths import (
    project_dir,
    resolve_projects_root,
    sources_dir,
    validate_project_slug,
)
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.events.schema import (
    AssetRegistryReplacedPayload,
    TimelineActor,
    TimelineEvent,
)
from astrid.core.timeline.paths import assembly_identity_path


def _entry_from_source_ref(
    *,
    asset_key: str,
    source_ref: dict[str, Any],
    project_slug: str,
    sources_root: Path,
) -> dict[str, Any]:
    """Resolve a single manifest entry into a registry asset dict.

    *source_ref* must contain EXACTLY ONE of ``source_id`` or ``file``.

    Returns a dict with ``file|url``, MIME ``type``, and ``duration`` (when
    available from the registered source).
    """
    source_id = source_ref.get("source_id")
    file_path = source_ref.get("file")

    if source_id is not None and file_path is not None:
        raise AstridError(
            f"asset '{asset_key}': provide exactly one of source_id or file, not both"
        )
    if source_id is None and file_path is None:
        raise AstridError(
            f"asset '{asset_key}': must provide source_id or file"
        )

    if source_id is not None:
        # Resolve via registered sources. sources_root is
        # <projects_root>/<slug>/sources, so the projects root is two levels up.
        projects_root = sources_root.parent.parent
        sources_payload = _load_project_sources(project_slug, projects_root)
        sources = sources_payload.get("sources", {})
        src_entry = sources.get(source_id) if isinstance(sources, dict) else None
        if src_entry is None:
            # `astrid projects source add` writes per-source metadata to
            # sources/<id>/source.json (media fields nested under `asset`) and
            # does NOT update the project-level flat sources.json (only the
            # bridge sync does). Fall back to that per-source sidecar so the
            # advertised source add → registry sync workflow works.
            per_source = sources_root / source_id / "source.json"
            try:
                per_payload = read_json(per_source)
            except Exception:
                per_payload = None
            if isinstance(per_payload, dict):
                per_asset = per_payload.get("asset")
                if isinstance(per_asset, dict):
                    src_entry = per_asset
        if not isinstance(src_entry, dict):
            raise AstridError(
                f"asset '{asset_key}': source_id '{source_id}' not found in project sources; "
                f"add it with 'astrid projects source add'"
            )
        result: dict[str, Any] = {}
        # Copy file/url/type/duration from the source entry
        src_file = src_entry.get("file")
        src_url = src_entry.get("url")
        if isinstance(src_file, str) and src_file.strip():
            result["file"] = src_file.strip()
        if isinstance(src_url, str) and src_url.strip():
            result["url"] = src_url.strip()
        src_type = src_entry.get("type")
        if isinstance(src_type, str) and src_type.strip():
            result["type"] = src_type.strip()
        src_duration = src_entry.get("duration")
        if isinstance(src_duration, (int, float)) and src_duration > 0:
            result["duration"] = float(src_duration)
        if not result:
            raise AstridError(
                f"asset '{asset_key}': source '{source_id}' has no file, url, or other content"
            )
        return result

    # file path — must be contained under sources/
    if not isinstance(file_path, str) or not file_path.strip():
        raise AstridError(f"asset '{asset_key}': file must be a non-empty path")
    file_path = file_path.strip()
    resolved = _resolve_file_under_sources(file_path, sources_root)
    if resolved is None:
        raise AstridError(
            f"asset '{asset_key}': file '{file_path}' is not under the project sources/ root; "
            f"import the asset first with 'astrid projects source import'"
        )
    if not resolved.is_file():
        raise AstridError(
            f"asset '{asset_key}': file '{resolved}' does not exist"
        )

    import mimetypes

    mime_type, _encoding = mimetypes.guess_type(resolved.name)
    entry: dict[str, Any] = {"file": file_path}
    if mime_type:
        entry["type"] = mime_type
    return entry


def _load_project_sources(project_slug: str, root: Path) -> dict[str, Any]:
    """Load sources.json for *project_slug*."""
    # Lazy import: local_bridge imports this package's __init__ at module load,
    # which would otherwise create an import cycle (local_bridge → timeline →
    # asset_registry_edits → local_bridge).
    from astrid.core.integrations.reigh.local_bridge import BRIDGE_SOURCES_VERSION

    sources_path = project_dir(project_slug, root=root) / "sources.json"
    try:
        payload = read_json(sources_path)
    except Exception:
        return {"version": BRIDGE_SOURCES_VERSION, "sources": {}}
    if not isinstance(payload, dict):
        return {"version": BRIDGE_SOURCES_VERSION, "sources": {}}
    return payload


def _resolve_file_under_sources(file_path: str, sources_root: Path) -> Path | None:
    """Return the absolute path if *file_path* is contained under *sources_root*."""
    candidate = (sources_root / file_path).resolve()
    try:
        candidate.relative_to(sources_root.resolve())
    except ValueError:
        return None
    return candidate


def sync_asset_registry(
    project_slug: str,
    slug: str,
    *,
    manifest_path: str | Path,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    root: str | Path | None = None,
) -> TimelineEvent | None:
    """Sync asset registry entries from a JSON manifest into the timeline.

    The manifest format is::

        {"assets": {"<asset-key>": {"source_id": "<id>"} | {"file": "<path>"}}}

    Each entry must contain EXACTLY ONE of ``source_id`` or ``file``.

    Returns the appended event, or ``None`` when the merged registry is
    unchanged (no-op).
    """
    validate_project_slug(project_slug)
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise AstridError(f"manifest file not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AstridError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(manifest, dict):
        raise AstridError("manifest must be a JSON object")

    manifest_assets = manifest.get("assets")
    if not isinstance(manifest_assets, dict):
        raise AstridError("manifest must contain an 'assets' object")

    # Resolve timeline directory
    projects_root = resolve_projects_root(root=root)
    sources_root_dir = sources_dir(project_slug, root=projects_root)
    if not sources_root_dir.is_dir():
        sources_root_dir.mkdir(parents=True, exist_ok=True)

    # Find the timeline
    from astrid.core.timeline.paths import find_timeline_by_slug

    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise AstridError(f"timeline '{slug}' not found in project '{project_slug}'")
    ulid, tdir = found

    # Lazy import: local_bridge imports this package's __init__ at module load,
    # which would otherwise create an import cycle.
    from astrid.core.integrations.reigh.local_bridge import (
        _ensure_bridge_registry,
        find_bridge_timeline,
    )

    # Load the LATEST full registry (via event stream recovery path). Use the
    # RAW registry, not the served/validated one: the sync must preserve
    # entries whose media file is temporarily missing (never prune implicitly),
    # while the served registry drops them from bridge responses.
    record = find_bridge_timeline(project_slug, slug, root=root)
    if record is None:
        current_registry: dict[str, Any] = {"assets": {}}
    else:
        current_registry = _ensure_bridge_registry(record, root=root)

    current_assets = current_registry.get("assets", {})
    if not isinstance(current_assets, dict):
        current_assets = {}

    # Build mapped entries
    merged_assets: dict[str, dict[str, Any]] = dict(current_assets)  # shallow copy
    for asset_key, source_ref in manifest_assets.items():
        if not isinstance(source_ref, dict):
            raise AstridError(
                f"manifest asset '{asset_key}' must be an object"
            )
        entry = _entry_from_source_ref(
            asset_key=asset_key,
            source_ref=source_ref,
            project_slug=project_slug,
            sources_root=sources_root_dir,
        )
        merged_assets[asset_key] = entry

    # Check for no-op
    if merged_assets == current_assets:
        return None

    # Build the new registry
    new_registry: dict[str, Any] = {"assets": merged_assets}

    # Use selected backend (sqlite for marked) — single-authority writer.
    identity_path = assembly_identity_path(project_slug, tdir.name, root=projects_root)
    identity = read_json(identity_path) if identity_path.is_file() else {}
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str) or not timeline_id.strip():
        # Try kernel fallback for sidecarless backfilled
        try:
            from astrid.core.foundation.project_paths import resolve_projects_root as _rr3
            from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd3
            import sqlite3 as _sq3
            _pr3 = _rr3(projects_root)
            _db3 = _dd3(_pr3)
            if _db3.is_file():
                c = _sq3.connect(f"file:{_db3}?mode=ro", uri=True)
                c.row_factory = _sq3.Row
                r = c.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_ulid')=? LIMIT 1", (tdir.name,)).fetchone()
                if r and r["tid"]:
                    timeline_id = str(r["tid"])
                c.close()
        except Exception:
            pass
        if not isinstance(timeline_id, str) or not timeline_id.strip():
            raise AstridError("timeline identity is missing timeline_id")
    # Marker-gated backend selection
    try:
        from astrid.core.foundation.project_paths import resolve_projects_root as _rr4
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _dd4
        from astrid.packs.timeline.backfill import read_backfill_state as _rbs4
        _pr4 = _rr4(projects_root)
        _db4 = _dd4(_pr4)
        _is_back4 = False
        if _db4.is_file():
            try:
                _st4 = _rbs4(_pr4)
                _is_back4 = timeline_id in _st4
            except Exception:
                _is_back4 = False
        if _is_back4:
            from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
            backend = SqliteEventLogBackend(timeline_id=timeline_id, timeline_home=tdir, projects_root=_pr4)
        else:
            backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)
    except Exception:
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)
    act = actor or TimelineActor(
        type="agent",
        id="agent:project:" + project_slug,
        display="project:" + project_slug,
    )

    event = backend.append_event(
        timeline_id,
        "timeline.asset_registry_replaced",
        AssetRegistryReplacedPayload(
            registry=new_registry,
            source="other",
        ),
        actor=act,
        expected_version=expected_version,
    )

    # Update the registry.json sidecar
    registry_path = tdir / "registry.json"
    write_json_atomic(registry_path, new_registry)

    return event
