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
from astrid.core.store.ownership import OwnerLockError
from astrid.core.timeline.eventlog.turso import (
    TursoDocumentRow,
    TursoError,
    TursoEventRow,
    TursoOwnershipError,
    TursoReplicaClient,
    TursoReplicationError,
)
from astrid.core.timeline.eventlog.types import EventLogError
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent
from astrid.core.timeline.sync_divergence import write_keep_both_artifact
from astrid.core.timeline.sync_state import (
    HeadSnapshot,
    SyncBookmark,
    classify_sync_state,
    head_snapshot_from_backend,
)
from astrid.core.util.time import utc_now_iso, utc_now_milliseconds

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
        raise TursoSyncError(
            f"turso sync state is unreadable at {path}: {exc}"
        ) from exc
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


def _projects_root_from_timeline_home(
    timeline_home: str | Path | None,
) -> Path:
    from astrid.core.foundation.project_paths import (
        resolve_projects_root as _resolve,
    )

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
        row = conn.execute(
            "SELECT id, project_id, event_stream_id, name, "
            "document_json, created_at, updated_at "
            "FROM timelines WHERE id = ?",
            (timeline_id,),
        ).fetchone()
        if row is None:
            raise TursoSyncConfigError(
                f"local timeline {timeline_id!r} not found in timelines"
            )
        stream_id = str(row["event_stream_id"])
        head = conn.execute(
            "SELECT head_seq FROM event_streams WHERE id = ?",
            (stream_id,),
        ).fetchone()
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


def _remote_head_snapshot(
    replica: TursoReplicaClient, timeline_id: str
) -> HeadSnapshot:
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


def _assert_backfilled_or_fail_closed(
    timeline_id: str, projects_root: Path
) -> None:
    """R5: only SQLite-authoritative (marked) timelines may sync (fail closed)."""
    try:
        from astrid.core.timeline.authority import is_backfilled_timeline
    except Exception as exc:
        raise TursoSyncError(f"failed to resolve authority seam: {exc}") from exc
    try:
        marked = is_backfilled_timeline(timeline_id, projects_root=projects_root)
    except Exception as exc:
        # authority seam fails closed on corrupt marker — surface as typed sync error (no pack import)  # noqa: E501
        raise TursoSyncError(f"authority check failed for {timeline_id!r}: {exc}") from exc
    if not marked:
        raise TursoSyncError(
            f"timeline {timeline_id!r} is not SQLite-authoritative (missing backfill marker) — refusing sync (R5)"  # noqa: E501
        )


