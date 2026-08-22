"""Shared internal helpers for timeline edit modules.

Extracted from ``clip_edits.py`` to avoid duplication across the active
secondary domain edit modules (transition_edits, effect_edits, theme_edits,
track_edits, audio_edits).

Every public mutation function in the edit modules uses:

* ``_resolve_or_bootstrap_backend`` — locate the timeline, then resolve the
  event-log backend.  Handles two cases:
  1. Identity exists with provenance ``"created"`` → resolve backend normally,
     first domain event is bare (no ``timeline.imported``).
  2. Identity missing → fail closed. Legacy conversion is handled only by the
     Sprint 2 migration scripts.
* ``_materialize`` — post-append projection regenerator that calls
  ``regenerate_projection()`` to rewrite ``assembly.json`` from the
  canonical event stream.
* ``_default_actor`` — sensible system actor for editing operations
* ``TimelineEditError`` — shared exception base caught by the CLI handler

Pack / worker write paths use:

* ``pack_write_gateway`` — centralized append-then-regenerate gateway that
  accepts a managed binding tuple, resolves an identity-backed backend,
  appends events in a batch, regenerates ``assembly.json`` once from the
  canonical event stream, and returns a
  normalised ``PackWriteResult``. Batch-level CAS, soft-lock enforcement,
  and explicit transaction orchestration are intentionally deferred in m5.
* ``PackWriteResult`` — dataclass carrying new_version, event_ids, attempts,
  backend_name, timeline_ulid, timeline_slug, timeline_event_stream_id,
  and timeline_home.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json
from astrid.core.contracts.errors import AstridError
from astrid.core.events.registry import validate_event_kind
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry
from astrid.core.store.writer import DatabaseWriter

from .eventlog import EventLogBackend, select_timeline_backend
from .eventlog.types import SupabaseEventLogOptions
from .events.schema import TimelineActor, TimelineEvent
from .paths import (
    assembly_identity_path,
    find_timeline_by_slug,
)
from .projection import regenerate_projection

_composed_registry: FrozenSchemaPackRegistry | None = None
"""Process-wide composed standard registry cache for the pack write gateway.

Built once via the kernel-side composition (``astrid.core.schema_packs.
standard``) so this core module never imports ``astrid.packs``; validated
event kinds must be declared by the same composed registry the runtime
writer uses.
"""


def _composed_registry_or_build() -> FrozenSchemaPackRegistry:
    global _composed_registry
    if _composed_registry is None:
        from astrid.core.schema_packs.standard import build_standard_registry

        _composed_registry = build_standard_registry()
    return _composed_registry

# ---------------------------------------------------------------------------
# Shared exception base
# ---------------------------------------------------------------------------


class TimelineEditError(AstridError):
    """Raised when a timeline edit cannot be completed.

    All domain edit modules (clip_edits, transition_edits, effect_edits,
    theme_edits, track_edits, audio_edits)
    raise this exception or a subclass.  The CLI entrypoint catches it
    via a single ``except TimelineEditError`` clause.
    """

    def __init__(self, cause: str) -> None:
        super().__init__(cause)


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
    supabase_options: SupabaseEventLogOptions | None = None,
) -> tuple[str, Path, EventLogBackend, bool]:
    """Resolve the event-log backend for an identity-backed timeline.

    Three cases
    -----------
    1. **Identity exists with provenance ``"created"``** —
       resolve the backend normally.  The first domain event is bare
       (no ``timeline.imported``).
    2. **Identity missing** — fail closed with a clear migration error.

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
            raise TimelineEditError("timeline identity sidecar is missing timeline_id")
        preferred_backend = identity.get("backend")
        if preferred_backend is not None and not isinstance(preferred_backend, str):
            raise TimelineEditError("timeline identity sidecar has malformed backend")
        select_kwargs: dict[str, Any] = {"timeline_id": timeline_id, "timeline_home": tdir, "preferred_backend": preferred_backend}
        if supabase_options is not None:
            select_kwargs["supabase_options"] = supabase_options
        _stream, backend = select_timeline_backend(**select_kwargs)
        return timeline_id, tdir, backend, False
    # Identity missing: try kernel fallback for backfilled timelines (W4 sidecar disposable)
    try:
        from astrid.core.foundation.project_paths import resolve_projects_root as _resolve_pr
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _derive
        from astrid.packs.timeline.backfill import read_backfill_state as _read_state
        import sqlite3 as _sql
        _pr = _resolve_pr(root)
        # ulid is directory name
        ulid_try = tdir.name
        # Try kernel lookup by ulid
        _db = _derive(_pr)
        tl_id_k = None
        if _db.is_file():
            _conn = _sql.connect(str(_db))
            try:
                _conn.row_factory = _sql.Row
                _row = _conn.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_ulid')=? LIMIT 1", (ulid_try,)).fetchone()
                if _row and _row["tid"]:
                    tl_id_k = str(_row["tid"])
                else:
                    # Fallback: slug→ timeline_id via events where slug matches project+slug?
                    # Try direct slug lookup in timelines table via kernel repo not available; try events with slug
                    _row2 = _conn.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.slug')=? LIMIT 1", (slug,)).fetchone()
                    if _row2 and _row2["tid"]:
                        tl_id_k = str(_row2["tid"])
            finally:
                _conn.close()
            if tl_id_k:
                try:
                    _state = _read_state(_pr)
                    if tl_id_k in _state:
                        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend as _SqliteBE
                        be = _SqliteBE(timeline_id=tl_id_k, timeline_home=tdir, projects_root=_pr)
                        return tl_id_k, tdir, be, False
                except Exception:
                    pass
    except Exception:
        pass
    detail = (
        f"timeline '{slug}' has an event log ({jsonl_path.name}) but no identity sidecar"
        if jsonl_path.is_file()
        else f"timeline '{slug}' has no identity sidecar"
    )
    raise TimelineEditError(f"{detail}. Runtime legacy bootstrap is disabled; run the Sprint 2 migration before editing this timeline.")

