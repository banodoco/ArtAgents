"""Shared internal helpers for timeline edit modules.

Extracted from ``clip_edits.py`` to avoid duplication across the seven
secondary domain edit modules (transition_edits, effect_edits, theme_edits,
track_edits, audio_edits, pool_edits, arrangement_edits).

Every public mutation function in the edit modules uses:

* ``_resolve_backend`` — resolve (timeline_id, timeline_home, backend)
* ``_materialize`` — synchronous compatibility materializer (m4 removal seam)
* ``_default_actor`` — sensible system actor for editing operations
* ``TimelineEditError`` — shared exception base caught by the CLI handler

Pack / worker write paths (m3.5) use:

* ``pack_write_gateway`` — centralized append-then-materialize gateway that
  accepts a managed binding tuple, resolves the backend, handles first-write
  bootstrap (``timeline.imported``), appends events, materializes compatibility
  outputs, and returns a normalized ``PackWriteResult``.
* ``PackWriteResult`` — dataclass carrying new_version, event_ids, attempts,
  backend_name, timeline_ulid, timeline_slug, timeline_event_stream_id,
  and timeline_home.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import read_json

from .assembly_helper import materialize_event
from .eventlog import EventLogBackend, select_timeline_backend
from .events.schema import TimelineActor, TimelineEvent
from .paths import assembly_identity_path, find_timeline_by_slug


# ---------------------------------------------------------------------------
# Shared exception base
# ---------------------------------------------------------------------------


class TimelineEditError(RuntimeError):
    """Raised when a timeline edit cannot be completed.

    All domain edit modules (clip_edits, transition_edits, effect_edits,
    theme_edits, track_edits, audio_edits, pool_edits, arrangement_edits)
    raise this exception or a subclass.  The CLI entrypoint catches it
    via a single ``except TimelineEditError`` clause.
    """


# Backward-compatible alias for clip_edits
ClipEditError = TimelineEditError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_backend(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, Path, EventLogBackend]:
    """Look up *slug* in *project_slug*, read the identity sidecar, and
    return ``(timeline_id, timeline_home, backend)``.

    Raises ``TimelineEditError`` when the timeline cannot be found or its
    identity sidecar is missing/malformed.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise TimelineEditError(
            f"timeline '{slug}' not found in project '{project_slug}'"
        )
    ulid, tdir = found

    identity = read_json(assembly_identity_path(project_slug, ulid, root=root))
    if not isinstance(identity, dict):
        raise TimelineEditError("timeline identity sidecar is malformed")

    timeline_id = identity.get("timeline_id")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise TimelineEditError("timeline identity sidecar is missing timeline_id")

    preferred_backend = identity.get("backend")
    if preferred_backend is not None and not isinstance(preferred_backend, str):
        raise TimelineEditError("timeline identity sidecar has malformed backend")

    _stream, backend = select_timeline_backend(
        timeline_id=timeline_id,
        timeline_home=tdir,
        preferred_backend=preferred_backend,
    )
    return timeline_id, tdir, backend


def _materialize(tdir: Path, event: TimelineEvent) -> None:
    """Synchronous compatibility materializer call — m4 removal seam.

    Keeps ``assembly.json`` in sync with the event stream so that
    readers like ``crud.show_timeline()`` see the latest state
    before projection becomes authoritative in m4.

    A crash between ``append_event`` and this call leaves the event log
    ahead of ``assembly.json``.  Accept this window for m2+m3; m4 projection
    will close it.
    """
    materialize_event(tdir, event)


def _default_actor(fn_name: str) -> TimelineActor:
    """Return a sensible system actor for timeline editing operations."""
    return TimelineActor(
        type="system",
        id=f"timeline-edits:{fn_name}",
        display="timeline-edits",
    )


# ---------------------------------------------------------------------------
# Pack / worker write gateway (m3.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackWriteResult:
    """Normalized return from ``pack_write_gateway()``.

    Carries everything a pack or worker caller needs to know after
    appending events through the managed binding seam.
    """

    new_version: int
    """Event-stream version after appending all events (including bootstrap)."""

    event_ids: list[str]
    """ULID event ids of every event appended (bootstrap + domain), in order."""

    attempts: int
    """Number of events appended (bootstrap + domain)."""

    backend_name: str
    """Name of the backend that serviced the append (e.g. ``"local_fs"``)."""

    timeline_ulid: str
    """26-char Crockford ULID of the timeline container."""

    timeline_slug: str
    """Validated timeline slug."""

    timeline_event_stream_id: str
    """UUID from the timeline identity sidecar."""

    timeline_home: Path
    """Filesystem path to the timeline directory (for compatibility outputs)."""

    bootstrap_emitted: bool = False
    """True when ``timeline.imported`` was emitted before the first domain event."""

    # Ancillary handles (populated by callers that track artifacts).
    artifact_handles: dict[str, Any] = field(default_factory=dict)


