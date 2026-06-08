"""Path and id helpers for Astrid timelines."""

from __future__ import annotations

import re
from pathlib import Path

from astrid.core.threads.ids import is_ulid

from ..project.jsonio import ProjectJsonError, read_json
from ..project.paths import ProjectPathError, project_dir

_TIMELINE_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def validate_timeline_slug(slug: object) -> str:
    if not isinstance(slug, str) or _TIMELINE_SLUG_RE.fullmatch(slug) is None:
        raise ProjectPathError(
            "timeline slug must start with a lowercase letter, contain only "
            "lowercase letters, digits or '-', and be 1–32 characters long"
        )
    return slug


def validate_timeline_ulid(ulid: object) -> str:
    if not is_ulid(ulid):
        raise ProjectPathError(
            "timeline ULID must be a 26-character Crockford ULID"
        )
    return str(ulid)


def timelines_dir(project_slug: str, *, root: str | Path | None = None) -> Path:
    return project_dir(project_slug, root=root) / "timelines"


def timeline_dir(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timelines_dir(project_slug, root=root) / validate_timeline_ulid(ulid)


def assembly_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.json"


def assembly_log_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.jsonl"


def assembly_head_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.head.json"


def assembly_identity_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "assembly.identity.json"


def manifest_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "manifest.json"


def display_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    return timeline_dir(project_slug, ulid, root=root) / "display.json"


def checkpoint_path(
    project_slug: str, ulid: str, *, root: str | Path | None = None
) -> Path:
    """Return the path to ``assembly.checkpoint.json`` inside the timeline home."""
    return timeline_dir(project_slug, ulid, root=root) / "assembly.checkpoint.json"


def find_timeline_by_slug(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
    include_tombstoned: bool = False,
) -> tuple[str, Path] | None:
    """Scan timelines/*/display.json for a matching slug.

    Returns (ulid, timeline_dir) or None if not found.
    """
    target = validate_timeline_slug(slug)
    td = timelines_dir(project_slug, root=root)
    if not td.is_dir():
        return None
    for child in sorted(td.iterdir()):
        if not child.is_dir():
            continue
        if not include_tombstoned and _timeline_home_is_tombstoned(child):
            continue
        try:
            data = load_display_json_with_repair(child)
        except (ProjectJsonError, OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("slug") == target:
            # The directory name is the ULID.
            return (child.name, child)
    return None


def _timeline_home_is_tombstoned(timeline_home: str | Path) -> bool:
    manifest_file = Path(timeline_home) / "manifest.json"
    if not manifest_file.is_file():
        return False
    try:
        manifest = read_json(manifest_file)
    except (ProjectJsonError, OSError, ValueError):
        return False
    return isinstance(manifest, dict) and manifest.get("tombstoned_at") is not None


def find_timeline_slug_for_ulid(
    project_slug: str,
    ulid: str,
    *,
    root: str | Path | None = None,
    include_tombstoned: bool = False,
) -> str | None:
    """Reverse-lookup: read display.json for the given ULID and return the slug."""
    tdir = timeline_dir(project_slug, ulid, root=root)
    if not tdir.is_dir():
        return None
    if not include_tombstoned and _timeline_home_is_tombstoned(tdir):
        return None
    try:
        data = load_display_json_with_repair(tdir)
    except (ProjectJsonError, OSError, ValueError):
        return None
    if isinstance(data, dict):
        slug = data.get("slug")
        if isinstance(slug, str):
            return slug
    return None


def find_timeline_by_event_stream_id(
    project_slug: str, event_stream_id: str, *, root: str | Path | None = None
) -> tuple[str, str] | None:
    """Find a local timeline whose identity sidecar carries *event_stream_id*.

    Scans ``timelines/*/assembly.identity.json`` and returns
    ``(timeline_ulid, timeline_slug)`` for the first match, or ``None``.
    """
    td = timelines_dir(project_slug, root=root)
    if not td.is_dir():
        return None
    for child in sorted(td.iterdir()):
        if not child.is_dir():
            continue
        identity_path = child / "assembly.identity.json"
        if not identity_path.is_file():
            continue
        try:
            identity = read_json(identity_path)
        except (ProjectJsonError, OSError, ValueError):
            continue
        if isinstance(identity, dict) and identity.get("timeline_id") == event_stream_id:
            try:
                data = load_display_json_with_repair(child)
                slug = data.get("slug") if isinstance(data, dict) else None
            except (ProjectJsonError, OSError, ValueError):
                slug = None
            if isinstance(slug, str):
                return (child.name, slug)
    return None


def load_display_json_with_repair(timeline_home: str | Path) -> dict[str, object] | None:
    from .eventlog import LocalFsBackend, project_display
    from .model import Display, TimelineValidationError

    timeline_dir_path = Path(timeline_home)
    display_file = timeline_dir_path / "display.json"
    events_file = timeline_dir_path / "assembly.jsonl"
    identity_file = timeline_dir_path / "assembly.identity.json"

    if not events_file.is_file():
        if not display_file.is_file():
            return None
        raw = read_json(display_file)
        return raw if isinstance(raw, dict) else None

    if not identity_file.is_file():
        return None

    identity = read_json(identity_file)
    if not isinstance(identity, dict):
        return None
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str):
        return None
    fallback_display = None
    raw_identity_display = identity.get("display")
    if isinstance(raw_identity_display, dict):
        try:
            fallback_display = Display.from_dict(raw_identity_display)
        except TimelineValidationError:
            fallback_display = None

    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_dir_path)
    projection = project_display(backend.read_events(), fallback_display=fallback_display)
    if projection.deleted:
        return None
    if projection.display is None:
        return None

    projected = projection.display.to_json_obj()
    needs_write = True
    if display_file.is_file():
        try:
            current = read_json(display_file)
        except (ProjectJsonError, FileNotFoundError):
            current = None
        needs_write = current != projected
    if needs_write:
        projection.display.write(display_file)
    return projected


