"""Run-lease helpers.

The lease lives at ``runs/<run_id>/lease.json`` with schema::

    {"writer_epoch": int, "attached_session_id": str | None, "plan_hash": str}

The epoch is the fence: every event append CAS-checks it (see
:func:`astrid.core.task.events.append_event_locked`), so a stale writer that
loses a takeover race is rejected at append time, not silently committed.

Takeover/orphan-claim/release ALL acquire the same ``fcntl.flock(LOCK_EX)``
on ``events.jsonl`` that :func:`append_event_locked` uses — this is what
serializes a takeover against an in-flight append.

Implementation contract:

* Lease rewrites must start from the normalized current lease and update only
  the keys owned by the operation. Preserve passthrough metadata such as
  ``timeline_id``, ``plan_hash``, and unknown future fields across takeover,
  orphan claim, and release.
* Takeover and orphan-claim helpers are the only production task-run write path
  allowed to emit an event outside ``WriterContext.append()``. They do it
  while holding the same events-file flock as the lease rewrite.
* Warm-target refusal must be computed from pre-touch file state. Do not
  create or touch ``events.jsonl`` before deciding whether the target is warm;
  touching first can make a cold run look live and block legitimate takeover.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from astrid.core.project.jsonio import write_json_atomic
from astrid.core.session.constants import STUCK_NO_EVENT_SECONDS
from astrid.core.task.events import (
    EVENTS_FILENAME,
    LEASE_FILENAME,
    append_event_to_locked_handle,
)
from astrid.core.util.time import utc_now_iso

LEASE_DEFAULTS: dict[str, Any] = {
    "writer_epoch": 0,
    "attached_session_id": None,
    "plan_hash": "",
}


class LeaseError(RuntimeError):
    """Raised when the lease file is malformed or operation preconditions fail."""


class LeaseRecoveryHintError(LeaseError):
    """Lease precondition failure with an operator-facing recovery hint."""

    def __init__(self, message: str, *, recovery_hint: str) -> None:
        self.recovery_hint = recovery_hint
        super().__init__(f"{message} ({recovery_hint})")


def read_lease(run_dir: str | Path) -> dict[str, Any]:
    """Return the normalized lease dict.

    Missing, unreadable, malformed, or incomplete canonical leases are hard
    errors. The only approved missing-lease recovery path is the explicit
    legacy active-run migration that writes a lease before writer auth.
    """

    lease_path = Path(run_dir) / LEASE_FILENAME
    try:
        raw = lease_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise LeaseError(
            f"missing lease {lease_path}; recovery: migrate legacy active_run.json "
            "or start/take over a run to create canonical lease state"
        )
    except OSError as exc:
        raise LeaseError(f"unreadable lease {lease_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LeaseError(f"invalid JSON in lease {lease_path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise LeaseError(f"lease {lease_path} must be a JSON object")
    return _normalize_lease(data, lease_path)


def write_lease_init(
    run_dir: str | Path,
    *,
    session_id: str,
    plan_hash: str,
    timeline_id: str | None = None,
) -> dict[str, Any]:
    """Write the initial lease for a new run (atomic tmp+os.replace).

    Use this in ``cmd_start`` BEFORE writing ``current_run.json`` so that any
    reader observing the new current-run pointer is guaranteed to find a
    lease behind it.

    *timeline_id* is a passthrough field — Sprint 5a consumers check it
    defensively and fall back to ``project.json`` default when absent.
    """

    payload: dict[str, Any] = {
        "writer_epoch": 0,
        "attached_session_id": session_id,
        "plan_hash": plan_hash,
    }
    if timeline_id is not None:
        payload["timeline_id"] = timeline_id
    write_json_atomic(Path(run_dir) / LEASE_FILENAME, payload)
    return payload


def bump_epoch_and_swap_session(
    run_dir: str | Path,
    *,
    new_session_id: str,
    prev_session_id: str | None,
    reason: str,
    force: bool = False,
) -> dict[str, Any]:
    """Atomically bump ``writer_epoch`` and swap the lease writer.

    Holds the SAME ``fcntl.flock(LOCK_EX)`` on ``events.jsonl`` that
    :func:`append_event_locked` uses, then:

    1. Reads the current lease (under the lock).
    2. Increments ``writer_epoch`` (N → N+1), swaps ``attached_session_id``
       to ``new_session_id``, preserves ``plan_hash``, atomically rewrites
       ``lease.json``.
    3. Appends a ``takeover`` event with ``expected_writer_epoch = N+1`` (the
       lease already holds N+1 by the time we call into append_event_locked,
       which re-reads the epoch under the same flock).
    """

    run_path = Path(run_dir)
    events_path = run_path / EVENTS_FILENAME
    lease_path = run_path / LEASE_FILENAME
    run_path.mkdir(parents=True, exist_ok=True)

    with events_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            _raise_if_events_file_warm(handle, force=force, operation="takeover")
            current = _read_lease_under_lock(lease_path)
            prev_epoch = current["writer_epoch"]
            new_epoch = prev_epoch + 1
            prev_writer = current["attached_session_id"]
            updated = dict(current)
            updated["writer_epoch"] = new_epoch
            updated["attached_session_id"] = new_session_id
            write_json_atomic(lease_path, updated)

            takeover_event = {
                "kind": "takeover",
                "prev_session": prev_writer if prev_writer is not None else prev_session_id,
                "new_session": new_session_id,
                "prev_epoch": prev_epoch,
                "new_epoch": new_epoch,
                "reason": reason,
                "ts": _utc_now_iso(),
            }
            append_event_to_locked_handle(handle, takeover_event)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return updated


def claim_orphan_lease(
    run_dir: str | Path,
    *,
    new_session_id: str,
    force: bool = False,
) -> dict[str, Any]:
    """Claim a lease whose ``attached_session_id`` is ``None``.

    Same flock as :func:`bump_epoch_and_swap_session`. Sets the writer AND
    bumps the epoch by 1 so any stale appender from the previous era is
    rejected via :class:`StaleEpochError`.
    """

    run_path = Path(run_dir)
    events_path = run_path / EVENTS_FILENAME
    lease_path = run_path / LEASE_FILENAME
    run_path.mkdir(parents=True, exist_ok=True)

    with events_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            _raise_if_events_file_warm(handle, force=force, operation="orphan claim")
            current = _read_lease_under_lock(lease_path)
            if current["attached_session_id"] is not None:
                raise LeaseRecoveryHintError(
                    "claim_orphan_lease requires lease.attached_session_id == None; "
                    f"current writer is {current['attached_session_id']!r}",
                    recovery_hint="use sessions takeover --force for an attached writer",
                )
            prev_epoch = current["writer_epoch"]
            new_epoch = prev_epoch + 1
            updated = dict(current)
            updated["writer_epoch"] = new_epoch
            updated["attached_session_id"] = new_session_id
            write_json_atomic(lease_path, updated)

            event = {
                "kind": "takeover",
                "prev_session": None,
                "new_session": new_session_id,
                "prev_epoch": prev_epoch,
                "new_epoch": new_epoch,
                "reason": "orphan-claim",
                "ts": _utc_now_iso(),
            }
            append_event_to_locked_handle(handle, event)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return updated


def _raise_if_events_file_warm(handle: Any, *, force: bool, operation: str) -> None:
    """Refuse warm takeover/orphan mutation while holding the events lock.

    The check uses the locked file descriptor's current stat. Opening an absent
    events file creates an empty file, but empty files are cold by contract; a
    real warm signal requires existing event bytes with a recent mtime.
    """

    if force:
        return
    stat = os.fstat(handle.fileno())
    if stat.st_size <= 0:
        return
    age = time.time() - stat.st_mtime
    if age < STUCK_NO_EVENT_SECONDS:
        raise LeaseRecoveryHintError(
            f"{operation} refused because target wrote within the last "
            f"{STUCK_NO_EVENT_SECONDS}s",
            recovery_hint="confirm the previous writer is dead, then re-run with --force",
        )


def release_writer_lease(run_dir: str | Path) -> dict[str, Any]:
    """Clear ``attached_session_id`` under the same flock; preserve epoch + plan_hash."""

    run_path = Path(run_dir)
    events_path = run_path / EVENTS_FILENAME
    lease_path = run_path / LEASE_FILENAME
    run_path.mkdir(parents=True, exist_ok=True)

    with events_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            current = _read_lease_under_lock(lease_path)
            updated = dict(current)
            updated["attached_session_id"] = None
            write_json_atomic(lease_path, updated)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return updated


def _read_lease_under_lock(lease_path: Path) -> dict[str, Any]:
    try:
        raw = lease_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise LeaseError(
            f"missing lease {lease_path}; recovery: migrate legacy active_run.json "
            "or start/take over a run to create canonical lease state"
        )
    except OSError as exc:
        raise LeaseError(f"unreadable lease {lease_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LeaseError(f"invalid JSON in lease {lease_path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise LeaseError(f"lease {lease_path} must be a JSON object")
    return _normalize_lease(data, lease_path)


def _normalize_lease(data: dict[str, Any], lease_path: Path) -> dict[str, Any]:
    missing = [key for key in LEASE_DEFAULTS if key not in data]
    if missing:
        joined = ", ".join(missing)
        raise LeaseError(f"lease {lease_path} missing required key(s): {joined}")
    out = dict(data)
    epoch = out["writer_epoch"]
    if not isinstance(epoch, int) or isinstance(epoch, bool):
        raise LeaseError(f"lease {lease_path} writer_epoch must be an int, got {epoch!r}")
    attached = out["attached_session_id"]
    if attached is not None and not isinstance(attached, str):
        raise LeaseError(
            f"lease {lease_path} attached_session_id must be a string or null, got {attached!r}"
        )
    plan_hash = out["plan_hash"]
    if not isinstance(plan_hash, str):
        raise LeaseError(f"lease {lease_path} plan_hash must be a string, got {plan_hash!r}")
    return out


def _utc_now_iso() -> str:
    return utc_now_iso()