def _resolve_backend(
    project_slug: str,
    slug: str,
    *,
    root: str | Path | None = None,
    supabase_options: SupabaseEventLogOptions | None = None,
) -> tuple[str, Path, EventLogBackend, bool]:
    """Look up *slug* in *project_slug*, read the identity sidecar, and
    return ``(timeline_id, timeline_home, backend, bootstrap_performed)``.

    Kept for backward compatibility with existing edit modules that call
    ``_resolve_backend`` directly.  Delegates to
    ``_resolve_or_bootstrap_backend``.

    Raises ``TimelineEditError`` when the timeline cannot be found or its
    identity sidecar is missing/malformed.
    """
    return _resolve_or_bootstrap_backend(
        project_slug,
        slug,
        root=root,
        supabase_options=supabase_options,
    )


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
    """ULID event ids of every event appended, in order."""

    attempts: int
    """Number of events appended."""

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
    """Always False; kept for compatibility with older result consumers."""

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
    supabase_options: SupabaseEventLogOptions | None = None,
    writer: DatabaseWriter | None = None,
    timeline_repository: Any | None = None,
    timeline_stream_type: str | None = None,
) -> PackWriteResult:
    """Centralized append-then-materialize gateway for pack / worker writes.

    Accepts the **managed binding tuple** produced by
    ``bind_managed_timeline()``, resolves an identity-backed event-log backend,
    appends every event, materializes compatibility outputs synchronously, and returns a
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
    writer:
        Optional kernel :class:`~astrid.core.store.writer.DatabaseWriter`.
        When supplied, every ``timeline.config_replaced`` event is
        additionally committed to the **kernel timeline store** through
        :meth:`astrid.packs.timeline.repository.TimelineRepository.replace_config`
        (the declared ``timeline.replace_config`` command) inside one
        ``UnitOfWork(writer)`` per event, with receipt key
        ``timeline.replace_config:{timeline_id}:{expected_version}`` —
        committed **before** the eventlog append (fail-closed: no eventlog
        event without its kernel receipt). When omitted (packs running
        without kernel access), the gateway keeps its eventlog-only
        behavior and no kernel receipt is written.

    Returns
    -------
    PackWriteResult
        Normalised result carrying the version after appends, event ids,
        backend name, timeline identifiers, and the timeline home path.

    Raises
    ------
    TimelineEditError
        When the backend cannot be resolved or an append fails.
    EventVocabularyError
        When any event kind is not declared by the composed standard
        registry (raised before any backend or append work).
    """
    # 0. Registry vocabulary gate (m8): every emitted kind must be declared
    # by the composed standard registry before any backend resolution,
    # bootstrap, or append — an undeclared kind rejects the whole batch
    # with zero side effects.
    registry = _composed_registry_or_build()
    for event_spec in events:
        validate_event_kind(registry, event_spec["kind"])

    # 0.5 Kernel replace_config commit (m2): when the caller supplies a
    # kernel writer, every timeline.config_replaced event is additionally
    # committed to the kernel timeline store through the repository command
    # Ensure kernel writer/repository available for atomic replace_config (W2).
    # Pack callers historically omit writer; we now obtain it via the standard seam
    # so whole-document saves are always document_json+registry+event in ONE txn.
    effective_writer = writer
    effective_repo = timeline_repository
    effective_stream_type = timeline_stream_type
    _owns_effective_writer = False
    _writer_lock = None
    if effective_writer is None:
        # Try to compose standard writer (requires projects_root)
        try:
            from astrid.core.foundation.project_paths import resolve_projects_root as _resolve_root
            from astrid.core.integrations.reigh.bridge_service import derive_database_path as _derive_db
            from astrid.core.store.ownership import DatabaseOwnerLock as _OwnerLock
            from astrid.packs import build_standard_registry as _build_reg, open_standard_writer as _open_writer
            from astrid.core.events.service import EventAppendService as _EvtSvc
            from astrid.core.receipts.service import ReceiptService as _ReceiptSvc
            from astrid.core.repositories.projects import ProjectRepository as _ProjRepo
            from astrid.packs.timeline.repository import TimelineRepository as _TLRepo
            _projects_root = _resolve_root(root)
            _db_path = _derive_db(_projects_root)
            _db_path.parent.mkdir(parents=True, exist_ok=True)
            # Readers exempt, but writer needs exclusive owner; try lock, but if fails
            # fall back to no-writer (legacy) rather than raising — fail-closed handled downstream.
            try:
                _writer_lock = _OwnerLock(_db_path)
            except Exception:
                _writer_lock = None
            if _writer_lock is not None or _db_path.is_file():
                _reg = _build_reg()
                effective_writer = _open_writer(_db_path, registry=_reg)
                _owns_effective_writer = True
                if effective_repo is None:
                    _evt = _EvtSvc(_reg)
                    _rcpt = _ReceiptSvc()
                    _proj = _ProjRepo(events=_evt, receipts=_rcpt)
                    effective_repo = _TLRepo(events=_evt, receipts=_rcpt, projects=_proj)
                    effective_stream_type = "timeline.timeline"
        except Exception:
            effective_writer = None
    # If we now have a writer/repo, handle timeline.config_replaced atomically
    if effective_writer is not None and effective_repo is not None and effective_stream_type:
        from astrid.core.events.service import EventAppendService
        from astrid.core.receipts.service import ReceiptService
        from astrid.core.repositories.projects import ProjectRepository
        from astrid.core.store.uow import UnitOfWork
        registry = _composed_registry_or_build()
        kernel_events = EventAppendService(registry)
        kernel_receipts = ReceiptService()
        kernel_projects = ProjectRepository(events=kernel_events, receipts=kernel_receipts)
        kernel_timelines = effective_repo
        try:
            project_id = kernel_projects.resolve(effective_writer, project_slug)
        except Exception:
            project_id = None
        if project_id is not None:
            def _commit_replace_config(payload: Mapping[str, Any]) -> None:
                def run(uow: UnitOfWork) -> None:
                    timeline_id = kernel_timelines._resolve_id(uow, project_id, timeline_slug)
                    head = uow.query_one("SELECT head_seq FROM event_streams WHERE id = ?", (f"{timeline_id}:{effective_stream_type}",))
                    if head is None:
                        raise TimelineEditError(f"timeline {timeline_slug!r} in project {project_slug!r} has no kernel event stream")
                    config = payload.get("config", {})
                    reg = payload.get("asset_registry")
                    if reg is None:
                        reg = {"assets": {}}
                    if not isinstance(config, Mapping):
                        raise TimelineEditError("config_replaced payload.config must be a JSON object")
                    if not isinstance(reg, Mapping):
                        raise TimelineEditError("config_replaced payload.asset_registry must be a JSON object")
                    kernel_timelines.replace_config(uow, project_id=project_id, ref=timeline_slug, config=dict(config), registry=dict(reg), expected_version=int(head["head_seq"]), idempotency_key=f"timeline.replace_config:{timeline_id}:{head['head_seq']}")
                UnitOfWork(effective_writer).run(run)
            for event_spec in events:
                if event_spec["kind"] == "timeline.config_replaced":
                    _commit_replace_config(event_spec.get("payload", {}))
            # For config_replaced, document already updated atomically; skip backend append for that kind
            # Track that we handled it
            _config_replaced_handled = any(e["kind"] == "timeline.config_replaced" for e in events)
        else:
            _config_replaced_handled = False
    else:
        _config_replaced_handled = False

    # 4. Append domain events (batch — no per-event materialization).
    event_ids: list[str] = []
    for event_spec in events:
        if _config_replaced_handled and event_spec["kind"] == "timeline.config_replaced":
            # Already committed atomically via replace_config; count it without second append
            # Retrieve last event id from backend head later
            continue
        kind = event_spec["kind"]
        payload = event_spec.get("payload", {})
        event = backend.append_event(timeline_id=effective_stream_id, kind=kind, payload=payload, actor=actor)
        event_ids.append(event.event_id)
    # If config_replaced was handled, fetch its event id from kernel head
    if _config_replaced_handled:
        try:
            last = backend.head()
            if last.last_event_id:
                event_ids.append(last.last_event_id)
        except Exception:
            pass
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