def load_assembly_json_with_repair(
    timeline_home: str | Path,
) -> dict[str, object] | None:
    """Return the raw TimelineConfig with repair from the event log.

    When an event log (``assembly.jsonl``) and identity sidecar exist,
    resolve the backend, read events, call ``regenerate_projection()``,
    and return the projected raw TimelineConfig.  When no event log
    exists, fall back to reading ``assembly.json`` directly.

    This is the assembly analogue of ``load_display_json_with_repair()``.
    It closes the debt item ``timeline-assembly-repair``: stale or missing
    ``assembly.json`` is regenerated from the canonical event stream on
    every Astrid-owned read/export entry point.
    """
    from .eventlog import LocalFsBackend
    from .model import TimelineValidationError, validate_timeline_config_json
    from .projection import ErasedPayloadProjectionError, ProjectionError, regenerate_projection

    timeline_dir_path = Path(timeline_home)
    assembly_file = timeline_dir_path / "assembly.json"
    events_file = timeline_dir_path / "assembly.jsonl"
    identity_file = timeline_dir_path / "assembly.identity.json"

    # No event log → fall back to direct file read.
    if not events_file.is_file():
        if not assembly_file.is_file():
            return None
        try:
            raw = read_json(assembly_file)
        except (ProjectJsonError, FileNotFoundError):
            return None
        try:
            return validate_timeline_config_json(raw)
        except TimelineValidationError:
            return None

    # Event log exists but no identity → can't resolve backend.
    if not identity_file.is_file():
        return None

    identity = read_json(identity_file)
    if not isinstance(identity, dict):
        return None
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str):
        return None

    # Resolve backend and regenerate projection from events.
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_dir_path)
    try:
        inner_assembly = regenerate_projection(
            timeline_id, backend, timeline_home=timeline_dir_path,
        )
    except (ErasedPayloadProjectionError, ProjectionError):
        # ErasedPayloadProjectionError MUST NOT fall back to stale assembly.json.
        # Projection errors from the canonical event stream must surface on
        # user-facing reads rather than silently serving stale compatibility
        # snapshots from assembly.json.
        raise
    except TimelineValidationError:
        raise
    except Exception:
        # If projection fails for other reasons, fall back to reading
        # assembly.json directly.  This preserves backward compatibility
        # for non-erasure-related projection failures while ensuring
        # erased content is never silently served.
        if assembly_file.is_file():
            try:
                raw = read_json(assembly_file)
            except (ProjectJsonError, FileNotFoundError):
                return None
            try:
                return validate_timeline_config_json(raw)
            except TimelineValidationError:
                return None
        return None

    try:
        return validate_timeline_config_json(inner_assembly)
    except TimelineValidationError:
        raise
