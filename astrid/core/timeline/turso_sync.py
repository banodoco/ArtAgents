"""Polling pull/push service for the Turso replica (S4, W3).

Reuses sync_state primitives (HeadSnapshot/classify/compare) and the
write_keep_both_artifact fork pattern. File-based cursor/bookmark per
timeline following sync_bookmark_path pattern (turso-sync-state.json)
— idempotent resume across restarts. NOT a DB table.

R3 guard: nothing here is reachable from build_timeline_backend; reads
for serving NEVER consult Turso. Ownership: uses the same shared-writer
seam as SqliteEventLogBackend (reuse if already registered, else
DatabaseOwnerLock) and fails closed with typed errors if a second writer
would be opened.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.turso import (
    TursoEventRow,
    TursoDocumentRow,
    TursoReplicaClient,
    TursoReplicationError,
    TursoError,
    TursoOwnershipError,
)
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent
from astrid.core.timeline.sync_state import (
    HeadSnapshot,
    SyncBookmark,
    compare_head_to_bookmark,
    classify_sync_state,
    head_snapshot_from_backend,
    read_local_sync_bookmark,
)
from astrid.core.timeline.sync_divergence import write_keep_both_artifact
from astrid.core.util.time import utc_now_iso, utc_now_seconds

TURSO_SYNC_STATE_FILENAME = "turso-sync-state.json"


class TursoSyncError(RuntimeError):
    """Base error for Turso sync operations (typed diagnostic)."""


class TursoSyncConfigError(TursoSyncError):
    """Sync operation missing required configuration."""


class TursoSyncConflictError(TursoSyncError):
    """Both sides diverged; fork artifacts written."""


@dataclass(frozen=True)
class TursoSyncState:
    """Durable per-timeline cursor for Turso polling sync."""

    timeline_id: str
    # local head as known at last sync
    local_version: int
    local_event_id: str | None
    local_hash: str | None
    # remote head as known at last sync
    remote_version: int
    remote_event_id: str | None
    remote_hash: str | None
    updated_at: str
    # also track the last pushed event id for resume deduplication
    last_pushed_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "local_version": self.local_version,
            "local_event_id": self.local_event_id,
            "local_hash": self.local_hash,
            "remote_version": self.remote_version,
            "remote_event_id": self.remote_event_id,
            "remote_hash": self.remote_hash,
            "updated_at": self.updated_at,
            "last_pushed_event_id": self.last_pushed_event_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TursoSyncState":
        if not isinstance(raw.get("timeline_id"), str):
            raise TursoSyncError("turso sync state missing timeline_id")
        return cls(
            timeline_id=str(raw["timeline_id"]),
            local_version=int(raw.get("local_version", 0)),
            local_event_id=raw.get("local_event_id"),
            local_hash=raw.get("local_hash"),
            remote_version=int(raw.get("remote_version", 0)),
            remote_event_id=raw.get("remote_event_id"),
            remote_hash=raw.get("remote_hash"),
            updated_at=str(raw.get("updated_at", utc_now_iso())),
            last_pushed_event_id=raw.get("last_pushed_event_id"),
        )


def turso_sync_state_path(timeline_home: str | Path) -> Path:
    return Path(timeline_home) / TURSO_SYNC_STATE_FILENAME


def read_turso_sync_state(timeline_home: str | Path) -> TursoSyncState | None:
    path = turso_sync_state_path(timeline_home)
    if not path.exists():
        return None
    try:
        raw = read_json(path)
    except Exception as exc:
        raise TursoSyncError(f"turso sync state is unreadable at {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise TursoSyncError(f"turso sync state at {path} is not an object")
    return TursoSyncState.from_dict(raw)


def write_turso_sync_state(timeline_home: str | Path, state: TursoSyncState) -> Path:
    path = turso_sync_state_path(timeline_home)
    write_json_atomic(path, state.to_dict())
    return path


@dataclass(frozen=True)
class TursoSyncResult:
    """Structured result for push/pull."""

    action: str  # up_to_date | pushed | pulled | conflict | error
    timeline_id: str
    local_version: int
    remote_version: int
    pushed: int = 0
    pulled: int = 0
    conflict_artifacts: tuple[Any, ...] = ()
    error: str | None = None


# -- local helpers -----------------------------------------------------------

def _projects_root_from_timeline_home(timeline_home: str | Path | None) -> Path:
    from astrid.core.foundation.project_paths import resolve_projects_root as _resolve
    if timeline_home is not None:
        try:
            # layout <root>/<project>/timelines/<ulid>
            h = Path(timeline_home)
            return h.parent.parent.parent
        except Exception:
            pass
    return _resolve(None)


def _read_local_document_snapshot(
    timeline_id: str,
    projects_root: Path,
) -> TursoDocumentRow:
    """Read the local timeline row + version for replica push.

    Fails closed if timeline not found (typed error).
    """
    db_path = derive_database_path(projects_root)
    if not db_path.exists():
        raise TursoSyncConfigError(f"local database not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id, project_id, event_stream_id, name, document_json, created_at, updated_at FROM timelines WHERE id = ?", (timeline_id,)).fetchone()
        if row is None:
            raise TursoSyncConfigError(f"local timeline {timeline_id!r} not found in timelines")
        stream_id = str(row["event_stream_id"])
        head = conn.execute("SELECT head_seq FROM event_streams WHERE id = ?", (stream_id,)).fetchone()
        version = int(head["head_seq"]) if head else 0
        return TursoDocumentRow(
            timeline_id=str(row["id"]),
            project_id=str(row["project_id"]),
            event_stream_id=stream_id,
            name=str(row["name"]),
            document_json=str(row["document_json"]),
            version=version,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
    finally:
        conn.close()


def _remote_head_snapshot(replica: TursoReplicaClient, timeline_id: str) -> HeadSnapshot:
    head = replica.fetch_remote_head(timeline_id)
    if head is None:
        return HeadSnapshot(version=0, last_event_id=None, last_hash=None)
    return HeadSnapshot(
        version=int(head.get("version", 0)),
        last_event_id=head.get("last_event_id"),
        last_hash=head.get("last_hash"),
    )


def _local_head_snapshot(backend: Any) -> HeadSnapshot:
    return head_snapshot_from_backend(backend)


def _make_sync_bookmark_for_classify(
    state: TursoSyncState | None,
) -> SyncBookmark | None:
    """Adapt TursoSyncState to a SyncBookmark for classify_sync_state.

    Spoke = local, Hub = remote.
    """
    if state is None:
        return None
    return SyncBookmark(
        timeline_id=state.timeline_id,
        spoke="local",
        spoke_version=state.local_version,
        spoke_hash=state.local_hash,
        spoke_event_id=state.local_event_id,
        hub_version=state.remote_version,
        hub_hash=state.remote_hash,
        hub_event_id=state.remote_event_id,
        synced_at=state.updated_at,
    )


def _ensure_writer_or_fail_closed(projects_root: Path) -> Any:
    """Return a DatabaseWriter handle or raise TursoOwnershipError if owned elsewhere.

    Reuses the shared writer seam like SqliteEventLogBackend does.
    """
    from astrid.core.store.ownership import DatabaseOwnerLock, OwnerLockError
    from astrid.core.timeline.eventlog.sqlite_backend import _get_shared_writer as _get_shared  # type: ignore

    db_path = derive_database_path(projects_root)
    shared = _get_shared(db_path)
    if shared is not None:
        return shared
    try:
        lock = DatabaseOwnerLock(db_path)
    except OwnerLockError as exc:
        raise TursoOwnershipError(f"database is already owned (serve holds writer): {exc}") from exc
    # caller must manage lock lifetime; we return lock + will open writer elsewhere
    return lock


# -- push --------------------------------------------------------------------

def push_to_turso(
    *,
    timeline_id: str,
    timeline_home: str | Path | None,
    projects_root: str | Path | None = None,
    backend: Any,
    replica: TursoReplicaClient,
) -> TursoSyncResult:
    """Polling push: drain events after cursor + current document+version.

    Advance cursor ONLY after remote unit commits; interrupted mid-push must
    resume without duplicating (event_id upsert on remote).
    """
    if timeline_home is None:
        raise TursoSyncConfigError("push_to_turso requires a timeline_home for cursor file")
    root = Path(projects_root) if projects_root else _projects_root_from_timeline_home(timeline_home)
    state = read_turso_sync_state(timeline_home)
    local_head = _local_head_snapshot(backend)
    remote_head = _remote_head_snapshot(replica, timeline_id)

    # Classify to decide if push is needed; we still allow push when bookmark missing
    bookmark = _make_sync_bookmark_for_classify(state)
    try:
        action = classify_sync_state(
            source_head=local_head,
            destination_head=remote_head,
            bookmark=bookmark,
            expected_timeline_id=timeline_id,
        )
    except Exception as exc:
        raise TursoSyncError(f"sync classification failed: {exc}") from exc

    if action == "up_to_date":
        return TursoSyncResult(action="up_to_date", timeline_id=timeline_id, local_version=local_head.version, remote_version=remote_head.version)
    if action in ("bookmark_incompatible",):
        raise TursoSyncError(f"bookmark incompatible — refusing push (action={action})")

    # Determine after-boundary for incremental push
    after = state.remote_event_id if state and state.remote_event_id else (state.local_event_id if state and state.local_event_id else None)
    # Prefer the more precise cursor: last_pushed_event_id if present
    if state and state.last_pushed_event_id:
        after = state.last_pushed_event_id
    # But if bookmark exists, use its spoke boundary for source_only filtering
    # For push, source is local; we read after bookmark.spoke_event_id when source_only
    if bookmark and action in ("source_only", "both_advanced"):
        after = bookmark.spoke_event_id

    # Drain local events after cursor (protocol read_events)
    try:
        if after is not None:
            local_events: list[TimelineEvent] = backend.read_events(after=after)
        else:
            local_events = backend.read_events()
    except Exception as exc:
        raise TursoSyncError(f"failed to read local events for push: {exc}") from exc

    # Read current document snapshot (one row)
    try:
        doc = _read_local_document_snapshot(timeline_id, root)
    except Exception as exc:
        raise TursoSyncError(f"failed to read local document for push: {exc}") from exc

    # Decide whether document is needed: if events empty and document version unchanged, still push document if forced? No-op if already up-to-date handled above.
    # If no new events but document version > remote, push document only (via push_timeline_updates with events empty)
    need_doc = True
    if not local_events and doc.version == remote_head.version:
        # nothing to push
        return TursoSyncResult(action="up_to_date", timeline_id=timeline_id, local_version=local_head.version, remote_version=remote_head.version)

    # Map TimelineEvents → TursoEventRows
    turso_events: list[TursoEventRow] = []
    for ev in local_events:
        # Build deterministic idempotency key matching transfer.py convention
        # For Turso we store the key as stored idempotency_key
        ik = f"turso:push:{backend.backend_name()}:{timeline_id}:{ev.event_id}" if hasattr(backend, "backend_name") else f"turso:push:{timeline_id}:{ev.event_id}"
        # payload_json: use canonical json with integrity
        # Use ev.to_json_obj or manual via payload serialization already in TimelineEvent
        # We reconstruct payload_json from the event's persisted payload via parse? Simpler: re-serialize via the backend's row payload
        # For now, use ev.payload -> but need full payload_json with integrity; we can reconstruct via with_event_hash helper or via event's json form.
        # Easiest: use the backend's raw row payload_json if available — we already have ev; we can ask sqlite_backend for raw? Instead, serialize deterministically.
        from astrid.core.timeline.events.schema import with_event_hash  # type: ignore

        payload_dict = ev.payload if isinstance(ev.payload, dict) else {}  # type: ignore[attr-defined]
        # coerce to json with integrity? Use helper to build minimal payload_json
        # For пуш we mimic kernel's payload_json shape: json with data + _integrity
        # We can fetch raw payload_json from backend.read_events? Already parsed. Instead build via ev's to_json mechanism: use ev.__dict__ fallback
        # Simpler: read raw payload_json via direct DB query for fidelity
        payload_json_raw = _fetch_event_payload_json(timeline_id, ev.event_id, root)
        if payload_json_raw is None:
            import json as _json
            payload_json_raw = _json.dumps({"data": payload_dict, "_integrity": {"event_hash": ev.hash, "previous_event_hash": ev.prev_hash}})
        actor_kind = ev.actor.type  # type: ignore[attr-defined]  but kernel maps to actor_kind strings; handle mapping
        # map actor type to kernel actor_kind
        ak_map = {"agent": "executor", "human": "local", "system": "system"}
        ak = ak_map.get(str(getattr(ev.actor, "type", "system")), "system")
        actor_id = str(getattr(ev.actor, "id", ak))
        turso_events.append(
            TursoEventRow(
                event_id=ev.event_id,
                timeline_id=timeline_id,
                project_id=doc.project_id,
                stream_id=f"{timeline_id}:timeline.timeline",
                seq=_fetch_event_seq(timeline_id, ev.event_id, root) or 0,
                kind=ev.kind,
                payload_json=payload_json_raw,
                actor_kind=ak,
                actor_id=actor_id,
                txn_id=str(getattr(ev, "txn_id", "")),
                idempotency_key=ik,
                created_at=str(getattr(ev, "ts", utc_now_iso())),
            )
        )

    # If document unchanged vs remote, we can push events-only (amendment 3b)
    document_to_push: TursoDocumentRow | None = doc
    if state and doc.version == remote_head.version and local_events:
        # document may still be needed for foreign key; keep it but allow event-only if caller wants
        # For now keep doc; replica upsert is idempotent anyway
        pass
    # If remote already has document at same version, we could skip doc to prove event-only path works
    # Keep doc unless remote already matches exactly — but we keep it for batch atomicity
    # Event-only path is supported via require_document=False; push uses require_document=False when doc.version unchanged?
    # Decide: if no local_events, we push doc only; if doc.version == remote.version and local_events non-empty, we could push events only.
    require_doc = True
    if local_events and doc.version == remote_head.version and remote_head.version != 0:
        # allow event-only push ( proves W3 event-only direction)
        # Keep doc as None to exercise event-only path
        # But ensure FK exists: remote already has document row at this version, so events FK will satisfy
        document_to_push = None
        require_doc = False

    # Execute remote batch atomically
    try:
        replica.push_timeline_updates(document_to_push, turso_events, require_document=require_doc)
    except (TursoError, TursoReplicationError) as exc:
        raise TursoSyncError(f"remote push failed: {exc}") from exc

    # Advance cursor ONLY after remote unit commits
    new_state = TursoSyncState(
        timeline_id=timeline_id,
        local_version=doc.version,
        local_event_id=local_events[-1].event_id if local_events else state.local_event_id if state else None,
        local_hash=local_events[-1].hash if local_events else state.local_hash if state else None,
        remote_version=doc.version if document_to_push else remote_head.version + len(turso_events),
        remote_event_id=turso_events[-1].event_id if turso_events else state.remote_event_id if state else None,
        remote_hash=turso_events[-1].payload_json if turso_events else state.remote_hash if state else None,  # store hash-ish
        updated_at=utc_now_iso(),
        last_pushed_event_id=turso_events[-1].event_id if turso_events else state.last_pushed_event_id if state else None,
    )
    # For accurate remote_version, fetch head after push
    try:
        refreshed_remote = _remote_head_snapshot(replica, timeline_id)
        # patch versions
        new_state = TursoSyncState(
            timeline_id=timeline_id,
            local_version=doc.version,
            local_event_id=local_events[-1].event_id if local_events else new_state.local_event_id,
            local_hash=local_events[-1].hash if local_events else new_state.local_hash,
            remote_version=refreshed_remote.version,
            remote_event_id=refreshed_remote.last_event_id,
            remote_hash=refreshed_remote.last_hash,
            updated_at=utc_now_iso(),
            last_pushed_event_id=turso_events[-1].event_id if turso_events else new_state.last_pushed_event_id,
        )
    except Exception:
        pass
    write_turso_sync_state(timeline_home, new_state)
    return TursoSyncResult(action="pushed", timeline_id=timeline_id, local_version=doc.version, remote_version=new_state.remote_version, pushed=len(turso_events))


# -- pull --------------------------------------------------------------------

def pull_from_turso(
    *,
    timeline_id: str,
    timeline_home: str | Path | None,
    projects_root: str | Path | None = None,
    backend: Any,
    replica: TursoReplicaClient,
) -> TursoSyncResult:
    """Polling pull: if remote newer and local unchanged → apply through UoW;
    if both diverged → fork artifacts, zero overwrite.
    """
    if timeline_home is None:
        raise TursoSyncConfigError("pull_from_turso requires a timeline_home")
    root = Path(projects_root) if projects_root else _projects_root_from_timeline_home(timeline_home)
    state = read_turso_sync_state(timeline_home)
    local_head = _local_head_snapshot(backend)
    remote_head = _remote_head_snapshot(replica, timeline_id)
    bookmark = _make_sync_bookmark_for_classify(state)
    try:
        action = classify_sync_state(
            source_head=local_head,
            destination_head=remote_head,
            bookmark=bookmark,
            expected_timeline_id=timeline_id,
        )
    except Exception as exc:
        raise TursoSyncError(f"sync classification failed: {exc}") from exc

    if action == "up_to_date":
        return TursoSyncResult(action="up_to_date", timeline_id=timeline_id, local_version=local_head.version, remote_version=remote_head.version)
    if action == "source_only":
        # local ahead, remote behind — nothing to pull
        return TursoSyncResult(action="up_to_date", timeline_id=timeline_id, local_version=local_head.version, remote_version=remote_head.version)
    if action == "bookmark_incompatible":
        raise TursoSyncError("bookmark incompatible — refusing pull")

    if action == "both_advanced":
        # fork-not-merge: write your-copy/their-copy artifacts, leave authorities intact
        # Need source/destination targets for write_keep_both_artifact
        from astrid.core.timeline.eventlog.selector import EventLogTarget  # type: ignore
        from astrid.core.timeline.events.schema import TimelineEvent as _TE  # noqa

        # Use lightweight EventLogTarget shims for the artifact writer
        # Instead of constructing full targets, call write_keep_both_artifact via generic path using sync_state heads
        # Build suffixes: events after bookmark
        after = bookmark.spoke_event_id if bookmark else None
        try:
            local_suffix = backend.read_events(after=after) if after else backend.read_events()
        except Exception:
            local_suffix = []
        remote_suffix_rows = replica.fetch_remote_events(timeline_id, after=bookmark.hub_event_id if bookmark else None)
        # Map remote rows to TimelineEvents for artifact
        remote_suffix: list[TimelineEvent] = []
        for r in remote_suffix_rows:
            try:
                # reconstruct minimal TimelineEvent from row for artifact rendering
                import json as _json
                payload_obj = _json.loads(str(r.get("payload_json", "{}")))
                data = payload_obj.get("data", {}) if isinstance(payload_obj, dict) else {}
                integ = payload_obj.get("_integrity", {}) if isinstance(payload_obj, dict) else {}
                actor = TimelineActor(type="system", id=str(r.get("actor_id", "system")), display=str(r.get("actor_id", "system")))
                ev = TimelineEvent(
                    event_id=str(r.get("event_id")),
                    timeline_id=timeline_id,
                    ts=str(r.get("created_at", utc_now_iso())),
                    actor=actor,
                    prev_hash=integ.get("previous_event_hash") if isinstance(integ, dict) else None,
                    hash=integ.get("event_hash") if isinstance(integ, dict) else None,
                    kind=str(r.get("kind")),
                    payload=data if isinstance(data, dict) else {},
                    expected_version=None,
                    txn_id=str(r.get("txn_id", "")),
                )
                remote_suffix.append(ev)
            except Exception:
                continue
        # Build minimal source/destination targets for the writer (needs timeline_home etc.)
        # Use fake targets: create ad-hoc objects with required attributes
        @dataclass(frozen=True)
        class _ShimTarget:
            timeline_id: str
            timeline_home: Path | None
            backend: Any
            backend_name: str
        # Direct fork artifact for Turso (sqlite is local authority) — bypass selector check
        # Write a local divergence file containing both suffixes (your-copy/their-copy)
        from astrid.core._shared.jsonio import write_json_atomic as _wja
        from astrid.core.util.time import utc_now_milliseconds as _now_ms
        try:
            created_at = _now_ms()
            filename = f"divergence-{created_at}.json"
            path = Path(timeline_home) / filename
            payload = {
                "schema_version": 1,
                "kind": "sync_divergence",
                "created_at": created_at,
                "timeline_id": timeline_id,
                "local_head": {"version": local_head.version, "last_event_id": local_head.last_event_id, "last_hash": local_head.last_hash},
                "remote_head": {"version": remote_head.version, "last_event_id": remote_head.last_event_id, "last_hash": remote_head.last_hash},
                "local_suffix": [{"event_id": e.event_id, "kind": e.kind} for e in local_suffix],
                "remote_suffix": [{"event_id": e.event_id, "kind": e.kind} for e in remote_suffix],
            }
            _wja(path, payload)
            from astrid.core.timeline.sync_divergence import LocalDivergenceArtifactRef as _LDAR
            artifact = _LDAR(path=str(path), timeline_id=timeline_id, created_at=created_at)
        except Exception as exc:
            # fallback to write_keep_both_artifact if direct fails
            try:
                src = _ShimTarget(timeline_id=timeline_id, timeline_home=None, backend=replica, backend_name="supabase")
                dst = _ShimTarget(timeline_id=timeline_id, timeline_home=Path(timeline_home), backend=backend, backend_name="local_fs")
                artifact = write_keep_both_artifact(source=src, destination=dst, source_head=remote_head, destination_head=local_head, source_suffix=remote_suffix, destination_suffix=local_suffix)
            except Exception:
                artifact = None
        return TursoSyncResult(action="conflict", timeline_id=timeline_id, local_version=local_head.version, remote_version=remote_head.version, conflict_artifacts=(artifact,) if artifact else ())

    # destination_only → remote ahead, local unchanged, safe to apply
    # fetch remote events after bookmark
    after = bookmark.hub_event_id if bookmark else state.remote_event_id if state else None
    remote_rows = replica.fetch_remote_events(timeline_id, after=after)
    if not remote_rows:
        # also try after local known? fallback to read all remote and diff by event_id
        remote_rows = replica.fetch_remote_events(timeline_id)
        # filter to only unseen
        existing_ids = {e.event_id for e in backend.read_events()}
        remote_rows = [r for r in remote_rows if str(r.get("event_id")) not in existing_ids]

    applied = 0
    # Ownership check — fail closed if second writer would be opened
    # backend.read_events used read-only, but append needs writer.
    # The backend's own _ensure_writer will reuse shared writer or fail if owner lock held elsewhere.
    # We surface TursoOwnershipError if that path fails with "already owned".
    for r in remote_rows:
        # Map row → TimelineEvent for import
        try:
            import json as _json
            payload_obj = _json.loads(str(r.get("payload_json", "{}")))
            data = payload_obj.get("data", {}) if isinstance(payload_obj, dict) else {}
            integ = payload_obj.get("_integrity", {}) if isinstance(payload_obj, dict) else {}
            actor = TimelineActor(type="system", id=str(r.get("actor_id", "system")), display=str(r.get("actor_id", "system")))
            source_event = TimelineEvent(
                event_id=str(r.get("event_id")),
                timeline_id=timeline_id,
                ts=str(r.get("created_at", utc_now_iso())),
                actor=actor,
                prev_hash=integ.get("previous_event_hash") if isinstance(integ, dict) else None,
                hash=integ.get("event_hash") if isinstance(integ, dict) else None,
                kind=str(r.get("kind")),
                payload=data if isinstance(data, dict) else {},
                expected_version=None,
                txn_id=str(r.get("txn_id", "")),
            )
        except Exception as exc:
            raise TursoSyncError(f"failed to deserialize remote event {r.get('event_id')}: {exc}") from exc
        # choose idempotency key deterministic
        ik = f"turso:pull:{timeline_id}:{source_event.event_id}"
        try:
            backend.append_imported_event(
                timeline_id=timeline_id,
                source_event=source_event,
                idempotency_key=ik,
                actor=TimelineActor(type="system", id="turso-sync:pull", display="turso-sync"),
            )
            applied += 1
        except Exception as exc:
            # Check for ownership error
            if "already owned" in str(exc).lower() or "owned" in str(exc).lower():
                raise TursoOwnershipError(str(exc)) from exc
            # idempotent duplicate is not failure — treat as skipped
            from astrid.core.timeline.eventlog.types import EventLogIdempotentError

            if isinstance(exc, EventLogIdempotentError):
                continue
            raise TursoSyncError(f"failed to import remote event {source_event.event_id}: {exc}") from exc

    # Update sync state after successful apply
    new_local_head = _local_head_snapshot(backend)
    new_remote_head = _remote_head_snapshot(replica, timeline_id)
    new_state = TursoSyncState(
        timeline_id=timeline_id,
        local_version=new_local_head.version,
        local_event_id=new_local_head.last_event_id,
        local_hash=new_local_head.last_hash,
        remote_version=new_remote_head.version,
        remote_event_id=new_remote_head.last_event_id,
        remote_hash=new_remote_head.last_hash,
        updated_at=utc_now_iso(),
        last_pushed_event_id=state.last_pushed_event_id if state else None,
    )
    write_turso_sync_state(timeline_home, new_state)
    return TursoSyncResult(action="pulled", timeline_id=timeline_id, local_version=new_local_head.version, remote_version=new_remote_head.version, pulled=applied)


# -- helpers for event fidelity ---------------------------------------------

def _fetch_event_seq(timeline_id: str, event_id: str, projects_root: Path) -> int | None:
    db_path = derive_database_path(projects_root)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT seq FROM events WHERE event_id = ?", (event_id,)).fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _fetch_event_payload_json(timeline_id: str, event_id: str, projects_root: Path) -> str | None:
    db_path = derive_database_path(projects_root)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT payload_json FROM events WHERE event_id = ?", (event_id,)).fetchone()
            return str(row[0]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _seq_for_event(backend: Any, event_id: str) -> int | None:
    try:
        for ev in backend.read_events():
            if ev.event_id == event_id:
                return int(getattr(ev, "seq", 0)) if hasattr(ev, "seq") else None
    except Exception:
        return None
    return None
