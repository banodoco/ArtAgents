"""Backend selection helpers for timeline event streams.

Provides:
- select_timeline_stream / select_timeline_backend: low-level backend
  construction from a timeline_id + optional home/backend preference.

- resolve_event_log_target: high-level resolver that distinguishes local
  timelines (resolved by slug/ULID/UUID from the project directory) from
  Supabase streams (resolved only when an explicit ``--from`` or ``--to``
  backend ref is supplied).

- resolve_pull_destination: pull-specific destination resolution that
  creates a local home when needed, writes ``assembly.identity.json`` plus a
  raw empty TimelineConfig, and refuses ambiguous destinations before
  performing any writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .local_fs import LocalFsBackend
from .protocol import EventLogBackend
from .supabase import SupabaseBackend
from .types import (
    BackendName,
    SupabaseEventLogOptions,
    TimelineStreamRef,
)

# ============================================================================
# Low-level stream/backend construction
# ============================================================================


def select_timeline_stream(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
    supabase_options: SupabaseEventLogOptions | None = None,
) -> TimelineStreamRef:
    backend = (preferred_backend or "").strip().lower()
    if backend == "supabase":
        return TimelineStreamRef(
            backend="supabase",
            timeline_id=timeline_id,
            home=None,
            source="preferred_backend",
            supabase_options=supabase_options,
        )
    if timeline_home is not None:
        return TimelineStreamRef(
            backend="local_fs",
            timeline_id=timeline_id,
            home=Path(timeline_home),
            source="timeline_home",
            supabase_options=supabase_options,
        )
    return TimelineStreamRef(
        backend="local_fs",
        timeline_id=timeline_id,
        home=None,
        source="default_local",
        supabase_options=supabase_options,
    )


def build_timeline_backend(stream: TimelineStreamRef) -> EventLogBackend:
    if stream.backend == "supabase":
        options = stream.supabase_options
        backend_kwargs = {
            "timeline_id": stream.timeline_id,
            "supabase_url": options.url if options is not None else None,
            "auth_token": options.auth_token if options is not None else None,
            "enabled": options is not None,
            "verified_subject": options.verified_subject if options is not None else None,
            "actor_id": options.actor_id if options is not None else None,
            "actor_display": options.actor_display if options is not None else None,
            "rpc_append_name": (
                options.rpc_append_name if options is not None else "append_timeline_event"
            ),
        }
        return SupabaseBackend(
            **backend_kwargs,
        )
    if stream.home is None:
        raise ValueError("local_fs timeline stream requires a timeline home")
    return LocalFsBackend(timeline_id=stream.timeline_id, timeline_home=stream.home)


def select_timeline_backend(
    *,
    timeline_id: str,
    timeline_home: str | Path | None = None,
    preferred_backend: str | None = None,
    supabase_options: SupabaseEventLogOptions | None = None,
) -> tuple[TimelineStreamRef, EventLogBackend]:
    stream = select_timeline_stream(
        timeline_id=timeline_id,
        timeline_home=timeline_home,
        preferred_backend=preferred_backend,
        supabase_options=supabase_options,
    )
    return stream, build_timeline_backend(stream)


# ============================================================================
# High-level event-log target resolution
# ============================================================================


@dataclass(frozen=True)
class EventLogTarget:
    """Resolved event-log target for backend operations.

    Distinct from ``ResolvedTarget`` (observability) — this carries
    the backend instance itself, so callers don't need to re-resolve.
    """

    backend_name: BackendName
    timeline_id: str
    timeline_ulid: str | None  # None for Supabase-only streams
    timeline_home: Path | None  # None for Supabase-only streams
    slug: str | None
    backend: EventLogBackend
    source: str  # 'local', 'supabase', 'imported'


def resolve_event_log_target(
    project_slug: str,
    slug_or_id: str,
    *,
    root: str | Path | None = None,
    preferred_backend: str | None = None,
) -> EventLogTarget:
    """Resolve a timeline to a concrete event-log backend.

    Resolution strategy:
    1. If *preferred_backend* is ``"supabase"``, resolve as a Supabase
       stream (no local filesystem scanning).  Supabase credentials are
       required only for this path.
    2. Otherwise, use the local-project resolver (``resolve_timeline_target``
       from observability) to find a local timeline.
    3. If the local timeline's identity declares backend ``supabase``,
       build a Supabase backend for that stream.

    Supabase credentials are **only** required when *preferred_backend* is
    ``"supabase"`` or when a local timeline's identity sidecar declares
    ``backend: supabase``.  Local-only commands work without any Supabase
    environment variables.
    """
    # Strategy 1: Explicit Supabase backend
    if preferred_backend == "supabase":
        return _resolve_supabase_target(project_slug, slug_or_id, root=root)

    # Strategy 2: Local resolver
    from astrid.core.timeline.observability import resolve_timeline_target

    target = resolve_timeline_target(project_slug, slug_or_id, root=root)

    # Strategy 3: Local timeline with Supabase backend declared in identity
    if target.backend == "supabase":
        # Build Supabase backend for this stream
        return _resolve_supabase_target(
            project_slug,
            target.timeline_id,
            root=root,
            timeline_home=target.timeline_home,
        )

    # Default: LocalFs
    backend = LocalFsBackend(
        timeline_id=target.timeline_id,
        timeline_home=target.timeline_home,
    )
    return EventLogTarget(
        backend_name="local_fs",
        timeline_id=target.timeline_id,
        timeline_ulid=target.timeline_ulid,
        timeline_home=target.timeline_home,
        slug=target.slug,
        backend=backend,
        source="local",
    )


# ============================================================================
# Pull destination resolution
# ============================================================================


@dataclass(frozen=True)
class PullDestination:
    """Resolved pull destination for cross-backend transfer."""

    target: EventLogTarget
    """The resolved local destination."""

    created: bool
    """True when the local home was created by this resolution (not pre-existing)."""

    identity_path: Path | None
    """Path to assembly.identity.json when created, None otherwise."""


def resolve_pull_destination(
    project_slug: str,
    *,
    into: str | None = None,
    create_as: str | None = None,
    create: bool = False,
    remote_source_slug: str | None = None,
    remote_source_timeline_id: str | None = None,
    root: str | Path | None = None,
) -> PullDestination:
    """Resolve the **local** destination for a pull operation.

    Source resolution happens separately via *remote_source_slug* and
    *remote_source_timeline_id*.  This function only handles the local
    destination side.

    Destination binding (in priority order):
    1. ``--into <slug>``: pull into an existing local timeline.
    2. ``--create --as <slug>``: create a new local timeline home.
    3. ``--create`` with no ``--as``: implicit creation when the remote
       stream identity exposes exactly one safe slug with no local collision.
    4. Anything else: error — ambiguous destination refused before writes.

    When a new local home is created, ``assembly.identity.json`` is written
    with ``provenance: imported`` (not ``provenance: created``).

    Raises:
        ValueError: When destination is ambiguous or invalid.
    """

    from astrid.core.timeline.paths import (
        find_timeline_by_slug,
        timelines_dir,
        validate_timeline_slug,
    )

    td = timelines_dir(project_slug, root=root)

    # Priority 1: --into <existing-slug>
    if into is not None:
        found = find_timeline_by_slug(project_slug, into, root=root)
        if found is None:
            raise ValueError(
                f"pull destination '--into {into}' not found: "
                f"no timeline with slug '{into}' in project '{project_slug}'"
            )
        ulid, tdir = found
        return _build_pull_destination_for_existing(
            project_slug, ulid, tdir, root=root, created=False
        )

    # Priority 2: --create --as <slug>
    if create and create_as is not None:
        slug = validate_timeline_slug(create_as)
        existing = find_timeline_by_slug(project_slug, slug, root=root)
        if existing is not None:
            raise ValueError(
                f"pull destination '--create --as {slug}' already exists "
                f"in project '{project_slug}' (ULID {existing[0]}); "
                f"use '--into {slug}' to pull into the existing timeline"
            )
        return _create_pull_destination(
            project_slug, slug, remote_source_timeline_id, root=root
        )

    # Priority 3: --create (no --as) — implicit creation
    if create:
        if remote_source_slug is None:
            raise ValueError(
                "pull --create requires either --as <slug> or a remote source "
                "with identifiable slug metadata"
            )
        slug = _safe_slug_from_remote(remote_source_slug)
        if slug is None:
            raise ValueError(
                f"pull --create cannot derive a safe slug from remote source "
                f"'{remote_source_slug}'; use --as to specify an explicit slug"
            )
        existing = find_timeline_by_slug(project_slug, slug, root=root)
        if existing is not None:
            raise ValueError(
                f"pull --create cannot use implicit slug '{slug}': "
                f"it already exists in project '{project_slug}'; "
                f"use '--into {slug}' or '--as <other>'"
            )
        return _create_pull_destination(
            project_slug, slug, remote_source_timeline_id, root=root
        )

    # Anything else: ambiguous
    raise ValueError(
        "pull requires a local destination: use --into <existing-slug>, "
        "--create --as <new-slug>, or --create (with identifiable remote slug)"
    )


# ============================================================================
# Internal helpers
# ============================================================================


def _resolve_supabase_target(
    project_slug: str,
    timeline_id: str,
    *,
    root: str | Path | None = None,
    timeline_home: Path | None = None,
) -> EventLogTarget:
    """Build a Supabase-backed EventLogTarget.

    Supabase credentials are required here — this should only be called
    when ``preferred_backend="supabase"`` or when the local identity
    sidecar declares ``backend: supabase``.
    """
    import os

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Supabase backend requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "environment variables"
        )

    options = SupabaseEventLogOptions(
        url=supabase_url,
        auth_token=supabase_key,
    )
    stream = TimelineStreamRef(
        backend="supabase",
        timeline_id=timeline_id,
        home=timeline_home,
        source="preferred_backend",
        supabase_options=options,
    )
    backend = build_timeline_backend(stream)
    return EventLogTarget(
        backend_name="supabase",
        timeline_id=timeline_id,
        timeline_ulid=None,
        timeline_home=timeline_home,
        slug=None,
        backend=backend,
        source="supabase",
    )


def _build_pull_destination_for_existing(
    project_slug: str,
    timeline_ulid: str,
    timeline_home: Path,
    *,
    root: str | Path | None = None,
    created: bool = False,
) -> PullDestination:
    """Build a PullDestination for an existing timeline home."""
    from astrid.core.project.jsonio import read_json
    from astrid.core.timeline.paths import assembly_identity_path

    # Read identity to get timeline_id
    identity_path = assembly_identity_path(project_slug, timeline_ulid, root=root)
    try:
        identity = read_json(identity_path)
    except Exception:
        raise ValueError(
            f"pull destination timeline {timeline_ulid} has no readable "
            f"assembly.identity.json"
        )

    if not isinstance(identity, dict):
        raise ValueError(
            f"pull destination timeline {timeline_ulid} has invalid identity"
        )

    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str):
        raise ValueError(
            f"pull destination timeline {timeline_ulid} identity missing timeline_id"
        )

    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=timeline_home)
    target = EventLogTarget(
        backend_name="local_fs",
        timeline_id=timeline_id,
        timeline_ulid=timeline_ulid,
        timeline_home=timeline_home,
        slug=None,
        backend=backend,
        source="imported" if created else "local",
    )
    return PullDestination(
        target=target,
        created=created,
        identity_path=identity_path if created else None,
    )


def _create_pull_destination(
    project_slug: str,
    slug: str,
    remote_source_timeline_id: str | None,
    *,
    root: str | Path | None = None,
) -> PullDestination:
    """Create a new local timeline home for a pull destination.

    Writes ``assembly.identity.json`` with ``provenance: imported``.
    """
    from uuid import uuid4

    from astrid.core.project.jsonio import write_json_atomic
    from astrid.core.timeline.banodoco_schema import canonical_empty_timeline
    from astrid.core.timeline.events.schema import EVENT_SCHEMA_VERSION
    from astrid.core.timeline.model import (
        TIMELINE_SCHEMA_VERSION,
        Display,
        Manifest,
    )
    from astrid.core.timeline.paths import (
        timeline_dir,
        validate_timeline_slug,
    )
    from astrid.core.util.time import utc_now_seconds as utc_now_iso

    slug = validate_timeline_slug(slug)
    timeline_id = str(uuid4())

    # Generate a ULID for the timeline directory
    from astrid.threads.ids import generate_ulid
    ulid = generate_ulid()

    tdir = timeline_dir(project_slug, ulid, root=root)
    tdir.mkdir(parents=True, exist_ok=False)

    # Write identity with provenance: imported
    identity = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "timeline_id": timeline_id,
        "timeline_ulid": ulid,
        "backend": "local_fs",
        "provenance": "imported",
        "created_at": utc_now_iso(),
    }
    if remote_source_timeline_id is not None:
        identity["source_timeline_id"] = remote_source_timeline_id

    identity_path = tdir / "assembly.identity.json"
    write_json_atomic(identity_path, identity)

    # Write a raw empty TimelineConfig, not a legacy wrapper.
    write_json_atomic(tdir / "assembly.json", canonical_empty_timeline())

    display = Display(
        schema_version=TIMELINE_SCHEMA_VERSION,
        slug=slug,
        name=slug,
        is_default=False,
    )
    display.write(tdir / "display.json")

    manifest = Manifest(
        schema_version=TIMELINE_SCHEMA_VERSION,
        contributing_runs=[],
        final_outputs=[],
        tombstoned_at=None,
    )
    manifest.write(tdir / "manifest.json")

    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tdir)
    target = EventLogTarget(
        backend_name="local_fs",
        timeline_id=timeline_id,
        timeline_ulid=ulid,
        timeline_home=tdir,
        slug=slug,
        backend=backend,
        source="imported",
    )
    return PullDestination(
        target=target,
        created=True,
        identity_path=identity_path,
    )


def _safe_slug_from_remote(remote_slug: str | None) -> str | None:
    """Derive a safe local slug from the remote source slug.

    Returns None when the remote slug cannot be safely transformed.
    """
    if remote_slug is None:
        return None
    # Basic sanitisation: lowercase, replace underscores with hyphens
    slug = remote_slug.lower().replace("_", "-")
    # Must match the slug regex
    import re
    if re.fullmatch(r"^[a-z][a-z0-9-]{0,31}$", slug):
        return slug
    return None
