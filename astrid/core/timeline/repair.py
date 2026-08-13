"""Erasure repair operations for timeline event streams.

Provides backend-level erasure repair that replaces selected historical
event payloads with the canonical ErasedPayload envelope, recomputes
downstream hash chains, and updates backend head state.

This is the core repair infrastructure — the CLI/tooling layer wraps it
with selector resolution and policy enforcement.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

from astrid.core.contracts.errors import AstridError
from astrid.core.util.time import utc_now_seconds as utc_now_iso

from .events.schema import (
    ErasedPayload,
    TimelineEvent,
    with_event_hash,
)

# ============================================================================
# Erasure repair for LocalFsBackend
# ============================================================================


def repair_erasure_local_fs(
    timeline_home: Path,
    events_path: Path,
    head_path: Path,
    target_event_ids: Sequence[str],
    *,
    reason: str,
    erased_by: str,
    policy_ref: str | None = None,
) -> dict[str, Any]:
    """Replace payloads of selected historical events with ErasedPayload envelope.

    Under the existing file lock:
    1. Read all events from the stream.
    2. Replace payloads for matching event IDs with canonical ErasedPayload.
    3. Recompute downstream prev_hash/hash for all affected events.
    4. Write the repaired stream to a temp file and atomically replace.
    5. Rebuild and write the head.
    6. Delete compatibility projections (assembly.checkpoint.json, assembly.json)
       so they are regenerated from events only on next read.

    Returns a dict with keys: replaced_count, downstream_count, head_event_count,
    head_version, last_event_id, last_hash.

    Ignores event IDs that are not found in the stream.
    Events already carrying ErasedPayload are not re-erased (idempotent).
    """
    import fcntl

    erased_at = utc_now_iso()
    target_set = frozenset(target_event_ids)

    # Read all events
    all_events = _read_all_events_from_path(events_path)

    # Find which events need erasure
    to_erase: list[int] = []  # indices
    for i, evt in enumerate(all_events):
        if evt.event_id in target_set:
            # Idempotent: skip if already erased
            if isinstance(evt.payload, ErasedPayload):
                continue
            to_erase.append(i)

    if not to_erase:
        return {
            "replaced_count": 0,
            "downstream_count": 0,
            "head_event_count": len(all_events),
            "head_version": len(all_events),
            "last_event_id": all_events[-1].event_id if all_events else None,
            "last_hash": all_events[-1].hash if all_events else None,
        }

    # Sort indices to process in order
    to_erase.sort()
    first_erased_idx = to_erase[0]

    # Build repaired event list
    repaired: list[TimelineEvent] = []
    for i, evt in enumerate(all_events):
        if i in to_erase:
            # Replace payload with canonical ErasedPayload
            erased_payload = ErasedPayload(
                erased=True,
                reason=reason,
                erased_at=erased_at,
                erased_by=erased_by,
                policy_ref=policy_ref,
            )
            # Build new event preserving all immutable audit metadata
            repaired_evt = TimelineEvent(
                schema_version=evt.schema_version,
                event_id=evt.event_id,
                timeline_id=evt.timeline_id,
                ts=evt.ts,
                actor=evt.actor,
                kind=evt.kind,
                payload=erased_payload,
                prev_hash=evt.prev_hash if i == 0 else repaired[-1].hash,
                hash=None,  # recomputed below
                expected_version=evt.expected_version,
                txn_id=evt.txn_id,
                source_backend=evt.source_backend,
                source_timeline_id=evt.source_timeline_id,
                source_event_id=evt.source_event_id,
                source_version=evt.source_version,
                source_hash=evt.source_hash,
            )
            repaired.append(repaired_evt)
        elif i >= first_erased_idx:
            # Downstream event: recompute hash chain
            prev = repaired[-1].hash if repaired else None
            downstream = TimelineEvent(
                schema_version=evt.schema_version,
                event_id=evt.event_id,
                timeline_id=evt.timeline_id,
                ts=evt.ts,
                actor=evt.actor,
                kind=evt.kind,
                payload=evt.payload,
                prev_hash=prev,
                hash=None,  # recomputed below
                expected_version=evt.expected_version,
                txn_id=evt.txn_id,
                source_backend=evt.source_backend,
                source_timeline_id=evt.source_timeline_id,
                source_event_id=evt.source_event_id,
                source_version=evt.source_version,
                source_hash=evt.source_hash,
            )
            repaired.append(downstream)
        else:
            repaired.append(evt)

    # Recompute hashes for all events from first_erased_idx onward
    for i in range(first_erased_idx, len(repaired)):
        prev_hash = repaired[i - 1].hash if i > 0 else None
        repaired[i] = with_event_hash(repaired[i], prev_hash=prev_hash)

    # Write repaired stream under lock
    created = not events_path.exists()
    try:
        fd = os.open(
            events_path, os.O_CREAT | os.O_APPEND | os.O_RDWR, 0o644
        )
    except OSError as exc:
        raise AstridError(
            f"failed to open {events_path}: {exc}",
            recovery_command="check file permissions and disk health, then retry",
        ) from exc

    try:
        with os.fdopen(fd, "a+b", closefd=True) as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                # Write repaired stream to temp file
                tmp = tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".jsonl",
                    dir=events_path.parent,
                    delete=False,
                )
                try:
                    from .events.schema import canonical_json_bytes
                    for evt in repaired:
                        line = canonical_json_bytes(evt.to_json_obj()) + b"\n"
                        tmp.write(line.decode("utf-8"))
                    tmp_name = tmp.name
                finally:
                    tmp.close()

                # Truncate and replace events file
                handle.seek(0)
                handle.truncate()
                with open(tmp_name, "rb") as tmpf:
                    shutil.copyfileobj(tmpf, handle)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                # Clean up temp file
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
    except OSError as exc:
        raise AstridError(
            f"failed to repair {events_path}: {exc}",
            recovery_command="check file permissions and disk health, then retry",
        ) from exc

    # Rebuild head
    head = _rebuild_head(repaired, head_path, events_path=events_path)

    # Delete compatibility projections so they are regenerated from events only
    _delete_if_exists(events_path.parent / "assembly.checkpoint.json")
    _delete_if_exists(events_path.parent / "assembly.json")
    # Also delete display.json so it gets regenerated
    _delete_if_exists(events_path.parent / "display.json")

    if created:
        _fsync_dir(events_path.parent)

    downstream_count = len(repaired) - first_erased_idx
    # downstream_count is events whose hash chain was recomputed
    # (includes the erased events themselves plus all later events)
    return {
        "replaced_count": len(to_erase),
        "downstream_count": downstream_count,
        "head_event_count": head.event_count,
        "head_version": head.version,
        "last_event_id": head.last_event_id,
        "last_hash": head.last_hash,
    }


# ============================================================================
# Internal helpers
# ============================================================================


def _read_all_events_from_path(events_path: Path) -> list[TimelineEvent]:
    """Read all events from a JSONL file path."""
    import json

    try:
        with events_path.open("r", encoding="utf-8") as h:
            events: list[TimelineEvent] = []
            for line in h:
                if not line.endswith("\n"):
                    raise ValueError(
                        f"{events_path} line is not newline-terminated"
                    )
                data = json.loads(line)
                events.append(TimelineEvent.from_dict(data))
            return events
    except FileNotFoundError:
        return []


def _rebuild_head(
    events: list[TimelineEvent],
    head_path: Path,
    *,
    events_path: Path | None = None,
) -> Any:
    """Rebuild and write the head from a list of events.

    When *events_path* is supplied the head also carries the incremental
    append offsets (``log_size`` / ``last_event_offset``) so subsequent
    ``append_prebuilt_events`` calls skip full-log parses.  The offsets are
    derived from the canonical line encoding used by every writer in this
    repo; the empty-log head carries ``log_size=0`` / ``last_event_offset=0``.
    """
    from astrid.core._shared.jsonio import write_json_atomic

    from .eventlog.types import EventLogHead

    if not events:
        head = EventLogHead(
            timeline_id="",
            last_event_id=None,
            last_hash=None,
            event_count=0,
            version=0,
            log_size=0,
            last_event_offset=0,
        )
    else:
        from .events.schema import canonical_json_bytes

        last = events[-1]
        log_size: int | None = None
        last_event_offset: int | None = None
        if events_path is not None and events_path.exists():
            log_size = events_path.stat().st_size
            last_line_len = len(canonical_json_bytes(last.to_json_obj())) + 1
            last_event_offset = max(0, log_size - last_line_len)
        head = EventLogHead(
            timeline_id=last.timeline_id,
            last_event_id=last.event_id,
            last_hash=last.hash,
            event_count=len(events),
            version=len(events),
            log_size=log_size,
            last_event_offset=last_event_offset,
        )
    write_json_atomic(
        head_path,
        {
            "timeline_id": head.timeline_id,
            "last_event_id": head.last_event_id,
            "last_hash": head.last_hash,
            "event_count": head.event_count,
            "version": head.version,
            "log_size": head.log_size,
            "last_event_offset": head.last_event_offset,
        },
    )
    return head


def _delete_if_exists(path: Path) -> None:
    """Delete a file if it exists, silently ignoring errors."""
    try:
        path.unlink()
    except (FileNotFoundError, OSError):
        pass


def _fsync_dir(path: Path) -> None:
    """Fsync a directory to ensure metadata is durable."""
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    fd: int | None = None
    try:
        fd = os.open(str(path), flags)
        os.fsync(fd)
    except OSError:
        pass
    finally:
        if fd is not None:
            os.close(fd)
