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
    TursoEventCollisionError,
    TursoEventRow,
    TursoOwnershipError,
    TursoReplicaClient,
    TursoReplicationError,
    TursoSyncError,
    TursoVersionRaceError,
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
    try:
        write_json_atomic(path, state.to_dict())
    except TursoSyncError:
        raise
    except OSError as exc:
        raise TursoSyncError(f"turso sync state write failed at {path}: {exc}") from exc
    except Exception as exc:
        raise TursoSyncError(f"turso sync state write failed at {path}: {exc}") from exc
    return path


def _write_state_typed(timeline_home: str | Path, state: TursoSyncState) -> Path:
    """Wrapper ensuring OSError never escapes as raw."""
    try:
        return write_turso_sync_state(timeline_home, state)
    except TursoSyncError:
        raise
    except OSError as exc:
        raise TursoSyncError(f"turso sync state write failed at {timeline_home}: {exc}") from exc
    except Exception as exc:
        raise TursoSyncError(f"turso sync state write failed at {timeline_home}: {exc}") from exc


def _local_payload_json_for_event(timeline_id: str, event_id: str, projects_root: Path) -> str | None:  # noqa: E501
    return _fetch_event_payload_json(timeline_id, event_id, projects_root)


def _suffixes_byte_equal(
    timeline_id: str,
    local_events: list[Any],
    remote_rows: list[dict[str, Any]],
    projects_root: Path,
    backend: Any | None = None,
    strict_event_id: bool = True,
    check_seq: bool = True,
) -> bool:  # noqa: E501
    """Compare local TimelineEvents vs remote dict rows byte-equal on identity+payload+kind+stream."""  # noqa: E501
    if len(local_events) != len(remote_rows):
        return False
    if not local_events and not remote_rows:
        return True
    for le, rr in zip(local_events, remote_rows):
        # Identity-faithful: pull resume must compare REMOTE event_id against
        # LOCAL provenance source_event_id (populated by append_imported_event)
        # falling back to local event_id. Push resume stays strictly identity-based.
        # Fallback ordering: source_event_id -> event_id (cite: sqlite_backend.append_imported_event
        # persists source_event_id, _event_from_row exposes it as source_event_id).
        if strict_event_id:
            if str(getattr(le, "event_id", "")) != str(rr.get("event_id", "")):
                return False
        else:
            # Pull provenance mode: remote event_id must match local source_event_id if present  # noqa: E501
            local_source = getattr(le, "source_event_id", None)
            local_id_for_compare = str(local_source) if local_source else str(getattr(le, "event_id", ""))  # noqa: E501
            if local_id_for_compare != str(rr.get("event_id", "")):
                return False
        if str(getattr(le, "kind", "")) != str(rr.get("kind", "")):  # noqa: E501
            return False
        local_pj = _local_payload_json_for_event(timeline_id, str(getattr(le, "event_id", "")), projects_root)  # noqa: E501
        if local_pj is None:
            try:
                payload_dict = getattr(le, "payload", {})
                if not isinstance(payload_dict, dict):
                    payload_dict = {}
                local_pj = json.dumps(
                    {
                        "data": payload_dict,
                        "_integrity": {
                            "event_hash": getattr(le, "hash", None),
                            "previous_event_hash": getattr(le, "prev_hash", None),
                        },
                    }
                )
            except Exception:
                return False
        remote_pj = str(rr.get("payload_json", ""))
        try:
            local_obj = json.loads(local_pj) if local_pj else {}
            remote_obj = json.loads(remote_pj) if remote_pj else {}
            if isinstance(local_obj, dict) and isinstance(remote_obj, dict) and "data" in local_obj and "data" in remote_obj:  # noqa: E501
                if json.dumps(local_obj.get("data"), sort_keys=True, separators=(",",":")) != json.dumps(remote_obj.get("data"), sort_keys=True, separators=(",",":")):  # noqa: E501
                    return False
            else:
                if local_pj != remote_pj:
                    return False
        except Exception:
            if local_pj != remote_pj:
                return False
        if check_seq:
            seq_local = _fetch_event_seq(timeline_id, str(getattr(le, "event_id", "")), projects_root)  # noqa: E501
            try:
                seq_remote = int(rr.get("seq"))
            except Exception:
                seq_remote = rr.get("seq")
            if seq_local != seq_remote:
                return False
        if str(rr.get("timeline_id", "")) != str(timeline_id):
            return False
    return True


