"""Local filesystem timeline eventlog backend."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from astrid.core.project.jsonio import read_json, write_json_atomic
from astrid.core.project.schema import utc_now_iso
from astrid.core.timeline.events.schema import (
    EVENT_SCHEMA_VERSION,
    TimelineActor,
    TimelineEvent,
    TimelineImportedPayload,
    canonical_json_bytes,
    with_event_hash,
)

from .types import (
    EventLogError,
    EventLogHead,
    EventLogStaleVersionError,
    EventLogVerification,
    TimelineVersionConflict,
)


class LocalFsBackend:
    """Append-only JSONL eventlog rooted at one timeline directory."""

    def __init__(self, *, timeline_id: str, timeline_home: str | Path) -> None:
        self.timeline_id = timeline_id
        self.timeline_home = Path(timeline_home)
        self.events_path = self.timeline_home / "assembly.jsonl"
        self.head_path = self.timeline_home / "assembly.head.json"
        self.identity_path = self.timeline_home / "assembly.identity.json"

    def backend_name(self) -> str:
        return "local_fs"

    def bootstrap_legacy(
        self,
        *,
        actor: TimelineActor,
    ) -> tuple[str, dict[str, Any]]:
        """Bootstrap a true-legacy timeline (no identity sidecar) into the
        event-sourced model.

        Synthesises a ``timeline.imported`` event from the compatibility
        files on disk, writes the identity sidecar with provenance
        ``"imported"``, and returns ``(timeline_id, identity_dict)``.

        After this call the caller can resolve the backend normally and
        append domain events.

        Raises ``EventLogError`` when the compatibility files cannot be
        read or the identity cannot be written.
        """
        self.timeline_home.mkdir(parents=True, exist_ok=True)
        imported_event = self._build_imported_event(actor=actor, prev_hash=None)
        identity = self._write_imported_identity(imported_event.timeline_id)

        # Write the imported event into the event log.
        created = not self.events_path.exists()
        try:
            fd = os.open(
                self.events_path, os.O_CREAT | os.O_APPEND | os.O_RDWR, 0o644
            )
        except OSError as exc:
            raise EventLogError(
                f"failed to open {self.events_path}: {exc}"
            ) from exc

        try:
            with os.fdopen(fd, "a+b", closefd=True) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    self._append_line_locked(handle, imported_event)
                    head = self._rebuild_head_locked()
                    self._write_head_atomic(head)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise EventLogError(
                f"failed to write imported event to {self.events_path}: {exc}"
            ) from exc

        if created:
            _fsync_dir(self.timeline_home)
        return imported_event.timeline_id, identity

    def append_event(
        self,
        timeline_id: str,
        kind: str,
        payload: dict[str, object],
        *,
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> TimelineEvent:
        if timeline_id != self.timeline_id:
            raise EventLogError(
                f"timeline_id mismatch: expected {self.timeline_id!r}, "
                f"got {timeline_id!r}"
            )
        self.timeline_home.mkdir(parents=True, exist_ok=True)
        created = not self.events_path.exists()
        try:
            fd = os.open(self.events_path, os.O_CREAT | os.O_APPEND | os.O_RDWR, 0o644)
        except OSError as exc:
            raise EventLogError(f"failed to open {self.events_path}: {exc}") from exc

        try:
            with os.fdopen(fd, "a+b", closefd=True) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    identity = self._load_identity_locked()
                    tail = self._read_tail_event_locked(handle)
                    locked_head = self._rebuild_head_locked()
                    bootstrap_events: list[TimelineEvent] = []
                    prev_hash = tail.hash if tail is not None else None

                    if identity is None:
                        imported_event = self._build_imported_event(actor=actor, prev_hash=prev_hash)
                        bootstrap_events.append(imported_event)
                        identity = self._write_imported_identity(imported_event.timeline_id)
                        prev_hash = imported_event.hash
                        locked_head = EventLogHead(
                            timeline_id=imported_event.timeline_id,
                            last_event_id=imported_event.event_id,
                            last_hash=imported_event.hash,
                            event_count=1,
                            version=1,
                        )
                        tail = imported_event

                    if tail is not None and tail.kind == "timeline.deleted":
                        raise EventLogError(
                            f"timeline {identity['timeline_ulid']} rejects appends after timeline.deleted"
                        )

                    if expected_version is not None and expected_version != locked_head.version:
                        raise EventLogStaleVersionError(
                            TimelineVersionConflict(
                                timeline_id=identity["timeline_id"],
                                expected_version=expected_version,
                                current_version=locked_head.version,
                                last_event_id=locked_head.last_event_id,
                                last_event_kind=tail.kind if tail is not None else None,
                                last_event_summary=self._summarize_event(tail),
                            )
                        )

                    event = TimelineEvent.new(
                        timeline_id=identity["timeline_id"],
                        ts=utc_now_iso(),
                        actor=actor,
                        kind=kind,
                        payload=payload,
                        prev_hash=prev_hash,
                        expected_version=expected_version,
                        txn_id=txn_id,
                    )
                    event = with_event_hash(event, prev_hash=prev_hash)
                    to_write = [*bootstrap_events, event]
                    for item in to_write:
                        self._append_line_locked(handle, item)
                    head = self._rebuild_head_locked()
                    self._write_head_atomic(head)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise EventLogError(f"failed to append event to {self.events_path}: {exc}") from exc

        if created:
            _fsync_dir(self.timeline_home)
        return event

    def read_events(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]:
        events = self._read_all_events()
        if after is not None:
            index = next((i for i, event in enumerate(events) if event.event_id == after), None)
            if index is None:
                return []
            events = events[index + 1 :]
        if limit is not None:
            events = events[:limit]
        return events

    def head(self) -> EventLogHead:
        try:
            raw = read_json(self.head_path)
        except FileNotFoundError:
            head = self._rebuild_head()
            if head.event_count > 0:
                self._write_head_atomic(head)
            return head
        except Exception as exc:
            raise EventLogError(f"failed to read {self.head_path}: {exc}") from exc
        return EventLogHead(
            timeline_id=raw["timeline_id"],
            last_event_id=raw.get("last_event_id"),
            last_hash=raw.get("last_hash"),
            event_count=raw["event_count"],
            version=raw["version"],
        )

    def verify_chain(self) -> EventLogVerification:
        try:
            events = self._read_all_events()
        except EventLogError as exc:
            return EventLogVerification(ok=False, checked_events=0, last_event_id=None, error=str(exc))

        prev_hash: str | None = None
        last_event_id: str | None = None
        for index, event in enumerate(events):
            expected = with_event_hash(
                TimelineEvent.from_dict({**event.to_json_obj(), "hash": None}),
                prev_hash=prev_hash,
            )
            if event.prev_hash != prev_hash:
                return EventLogVerification(
                    ok=False,
                    checked_events=index,
                    last_event_id=last_event_id,
                    error=f"event {event.event_id} prev_hash mismatch",
                )
            if event.hash != expected.hash:
                return EventLogVerification(
                    ok=False,
                    checked_events=index,
                    last_event_id=last_event_id,
                    error=f"event {event.event_id} hash mismatch",
                )
            prev_hash = event.hash
            last_event_id = event.event_id
        return EventLogVerification(
            ok=True,
            checked_events=len(events),
            last_event_id=last_event_id,
            error=None,
        )

    def _load_identity_locked(self) -> dict[str, Any] | None:
        try:
            raw = read_json(self.identity_path)
        except FileNotFoundError:
            return None
        except Exception as exc:
            raise EventLogError(f"failed to read {self.identity_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise EventLogError(f"{self.identity_path} must contain a JSON object")
        return raw

    def _write_imported_identity(self, timeline_id: str) -> dict[str, Any]:
        payload = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "timeline_id": timeline_id,
            "timeline_ulid": self.timeline_home.name,
            "backend": "local_fs",
            "provenance": "imported",
            "created_at": utc_now_iso(),
        }
        write_json_atomic(self.identity_path, payload)
        return payload

    def _read_tail_event_locked(self, handle: Any) -> TimelineEvent | None:
        handle.seek(0)
        last = b""
        for line in handle:
            if line:
                last = line
        if not last:
            return None
        if not last.endswith(b"\n"):
            raise EventLogError(f"{self.events_path} contains a non-terminated JSONL line")
        try:
            data = json.loads(last.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise EventLogError(f"invalid JSON in {self.events_path}: {exc.msg}") from exc
        return TimelineEvent.from_dict(data)

    def _append_line_locked(self, handle: Any, event: TimelineEvent) -> None:
        line = canonical_json_bytes(event.to_json_obj()) + b"\n"
        handle.seek(0, os.SEEK_END)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())

    def _rebuild_head_locked(self) -> EventLogHead:
        events = self._read_all_events()
        if not events:
            return EventLogHead(
                timeline_id=self.timeline_id,
                last_event_id=None,
                last_hash=None,
                event_count=0,
                version=0,
            )
        last = events[-1]
        return EventLogHead(
            timeline_id=last.timeline_id,
            last_event_id=last.event_id,
            last_hash=last.hash,
            event_count=len(events),
            version=len(events),
        )

    def _rebuild_head(self) -> EventLogHead:
        return self._rebuild_head_locked()

    def _write_head_atomic(self, head: EventLogHead) -> None:
        write_json_atomic(
            self.head_path,
            {
                "timeline_id": head.timeline_id,
                "last_event_id": head.last_event_id,
                "last_hash": head.last_hash,
                "event_count": head.event_count,
                "version": head.version,
            },
        )

    def _read_all_events(self) -> list[TimelineEvent]:
        try:
            with self.events_path.open("r", encoding="utf-8") as handle:
                events: list[TimelineEvent] = []
                for line_number, line in enumerate(handle, start=1):
                    if not line.endswith("\n"):
                        raise EventLogError(
                            f"{self.events_path} line {line_number} is not newline-terminated"
                        )
                    data = json.loads(line)
                    events.append(TimelineEvent.from_dict(data))
                return events
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as exc:
            raise EventLogError(f"invalid JSON in {self.events_path}: {exc.msg}") from exc
        except OSError as exc:
            raise EventLogError(f"failed to read {self.events_path}: {exc}") from exc

    def _build_imported_event(self, *, actor: TimelineActor, prev_hash: str | None) -> TimelineEvent:
        snapshot: dict[str, Any] = {}
        for name in ("display.json", "manifest.json", "assembly.json"):
            path = self.timeline_home / name
            if not path.is_file():
                continue
            snapshot[name] = read_json(path)
        imported = TimelineEvent.new(
            timeline_id=str(uuid4()),
            ts=utc_now_iso(),
            actor=actor,
            kind="timeline.imported",
            payload=TimelineImportedPayload(snapshot=snapshot, source="legacy_local"),
            prev_hash=prev_hash,
        )
        return with_event_hash(imported, prev_hash=prev_hash)

    def _summarize_event(self, event: TimelineEvent | None) -> str | None:
        if event is None:
            return None
        return f"{event.kind}#{event.event_id}"


def _fsync_dir(path: Path) -> None:
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    fd: int | None = None
    try:
        fd = os.open(path, flags)
        os.fsync(fd)
    except OSError as exc:
        if exc.errno not in {errno.EINVAL, errno.ENOTSUP, errno.EBADF}:
            raise
    finally:
        if fd is not None:
            os.close(fd)
