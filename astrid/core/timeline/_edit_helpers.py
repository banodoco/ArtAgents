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
    # H2 kernel-first authoritative resolution: ULID/dir -> marker/kernel binding FIRST;
    # sidecar consulted ONLY for unbackfilled legacy. This subsumes is_backfilled usage.
    from astrid.core.timeline.authority import resolve_authoritative_timeline_id

    auth_tid = resolve_authoritative_timeline_id(tdir, root)
    if isinstance(auth_tid, str) and auth_tid:
        # Authoritative id found — check if backfilled to force SQLite authority.
        try:
            import importlib as _il_bf

            from astrid.core.timeline.authority import is_backfilled_timeline as _isbf
            _bfm = _il_bf.import_module("astrid.packs.timeline.backfill")
            BackfillErrorAuth = _bfm.BackfillError  # type: ignore[attr-defined]
            try:
                if _isbf(auth_tid, root):
                    from astrid.core.foundation.project_paths import (
                        resolve_projects_root as _rr_auth,
                    )
                    from astrid.core.timeline.eventlog.sqlite_backend import (
                        SqliteEventLogBackend as _SBEAuth,
                    )
                    _pr_auth = _rr_auth(root)
                    # Derive.projects_root from tdir if layout matches
                    try:
                        td_par = tdir.parent
                        if td_par.name == "timelines" and td_par.parent.is_dir():
                            _pr_auth = td_par.parent.parent
                    except Exception:
                        pass
                    return auth_tid, tdir, _SBEAuth(timeline_id=auth_tid, timeline_home=tdir, projects_root=_pr_auth), False
            except BackfillErrorAuth:
                raise
            except Exception:
                pass
        except Exception:
            pass
        # If not backfilled or check failed, fall through to sidecar-driven selection
        # but still use auth_tid as preferred (for legacy unbackfilled sidecarless case, auth_tid is sidecar id)
        # For legacy backfilled==False, we still need preferred_backend from sidecar if present.
        # Use select_timeline_backend with auth_tid to ensure legacy path still works.
        try:
            identity_side = None
            try:
                identity_side = read_json(assembly_identity_path(project_slug, ulid, root=root))
            except Exception:
                identity_side = None
            pref = None
            if isinstance(identity_side, dict):
                pref = identity_side.get("backend")
                if pref is not None and not isinstance(pref, str):
                    raise TimelineEditError("timeline identity sidecar has malformed backend")
            sel_kwargs: dict[str, Any] = {"timeline_id": auth_tid, "timeline_home": tdir, "preferred_backend": pref}
            if supabase_options is not None:
                sel_kwargs["supabase_options"] = supabase_options
            _st, be = select_timeline_backend(**sel_kwargs)
            return auth_tid, tdir, be, False
        except TimelineEditError:
            raise
        except Exception:
            pass
    # Fallback legacy path (no authoritative id): original sidecar-or-kernel logic
    identity_path = assembly_identity_path(project_slug, ulid, root=root)
    jsonl_path = tdir / "assembly.jsonl"
    identity = None
    try:
        identity = read_json(identity_path)
    except FileNotFoundError:
        identity = None
    except Exception:
        identity = None
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
    try:
        import importlib as _il

        from astrid.core.foundation.project_paths import resolve_projects_root as _resolve_pr
        from astrid.core.integrations.reigh.bridge_service import derive_database_path as _derive
        _bf_mod = _il.import_module("astrid.packs.timeline.backfill")
        _read_state = _bf_mod.read_backfill_state  # type: ignore[attr-defined]
        BackfillError = _bf_mod.BackfillError  # type: ignore[attr-defined]
        import sqlite3 as _sql
        _pr = _resolve_pr(root)
        ulid_try = tdir.name
        _db = _derive(_pr)
        tl_id_k = None
        if _db.is_file():
            _conn = _sql.connect(f"file:{_db}?mode=ro", uri=True)
            try:
                _conn.row_factory = _sql.Row
                _row = _conn.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.timeline_ulid')=? LIMIT 1", (ulid_try,)).fetchone()
                if _row and _row["tid"]:
                    tl_id_k = str(_row["tid"])
                else:
                    _row2 = _conn.execute("SELECT json_extract(payload_json,'$.data.timeline_id') as tid FROM events WHERE kind='timeline.created' AND json_extract(payload_json,'$.data.slug')=? LIMIT 1", (slug,)).fetchone()
                    if _row2 and _row2["tid"]:
                        tl_id_k = str(_row2["tid"])
            finally:
                _conn.close()
            if tl_id_k:
                try:
                    _state = _read_state(_pr)
                    if tl_id_k in _state:
                        from astrid.core.timeline.eventlog.sqlite_backend import (
                            SqliteEventLogBackend as _SqliteBE,
                        )
                        be = _SqliteBE(timeline_id=tl_id_k, timeline_home=tdir, projects_root=_pr)
                        return tl_id_k, tdir, be, False
                except BackfillError:
                    raise
                except Exception as exc:
                    raise TimelineEditError(f"backfill authority marker is unreadable: {exc}") from exc
    except BackfillError:
        raise
    except TimelineEditError:
        raise
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
    ``bind_managed_timeline()``, resolves an identity-backed event-log backend
    (including the kernel-fallback-for-backfilled-sidecarless path), ensures
    a kernel writer under :class:`DatabaseOwnerLock` for whole-document
    ``timeline.config_replaced`` (atomic ``replace_config``: ``document_json`` +
    ``asset_registry_json`` + event in one transaction, receipt
    ``timeline.replace_config:{timeline_id}:{expected_version}``), appends
    remaining events, then materializes ``assembly.json`` once.

    Writer ownership is fail-closed: if a kernel database file exists and
    another owner holds the lock, a typed :class:`TimelineEditError` is
    raised and no writer is opened. Eventlog-only legacy behavior is
    permitted **only** when no kernel database file exists at all
    (un-backfilled directories).
    """
    # 0. Registry vocabulary gate
    registry = _composed_registry_or_build()
    for event_spec in events:
        validate_event_kind(registry, event_spec["kind"])

    # 1. Resolve ULID fallback when caller only knows slug
    effective_ulid = timeline_ulid
    if not effective_ulid:
        found = find_timeline_by_slug(project_slug, timeline_slug, root=root)
        if found is not None:
            effective_ulid, _ = found

    # 2. Build actor
    if actor is None:
        effective_id = actor_id or f"pack-gateway:{effective_ulid}"
        actor = TimelineActor(
            type=actor_type,  # type: ignore[arg-type]
            id=effective_id,
            display=actor_display,
            via=[actor_via] if actor_via is not None else None,
        )
    elif actor_via is not None:
        existing_via = list(actor.via) if actor.via else []
        actor = TimelineActor(
            type=actor.type,
            id=actor.id,
            display=actor.display,
            via=existing_via + [actor_via],
        )

    # 3. Resolve identity-backed backend (includes kernel fallback for backfilled sidecar-less).
    resolved_timeline_id, timeline_home, backend, bootstrap_emitted = _resolve_or_bootstrap_backend(
        project_slug,
        timeline_slug,
        root=root,
        actor=actor,
        supabase_options=supabase_options,
    )
    effective_stream_id = resolved_timeline_id

    # 4. Handle whole-document saves atomically when needed.
    #    Kernel replace_config is required whenever a config_replaced event is present
    #    AND a kernel DB file exists (backfilled). Eventlog-only is allowed only when
    #    no DB file exists (un-backfilled legacy).
    wants_config_replaced = any(e.get("kind") == "timeline.config_replaced" for e in events)
    _config_replaced_handled = False
    effective_writer = writer
    effective_repo = timeline_repository
    effective_stream_type = timeline_stream_type
    _owns_effective_writer = False
    _writer_lock = None
    _compose_projects_root = None
    _compose_db_path = None
    if wants_config_replaced:
        if effective_writer is None:
            # Determine if we are in legacy (no DB file) or backfilled (DB exists).
            from astrid.core.foundation.project_paths import resolve_projects_root as _resolve_root
            from astrid.core.integrations.reigh.bridge_service import (
                derive_database_path as _derive_db,
            )

            _compose_projects_root = _resolve_root(root)
            _compose_db_path = _derive_db(_compose_projects_root)
            if not _compose_db_path.is_file():
                # Un-backfilled directory: legacy eventlog-only permitted explicitly.
                _config_replaced_handled = False
            else:
                # Backfilled: must acquire owner lock fail-closed, then open writer.
                import importlib as _il2

                from astrid.core.store.ownership import DatabaseOwnerLock as _OwnerLock
                from astrid.core.store.ownership import OwnerLockError as _OwnerLockError
                _packs_mod = _il2.import_module("astrid.packs")
                _build_reg = _packs_mod.build_standard_registry  # type: ignore[attr-defined]
                _open_writer = _packs_mod.open_standard_writer  # type: ignore[attr-defined]
                from astrid.core.events.service import EventAppendService as _EvtSvc
                from astrid.core.receipts.service import ReceiptService as _ReceiptSvc
                from astrid.core.repositories.projects import ProjectRepository as _ProjRepo
                _tl_mod = _il2.import_module("astrid.packs.timeline.repository")
                _TLRepo = _tl_mod.TimelineRepository  # type: ignore[attr-defined]

                try:
                    _writer_lock = _OwnerLock(_compose_db_path)
                except _OwnerLockError as exc:
                    raise TimelineEditError(f"database is already owned: {exc}") from exc
                except OSError as exc:
                    raise TimelineEditError(f"database owner lock failed: {exc}") from exc
                try:
                    _reg = _build_reg()
                except Exception as exc:
                    try:
                        _writer_lock.release()
                    except Exception:
                        pass
                    raise TimelineEditError(f"failed to build registry for writer: {exc}") from exc
                try:
                    effective_writer = _open_writer(_compose_db_path, registry=_reg)
                except Exception as exc:
                    try:
                        _writer_lock.release()
                    except Exception:
                        pass
                    raise TimelineEditError(f"failed to open writer: {exc}") from exc
                _owns_effective_writer = True
                if effective_repo is None:
                    _evt = _EvtSvc(_reg)
                    _rcpt = _ReceiptSvc()
                    _proj = _ProjRepo(events=_evt, receipts=_rcpt)
                    effective_repo = _TLRepo(events=_evt, receipts=_rcpt, projects=_proj)
                    effective_stream_type = "timeline.timeline"
        # If we now have a writer/repo, commit replace_config atomically for each config_replaced payload.
        if effective_writer is not None and effective_repo is not None and effective_stream_type:
            from astrid.core.events.service import EventAppendService
            from astrid.core.receipts.service import ReceiptService
            from astrid.core.repositories.projects import ProjectRepository
            from astrid.core.store.uow import UnitOfWork

            kernel_events = EventAppendService(registry)
            kernel_receipts = ReceiptService()
            kernel_projects = ProjectRepository(events=kernel_events, receipts=kernel_receipts)
            kernel_timelines = effective_repo
            # Resolve project_id fail-closed
            try:
                project_id = kernel_projects.resolve(effective_writer, project_slug)
            except Exception as exc:
                if _owns_effective_writer:
                    try:
                        effective_writer.close()
                    except Exception:
                        pass
                    try:
                        if _writer_lock is not None:
                            _writer_lock.release()
                    except Exception:
                        pass
                raise TimelineEditError(f"failed to resolve project {project_slug!r}: {exc}") from exc
            if project_id is None:
                if _owns_effective_writer:
                    try:
                        effective_writer.close()
                    except Exception:
                        pass
                    try:
                        if _writer_lock is not None:
                            _writer_lock.release()
                    except Exception:
                        pass
                raise TimelineEditError(f"project {project_slug!r} not found in kernel store")
            def _commit_replace_config(payload: Mapping[str, Any]) -> None:
                def run(uow: UnitOfWork) -> None:
                    timeline_id = kernel_timelines.resolve_id(uow, project_id, timeline_slug)
                    head = uow.query_one("SELECT head_seq FROM event_streams WHERE id = ?", (f"{timeline_id}:{effective_stream_type}",))
                    if head is None:
                        raise TimelineEditError(f"timeline {timeline_slug!r} in project {project_slug!r} has no kernel event stream")
                    current_head = int(head["head_seq"])
                    raw_expected = payload.get("expected_version")
                    if isinstance(raw_expected, bool):
                        raise TimelineEditError("payload.expected_version must be an integer")
                    if raw_expected is not None:
                        if not isinstance(raw_expected, int):
                            raise TimelineEditError("payload.expected_version must be an integer")
                        if raw_expected != current_head:
                            from astrid.core.timeline.eventlog.types import (
                                EventLogStaleVersionError,
                                TimelineVersionConflict,
                            )
                            raise EventLogStaleVersionError(TimelineVersionConflict(timeline_id=timeline_id, expected_version=raw_expected, current_version=current_head, last_event_id=None, last_event_kind=None, last_event_summary=None))
                        expected_version = raw_expected
                    else:
                        expected_version = current_head
                    config = payload.get("config", {})
                    if "registry" in payload:
                        reg = payload.get("registry")
                        if reg is None:
                            raise TimelineEditError("config_replaced payload.registry must be an object when present")
                    elif "asset_registry" in payload:
                        reg = payload.get("asset_registry")
                    else:
                        reg = None
                    if reg is None:
                        cur = uow.query_one("SELECT asset_registry_json FROM timelines WHERE id = ?", (timeline_id,))
                        if cur is not None and cur["asset_registry_json"]:
                            try:
                                from astrid.core.receipts.canonical import parse_json as _parse
                                cur_reg = _parse(cur["asset_registry_json"])
                                if isinstance(cur_reg, dict):
                                    reg = {"assets": dict(cur_reg)}
                                else:
                                    reg = {"assets": {}}
                            except Exception:
                                reg = {"assets": {}}
                        else:
                            reg = {"assets": {}}
                    if not isinstance(config, Mapping):
                        raise TimelineEditError("config_replaced payload.config must be a JSON object")
                    if not isinstance(reg, Mapping):
                        raise TimelineEditError("config_replaced payload.registry must be a JSON object")
                    kernel_timelines.replace_config(uow, project_id=project_id, ref=timeline_slug, config=dict(config), registry=dict(reg), expected_version=expected_version, idempotency_key=f"timeline.replace_config:{timeline_id}:{expected_version}")
                UnitOfWork(effective_writer).run(run)
            try:
                for event_spec in events:
                    if event_spec["kind"] == "timeline.config_replaced":
                        _commit_replace_config(event_spec.get("payload", {}))
                _config_replaced_handled = any(e["kind"] == "timeline.config_replaced" for e in events)
            except TimelineEditError:
                raise
            except Exception as exc:
                raise TimelineEditError(f"replace_config failed: {exc}") from exc
            finally:
                if _owns_effective_writer:
                    try:
                        effective_writer.close()
                    except Exception:
                        pass
                    try:
                        if _writer_lock is not None:
                            _writer_lock.release()
                    except Exception:
                        pass
                    effective_writer = None
                    _writer_lock = None
        elif wants_config_replaced and _compose_db_path is not None and _compose_db_path.is_file():
            # Backfilled but no repo/stream type to perform atomic replace — fail closed.
            raise TimelineEditError("backfilled timeline requires kernel replace_config for whole-document saves")

    # 5. Append domain events (batch — no per-event materialization).
    #    For config_replaced already handled atomically, skip second append.
    event_ids: list[str] = []
    for event_spec in events:
        if _config_replaced_handled and event_spec["kind"] == "timeline.config_replaced":
            continue
        kind = event_spec["kind"]
        payload = event_spec.get("payload", {})
        event = backend.append_event(timeline_id=effective_stream_id, kind=kind, payload=payload, actor=actor)
        event_ids.append(event.event_id)
    # If config_replaced was handled, fetch its event id from backend head
    if _config_replaced_handled:
        try:
            last = backend.head()
            if last.last_event_id:
                event_ids.append(last.last_event_id)
        except Exception:
            pass
    # 6. Regenerate assembly.json once from the canonical event stream.
    regenerate_projection(effective_stream_id, backend, timeline_home=timeline_home)

    # 7. Read final head for version.
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
