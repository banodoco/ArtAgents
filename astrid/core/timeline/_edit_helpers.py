"""Shared internal helpers for timeline edit modules.

Extracted from ``clip_edits.py`` to avoid duplication across the seven
secondary domain edit modules (transition_edits, effect_edits, theme_edits,
track_edits, audio_edits, pool_edits, arrangement_edits).

Every public mutation function in the edit modules uses:

* ``_resolve_or_bootstrap_backend`` — locate the timeline, then resolve or
  bootstrap the event-log backend.  Handles three cases:
  1. Identity exists with provenance ``"created"`` → resolve backend normally,
     first domain event is bare (no ``timeline.imported``).
  2. No identity, no ``assembly.jsonl``, compatibility files exist →
     true-legacy bootstrap: emit ``timeline.imported`` via
     ``LocalFsBackend.bootstrap_legacy()``, write identity with provenance
     ``"imported"``, then resolve backend normally.
  3. Identity missing but ``assembly.jsonl`` already exists → fail closed.
* ``_materialize`` — post-append projection regenerator that calls
  ``regenerate_projection()`` to rewrite ``assembly.json`` from the
  canonical event stream.
* ``_default_actor`` — sensible system actor for editing operations
* ``TimelineEditError`` — shared exception base caught by the CLI handler

Pack / worker write paths use:

* ``pack_write_gateway`` — centralized append-then-regenerate gateway that
  accepts a managed binding tuple, resolves the backend through the legacy
  bootstrap seam (only true-legacy timelines with no identity sidecar get
  ``timeline.imported``; created timelines with provenance ``"created"``
  accept bare first domain events), appends events in a batch, regenerates
  ``assembly.json`` once from the canonical event stream, and returns a
  normalised ``PackWriteResult``. Batch-level CAS, soft-lock enforcement,
  and explicit transaction orchestration are intentionally deferred in m5.
* ``PackWriteResult`` — dataclass carrying new_version, event_ids, attempts,
  backend_name, timeline_ulid, timeline_slug, timeline_event_stream_id,
  and timeline_home.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import read_json

from .eventlog import EventLogBackend, select_timeline_backend
from .eventlog.local_fs import LocalFsBackend
from .events.schema import TimelineActor, TimelineEvent
from .paths import (
    assembly_identity_path,
    find_timeline_by_slug,
)
from .projection import regenerate_projection


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


def _locate_timeline(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, Path]:
    """Find the timeline ULID and home directory for *slug*.

    Returns ``(timeline_ulid, timeline_home)``.

    Raises ``TimelineEditError`` when the timeline cannot be found.
    """
    found = find_timeline_by_slug(project_slug, slug, root=root)
    if found is None:
        raise TimelineEditError(
            f"timeline '{slug}' not found in project '{project_slug}'"
        )
    return found  # (timeline_ulid, timeline_home)


def _resolve_or_bootstrap_backend(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
    actor: TimelineActor | None = None,
) -> tuple[str, Path, EventLogBackend, bool]:
    """Resolve the event-log backend, bootstrapping true-legacy timelines.

    Three cases
    -----------
    1. **Identity exists with provenance ``"created"``** —
       resolve the backend normally.  The first domain event is bare
       (no ``timeline.imported``).
    2. **No identity, no ``assembly.jsonl``, compatibility files exist** —
       true-legacy bootstrap.  Emit ``timeline.imported`` via
       ``LocalFsBackend.bootstrap_legacy()``, write identity with
       provenance ``"imported"``, then resolve.
    3. **Identity missing but ``assembly.jsonl`` already exists** —
       fail closed with a clear error.

    Returns ``(timeline_id, timeline_home, backend, bootstrap_performed)``.

    Raises ``TimelineEditError`` on any failure.
    """
    ulid, tdir = _locate_timeline(project_slug, slug, root=root)
    identity_path = assembly_identity_path(project_slug, ulid, root=root)
    jsonl_path = tdir / "assembly.jsonl"

    identity = None
    try:
        identity = read_json(identity_path)
    except FileNotFoundError:
        identity = None
    except Exception:
        identity = None

    # --- Case 1: Identity exists → resolve normally ---
    if isinstance(identity, dict):
        timeline_id = identity.get("timeline_id")
        if not isinstance(timeline_id, str) or not timeline_id:
            raise TimelineEditError(
                "timeline identity sidecar is missing timeline_id"
            )
        preferred_backend = identity.get("backend")
        if preferred_backend is not None and not isinstance(preferred_backend, str):
            raise TimelineEditError(
                "timeline identity sidecar has malformed backend"
            )
        _stream, backend = select_timeline_backend(
            timeline_id=timeline_id,
            timeline_home=tdir,
            preferred_backend=preferred_backend,
        )
        return timeline_id, tdir, backend, False

    # --- Case 3: No identity but assembly.jsonl already exists → fail closed ---
    if jsonl_path.is_file():
        raise TimelineEditError(
            f"timeline '{slug}' has an event log ({jsonl_path.name}) "
            f"but no identity sidecar.  This timeline may be corrupted "
            f"or was partially migrated.  Restore the identity sidecar "
            f"or delete the event log and retry."
        )

    # --- Case 2: No identity, no assembly.jsonl, compatibility files
    #     should exist → true-legacy bootstrap ---
    if actor is None:
        actor = _default_actor("bootstrap_legacy")

    # Construct a LocalFsBackend for the bootstrap.
    # We don't have a timeline_id yet, so use a temporary one.
    backend = LocalFsBackend(timeline_id="", timeline_home=tdir)
    new_timeline_id, _identity = backend.bootstrap_legacy(actor=actor)

    # Now resolve the backend with the newly written identity.
    timeline_id, tdir_resolved, backend_resolved, _ = _resolve_or_bootstrap_backend(
        project_slug, slug, root=root, actor=actor,
    )
    return timeline_id, tdir_resolved, backend_resolved, True


def _resolve_backend(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
) -> tuple[str, Path, EventLogBackend, bool]:
    """Look up *slug* in *project_slug*, read the identity sidecar, and
    return ``(timeline_id, timeline_home, backend, bootstrap_performed)``.

    Kept for backward compatibility with existing edit modules that call
    ``_resolve_backend`` directly.  Delegates to
    ``_resolve_or_bootstrap_backend``.

    Raises ``TimelineEditError`` when the timeline cannot be found or its
    identity sidecar is missing/malformed.
    """
    return _resolve_or_bootstrap_backend(project_slug, slug, root=root)


def _materialize(
    tdir: Path,
    event: TimelineEvent,
    *,
    timeline_id: str | None = None,
    backend: EventLogBackend | None = None,
) -> None:
    """Synchronous projection regenerator — m4 authority model.

    Regenerates ``assembly.json`` from the canonical event stream via
    ``regenerate_projection()``.  This is the single shared post-append
    materialization helper used by all edit modules and
    ``pack_write_gateway()``.

    When *timeline_id* and *backend* are provided, the full stream is
    replayed and ``assembly.json`` is atomically rewritten.  When they
    are ``None`` (backward-compatible callers), the call is a no-op:
    callers that haven't been updated yet will get projection repair
    from read-side entry points instead.

    Post-m4 there is no per-event ``materialize_event()`` delegation —
    the projector owns the authoritative applicator logic.
    """
    if timeline_id is not None and backend is not None:
        regenerate_projection(timeline_id, backend, timeline_home=tdir)


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
    ``bind_managed_timeline()``, resolves the event-log backend through
    the legacy bootstrap seam (only true-legacy timelines with no identity
    sidecar get ``timeline.imported``; created timelines with provenance
    ``"created"`` accept bare first domain events), appends every event,
    materializes compatibility outputs synchronously, and returns a
    normalised ``PackWriteResult``.

    Scope note
    ----------
    This helper remains a simple append loop in m5. It does not yet provide
    a pack-level ``expected_version`` / CAS boundary across the whole batch,
    soft-lock checks, or explicit transaction APIs; those require semantics
    beyond the per-event eventlog contract and are intentionally deferred.

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

    # 2. Resolve backend through the legacy bootstrap seam.
    #    Only true-legacy timelines (no identity sidecar, compatibility
    #    files present) get timeline.imported bootstrap.  Created timelines
    #    with provenance "created" accept bare first domain events.
    resolved_timeline_id, timeline_home, backend, bootstrap_emitted = \
        _resolve_or_bootstrap_backend(
            project_slug, timeline_slug, root=root, actor=actor,
        )
    effective_stream_id = resolved_timeline_id

    # 4. Append domain events (batch — no per-event materialization).
    event_ids: list[str] = []
    for event_spec in events:
        kind = event_spec["kind"]
        payload = event_spec.get("payload", {})
        event = backend.append_event(
            timeline_id=effective_stream_id,
            kind=kind,
            payload=payload,
            actor=actor,
        )
        event_ids.append(event.event_id)

    # 5. Regenerate assembly.json once from the canonical event stream.
    regenerate_projection(effective_stream_id, backend, timeline_home=timeline_home)

    # 6. Read final head for version.
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
