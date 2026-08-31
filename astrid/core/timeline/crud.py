"""Timeline CRUD primitives — create, list, show, rename, finalize, tombstone, purge, set-default."""

from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

try:  # pragma: no cover - non-POSIX fallback is exercised only off Unix.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.ids import generate_ulid
from astrid.core.timeline.banodoco_schema import canonical_empty_timeline
from astrid.core.util.time import utc_now_seconds as utc_now_iso

from .eventlog import select_timeline_backend
from .events.schema import TimelineActor
from .integrity import compute_sha256, file_size
from .model import (
    TIMELINE_SCHEMA_VERSION,
    Display,
    FinalOutput,
    Manifest,
    TimelineValidationError,
    read_timeline_config_json,
    validate_timeline_config_json,
    write_timeline_config_json,
)
from .paths import (
    assembly_identity_path,
    display_path,
    find_timeline_by_slug,
    load_assembly_json_with_repair,
    load_display_json_with_repair,
    timeline_dir,
    timelines_dir,
    validate_timeline_slug,
)


class TimelineCrudError(RuntimeError):
    """Raised when a timeline CRUD operation cannot be completed."""


@dataclass(frozen=True)
class TimelineSummary:
    """Lightweight timeline listing row."""

    ulid: str
    slug: str
    name: str
    is_default: bool
    run_count: int
    final_output_count: int
    last_finalized: str | None  # ISO-8601 timestamp of the most recent final output
    tombstoned_at: str | None = None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_timeline(
    project_slug: str,
    slug: str,
    *,
    name: str | None = None,
    is_default: bool = False,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Create a new timeline container under *project_slug*.

    Returns a dict with keys ``ulid``, ``slug``, ``display``, ``assembly``, ``manifest``.

    Milestone 1 keeps create on the legacy write path. This seeds the identity
    sidecar for later eventlog use, but it does not emit ``timeline.created``.
    """
    slug = validate_timeline_slug(slug)
    human_name = name or slug

    # Refuse duplicate slug within the same project.
    existing = find_timeline_by_slug(project_slug, slug, root=root)
    if existing is not None:
        raise TimelineCrudError(
            f"timeline slug '{slug}' already exists in project '{project_slug}' "
            f"(ULID {existing[0]})"
        )

    ulid = generate_ulid()
    tdir = timeline_dir(project_slug, ulid, root=root)
    tdir.mkdir(parents=True, exist_ok=False)

    assembly = validate_timeline_config_json(canonical_empty_timeline())
    manifest = Manifest(
        schema_version=TIMELINE_SCHEMA_VERSION,
        contributing_runs=[],
        final_outputs=[],
        tombstoned_at=None,
    )
    display = Display(
        schema_version=TIMELINE_SCHEMA_VERSION,
        slug=slug,
        name=human_name,
        is_default=is_default,
    )

    write_timeline_config_json(tdir / "assembly.json", assembly)
    manifest.write(tdir / "manifest.json")
    display.write(tdir / "display.json")
    write_json_atomic(
        assembly_identity_path(project_slug, ulid, root=root),
        {
            "schema_version": 1,
            "timeline_id": str(uuid4()),
            "timeline_ulid": ulid,
            "backend": "local_fs",
            "provenance": "created",
            "created_at": utc_now_iso(),
            "display": display.to_json_obj(),
        },
    )

    return {
        "ulid": ulid,
        "slug": slug,
        "display": display,
        "assembly": assembly,
        "manifest": manifest,
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def list_timelines(
    project_slug: str,
    *,
    root: str | Path | None = None,
    include_tombstoned: bool = False,
) -> list[TimelineSummary]:
    """Return summary rows for every timeline under *project_slug*."""
    td = timelines_dir(project_slug, root=root)
    if not td.is_dir():
        return []

    rows: list[TimelineSummary] = []
    for child in sorted(td.iterdir()):
        if not child.is_dir():
            continue
        ulid = child.name
        mp = child / "manifest.json"

        try:
            raw_display = load_display_json_with_repair(child)
            if raw_display is None:
                continue
            display = Display.from_dict(raw_display)
        except (TimelineValidationError, OSError, ValueError):
            continue

        run_count = 0
        final_output_count = 0
        last_finalized: str | None = None
        tombstoned_at: str | None = None
        if mp.is_file():
            try:
                manifest = Manifest.from_json(mp)
            except (TimelineValidationError, OSError):
                manifest = None
            if manifest is not None:
                tombstoned_at = manifest.tombstoned_at
                if tombstoned_at is not None and not include_tombstoned:
                    continue
                run_count = len(manifest.contributing_runs)
                final_output_count = len(manifest.final_outputs)
                if manifest.final_outputs:
                    last_finalized = max(
                        (fo.recorded_at for fo in manifest.final_outputs),
                        default=None,
                    )

        rows.append(
            TimelineSummary(
                ulid=ulid,
                slug=display.slug,
                name=display.name,
                is_default=display.is_default,
                run_count=run_count,
                final_output_count=final_output_count,
                last_finalized=last_finalized,
                tombstoned_at=tombstoned_at,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Show
# ---------------------------------------------------------------------------


def show_timeline(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
    include_tombstoned: bool = True,
    verify: bool = False,
) -> dict[str, Any] | None:
    """Return the full timeline record (assembly + manifest + display).

    ``assembly.json`` is now a derived projection regenerated from the
    canonical event stream via ``load_assembly_json_with_repair()``.
    If an event log exists, the assembly is rebuilt from events; if not,
    the on-disk ``assembly.json`` is read directly (legacy fallback).
    """
    found = find_timeline_by_slug(
        project_slug,
        slug,
        root=root,
        include_tombstoned=include_tombstoned,
    )
    if found is None:
        return None
    ulid, tdir = found
    # Normal reads repair stale projections from the event log. Verification
    # reads are intentionally read-only and inspect assembly.json as-is.
    raw_assembly = (
        read_timeline_config_json(tdir / "assembly.json")
        if verify
        else load_assembly_json_with_repair(tdir)
    )
    if raw_assembly is None:
        return None
    assembly = validate_timeline_config_json(raw_assembly)
    manifest = Manifest.from_json(tdir / "manifest.json")
    raw_display = (
        read_json(tdir / "display.json")
        if verify
        else load_display_json_with_repair(tdir)
    )
    if raw_display is None:
        return None
    display = Display.from_dict(raw_display)
    result: dict[str, Any] = {
        "ulid": ulid,
        "display": display,
        "assembly": assembly,
        "manifest": manifest,
    }
    if verify:
        result["verification"] = _verify_timeline_read_only(tdir)
    return result


def _verify_timeline_read_only(tdir: Path) -> dict[str, Any]:
    events_file = tdir / "assembly.jsonl"
    identity_file = tdir / "assembly.identity.json"
    if not events_file.is_file():
        return {"event_log": "absent", "ok": True, "checked_events": 0}
    if not identity_file.is_file():
        return {
            "event_log": "present",
            "ok": False,
            "checked_events": 0,
            "error": "assembly.identity.json missing",
        }
    identity = read_json(identity_file)
    timeline_id = identity.get("timeline_id") if isinstance(identity, dict) else None
    if not isinstance(timeline_id, str) or not timeline_id:
        return {
            "event_log": "present",
            "ok": False,
            "checked_events": 0,
            "error": "timeline identity sidecar missing timeline_id",
        }
    from .eventlog import LocalFsBackend

    verification = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir).verify_chain()
    return {
        "event_log": "present",
        "ok": verification.ok,
        "checked_events": verification.checked_events,
        "last_event_id": verification.last_event_id,
        "error": verification.error,
    }


# ---------------------------------------------------------------------------
# Arrangement read helper (m3 read model)
# ---------------------------------------------------------------------------


def get_arrangement(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return the arrangement dict from the materialized assembly, or *None*.

    Reads through the compatibility projection (``assembly.json``), not
    event log replay.  In m4 this will become a projection read.

    Args:
        project_slug: Project that owns the timeline.
        slug: Timeline slug within the project.
        root: Filesystem root override.
    """
    data = show_timeline(project_slug, slug, root=root)
    if data is None:
        return None
    assembly = data["assembly"]
    return assembly.get("arrangement")


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


def rename_timeline(
    project_slug: str,
    old_slug: str,
    new_slug: str,
    *,
    actor: TimelineActor | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Rewrite ``display.json`` so *old_slug* becomes *new_slug*.

    Refuses if *new_slug* is already taken within the same project.
    """
    found = find_timeline_by_slug(project_slug, old_slug, root=root)
    if found is None:
        raise TimelineCrudError(f"timeline '{old_slug}' not found in project '{project_slug}'")

    ulid, tdir = found
    new_slug = validate_timeline_slug(new_slug)

    # Check collision.
    collision = find_timeline_by_slug(project_slug, new_slug, root=root)
    if collision is not None and collision[0] != ulid:
        raise TimelineCrudError(
            f"timeline slug '{new_slug}' already exists in project '{project_slug}'"
        )

    identity = read_json(assembly_identity_path(project_slug, ulid, root=root))
    if not isinstance(identity, dict):
        raise TimelineCrudError("timeline identity sidecar is malformed")
    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise TimelineCrudError("timeline identity sidecar is missing timeline_id")
    preferred_backend = identity.get("backend")
    if preferred_backend is not None and not isinstance(preferred_backend, str):
        raise TimelineCrudError("timeline identity sidecar has malformed backend")

    select_kwargs: dict[str, Any] = {
        "timeline_id": timeline_id,
        "timeline_home": tdir,
        "preferred_backend": preferred_backend,
    }
    stream, backend = select_timeline_backend(**select_kwargs)
    rename_actor = actor or TimelineActor(
        type="system",
        id="timeline-crud:rename",
        display="timeline-crud",
    )
    backend.append_event(
        timeline_id,
        "timeline.renamed",
        {"old_slug": old_slug, "new_slug": new_slug},
        actor=rename_actor,
        expected_version=expected_version,
        txn_id=txn_id,
    )

    dp = tdir / "display.json"
    raw_display = load_display_json_with_repair(tdir)
    if raw_display is None:
        raise TimelineCrudError(f"timeline '{old_slug}' could not materialize display state")
    display = Display.from_dict(raw_display)
    updated = Display(
        schema_version=TIMELINE_SCHEMA_VERSION,
        slug=new_slug,
        name=display.name,
        is_default=display.is_default,
    )
    updated.write(dp)
    return {"ulid": ulid, "slug": new_slug, "display": updated}


# ---------------------------------------------------------------------------
# Finalize output
# ---------------------------------------------------------------------------


def finalize_output(
    project_slug: str,
    slug: str,
    output_path: str | Path,
    *,
    kind: str = "unknown",
    from_run: str | None = None,
    recorded_by: str = "agent:unknown",
    root: str | Path | None = None,
) -> FinalOutput:
    """Capture sha256 + size of *output_path* and append to the timeline's final outputs.

    ``check_status`` is stamped ``"ok"`` at call time; ``check_at`` equals ``recorded_at``.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise TimelineCrudError(f"timeline '{slug}' not found in project '{project_slug}'")

    ulid, tdir = found
    op = Path(output_path).expanduser().resolve()
    if not op.is_file():
        raise TimelineCrudError(f"output file not found: {op}")

    from astrid.core.util.time import utc_now_seconds as utc_now_iso

    now = utc_now_iso()
    sha256 = compute_sha256(op)
    size = file_size(op)

    fo = FinalOutput(
        ulid=generate_ulid(),
        path=str(op),
        kind=kind,
        size=size,
        sha256=sha256,
        check_status="ok",
        check_at=now,
        recorded_at=now,
        recorded_by=recorded_by,
        from_run=from_run or "",
    )

    mp = tdir / "manifest.json"
    manifest = Manifest.from_json(mp)
    new_outputs = list(manifest.final_outputs) + [fo]
    updated = Manifest(
        schema_version=TIMELINE_SCHEMA_VERSION,
        contributing_runs=list(manifest.contributing_runs),
        final_outputs=new_outputs,
        tombstoned_at=manifest.tombstoned_at,
    )
    updated.write(mp)
    return fo


def record_contributing_run(
    project_slug: str,
    timeline_ulid: str,
    run_id: str,
    *,
    root: str | Path | None = None,
) -> None:
    """Ensure *run_id* is listed as contributing to *timeline_ulid*."""
    tdir = timeline_dir(project_slug, timeline_ulid, root=root)
    mp = tdir / "manifest.json"
    if not mp.is_file():
        raise TimelineCrudError(
            f"timeline {timeline_ulid!r} has no manifest.json in project {project_slug!r}"
        )
    with _manifest_lock(mp):
        manifest = Manifest.from_dict(json.loads(mp.read_text(encoding="utf-8")))
        if run_id in manifest.contributing_runs:
            return
        updated = Manifest(
            schema_version=TIMELINE_SCHEMA_VERSION,
            contributing_runs=[*manifest.contributing_runs, run_id],
            final_outputs=list(manifest.final_outputs),
            tombstoned_at=manifest.tombstoned_at,
        )
        updated.write(mp)


@contextmanager
def _manifest_lock(manifest_path: Path):
    """Serialize manifest read-modify-write updates with a sidecar flock."""
    lock_path = manifest_path.with_suffix(f"{manifest_path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Tombstone
# ---------------------------------------------------------------------------


def tombstone_timeline(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Soft-delete: stamp ``tombstoned_at`` in the manifest, leave files in place.

    Milestone 1 intentionally leaves this on the legacy surface; it does not
    emit ``timeline.tombstoned``.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root, include_tombstoned=True)
    if found is None:
        raise TimelineCrudError(f"timeline '{slug}' not found in project '{project_slug}'")

    ulid, tdir = found
    mp = tdir / "manifest.json"
    manifest = Manifest.from_json(mp)

    if manifest.tombstoned_at is not None:
        raise TimelineCrudError(f"timeline '{slug}' is already tombstoned")

    from astrid.core.util.time import utc_now_seconds as utc_now_iso

    updated = Manifest(
        schema_version=TIMELINE_SCHEMA_VERSION,
        contributing_runs=list(manifest.contributing_runs),
        final_outputs=list(manifest.final_outputs),
        tombstoned_at=utc_now_iso(),
    )
    updated.write(mp)
    return {"ulid": ulid, "slug": slug, "tombstoned_at": updated.tombstoned_at}


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------


def purge_timeline(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> None:
    """Hard-delete the timeline directory tree.

    Refuses if the timeline is currently the project default — callers MUST
    ``set_default`` to a different timeline first.

    Milestone 1 does not emit ``timeline.deleted`` here. Any delete event seen
    by projection or append enforcement must already exist in the stream.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root, include_tombstoned=True)
    if found is None:
        raise TimelineCrudError(f"timeline '{slug}' not found in project '{project_slug}'")

    ulid, tdir = found

    # The runtime owns the canonical default; this local projection flag is
    # the only state used by file-backed timeline tooling.
    try:
        is_default = Display.from_json(tdir / "display.json").is_default
    except (TimelineValidationError, OSError):
        is_default = False
    if is_default:
        raise TimelineCrudError(
            f"timeline '{slug}' is the project default; "
            f"set another timeline as default first with 'astrid timelines set-default <other>'"
        )

    shutil.rmtree(tdir)


# ---------------------------------------------------------------------------
# Set default
# ---------------------------------------------------------------------------


def set_default(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Make *slug* the project default timeline.

    Rewrites ``display.json`` on the old default (clearing its ``is_default``),
    on the new one (setting ``is_default``), and updates ``project.json``
    ``default_timeline_id``.

    Milestone 1 intentionally keeps this on the legacy write path and does not
    emit ``timeline.default_set`` yet.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise TimelineCrudError(f"timeline '{slug}' not found in project '{project_slug}'")

    new_ulid, new_tdir = found

    # Clear old defaults in the local display projections only.
    for prior in list_timelines(project_slug, root=root, include_tombstoned=True):
        if not prior.is_default or prior.ulid == new_ulid:
            continue
        old_dp = display_path(project_slug, prior.ulid, root=root)
        try:
            old_display = Display.from_json(old_dp)
        except (TimelineValidationError, OSError):
            continue
        Display(
            schema_version=TIMELINE_SCHEMA_VERSION,
            slug=old_display.slug,
            name=old_display.name,
            is_default=False,
        ).write(old_dp)

    # Set new default.
    new_dp = new_tdir / "display.json"
    new_display = Display.from_json(new_dp)
    updated = Display(
        schema_version=TIMELINE_SCHEMA_VERSION,
        slug=new_display.slug,
        name=new_display.name,
        is_default=True,
    )
    updated.write(new_dp)

    return {"ulid": new_ulid, "slug": slug, "display": updated}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
