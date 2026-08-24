"""Public event-stream read and subscribe endpoints.

These functions adapt SDK calls to the core task event infrastructure.
They resolve internal helpers through ``astrid.sdk`` so monkeypatch seams
applied to the package namespace are visible at call time.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from astrid.core.foundation.project_paths import run_dir as project_run_dir
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.foundation.project_paths import validate_project_slug
from astrid.core.events import EVENTS_FILENAME, EventLogError
from astrid.core.events.service import (
    DATA_KEY,
    EVENT_HASH_KEY,
    INTEGRITY_KEY,
    PREVIOUS_EVENT_HASH_KEY,
    payload_event_hash,
)
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.receipts.canonical import CanonicalizationError, parse_json

from ._module import _sdk_module
from .dto import EventStreamRecord
from .exceptions import (
    AstridSDKError,
    CapabilityInvocationError,
    _sdk_error_from_event_exception,
)


def _resolve_event_stream_run_dir(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
) -> Path:
    """Resolve the filesystem path for a run's event stream directory.

    This function is exposed on ``astrid.sdk`` so tests can monkeypatch it.
    The public endpoints (``read_events``, ``subscribe_events``) resolve it
    through ``astrid.sdk`` to respect those monkeypatches.
    """
    slug = validate_project_slug(project)
    run_path = project_run_dir(slug, run_id, root=projects_root)
    if not run_path.is_dir():
        raise FileNotFoundError(f"run {run_id!r} not found in project {slug!r}")
    events_path = run_path / EVENTS_FILENAME
    if not events_path.is_file():
        raise FileNotFoundError(
            f"run {run_id!r} in project {slug!r} has no {EVENTS_FILENAME}"
        )
    return run_path


_KERNEL_EVENT_SELECT = (
    "SELECT event_id, project_id, project_seq, stream_id, seq, "
    "subject_type, subject_id, changes_json, kind, schema_version, "
    "idempotency_key, txn_id, actor_kind, payload_json, created_at "
    "FROM events"
)


def _read_kernel_event_stream(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    verify: bool = True,
) -> tuple[EventStreamRecord, ...]:
    """Read one run stream from the canonical kernel ledger.

    The filesystem ``events.jsonl`` is a local-process provenance projection,
    not the execution authority. Portable backups intentionally preserve the
    SQLite kernel but need not preserve that projection. This read-only
    fallback therefore addresses the project and run in SQLite and emits the
    same public DTO shape, while retaining the kernel event id/sequence/hash
    fields in ``payload``. It never creates a database or filesystem files.
    """

    slug = validate_project_slug(project)
    database_path = derive_database_path(resolve_projects_root(projects_root))
    if not database_path.is_file():
        raise FileNotFoundError(
            f"run {run_id!r} not found in project {slug!r}: "
            f"kernel database is absent at {database_path}"
        )

    uri = f"file:{database_path.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise EventLogError(
            f"kernel event ledger could not be opened read-only: {exc}"
        ) from exc
    connection.row_factory = sqlite3.Row
    try:
        project_row = connection.execute(
            "SELECT id FROM projects WHERE slug = ?", (slug,)
        ).fetchone()
        if project_row is None:
            raise FileNotFoundError(f"project {slug!r} not found")
        project_id = str(project_row["id"])
        run_row = connection.execute(
            "SELECT id FROM runs WHERE id = ? AND project_id = ?",
            (run_id, project_id),
        ).fetchone()
        if run_row is None:
            # This deliberately rejects a run from another project even when
            # its id is otherwise valid: project scoping is part of the read
            # contract and prevents cross-project event disclosure.
            raise FileNotFoundError(
                f"run {run_id!r} not found in project {slug!r}"
            )
        stream_id = f"{run_id}:core.run"
        stream_row = connection.execute(
            "SELECT head_seq FROM event_streams WHERE id = ? AND project_id = ?",
            (stream_id, project_id),
        ).fetchone()
        if stream_row is None:
            raise FileNotFoundError(
                f"run {run_id!r} in project {slug!r} has no kernel event stream"
            )
        rows = connection.execute(
            _KERNEL_EVENT_SELECT + " WHERE stream_id = ? ORDER BY seq ASC",
            (stream_id,),
        ).fetchall()
        head_seq = int(stream_row["head_seq"])
        if len(rows) != head_seq:
            raise EventLogError(
                f"kernel event verification failed for stream {stream_id!r}: "
                f"head seq is {head_seq} but {len(rows)} events are stored"
            )

        records: list[EventStreamRecord] = []
        previous_hash: str | None = None
        for index, row in enumerate(rows):
            seq = int(row["seq"])
            if seq != index + 1:
                raise EventLogError(
                    f"kernel event verification failed for stream {stream_id!r} "
                    f"at position {index}: expected seq {index + 1}, found {seq}"
                )
            try:
                payload = parse_json(row["payload_json"])
                changes = parse_json(row["changes_json"])
            except CanonicalizationError as exc:
                raise EventLogError(
                    f"kernel event verification failed for event "
                    f"{row['event_id']!r}: invalid JSON: {exc}"
                ) from exc
            if not isinstance(payload, dict) or not isinstance(changes, list):
                raise EventLogError(
                    f"kernel event verification failed for event "
                    f"{row['event_id']!r}: malformed event envelope"
                )
            integrity = payload.get(INTEGRITY_KEY)
            if not isinstance(integrity, dict):
                raise EventLogError(
                    f"kernel event verification failed for event "
                    f"{row['event_id']!r}: missing {INTEGRITY_KEY!r} envelope"
                )
            event_hash = integrity.get(EVENT_HASH_KEY)
            stored_previous = integrity.get(PREVIOUS_EVENT_HASH_KEY)
            if not isinstance(event_hash, str) or not event_hash:
                raise EventLogError(
                    f"kernel event verification failed for event "
                    f"{row['event_id']!r}: missing {EVENT_HASH_KEY!r}"
                )
            if stored_previous != previous_hash:
                raise EventLogError(
                    f"kernel event verification failed for event "
                    f"{row['event_id']!r}: previous hash mismatch"
                )
            if verify:
                recomputed = payload_event_hash(payload)
                if recomputed != event_hash:
                    raise EventLogError(
                        f"kernel event verification failed for event "
                        f"{row['event_id']!r}: event hash mismatch"
                    )
            previous_hash = event_hash
            public_payload: dict[str, Any] = {
                "event_id": row["event_id"],
                "project_id": row["project_id"],
                "project_seq": int(row["project_seq"]),
                "stream_id": row["stream_id"],
                "seq": seq,
                "subject_type": row["subject_type"],
                "subject_id": row["subject_id"],
                "changes": changes,
                "kind": row["kind"],
                "schema_version": int(row["schema_version"]),
                "idempotency_key": row["idempotency_key"],
                "txn_id": row["txn_id"],
                "actor_kind": row["actor_kind"],
                DATA_KEY: payload.get(DATA_KEY, {}),
                EVENT_HASH_KEY: event_hash,
                PREVIOUS_EVENT_HASH_KEY: stored_previous,
                "created_at": row["created_at"],
            }
            records.append(
                EventStreamRecord(
                    source="kernel",
                    line=seq,
                    timestamp=row["created_at"],
                    kind=row["kind"],
                    hash=event_hash,
                    payload=public_payload,
                )
            )
        return tuple(records)
    except sqlite3.Error as exc:
        raise EventLogError(f"kernel event ledger read failed: {exc}") from exc
    finally:
        connection.close()


def read_events(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    include_audit: bool = True,
    verify: bool = True,
) -> tuple[EventStreamRecord, ...]:
    """Return a verified read-only task/audit event snapshot for one run."""

    _sdk = _sdk_module()
    try:
        run_path = _sdk._resolve_event_stream_run_dir(project, run_id, projects_root=projects_root)
        return tuple(
            _sdk._read_task_event_stream(
                run_path,
                include_audit=include_audit,
                verify=verify,
            )
        )
    except FileNotFoundError:
        # ``events.jsonl`` is an optional local-process projection. Portable
        # restores preserve the canonical SQLite run/event ledger instead, so
        # fall back to its read-only run stream when that projection is absent.
        try:
            return _read_kernel_event_stream(
                project,
                run_id,
                projects_root=projects_root,
                verify=verify,
            )
        except AstridSDKError:
            raise
        except Exception as exc:
            mapped = _sdk_error_from_event_exception(exc)
            if mapped is not None:
                raise mapped from exc
            raise CapabilityInvocationError(
                f"failed to read events for project {project!r} run {run_id!r}"
            ) from exc
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_event_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to read events for project {project!r} run {run_id!r}"
        ) from exc


def subscribe_events(
    project: str,
    run_id: str,
    *,
    projects_root: str | Path | None = None,
    include_audit: bool = True,
    verify: bool = True,
    follow: bool = False,
    poll_interval: float = 0.1,
    idle_polls: int | None = None,
):
    """Yield a verified read-only task/audit event stream for one run."""

    _sdk = _sdk_module()
    try:
        run_path = _sdk._resolve_event_stream_run_dir(project, run_id, projects_root=projects_root)
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_event_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to subscribe to events for project {project!r} run {run_id!r}"
        ) from exc

    def _iter():
        try:
            yield from _sdk._subscribe_task_event_stream(
                run_path,
                include_audit=include_audit,
                verify=verify,
                follow=follow,
                poll_interval=poll_interval,
                idle_polls=idle_polls,
            )
        except AstridSDKError:
            raise
        except Exception as exc:
            mapped = _sdk_error_from_event_exception(exc)
            if mapped is not None:
                raise mapped from exc
            raise CapabilityInvocationError(
                f"failed to subscribe to events for project {project!r} run {run_id!r}"
            ) from exc

    return _iter()


__all__ = [
    "_resolve_event_stream_run_dir",
    "read_events",
    "subscribe_events",
]