def pack_write_gateway(
    project_slug: str,
    timeline_slug: str,
    timeline_ulid: str,
    timeline_event_stream_id: str,
    *,
    events: list[dict[str, Any]],
    actor: TimelineActor | None = None,
    actor_id: str | None = None,
    actor_type: str = "system",
    actor_display: str | None = None,
    actor_via: TimelineActor | None = None,
    root: str | Path | None = None,
) -> PackWriteResult:
    """Centralized append-then-materialize gateway for pack / worker writes.

    Accepts the **managed binding tuple** produced by
    ``bind_managed_timeline()``, resolves the event-log backend, constructs
    an actor with optional ``actor.via`` chaining, handles first-write
    bootstrap (``timeline.imported`` before the first domain mutation when
    the stream is empty), appends every event, materializes compatibility
    outputs synchronously, and returns a normalised ``PackWriteResult``.

    Parameters
    ----------
    project_slug:
        Project that owns the timeline.
    timeline_slug:
        Validated timeline slug.
    timeline_ulid:
        26-char Crockford ULID of the timeline container.
    timeline_event_stream_id:
        UUID from the timeline identity sidecar (the ``timeline_id`` used
        by backend append operations).
    events:
        List of event dicts, each with keys ``"kind"`` (str) and
        ``"payload"`` (dict).  Appended in order.
    actor:
        Fully constructed ``TimelineActor``.  Takes precedence over
        ``actor_id`` / ``actor_type`` / ``actor_display`` / ``actor_via``.
    actor_id:
        Actor identifier when *actor* is not supplied.  Defaults to
        ``"pack-gateway:<timeline_ulid>"``.
    actor_type:
        One of ``"system"``, ``"agent"``, ``"human"``.  Default ``"system"``.
    actor_display:
        Human-readable display name for the actor.
    actor_via:
        When set, the outer actor represents the proximate writer and
        *actor_via* is chained as ``actor.via`` — preserving upstream
        provenance (e.g. the human or agent that launched the pack).
    root:
        Project root override.

    Returns
    -------
    PackWriteResult
        Normalised result carrying the version after appends, event ids,
        backend name, timeline identifiers, and the timeline home path.

    Raises
    ------
    TimelineEditError
        When the backend cannot be resolved or an append fails.
    """
    # 0. Resolve the ULID from the slug if the caller did not supply one
    # (packs that only know project+slug from CLI args rely on this).
    effective_ulid = timeline_ulid
    if not effective_ulid:
        found = find_timeline_by_slug(project_slug, timeline_slug, root=root)
        if found is not None:
            effective_ulid, _tdir = found

    # 1. Build the actor.
    if actor is None:
        effective_id = actor_id or f"pack-gateway:{effective_ulid}"
        actor = TimelineActor(
            type=actor_type,
            id=effective_id,
            display=actor_display,
            via=[actor_via] if actor_via is not None else None,
        )
    elif actor_via is not None:
        # Merge: wrap the supplied actor with the via chain.
        existing_via = list(actor.via) if actor.via else []
        actor = TimelineActor(
            type=actor.type,
            id=actor.id,
            display=actor.display,
            via=existing_via + [actor_via],
        )

    # 2. Resolve backend.
    resolved_timeline_id, timeline_home, backend = _resolve_backend(
        project_slug, timeline_slug, root=root
    )
    # Use the backend-resolved timeline_id for all append operations.
    effective_stream_id = resolved_timeline_id

    # 3. First-write bootstrap: emit timeline.imported when the stream is empty.
    bootstrap_emitted = False
    event_ids: list[str] = []
    head = backend.head()
    if head.event_count == 0:
        # Build a snapshot from the identity sidecar for the imported event.
        identity_path = assembly_identity_path(project_slug, effective_ulid, root=root)
        identity = read_json(identity_path)
        snapshot: dict[str, Any] = {
            "timeline_ulid": effective_ulid,
            "slug": timeline_slug,
        }
        if isinstance(identity, dict):
            for key in ("display", "schema_version", "provenance", "created_at"):
                if key in identity:
                    snapshot[key] = identity[key]

        imported_event = backend.append_event(
            timeline_id=effective_stream_id,
            kind="timeline.imported",
            payload={"snapshot": snapshot, "source": "legacy_local"},
            actor=actor,
        )
        # timeline.imported is a system bootstrap event — it does not mutate
        # assembly.json, so skip synchronous materialization.
        event_ids.append(imported_event.event_id)
        bootstrap_emitted = True

    # 4. Append domain events.
    for event_spec in events:
        kind = event_spec["kind"]
        payload = event_spec.get("payload", {})
        event = backend.append_event(
            timeline_id=effective_stream_id,
            kind=kind,
            payload=payload,
            actor=actor,
        )
        _materialize(timeline_home, event)
        event_ids.append(event.event_id)

    # 5. Read final head for version.
    final_head = backend.head()

    return PackWriteResult(
        new_version=final_head.version,
        event_ids=event_ids,
        attempts=len(event_ids),
        backend_name=backend.backend_name(),
        timeline_ulid=effective_ulid,
        timeline_slug=timeline_slug,
        timeline_event_stream_id=effective_stream_id,
        timeline_home=timeline_home,
        bootstrap_emitted=bootstrap_emitted,
    )