def _extract_event_hash(payload_json: str | None) -> str | None:
    if not payload_json:
        return None
    try:
        obj = json.loads(str(payload_json))
        integ = obj.get("_integrity") if isinstance(obj, dict) else None
        if isinstance(integ, dict):
            h = integ.get("event_hash")
            return str(h) if h else None
    except Exception:
        return None
    return None

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
        raise TursoSyncConfigError(
            "push_to_turso requires a timeline_home for cursor file"
        )
    root = (
        Path(projects_root)
        if projects_root
        else _projects_root_from_timeline_home(timeline_home)
    )
    _assert_backfilled_or_fail_closed(timeline_id, root)
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
        return TursoSyncResult(
            action="up_to_date",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
        )
    if action in ("bookmark_incompatible",):
        raise TursoSyncError(
            f"bookmark incompatible — refusing push (action={action})"
        )

    if action == "both_advanced":
        # fork-not-merge: build keep-both artifact, never overwrite remote (R6)
        after_local = bookmark.spoke_event_id if bookmark else None
        after_remote = bookmark.hub_event_id if bookmark else None
        try:
            local_suffix = (
                backend.read_events(after=after_local) if after_local else backend.read_events()
            )
        except Exception as exc:
            raise TursoSyncError(f"failed to read local suffix for fork: {exc}") from exc
        try:
            remote_suffix_rows = replica.fetch_remote_events(
                timeline_id, after=after_remote
            )
        except Exception as exc:
            raise TursoSyncError(f"failed to read remote suffix for fork: {exc}") from exc
        # map remote rows to TimelineEvents with full payloads
        remote_suffix: list[TimelineEvent] = []
        for r in remote_suffix_rows:
            try:
                payload_obj = json.loads(str(r.get("payload_json", "{}")))
                data = payload_obj.get("data", {}) if isinstance(payload_obj, dict) else {}
                integ = payload_obj.get("_integrity", {}) if isinstance(payload_obj, dict) else {}
                actor = TimelineActor(type="system", id=str(r.get("actor_id", "system")), display=str(r.get("actor_id", "system")))  # noqa: E501
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
        # Build artifact via write_keep_both_artifact with honest backend names.
        # Destination must be local (sqlite/local_fs) so artifact lands under timeline_home.
        @dataclass(frozen=True)
        class _ShimTarget:
            timeline_id: str
            timeline_home: Path | None
            backend: Any
            backend_name: str
            slug: str = "t1"
            timeline_ulid: str = "01J000000000000000000000AA"
            source: str = "test"

        local_backend_name = backend.backend_name() if hasattr(backend, "backend_name") else "sqlite"  # noqa: E501
        src_target = _ShimTarget(timeline_id=timeline_id, timeline_home=None, backend=replica, backend_name="turso")  # noqa: E501
        dst_target = _ShimTarget(timeline_id=timeline_id, timeline_home=Path(timeline_home), backend=backend, backend_name=local_backend_name)  # noqa: E501
        try:
            artifact = write_keep_both_artifact(
                source=src_target,
                destination=dst_target,
                source_head=remote_head,
                destination_head=local_head,
                source_suffix=remote_suffix,
                destination_suffix=local_suffix,
            )
        except Exception as exc:
            raise TursoSyncError(f"failed to write keep-both artifact for fork: {exc}") from exc
        if artifact is None:
            raise TursoSyncError("fork artifact write returned None — failing closed")
        return TursoSyncResult(
            action="conflict",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
            conflict_artifacts=(artifact,),
        )

    # Determine after-boundary for incremental push
    after = (
        state.remote_event_id
        if state and state.remote_event_id
        else (state.local_event_id if state and state.local_event_id else None)
    )
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

    # If no new events but document version unchanged, nothing to push
    if not local_events and doc.version == remote_head.version:
        return TursoSyncResult(
            action="up_to_date",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
        )

    # Map TimelineEvents → TursoEventRows
    turso_events: list[TursoEventRow] = []
    for ev in local_events:
        bk_name = (
            backend.backend_name()
            if hasattr(backend, "backend_name")
            else "unknown"
        )
        ik = f"turso:push:{bk_name}:{timeline_id}:{ev.event_id}"
        payload_dict = (
            ev.payload if isinstance(ev.payload, dict) else {}  # type: ignore[attr-defined]
        )
        payload_json_raw = _fetch_event_payload_json(
            timeline_id, ev.event_id, root
        )
        if payload_json_raw is None:
            payload_json_raw = json.dumps(
                {
                    "data": payload_dict,
                    "_integrity": {
                        "event_hash": ev.hash,
                        "previous_event_hash": ev.prev_hash,
                    },
                }
            )
        ak_map = {"agent": "executor", "human": "local", "system": "system"}
        ak = ak_map.get(str(getattr(ev.actor, "type", "system")), "system")
        actor_id = str(getattr(ev.actor, "id", ak))
        seq_val = _fetch_event_seq(timeline_id, ev.event_id, root)
        if seq_val is None:
            raise TursoSyncError(
                f"missing seq for drained event {ev.event_id!r} — failing closed"
            )
        turso_events.append(
            TursoEventRow(
                event_id=ev.event_id,
                timeline_id=timeline_id,
                project_id=doc.project_id,
                stream_id=f"{timeline_id}:timeline.timeline",
                seq=seq_val,
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
    require_doc = True
    if local_events and doc.version == remote_head.version and remote_head.version != 0:
        # allow event-only push (proves W3 event-only direction)
        # Keep doc as None to exercise event-only path
        # But ensure FK exists: remote already has document row at this version
        document_to_push = None
        require_doc = False

    # Execute remote batch atomically
    try:
        replica.push_timeline_updates(
            document_to_push, turso_events, require_document=require_doc
        )
    except (TursoError, TursoReplicationError) as exc:
        raise TursoSyncError(f"remote push failed: {exc}") from exc

    # Advance cursor ONLY after remote unit commits
    # Use honest hash extraction — never store payload_json as hash
    inferred_remote_hash = _extract_event_hash(turso_events[-1].payload_json) if turso_events else (state.remote_hash if state else None)  # noqa: E501
    new_state = TursoSyncState(
        timeline_id=timeline_id,
        local_version=doc.version,
        local_event_id=(
            local_events[-1].event_id if local_events else state.local_event_id if state else None  # type: ignore[union-attr]
        ),
        local_hash=(
            local_events[-1].hash if local_events else state.local_hash if state else None  # type: ignore[union-attr]
        ),
        remote_version=(
            doc.version if document_to_push else remote_head.version + len(turso_events)
        ),
        remote_event_id=(
            turso_events[-1].event_id if turso_events else state.remote_event_id if state else None  # type: ignore[union-attr]
        ),
        remote_hash=inferred_remote_hash,
        updated_at=utc_now_iso(),
        last_pushed_event_id=(
            turso_events[-1].event_id  # type: ignore[union-attr]
            if turso_events
            else state.last_pushed_event_id  # type: ignore[union-attr]
            if state
            else None
        ),
    )
    # For accurate remote_version, fetch head after push — fail closed on transport failure
    try:
        refreshed_remote = _remote_head_snapshot(replica, timeline_id)
        new_state = TursoSyncState(
            timeline_id=timeline_id,
            local_version=doc.version,
            local_event_id=(
                local_events[-1].event_id if local_events else new_state.local_event_id
            ),
            local_hash=(
                local_events[-1].hash if local_events else new_state.local_hash
            ),
            remote_version=refreshed_remote.version,
            remote_event_id=refreshed_remote.last_event_id,
            remote_hash=refreshed_remote.last_hash,
            updated_at=utc_now_iso(),
            last_pushed_event_id=(
                turso_events[-1].event_id if turso_events else new_state.last_pushed_event_id
            ),
        )
    except Exception as exc:
        # Refresh is best-effort but failure must not silently store payload_json as hash.
        # We already have an honest inferred hash; if remote is unreachable, surface typed error
        # rather than silently advancing with potentially stale version.
        # However, the remote batch already committed, so we can still record with inferred values
        # but must not swallow a typed transport error silently. Raise typed.
        raise TursoSyncError(f"failed to refresh remote head after push: {exc}") from exc
    write_turso_sync_state(timeline_home, new_state)
    return TursoSyncResult(
        action="pushed",
        timeline_id=timeline_id,
        local_version=doc.version,
        remote_version=new_state.remote_version,
        pushed=len(turso_events),
    )


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
    root = (
        Path(projects_root)
        if projects_root
        else _projects_root_from_timeline_home(timeline_home)
    )
    _assert_backfilled_or_fail_closed(timeline_id, root)
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
        return TursoSyncResult(
            action="up_to_date",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
        )
    if action == "source_only":
        # local ahead, remote behind — nothing to pull
        return TursoSyncResult(
            action="up_to_date",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
        )
    if action == "bookmark_incompatible":
        raise TursoSyncError("bookmark incompatible — refusing pull")

    if action == "both_advanced":
        # fork-not-merge: primary is write_keep_both_artifact with full payloads
        after = bookmark.spoke_event_id if bookmark else None
        try:
            local_suffix = (
                backend.read_events(after=after) if after else backend.read_events()
            )
        except Exception as exc:
            raise TursoSyncError(f"failed to read local suffix for fork: {exc}") from exc
        try:
            remote_suffix_rows = replica.fetch_remote_events(
                timeline_id,
                after=bookmark.hub_event_id if bookmark else None,
            )
        except Exception as exc:
            raise TursoSyncError(f"failed to read remote suffix for fork: {exc}") from exc

        # Map remote rows to TimelineEvents for artifact; record skips inside artifact
        remote_suffix: list[TimelineEvent] = []
        skipped_rows: list[dict[str, Any]] = []
        for r in remote_suffix_rows:
            try:
                payload_obj = json.loads(str(r.get("payload_json", "{}")))
                data = (
                    payload_obj.get("data", {})
                    if isinstance(payload_obj, dict)
                    else {}
                )
                integ = (
                    payload_obj.get("_integrity", {})
                    if isinstance(payload_obj, dict)
                    else {}
                )
                actor = TimelineActor(
                    type="system",
                    id=str(r.get("actor_id", "system")),
                    display=str(r.get("actor_id", "system")),
                )
                ev = TimelineEvent(
                    event_id=str(r.get("event_id")),
                    timeline_id=timeline_id,
                    ts=str(r.get("created_at", utc_now_iso())),
                    actor=actor,
                    prev_hash=(
                        integ.get("previous_event_hash")
                        if isinstance(integ, dict)
                        else None
                    ),
                    hash=(
                        integ.get("event_hash")
                        if isinstance(integ, dict)
                        else None
                    ),
                    kind=str(r.get("kind")),
                    payload=data if isinstance(data, dict) else {},
                    expected_version=None,
                    txn_id=str(r.get("txn_id", "")),
                )
                remote_suffix.append(ev)
            except Exception as exc:
                skipped_rows.append(
                    {
                        "event_id": str(r.get("event_id", "")),
                        "error": str(exc),
                    }
                )
                continue

        # Build keep-both artifact via primary mechanism (honest backend names)
        @dataclass(frozen=True)
        class _ShimTarget:
            timeline_id: str
            timeline_home: Path | None
            backend: Any
            backend_name: str
            slug: str = "t1"
            timeline_ulid: str = "01J000000000000000000000AA"
            source: str = "test"

        # Determine honest backend name for local authority (sqlite or local_fs)
        local_backend_name = (
            backend.backend_name()
            if hasattr(backend, "backend_name")
            else "sqlite"
        )
        # Source is the hub (Turso); we report it as "turso" if the writer
        # supports it, otherwise fall back to generic hub label that still
        # round-trips through _render_side. The extension to accept sqlite
        # locally means we never need to fake supabase here.
        src_target = _ShimTarget(
            timeline_id=timeline_id,
            timeline_home=None,
            backend=replica,
            backend_name="turso",
        )
        dst_target = _ShimTarget(
            timeline_id=timeline_id,
            timeline_home=Path(timeline_home),
            backend=backend,
            backend_name=local_backend_name,
        )
        # Primary artifact — full payloads — must succeed or raise typed
        try:
            artifact = write_keep_both_artifact(
                source=src_target,
                destination=dst_target,
                source_head=remote_head,
                destination_head=local_head,
                source_suffix=remote_suffix,
                destination_suffix=local_suffix,
            )
        except Exception as exc:
            raise TursoSyncError(
                f"failed to write keep-both artifact for fork: {exc}"
            ) from exc

        if artifact is None:
            raise TursoSyncError(
                "fork artifact write returned None — failing closed"
            )

        # Inject skipped_rows diagnostic and re-wrap suffixes with full payloads
        # plus lightweight summary file for observability.
        try:
            art_path = Path(str(getattr(artifact, "path", "")))
            if art_path.exists():
                raw = read_json(art_path)
                if isinstance(raw, dict) and skipped_rows:
                    raw["skipped_rows"] = skipped_rows
                    write_json_atomic(art_path, raw)
            # Additional diagnostic file (summary-only) — not primary
            diag_path = art_path.with_name(art_path.stem + ".diagnostic.json")
            diag_payload = {
                "kind": "sync_divergence_diagnostic",
                "created_at": utc_now_milliseconds(),
                "timeline_id": timeline_id,
                "local_suffix": [
                    {"event_id": e.event_id, "kind": e.kind} for e in local_suffix
                ],
                "remote_suffix": [
                    {"event_id": e.event_id, "kind": e.kind} for e in remote_suffix
                ],
                "skipped_rows": skipped_rows,
            }
            try:
                write_json_atomic(diag_path, diag_payload)
            except Exception:
                pass
        except Exception as exc:
            raise TursoSyncError(
                f"failed to finalize fork artifact diagnostics: {exc}"
            ) from exc

        return TursoSyncResult(
            action="conflict",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
            conflict_artifacts=(artifact,),
        )

    # destination_only → remote ahead, local unchanged, safe to apply
    # fetch remote events after bookmark
    after = bookmark.hub_event_id if bookmark else state.remote_event_id if state else None
    remote_rows = replica.fetch_remote_events(timeline_id, after=after)
    if not remote_rows:
        # also try after local known? fallback to read all remote and diff by event_id
        remote_rows = replica.fetch_remote_events(timeline_id)
        # filter to only unseen
        existing_ids = {e.event_id for e in backend.read_events()}
        remote_rows = [
            r for r in remote_rows if str(r.get("event_id")) not in existing_ids
        ]
    if not remote_rows:
        # fail closed if classification says remote-ahead but zero rows fetched from both attempts
        # genuine absence stays legal only when remote genuinely has no rows (empty replica / version 0)  # noqa: E501
        if remote_head.version == 0 and remote_head.last_event_id is None:
            return TursoSyncResult(
                action="up_to_date",
                timeline_id=timeline_id,
                local_version=local_head.version,
                remote_version=remote_head.version,
            )
        raise TursoSyncError(
            f"remote ahead (action={action}, remote_version={remote_head.version}) but zero new rows fetched after both attempts — failing closed; events unfetchable"  # noqa: E501
        )

    applied = 0
    # Ownership check — fail closed if second writer would be opened
    # backend.read_events used read-only, but append needs writer.
    # The backend's own _ensure_writer will reuse shared writer or fail if owner lock held
    for r in remote_rows:
        try:
            payload_obj = json.loads(str(r.get("payload_json", "{}")))
            data = (
                payload_obj.get("data", {}) if isinstance(payload_obj, dict) else {}
            )
            integ = (
                payload_obj.get("_integrity", {})
                if isinstance(payload_obj, dict)
                else {}
            )
            actor = TimelineActor(
                type="system",
                id=str(r.get("actor_id", "system")),
                display=str(r.get("actor_id", "system")),
            )
            source_event = TimelineEvent(
                event_id=str(r.get("event_id")),
                timeline_id=timeline_id,
                ts=str(r.get("created_at", utc_now_iso())),
                actor=actor,
                prev_hash=(
                    integ.get("previous_event_hash") if isinstance(integ, dict) else None
                ),
                hash=(
                    integ.get("event_hash") if isinstance(integ, dict) else None
                ),
                kind=str(r.get("kind")),
                payload=data if isinstance(data, dict) else {},
                expected_version=None,
                txn_id=str(r.get("txn_id", "")),
            )
        except Exception as exc:
            raise TursoSyncError(
                f"failed to deserialize remote event {r.get('event_id')}: {exc}"
            ) from exc
        # choose idempotency key deterministic
        ik = f"turso:pull:{timeline_id}:{source_event.event_id}"
        try:
            backend.append_imported_event(
                timeline_id=timeline_id,
                source_event=source_event,
                idempotency_key=ik,
                actor=TimelineActor(
                    type="system", id="turso-sync:pull", display="turso-sync"
                ),
            )
            applied += 1
        except OwnerLockError as exc:
            raise TursoOwnershipError(str(exc)) from exc
        except EventLogError as exc:
            # Backend seam wraps OwnerLockError as EventLogError("database is already owned: ...")
            # Map only when cause chain contains typed OwnerLockError, never by substring.
            cause = exc.__cause__
            cur: Any = cause
            is_ownership = False
            while cur is not None:
                if isinstance(cur, OwnerLockError):
                    is_ownership = True
                    break
                cur = getattr(cur, "__cause__", None)
            if is_ownership:
                raise TursoOwnershipError(str(exc)) from exc
            # Not ownership: check idempotency (EventLogIdempotentError is subclass of EventLogError)  # noqa: E501
            from astrid.core.timeline.eventlog.types import EventLogIdempotentError

            if isinstance(exc, EventLogIdempotentError):
                continue
            raise TursoSyncError(f"failed to import remote event {source_event.event_id}: {exc}") from exc  # noqa: E501
        except Exception as exc:
            # idempotent duplicate is not failure — treat as skipped
            from astrid.core.timeline.eventlog.types import (
                EventLogIdempotentError,
            )

            if isinstance(exc, EventLogIdempotentError):
                continue
            raise TursoSyncError(
                f"failed to import remote event {source_event.event_id}: {exc}"
            ) from exc

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
    return TursoSyncResult(
        action="pulled",
        timeline_id=timeline_id,
        local_version=new_local_head.version,
        remote_version=new_remote_head.version,
        pulled=applied,
    )


# -- helpers for event fidelity ---------------------------------------------


def _fetch_event_seq(
    timeline_id: str, event_id: str, projects_root: Path
) -> int | None:
    db_path = derive_database_path(projects_root)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception as exc:
        raise TursoSyncError(f"failed to open DB for seq fetch: {exc}") from exc
    try:
        try:
            row = conn.execute(
                "SELECT seq FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            return int(row[0]) if row else None
        except Exception as exc:
            raise TursoSyncError(f"failed to fetch seq for {event_id!r}: {exc}") from exc
    finally:
        conn.close()


def _fetch_event_payload_json(
    timeline_id: str, event_id: str, projects_root: Path
) -> str | None:
    db_path = derive_database_path(projects_root)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception as exc:
        raise TursoSyncError(f"failed to open DB for payload fetch: {exc}") from exc
    try:
        try:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            raise TursoSyncError(
                f"failed to fetch payload for {event_id!r}: {exc}"
            ) from exc
    finally:
        conn.close()


def _seq_for_event(backend: Any, event_id: str) -> int | None:
    try:
        for ev in backend.read_events():
            if ev.event_id == event_id:
                return int(getattr(ev, "seq", 0)) if hasattr(ev, "seq") else None
    except Exception:
        return None
    return None