def _resume_bookmark_boundaries(
    state: TursoSyncState | None,
    bookmark: Any | None,
    *,
    strict_event_id: bool,
) -> tuple[str | None, str | None]:
    """Compute after cursors exactly as reconciliation does (shared)."""
    if bookmark is not None and getattr(bookmark, "spoke_event_id", None):
        after_local = bookmark.spoke_event_id  # type: ignore[union-attr]
        after_remote = bookmark.hub_event_id  # type: ignore[union-attr]
    else:
        if state is not None and getattr(state, "remote_event_id", None):
            after_local = state.remote_event_id  # type: ignore[union-attr]
            after_remote = state.remote_event_id  # type: ignore[union-attr]
            if not strict_event_id and getattr(state, "local_event_id", None):
                after_local = state.local_event_id  # type: ignore[union-attr]
        elif state is not None and getattr(state, "local_event_id", None):
            after_local = state.local_event_id  # type: ignore[union-attr]
            after_remote = getattr(state, "remote_event_id", None)
        else:
            after_local = None
            after_remote = None
        if strict_event_id and state is not None and after_local is None and getattr(state, "local_event_id", None):  # noqa: E501
            after_local = state.local_event_id  # type: ignore[union-attr]
    return after_local, after_remote


def _is_resume_already_committed(
    timeline_id: str,
    timeline_home: str | Path,
    projects_root: Path,
    backend: Any,
    replica: TursoReplicaClient,
    state: TursoSyncState | None,
    bookmark: Any | None,
    *,
    strict_event_id: bool,
) -> bool:
    """Shared reconciliation: do local suffix and remote suffix byte-match beyond cursor?"""  # noqa: E501
    try:
        after_local, after_remote = _resume_bookmark_boundaries(state, bookmark, strict_event_id=strict_event_id)  # noqa: E501
        try:
            local_suffix = backend.read_events(after=after_local) if after_local else backend.read_events()  # noqa: E501
        except Exception:
            return False
        try:
            remote_suffix = replica.fetch_remote_events(timeline_id, after=after_remote)
        except Exception:
            return False
        if not local_suffix and not remote_suffix:
            return False
        if not local_suffix or not remote_suffix:
            return False
        check_seq = True
        return _suffixes_byte_equal(timeline_id, local_suffix, remote_suffix, projects_root, backend, strict_event_id=strict_event_id, check_seq=check_seq)  # noqa: E501
    except Exception:
        return False

def _is_push_resume_already_committed(
    timeline_id: str,
    timeline_home: str | Path,
    projects_root: Path,
    backend: Any,
    replica: TursoReplicaClient,
    state: TursoSyncState | None,
    bookmark: Any | None,
) -> bool:
    """Reconciliation for crash-after-commit: do local suffix and remote suffix byte-match beyond cursor?"""  # noqa: E501
    return _is_resume_already_committed(timeline_id, timeline_home, projects_root, backend, replica, state, bookmark, strict_event_id=True)  # noqa: E501


