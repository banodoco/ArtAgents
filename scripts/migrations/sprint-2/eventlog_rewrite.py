"""Migration-only helpers for rewriting Sprint 2 timeline event logs."""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

from astrid.core._shared.jsonio import write_json_atomic
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import (
    TimelineEvent,
    canonical_json_bytes,
    with_event_hash,
)


class EventLogRewriteError(RuntimeError):
    """Raised when a migration event-log rewrite cannot be verified."""


def rewrite_local_fs_event_log_from_index(
    *,
    timeline_home: Path,
    events: Sequence[TimelineEvent],
    first_changed_index: int,
) -> dict[str, Any]:
    """Rewrite a LocalFs event log after mutating historical events.

    ``events`` is the full desired stream in order. Events before
    ``first_changed_index`` are preserved; the changed event and every
    downstream event have ``prev_hash`` and ``hash`` recomputed with the same
    ``with_event_hash`` contract used by ``LocalFsBackend.verify_chain()``.
    """
    timeline_home = Path(timeline_home)
    events_path = timeline_home / "assembly.jsonl"
    head_path = timeline_home / "assembly.head.json"
    if first_changed_index < 0 or first_changed_index > len(events):
        raise EventLogRewriteError("first_changed_index is outside the event stream")
    if not events:
        raise EventLogRewriteError("cannot rewrite an empty event stream")

    rewritten = list(events)
    for index in range(first_changed_index, len(rewritten)):
        prev_hash = rewritten[index - 1].hash if index > 0 else None
        unhashed = TimelineEvent.from_dict({
            **rewritten[index].to_json_obj(),
            "prev_hash": prev_hash,
            "hash": None,
        })
        rewritten[index] = with_event_hash(unhashed, prev_hash=prev_hash)

    timeline_home.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(events_path, os.O_CREAT | os.O_RDWR, 0o644)
    except OSError as exc:
        raise EventLogRewriteError(f"failed to open {events_path}: {exc}") from exc

    tmp_name: str | None = None
    try:
        with os.fdopen(fd, "a+b", closefd=True) as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                tmp = tempfile.NamedTemporaryFile(
                    mode="wb",
                    suffix=".jsonl",
                    dir=events_path.parent,
                    delete=False,
                )
                try:
                    for event in rewritten:
                        tmp.write(canonical_json_bytes(event.to_json_obj()) + b"\n")
                    tmp.flush()
                    os.fsync(tmp.fileno())
                    tmp_name = tmp.name
                finally:
                    tmp.close()

                handle.seek(0)
                handle.truncate()
                with open(tmp_name, "rb") as tmp_file:
                    shutil.copyfileobj(tmp_file, handle)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise EventLogRewriteError(f"failed to rewrite {events_path}: {exc}") from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass

    tail = rewritten[-1]
    write_json_atomic(
        head_path,
        {
            "timeline_id": tail.timeline_id,
            "last_event_id": tail.event_id,
            "last_hash": tail.hash,
            "event_count": len(rewritten),
            "version": len(rewritten),
        },
    )

    verification = LocalFsBackend(
        timeline_id=tail.timeline_id,
        timeline_home=timeline_home,
    ).verify_chain()
    if not verification.ok:
        raise EventLogRewriteError(
            f"rewritten event log failed verification: {verification.error}"
        )

    return {
        "rewritten_count": len(rewritten) - first_changed_index,
        "head_event_count": len(rewritten),
        "head_version": len(rewritten),
        "last_event_id": tail.event_id,
        "last_hash": tail.hash,
    }