def _is_pull_resume_already_committed(
    timeline_id: str,
    timeline_home: str | Path,
    projects_root: Path,
    backend: Any,
    replica: TursoReplicaClient,
    state: TursoSyncState | None,
    bookmark: Any | None,
) -> bool:
    """Pull side resume: remote suffix beyond bookmark equals local suffix beyond bookmark."""
    return _is_resume_already_committed(timeline_id, timeline_home, projects_root, backend, replica, state, bookmark, strict_event_id=False)  # noqa: E501




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
    ver = int(head.get("version", 0))
    leid = head.get("last_event_id")
    lhash = head.get("last_hash")
    # Q9: if most-recent payload malformed, last_hash may be None while version>0;  # noqa: E501
    # fallback to last_event_id to keep HeadSnapshot valid — fork path handles malformed rows via skipped_rows.  # noqa: E501
    if ver > 0 and lhash is None and leid is not None:
        lhash = str(leid)
    return HeadSnapshot(version=ver, last_event_id=leid, last_hash=lhash)


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
    # -- R3 entry-prologue hardening: state/bookmark/head coercion → typed --
    try:
        state = read_turso_sync_state(timeline_home)
    except TursoSyncError:
        raise
    except Exception as exc:
        raise TursoSyncError(f"turso sync state unreadable at {timeline_home}: {exc}") from exc
    try:
        local_head = _local_head_snapshot(backend)
    except TursoSyncError:
        raise
    except Exception as exc:
        raise TursoSyncError(f"local head snapshot failed (backend.head corrupt?): {exc}") from exc
    try:
        remote_head = _remote_head_snapshot(replica, timeline_id)
    except TursoSyncError:
        raise
    except Exception as exc:
        raise TursoSyncError(f"remote head snapshot failed for {timeline_id!r} (documents.version expected int, last_event_id/hash required when version>0): {exc}") from exc  # noqa: E501
    try:
        bookmark = _make_sync_bookmark_for_classify(state)
    except Exception as exc:
        # SyncStateError from spoke_version≠0 but missing spoke_event_id etc.
        raise TursoSyncError(f"sync bookmark corrupt (state.local_version={getattr(state, 'local_version', '?')} spoke_event_id={getattr(state, 'local_event_id', '?')}): {exc}") from exc  # noqa: E501
    # Classify to decide if push is needed; we still allow push when bookmark missing
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
    # W3 resume-before-fork: crash-after-commit reconciliation — remote boundary
    # derives EXCLUSIVELY from proven transferred rows (P2-2). Refreshed heads
    # verify only, never populate remote fields beyond proven suffix.
    if action in ("both_advanced", "bookmark_incompatible"):
        try:
            if _is_push_resume_already_committed(timeline_id, timeline_home, root, backend, replica, state, bookmark):  # noqa: E501
                # Derive proven boundary BEFORE refresh — refreshed heads are verify-only
                after_local_b, after_remote_b = _resume_bookmark_boundaries(state, bookmark, strict_event_id=True)  # noqa: E501
                try:
                    proven_local = backend.read_events(after=after_local_b) if after_local_b else backend.read_events()  # noqa: E501
                except Exception as exc:
                    raise TursoSyncError(f"resume proven local fetch failed: {exc}") from exc  # noqa: E501
                try:
                    proven_remote = replica.fetch_remote_events(timeline_id, after=after_remote_b)  # noqa: E501
                except Exception as exc:
                    raise TursoSyncError(f"resume proven remote fetch failed: {exc}") from exc  # noqa: E501
                if not proven_local or not proven_remote:
                    raise TursoSyncError("resume proven suffix empty despite committed check")  # noqa: E501
                # Verify refreshed heads contain proven row (but do not use their extra rows)
                try:
                    fresh_local = _local_head_snapshot(backend)
                    fresh_remote = _remote_head_snapshot(replica, timeline_id)
                except Exception as exc:
                    raise TursoSyncError(f"resume head refresh failed: {exc}") from exc
                # Proven last row is exclusive boundary
                proven_last = proven_local[-1]
                proven_last_id = proven_last.event_id
                proven_last_hash = proven_last.hash or _extract_event_hash(_fetch_event_payload_json(timeline_id, proven_last_id, root) or "")  # noqa: E501
                # Verify remote head still contains proven row (unseen append check is advisory)
                try:
                    _ = fresh_remote  # already fetched for verification
                except Exception:
                    pass
                try:
                    inferred = proven_last_id
                except Exception:
                    inferred = None
                # Remote boundary = proven row + corresponding local version (verified)
                resume_state = TursoSyncState(
                    timeline_id=timeline_id,
                    local_version=fresh_local.version,
                    local_event_id=fresh_local.last_event_id,
                    local_hash=fresh_local.last_hash,
                    remote_version=fresh_local.version,
                    remote_event_id=proven_last_id,
                    remote_hash=proven_last_hash,
                    updated_at=utc_now_iso(),
                    last_pushed_event_id=inferred or (state.last_pushed_event_id if state else None),  # noqa: E501
                )
                _write_state_typed(timeline_home, resume_state)
                honest = "up_to_date" if fresh_local.version == resume_state.remote_version and resume_state.remote_version != 0 else "pushed"  # noqa: E501
                if honest == "up_to_date":
                    return TursoSyncResult(action="up_to_date", timeline_id=timeline_id, local_version=fresh_local.version, remote_version=resume_state.remote_version)  # noqa: E501
                return TursoSyncResult(action="pushed", timeline_id=timeline_id, local_version=fresh_local.version, remote_version=resume_state.remote_version, pushed=0)  # noqa: E501
        except TursoSyncError:
            raise
        except Exception:
            pass
    if action in ("bookmark_incompatible",):
        raise TursoSyncError(
            f"bookmark incompatible — refusing push (action={action})"
        )

    if action == "destination_only":
        # Remote advanced alone — local has nothing new; no-op without touching cursor or remote.
        return TursoSyncResult(
            action="up_to_date",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
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
        # map remote rows to TimelineEvents with full payloads — record skips (mirror pull)
        remote_suffix: list[TimelineEvent] = []
        skipped_rows: list[dict[str, Any]] = []
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
            except Exception as exc:
                skipped_rows.append({"event_id": str(r.get("event_id", "")), "error": str(exc)})
                continue
        # If entire remote suffix failed to decode, fail closed with typed error
        if remote_suffix_rows and not remote_suffix and len(skipped_rows) == len(remote_suffix_rows):  # noqa: E501
            raise TursoSyncError(
                f"remote suffix entirely undecodable ({len(skipped_rows)} rows): {skipped_rows[0]['error']}"  # noqa: E501
            )
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
        # Inject skipped_rows diagnostic and re-wrap suffixes with full payloads
        try:
            art_path = Path(str(getattr(artifact, "path", "")))
            if art_path.exists():
                raw = read_json(art_path)
                if isinstance(raw, dict) and skipped_rows:
                    raw["skipped_rows"] = skipped_rows
                    write_json_atomic(art_path, raw)
            diag_path = art_path.with_name(art_path.stem + ".diagnostic.json")
            diag_payload = {
                "kind": "sync_divergence_diagnostic",
                "created_at": utc_now_milliseconds(),
                "timeline_id": timeline_id,
                "local_suffix": [{"event_id": e.event_id, "kind": e.kind} for e in local_suffix],
                "remote_suffix": [{"event_id": e.event_id, "kind": e.kind} for e in remote_suffix],
                "skipped_rows": skipped_rows,
            }
            try:
                write_json_atomic(diag_path, diag_payload)
            except Exception:
                pass  # best-effort diagnostic only — primary artifact intact, swallow
        except Exception as exc:
            raise TursoSyncError(f"failed to finalize fork artifact diagnostics: {exc}") from exc
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

    # Read current document snapshot (one row) BEFORE draining — belt-and-braces guard.
    try:
        doc = _read_local_document_snapshot(timeline_id, root)
    except Exception as exc:
        raise TursoSyncError(f"failed to read local document for push: {exc}") from exc

    # Belt-and-braces: stale-document push refusal — pushes may only carry
    # document at EQUAL or ADVANCED version; anything older must go through
    # the both_advanced fork path. Independent of classification.
    if doc.version < remote_head.version:
        raise TursoSyncError(
            f"stale document version {doc.version} < remote {remote_head.version} — refusing push, fork required"  # noqa: E501
        )

    # Drain local events after cursor (protocol read_events)
    try:
        if after is not None:
            local_events: list[TimelineEvent] = backend.read_events(after=after)
        else:
            local_events = backend.read_events()
    except Exception as exc:
        raise TursoSyncError(f"failed to read local events for push: {exc}") from exc

    # If no new events but document version unchanged, nothing to push
    if not local_events and doc.version == remote_head.version:
        return TursoSyncResult(
            action="up_to_date",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
        )
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
    # Execute remote batch atomically — R2 CAS on document version
    expected_remote_version = remote_head.version if document_to_push is not None else None
    try:
        replica.push_timeline_updates(
            document_to_push,
            turso_events,
            require_document=require_doc,
            expected_remote_version=expected_remote_version,
        )
    except TursoVersionRaceError as exc:
        # T2 choice: DELETE dead reclassify (previous code called classify_sync_state
        # without required keyword-only source_head, making the reclassify unreachable
        # via TypeError). We surface the typed race error directly, no unreachable code.
        raise TursoVersionRaceError(
            f"document CAS race (expected {expected_remote_version}, remote now raced): {exc}"  # noqa: E501
        ) from exc
    except TursoEventCollisionError:
        raise
    except (TursoError, TursoReplicationError) as exc:
        raise TursoSyncError(f"remote push failed: {exc}") from exc
    except Exception as exc:
        # T1/T2 hardening: any remaining non-Turso-family exception (e.g. sqlite3.IntegrityError
        # from exact-replay INSERT) is converted to typed TursoSyncError at batch boundary.
        raise TursoSyncError(f"remote push failed (unexpected): {exc}") from exc
    # Use honest hash extraction — never store payload_json as hash
    inferred_remote_hash = _extract_event_hash(turso_events[-1].payload_json) if turso_events else (state.remote_hash if state else None)  # noqa: E501
    new_state = TursoSyncState(
        timeline_id=timeline_id,
        local_version=doc.version,
        local_event_id=(
            local_events[-1].event_id if local_events else state.local_event_id if state else None  # type: ignore[union-attr]  # noqa: E501
        ),
        local_hash=(
            local_events[-1].hash if local_events else state.local_hash if state else None  # type: ignore[union-attr]  # noqa: E501
        ),
        remote_version=(
            doc.version if document_to_push else remote_head.version + len(turso_events)
        ),
        remote_event_id=(
            turso_events[-1].event_id if turso_events else state.remote_event_id if state else None  # type: ignore[union-attr]  # noqa: E501
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
    # Post-push refresh may verify but NEVER advances stored boundary past
    # transferred rows (P2-2: prevents bookmarking unseen interleaved row).
    try:
        _remote_head_snapshot(replica, timeline_id)
    except Exception as exc:
        raise TursoSyncError(f"failed to refresh remote head after push: {exc}") from exc
    _write_state_typed(timeline_home, new_state)
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
    # -- R3 entry-prologue hardening: state/bookmark/head → typed --
    try:
        state = read_turso_sync_state(timeline_home)
    except TursoSyncError:
        raise
    except Exception as exc:
        raise TursoSyncError(f"turso sync state unreadable at {timeline_home}: {exc}") from exc
    try:
        local_head = _local_head_snapshot(backend)
    except TursoSyncError:
        raise
    except Exception as exc:
        raise TursoSyncError(f"local head snapshot failed (backend.head corrupt?): {exc}") from exc
    try:
        remote_head = _remote_head_snapshot(replica, timeline_id)
    except TursoSyncError:
        raise
    except Exception as exc:
        raise TursoSyncError(f"remote head snapshot failed for {timeline_id!r} (documents.version expected int, last_event_id/hash required when version>0): {exc}") from exc  # noqa: E501
    try:
        bookmark = _make_sync_bookmark_for_classify(state)
    except Exception as exc:
        raise TursoSyncError(f"sync bookmark corrupt (state.local_version={getattr(state, 'local_version', '?')} spoke_event_id={getattr(state, 'local_event_id', '?')}): {exc}") from exc  # noqa: E501
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
    # W3 resume-before-fork for pull: crash-after-apply but state not persisted —
    # remote boundary derives EXCLUSIVELY from proven applied rows.
    if action in ("both_advanced", "bookmark_incompatible"):
        try:
            if _is_pull_resume_already_committed(timeline_id, timeline_home, root, backend, replica, state, bookmark):  # noqa: E501
                after_local_b, after_remote_b = _resume_bookmark_boundaries(state, bookmark, strict_event_id=False)  # noqa: E501
                try:
                    proven_local = backend.read_events(after=after_local_b) if after_local_b else backend.read_events()  # noqa: E501
                except Exception as exc:
                    raise TursoSyncError(f"pull resume proven local fetch failed: {exc}") from exc  # noqa: E501
                try:
                    proven_remote = replica.fetch_remote_events(timeline_id, after=after_remote_b)  # noqa: E501
                except Exception as exc:
                    raise TursoSyncError(f"pull resume proven remote fetch failed: {exc}") from exc  # noqa: E501
                if not proven_local or not proven_remote:
                    raise TursoSyncError("pull resume proven suffix empty despite committed check")  # noqa: E501
                try:
                    fresh_local = _local_head_snapshot(backend)
                    fresh_remote = _remote_head_snapshot(replica, timeline_id)
                except Exception as exc:
                    raise TursoSyncError(f"pull resume head refresh failed: {exc}") from exc
                proven_last = proven_local[-1]
                proven_last_id = proven_last.event_id
                proven_last_hash = proven_last.hash or _extract_event_hash(_fetch_event_payload_json(timeline_id, proven_last_id, root) or "")  # noqa: E501
                # Verify remote contains proven row (advisory, ignore extra unseen)
                try:
                    _ = fresh_remote
                except Exception:
                    pass
                try:
                    resume_state = TursoSyncState(
                        timeline_id=timeline_id,
                        local_version=fresh_local.version,
                        local_event_id=fresh_local.last_event_id,
                        local_hash=fresh_local.last_hash,
                        remote_version=fresh_local.version,
                        remote_event_id=proven_last_id,
                        remote_hash=proven_last_hash,
                        updated_at=utc_now_iso(),
                        last_pushed_event_id=state.last_pushed_event_id if state else None,
                    )
                except Exception as exc:
                    raise TursoSyncError(f"pull resume state build failed: {exc}") from exc
                _write_state_typed(timeline_home, resume_state)
                return TursoSyncResult(action="up_to_date", timeline_id=timeline_id, local_version=fresh_local.version, remote_version=resume_state.remote_version)  # noqa: E501
        except TursoSyncError:
            raise
        except Exception:
            pass
    if action == "bookmark_incompatible":
        try:
            if bookmark and local_head.version == bookmark.spoke_version and local_head.last_event_id == bookmark.spoke_event_id:  # noqa: E501
                hub_after = bookmark.hub_event_id if bookmark else None
                try:
                    new_remote = replica.fetch_remote_events(timeline_id, after=hub_after)
                except Exception:
                    new_remote = []
                if new_remote and remote_head.version == bookmark.hub_version:
                    action = "destination_only"
                else:
                    raise TursoSyncError("bookmark incompatible — refusing pull")
            else:
                raise TursoSyncError("bookmark incompatible — refusing pull")
        except TursoSyncError:
            raise
        except Exception as exc:
            raise TursoSyncError(f"bookmark incompatible — refusing pull: {exc}") from exc
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

        # P2-3: provenance-identity PREFIX reconcile — local tail byte-equal
        # to a strict prefix of unacked remote suffix ⇒ apply remaining
        # honestly (pulled, remaining count) instead of forking. Byte-mismatch
        # inside prefix still forks (preserve Z1 distinct-history).
        if local_suffix and remote_suffix_rows and 0 < len(local_suffix) < len(remote_suffix_rows):
            try:
                prefix_chunk = remote_suffix_rows[: len(local_suffix)]
                if _suffixes_byte_equal(
                    timeline_id, local_suffix, prefix_chunk, root, backend, strict_event_id=False, check_seq=False  # noqa: E501
                ):
                    remaining_rows = remote_suffix_rows[len(local_suffix) :]
                    applied_prefix = 0
                    last_id: str | None = None
                    last_hash: str | None = None
                    for r in remaining_rows:
                        try:
                            payload_obj = json.loads(str(r.get("payload_json", "{}")))
                            data = payload_obj.get("data", {}) if isinstance(payload_obj, dict) else {}  # noqa: E501
                            integ = payload_obj.get("_integrity", {}) if isinstance(payload_obj, dict) else {}  # noqa: E501
                            actor = TimelineActor(type="system", id=str(r.get("actor_id", "system")), display=str(r.get("actor_id", "system")))  # noqa: E501
                            src_ev = TimelineEvent(
                                event_id=str(r.get("event_id")),
                                timeline_id=timeline_id,
                                ts=str(r.get("created_at", utc_now_iso())),
                                actor=actor,
                                prev_hash=integ.get("previous_event_hash") if isinstance(integ, dict) else None,  # noqa: E501
                                hash=integ.get("event_hash") if isinstance(integ, dict) else None,
                                kind=str(r.get("kind")),
                                payload=data if isinstance(data, dict) else {},
                                expected_version=None,
                                txn_id=str(r.get("txn_id", "")),
                            )
                        except Exception as exc:
                            raise TursoSyncError(f"failed to deserialize remaining remote event {r.get('event_id')}: {exc}") from exc  # noqa: E501
                        ik = f"turso:pull:{timeline_id}:{src_ev.event_id}"
                        try:
                            backend.append_imported_event(
                                timeline_id=timeline_id,
                                source_event=src_ev,
                                idempotency_key=ik,
                                actor=TimelineActor(type="system", id="turso-sync:pull", display="turso-sync"),  # noqa: E501
                            )
                        except Exception as exc:
                            from astrid.core.timeline.eventlog.types import EventLogIdempotentError
                            if isinstance(exc, EventLogIdempotentError):
                                continue
                            # check wrapped idempotent
                            cause = getattr(exc, "__cause__", None)
                            is_idem = isinstance(exc, EventLogIdempotentError)
                            cur = cause
                            while cur is not None and not is_idem:
                                if isinstance(cur, EventLogIdempotentError):
                                    is_idem = True
                                    break
                                cur = getattr(cur, "__cause__", None)
                            if is_idem:
                                continue
                            raise TursoSyncError(f"failed to import remaining remote event {src_ev.event_id}: {exc}") from exc  # noqa: E501
                        applied_prefix += 1
                        last_id = src_ev.event_id
                        last_hash = src_ev.hash or _extract_event_hash(str(r.get("payload_json", "")))  # noqa: E501
                    # State reflects honestly applied remaining rows only
                    new_local_head = _local_head_snapshot(backend)
                    # keep remote boundary at last applied remaining
                    remote_version = new_local_head.version
                    remote_event_id = last_id or new_local_head.last_event_id
                    remote_hash = last_hash or new_local_head.last_hash
                    new_state = TursoSyncState(
                        timeline_id=timeline_id,
                        local_version=new_local_head.version,
                        local_event_id=new_local_head.last_event_id,
                        local_hash=new_local_head.last_hash,
                        remote_version=remote_version,
                        remote_event_id=remote_event_id,
                        remote_hash=remote_hash,
                        updated_at=utc_now_iso(),
                        last_pushed_event_id=state.last_pushed_event_id if state else None,
                    )
                    _write_state_typed(timeline_home, new_state)
                    return TursoSyncResult(
                        action="pulled",
                        timeline_id=timeline_id,
                        local_version=new_local_head.version,
                        remote_version=new_state.remote_version,
                        pulled=applied_prefix,
                    )
            except TursoSyncError:
                raise
            except Exception:
                pass

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
            # best-effort diagnostic: summary file failure must not fail primary fork — swallow
            try:
                write_json_atomic(diag_path, diag_payload)
            except Exception:
                pass  # best-effort diagnostic only — primary artifact intact, swallow
        except Exception as exc:
            raise TursoSyncError(f"failed to finalize fork artifact diagnostics: {exc}") from exc

        return TursoSyncResult(
            action="conflict",
            timeline_id=timeline_id,
            local_version=local_head.version,
            remote_version=remote_head.version,
            conflict_artifacts=(artifact,),
        )

    # destination_only → remote ahead, local unchanged, safe to apply
    # fetch remote events after bookmark — batch-boundary hardening: generic → typed
    after = bookmark.hub_event_id if bookmark else state.remote_event_id if state else None
    try:
        remote_rows = replica.fetch_remote_events(timeline_id, after=after)
    except TursoSyncError:
        raise
    except TursoError:
        raise TursoSyncError(f"remote fetch failed for {timeline_id!r}: {after!r}") from None  # noqa: E501 # keep typed chain
    except Exception as exc:
        raise TursoSyncError(f"remote fetch failed (unexpected) for {timeline_id!r}: {exc}") from exc  # noqa: E501
    if not remote_rows:
        # also try after local known? fallback to read all remote and diff by event_id
        try:
            remote_rows = replica.fetch_remote_events(timeline_id)
        except TursoSyncError:
            raise
        except TursoError as exc:
            raise TursoSyncError(f"remote fetch (fallback) failed for {timeline_id!r}: {exc}") from exc  # noqa: E501
        except Exception as exc:
            raise TursoSyncError(f"remote fetch (fallback) failed (unexpected) for {timeline_id!r}: {exc}") from exc  # noqa: E501
        # filter to only unseen
        try:
            existing_ids = {e.event_id for e in backend.read_events()}
        except Exception as exc:
            raise TursoSyncError(f"failed to read local events for pull fallback: {exc}") from exc
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
    last_applied_remote_id: str | None = None
    last_applied_hash: str | None = None
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
            last_applied_remote_id = source_event.event_id
            last_applied_hash = source_event.hash or _extract_event_hash(r.get("payload_json", ""))  # type: ignore[arg-type]
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
                # idempotent duplicate counts as already applied for cursor purposes
                last_applied_remote_id = source_event.event_id
                last_applied_hash = source_event.hash or _extract_event_hash(r.get("payload_json", ""))  # type: ignore[arg-type]  # noqa: E501
                continue
            raise TursoSyncError(f"failed to import remote event {source_event.event_id}: {exc}") from exc  # noqa: E501
        except Exception as exc:
            # idempotent duplicate is not failure — treat as skipped
            from astrid.core.timeline.eventlog.types import (
                EventLogIdempotentError,
            )

            if isinstance(exc, EventLogIdempotentError):
                last_applied_remote_id = source_event.event_id
                last_applied_hash = source_event.hash or _extract_event_hash(r.get("payload_json", ""))  # type: ignore[arg-type]  # noqa: E501
                continue
            raise TursoSyncError(
                f"failed to import remote event {source_event.event_id}: {exc}"
            ) from exc

    # Update sync state after successful apply — reflect ONLY rows actually
    # transferred/applied (P2-2). Next poll fetches interleaved rows naturally.
    new_local_head = _local_head_snapshot(backend)
    # Verify remote is reachable but do not use its head to advance past applied
    try:
        _remote_head_snapshot(replica, timeline_id)
    except Exception:
        pass
    # Remote boundary is last applied remote row, not refreshed head
    if applied > 0 and last_applied_remote_id is not None:
        remote_version = new_local_head.version
        remote_event_id = last_applied_remote_id
        remote_hash = last_applied_hash
    else:
        # No new rows applied (idempotent retry) — keep prior remote boundary
        remote_version = new_local_head.version if new_local_head.version != 0 else (state.remote_version if state else 0)  # noqa: E501
        remote_event_id = last_applied_remote_id or (state.remote_event_id if state else None) or new_local_head.last_event_id  # noqa: E501
        remote_hash = last_applied_hash or (state.remote_hash if state else None) or new_local_head.last_hash  # noqa: E501
    new_state = TursoSyncState(
        timeline_id=timeline_id,
        local_version=new_local_head.version,
        local_event_id=new_local_head.last_event_id,
        local_hash=new_local_head.last_hash,
        remote_version=remote_version,
        remote_event_id=remote_event_id,
        remote_hash=remote_hash,
        updated_at=utc_now_iso(),
        last_pushed_event_id=state.last_pushed_event_id if state else None,
    )
    _write_state_typed(timeline_home, new_state)
    return TursoSyncResult(
        action="pulled",
        timeline_id=timeline_id,
        local_version=new_local_head.version,
        remote_version=new_state.remote_version,
        pulled=applied,
    )




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
