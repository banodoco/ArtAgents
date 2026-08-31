"""Local filesystem timeline eventlog backend."""

from __future__ import annotations

import errno
import fcntl
import json
import os
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import read_json, write_json_atomic
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineEvent,
    canonical_json_bytes,
    with_event_hash,
)
from astrid.core.util.time import utc_now_seconds as utc_now_iso

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
        # Test instrumentation: number of full-log parses performed by this
        # instance (incremental append path must keep this at 0).
        self.full_log_reads = 0

    def backend_name(self) -> str:
        return "local_fs"

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
                    prev_hash = tail.hash if tail is not None else None

                    if identity is None:
                        raise EventLogError(
                            "timeline identity sidecar is missing; create the "
                            "timeline through the runtime before appending events."
                        )

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
                    self._append_line_locked(handle, event)
                    head = self._rebuild_head_locked()
                    self._write_head_atomic(head)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise EventLogError(f"failed to append event to {self.events_path}: {exc}") from exc

        if created:
            _fsync_dir(self.timeline_home)
        return event

    def preflight_append(
        self,
        *,
        actor: TimelineActor,
        kinds: list[str] | None = None,
    ) -> None:
        """Prove append capability without mutating any state.

        Read-only probe used by write gateways BEFORE any non-eventlog
        commit (e.g. the kernel ``replace_config`` receipt): runs the same
        deterministic checks :meth:`append_event` runs — identity sidecar
        presence, post-delete tombstone, and log writability — while
        creating nothing, writing nothing, and taking no lock. Transient
        failures (races, lock contention, disk-full at write time) remain
        the append path's to report. *actor* and *kinds* carry no local
        preconditions; they exist so every backend shares one preflight
        signature.
        """
        identity = self._load_identity_locked()
        if identity is None:
            raise EventLogError(
                "timeline identity sidecar is missing; create the timeline "
                "through the runtime before appending events."
            )
        if self.events_path.exists():
            if not os.access(self.events_path, os.W_OK):
                raise EventLogError(
                    f"event log {self.events_path} is not writable"
                )
            with self.events_path.open("rb") as handle:
                tail = self._read_tail_event_locked(handle)
            if tail is not None and tail.kind == "timeline.deleted":
                raise EventLogError(
                    f"timeline {identity['timeline_ulid']} rejects appends after timeline.deleted"
                )
        elif not os.access(self.timeline_home, os.W_OK):
            raise EventLogError(
                f"timeline home {self.timeline_home} is not writable"
            )

    def append_prebuilt_events(
        self,
        timeline_id: str,
        events: list[TimelineEvent],
        *,
        expected_version: int | None = None,
    ) -> list[TimelineEvent]:
        """Append preconstructed events without changing their IDs or hashes.

        Incremental fast path: reads ONLY the tail region of the log via the
        head's crash-reconciled ``log_size`` / ``last_event_offset``, validates
        the entire batch up front, then writes the batch with a single write +
        single fsync and writes a new head computed from known offsets — no
        full-log parse.  Full-log parsing happens only when the head is missing
        or predates the offset fields (cold start / legacy / corruption).
        """
        if timeline_id != self.timeline_id:
            raise EventLogError(
                f"timeline_id mismatch: expected {self.timeline_id!r}, "
                f"got {timeline_id!r}"
            )
        if not events:
            return []

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
                    if identity is None:
                        raise EventLogError(
                            "timeline identity sidecar is missing; create the "
                            "timeline through the runtime before appending events."
                        )

                    # Fast path: trusted head carrying the new offset fields;
                    # full rebuild only for cold start / legacy / corrupt head.
                    head = self._read_head_for_append(handle)
                    if head is None:
                        head = self._rebuild_head_locked()

                    tail, effective = self._reconcile_tail_locked(handle, head)

                    if tail is not None and tail.kind == "timeline.deleted":
                        raise EventLogError(
                            f"timeline {identity['timeline_ulid']} rejects appends after timeline.deleted"
                        )

                    if expected_version is not None and expected_version != effective["version"]:
                        raise EventLogStaleVersionError(
                            TimelineVersionConflict(
                                timeline_id=identity["timeline_id"],
                                expected_version=expected_version,
                                current_version=effective["version"],
                                last_event_id=effective["last_event_id"],
                                last_event_kind=tail.kind if tail is not None else None,
                                last_event_summary=self._summarize_event(tail),
                            )
                        )

                    # Validate the ENTIRE batch before writing anything so a
                    # bad middle event cannot leave a torn log.
                    prev_hash = tail.hash if tail is not None else None
                    for event in events:
                        if event.timeline_id != identity["timeline_id"]:
                            raise EventLogError(
                                f"prebuilt event {event.event_id} timeline_id does not match "
                                f"{identity['timeline_id']}"
                            )
                        if event.prev_hash != prev_hash:
                            raise EventLogError(
                                f"prebuilt event {event.event_id} prev_hash does not match "
                                "the current tail"
                            )
                        expected = with_event_hash(
                            TimelineEvent.from_dict({**event.to_json_obj(), "hash": None}),
                            prev_hash=prev_hash,
                        )
                        if event.hash != expected.hash:
                            raise EventLogError(
                                f"prebuilt event {event.event_id} hash does not match "
                                "Astrid canonical hashing"
                            )
                        prev_hash = event.hash

                    # Single write + single fsync for the whole event batch.
                    lines = [
                        canonical_json_bytes(event.to_json_obj()) + b"\n"
                        for event in events
                    ]
                    batch_bytes = b"".join(lines)
                    handle.seek(0, os.SEEK_END)
                    handle.write(batch_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())

                    # New head computed from known offsets — no rescan.
                    new_head = EventLogHead(
                        timeline_id=effective["timeline_id"],
                        last_event_id=events[-1].event_id,
                        last_hash=events[-1].hash,
                        event_count=effective["event_count"] + len(events),
                        version=effective["version"] + len(events),
                        log_size=effective["log_size"] + len(batch_bytes),
                        last_event_offset=(
                            effective["log_size"] + sum(len(line) for line in lines[:-1])
                            if lines
                            else effective["log_size"]
                        ),
                    )
                    self._write_head_atomic(new_head)
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise EventLogError(f"failed to append prebuilt events to {self.events_path}: {exc}") from exc

        if created:
            _fsync_dir(self.timeline_home)
        return list(events)

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

    def read_tail_events(self, *, limit: int = 64) -> list[TimelineEvent]:
        """Return the last up-to-*limit* complete events, in forward order.

        Reads ONLY the tail region of the log by walking backward from EOF
        (never a full-log parse).  A torn trailing line (crash residue) is
        silently dropped, matching the append path's truncation behaviour.
        Raises ``EventLogError`` when the log holds no complete line.

        Used by the checkpoint-cold projection bootstrap: when the tail's
        oldest event resets the assembly (``timeline.config_replaced`` /
        ``timeline.recovered``), the full projection equals the projection
        of this suffix alone.
        """
        if limit <= 0:
            return []
        try:
            size = self.events_path.stat().st_size
        except FileNotFoundError:
            return []
        if size <= 0:
            return []

        complete: list[bytes] = []  # complete lines, newest-first
        with self.events_path.open("rb") as handle:
            pos = size
            fragment = b""  # partial line bytes (carried across chunk boundaries)
            while pos > 0 and len(complete) < limit:
                step = min(64 * 1024, pos)
                pos -= step
                handle.seek(pos)
                data = handle.read(step) + fragment
                nl = data.find(b"\n")
                if nl == -1:
                    # The whole window is one (unterminated) partial line.
                    fragment = data
                    continue
                # ``data[:nl + 1]`` is a line whose start precedes this window
                # (carried forward); everything after it is complete lines.
                fragment = data[: nl + 1]
                rest = data[nl + 1 :]
                if not rest.endswith(b"\n"):
                    # Torn trailing line at EOF: drop it.
                    cut = rest.rfind(b"\n")
                    rest = b"" if cut == -1 else rest[: cut + 1]
                for line in reversed(rest.split(b"\n")):
                    if line:
                        complete.append(line)
                        if len(complete) >= limit:
                            break
            if pos == 0 and fragment and len(complete) < limit:
                if fragment.endswith(b"\n"):
                    complete.append(fragment[:-1])
                else:
                    raise EventLogError(
                        f"{self.events_path} contains a non-terminated JSONL line"
                    )

        events: list[TimelineEvent] = []
        for line in reversed(complete):
            try:
                data = json.loads(line.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("tail line is not a JSON object")
                events.append(TimelineEvent.from_dict(data))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise EventLogError(f"invalid JSON in {self.events_path}: {exc}") from exc
        return events

    def head(self) -> EventLogHead:
        """Return the crash-reconciled head, rebuilding it when corrupt.

        Never trusts and never raises on a corrupt sidecar: a head whose
        shape, offsets, or counts disagree with the actual
        ``assembly.jsonl`` is rebuilt from a scan of the log and the
        sidecar is rewritten atomically.  Crash residue beyond the head's
        ``log_size`` (an fsynced append whose head write did not survive)
        is adopted when it chains, and torn bytes are truncated, so the
        returned head always matches the durable log.
        """
        raw: Any = None
        sidecar_present = True
        try:
            raw = read_json(self.head_path)
        except FileNotFoundError:
            raw = None
            sidecar_present = False
        except Exception:
            # Corrupt sidecar: rebuild from the log below, never raise.
            raw = None
        head = self._parse_head_dict(raw) if raw is not None else None

        if not self.events_path.exists():
            # No log at all: only an empty head is consistent with reality.
            if head is not None and (head.log_size != 0 or head.event_count != 0):
                head = None
            if head is None:
                head = EventLogHead(
                    timeline_id=self.timeline_id,
                    last_event_id=None,
                    last_hash=None,
                    event_count=0,
                    version=0,
                    log_size=0,
                    last_event_offset=0,
                )
            return head

        try:
            fd = os.open(self.events_path, os.O_RDWR)
        except OSError as exc:
            raise EventLogError(f"failed to open {self.events_path}: {exc}") from exc

        try:
            with os.fdopen(fd, "r+b", closefd=True) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    handle.seek(0, os.SEEK_END)
                    actual_size = handle.tell()
                    if head is not None and not self._validate_head_boundary(handle, head):
                        head = None
                    if head is None:
                        # Corrupt / missing / legacy sidecar: the log is the
                        # authority.  Rebuild from a lenient full scan and
                        # rewrite the sidecar atomically (an existing sidecar
                        # is always healed, even to an empty head).
                        head = self._rebuild_head_lenient_locked(handle)
                        if head.event_count > 0 or sidecar_present:
                            self._write_head_atomic(head)
                        return head
                    if actual_size != head.log_size:
                        # Crash residue beyond the head (adopt chain-valid
                        # orphaned lines, truncate torn/non-chaining bytes).
                        _, effective = self._reconcile_tail_locked(handle, head)
                        reconciled = self._effective_to_head(effective)
                        if reconciled != head:
                            head = reconciled
                            self._write_head_atomic(head)
                    return head
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise EventLogError(f"failed to read {self.events_path}: {exc}") from exc


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

    def _read_head_for_append(self, handle: Any) -> EventLogHead | None:
        """Return a trusted head for the incremental append path.

        ``None`` when the head is missing, unreadable, corrupt (bad JSON,
        wrong shape, or offsets that do not line up with the actual log
        bytes), or predates the ``log_size`` / ``last_event_offset``
        fields (legacy), so the caller falls back to a full rebuild.
        Never raises on a corrupt sidecar and never trusts one.
        """
        try:
            raw = read_json(self.head_path)
        except FileNotFoundError:
            return None
        except Exception:
            # Corrupt sidecar: caller rebuilds from the log — never raise.
            return None
        head = self._parse_head_dict(raw)
        if head is None:
            return None
        if not self._validate_head_boundary(handle, head):
            return None
        return head

    @staticmethod
    def _parse_head_dict(raw: Any) -> EventLogHead | None:
        """Strictly parse a head sidecar, returning ``None`` when corrupt.

        ``None`` covers bad JSON, non-object shapes, missing/wrong-typed
        fields (including missing ``log_size`` / ``last_event_offset``
        legacy heads), impossible offsets, and internally inconsistent
        counts.
        """
        if not isinstance(raw, dict):
            return None
        log_size = raw.get("log_size")
        last_event_offset = raw.get("last_event_offset")
        if not isinstance(log_size, int) or isinstance(log_size, bool):
            return None
        if not isinstance(last_event_offset, int) or isinstance(last_event_offset, bool):
            return None
        if log_size < 0 or last_event_offset < 0:
            return None
        if log_size == 0:
            if last_event_offset != 0 or raw.get("event_count", 0) != 0:
                return None
        elif last_event_offset >= log_size:
            return None
        event_count = raw.get("event_count")
        version = raw.get("version")
        timeline_id = raw.get("timeline_id")
        if not isinstance(event_count, int) or isinstance(event_count, bool):
            return None
        if not isinstance(version, int) or isinstance(version, bool):
            return None
        if not isinstance(timeline_id, str):
            return None
        if event_count < 0 or version < 0:
            return None
        if event_count != version:
            # This backend keeps version == event_count by construction;
            # divergence means the sidecar is corrupt.
            return None
        if event_count == 0:
            if raw.get("last_event_id") is not None or raw.get("last_hash") is not None:
                return None
        return EventLogHead(
            timeline_id=timeline_id,
            last_event_id=raw.get("last_event_id"),
            last_hash=raw.get("last_hash"),
            event_count=event_count,
            version=version,
            log_size=log_size,
            last_event_offset=last_event_offset,
        )

    def _validate_head_boundary(self, handle: Any, head: EventLogHead) -> bool:
        """True when the head's byte offsets describe the actual last event.

        Verifies ``last_event_offset`` starts a complete JSONL line that
        ends exactly at ``log_size`` and parses to the event the head
        names (``last_event_id`` / ``last_hash``).  Crash residue beyond
        ``log_size`` (an fsynced append whose head write did not survive)
        is allowed — it is adopted by :meth:`_reconcile_tail_locked`.
        """
        if head.log_size == 0:
            return (
                head.last_event_offset == 0
                and head.last_event_id is None
                and head.last_hash is None
                and head.event_count == 0
            )
        if head.last_event_offset is None or head.last_event_offset < 0:
            return False
        if head.last_event_offset >= head.log_size:
            return False
        handle.seek(0, os.SEEK_END)
        if head.log_size > handle.tell():
            # The log is shorter than the head claims (external truncation).
            return False
        handle.seek(head.last_event_offset, os.SEEK_SET)
        line = handle.read(head.log_size - head.last_event_offset)
        if not line.endswith(b"\n"):
            return False
        try:
            data = json.loads(line.decode("utf-8"))
            if not isinstance(data, dict):
                return False
            event = TimelineEvent.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
        return event.event_id == head.last_event_id and event.hash == head.last_hash

    def _rebuild_head_lenient_locked(self, handle: Any) -> EventLogHead:
        """Full-scan head rebuild that tolerates a torn trailing line.

        Used when the head sidecar is corrupt or missing: the log itself
        is the authority.  Complete newline-terminated lines are parsed as
        events; a torn trailing fragment (crash residue) is dropped and
        truncated so the durable log matches the rebuilt head.
        """
        self.full_log_reads += 1
        handle.seek(0)
        events: list[TimelineEvent] = []
        offset = 0
        last_event_offset = 0
        for line in handle:
            if not line.endswith(b"\n"):
                handle.truncate(offset)
                break
            try:
                data = json.loads(line.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("log line is not a JSON object")
                events.append(TimelineEvent.from_dict(data))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise EventLogError(
                    f"invalid JSON in {self.events_path}: {exc}"
                ) from exc
            last_event_offset = offset
            offset += len(line)
        if not events:
            return EventLogHead(
                timeline_id=self.timeline_id,
                last_event_id=None,
                last_hash=None,
                event_count=0,
                version=0,
                log_size=offset,
                last_event_offset=0,
            )
        last = events[-1]
        return EventLogHead(
            timeline_id=last.timeline_id,
            last_event_id=last.event_id,
            last_hash=last.hash,
            event_count=len(events),
            version=len(events),
            log_size=offset,
            last_event_offset=last_event_offset,
        )

    @staticmethod
    def _effective_to_head(effective: dict[str, Any]) -> EventLogHead:
        """Convert ``_reconcile_tail_locked``'s effective dict to a head."""
        return EventLogHead(
            timeline_id=effective["timeline_id"],
            last_event_id=effective["last_event_id"],
            last_hash=effective["last_hash"],
            event_count=effective["event_count"],
            version=effective["version"],
            log_size=effective["log_size"],
            last_event_offset=effective["last_event_offset"],
        )


    def _reconcile_tail_locked(
        self,
        handle: Any,
        head: EventLogHead,
    ) -> tuple[TimelineEvent | None, dict[str, Any]]:
        """Reconcile the tail region beyond ``head.log_size``.

        Reads ONLY the region beyond the head's ``log_size`` (never the full
        log).  Returns ``(tail_event, effective)`` where *effective* carries
        the head-like state after adopting any crash residue.

        Crash residue: complete, chain-valid JSONL lines beyond ``log_size``
        were fsynced by an append whose head write did not survive; they are
        adopted into the effective state.  A torn trailing partial line (or
        residue that does not chain) is truncated so the log stays consistent
        with the head.
        """
        effective: dict[str, Any] = {
            "timeline_id": head.timeline_id,
            "last_event_id": head.last_event_id,
            "last_hash": head.last_hash,
            "event_count": head.event_count,
            "version": head.version,
            "log_size": head.log_size if head.log_size is not None else 0,
            "last_event_offset": head.last_event_offset if head.last_event_offset is not None else 0,
        }

        handle.seek(effective["log_size"], os.SEEK_SET)
        leftover = handle.read()
        if leftover == b"":
            if effective["log_size"] == 0:
                return None, effective
            tail = self._read_tail_at_offset(
                handle, effective["last_event_offset"], effective["log_size"]
            )
            return tail, effective

        # Split into complete newline-terminated lines + torn trailing bytes.
        complete_end = leftover.rfind(b"\n") + 1
        complete = leftover[:complete_end]
        torn = leftover[complete_end:]

        adopted: list[TimelineEvent] = []
        adopted_last_offset = effective["log_size"]
        if complete:
            try:
                adopted, adopted_last_offset = self._parse_and_verify_lines(
                    complete,
                    prev_hash=effective["last_hash"],
                    base_offset=effective["log_size"],
                )
            except (EventLogError, ValueError, json.JSONDecodeError):
                # Complete-looking residue that does not chain is corruption:
                # the head is authoritative, so discard everything beyond it.
                complete = b""
                complete_end = 0

        if torn or complete_end < len(leftover):
            handle.truncate(effective["log_size"] + complete_end)

        if adopted:
            effective["event_count"] += len(adopted)
            effective["version"] += len(adopted)
            effective["last_event_id"] = adopted[-1].event_id
            effective["last_hash"] = adopted[-1].hash
            effective["log_size"] += complete_end
            effective["last_event_offset"] = adopted_last_offset
            return adopted[-1], effective

        if effective["log_size"] == 0:
            return None, effective
        tail = self._read_tail_at_offset(
            handle, effective["last_event_offset"], effective["log_size"]
        )
        return tail, effective

    def _read_tail_at_offset(
        self,
        handle: Any,
        offset: int,
        end: int,
    ) -> TimelineEvent | None:
        """Read the single last-complete-event line in ``[offset, end)``."""
        if offset < 0 or offset >= end:
            return None
        handle.seek(offset, os.SEEK_SET)
        line = handle.read(end - offset)
        if not line.endswith(b"\n"):
            raise EventLogError(
                f"{self.events_path} contains a non-terminated JSONL line"
            )
        try:
            data = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise EventLogError(f"invalid JSON in {self.events_path}: {exc.msg}") from exc
        return TimelineEvent.from_dict(data)

    def _parse_and_verify_lines(
        self,
        raw: bytes,
        *,
        prev_hash: str | None,
        base_offset: int,
    ) -> tuple[list[TimelineEvent], int]:
        """Parse complete JSONL lines, verifying the prev_hash + hash chain.

        Returns ``(events, last_line_start_offset)``.  Raises ``EventLogError``
        when any line fails to parse or breaks the chain.
        """
        events: list[TimelineEvent] = []
        cursor = 0
        last_line_len = 0
        for line in raw.split(b"\n"):
            if not line:
                continue
            line_bytes = line + b"\n"
            try:
                data = json.loads(line.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("tail residue line is not a JSON object")
                event = TimelineEvent.from_dict(data)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise EventLogError(
                    f"invalid JSON in {self.events_path} tail residue: {exc}"
                ) from exc
            if event.prev_hash != prev_hash:
                raise EventLogError(
                    f"tail residue prev_hash does not chain at {event.event_id}"
                )
            expected = with_event_hash(
                TimelineEvent.from_dict({**event.to_json_obj(), "hash": None}),
                prev_hash=prev_hash,
            )
            if event.hash != expected.hash:
                raise EventLogError(
                    f"tail residue event {event.event_id} hash mismatch"
                )
            events.append(event)
            prev_hash = event.hash
            last_line_len = len(line_bytes)
            cursor += last_line_len
        if not events:
            raise EventLogError("empty tail residue")
        return events, base_offset + cursor - last_line_len

    def _rebuild_head_locked(self) -> EventLogHead:
        events, log_size, last_event_offset = self._read_all_events_with_offsets()
        if not events:
            return EventLogHead(
                timeline_id=self.timeline_id,
                last_event_id=None,
                last_hash=None,
                event_count=0,
                version=0,
                log_size=0,
                last_event_offset=0,
            )
        last = events[-1]
        return EventLogHead(
            timeline_id=last.timeline_id,
            last_event_id=last.event_id,
            last_hash=last.hash,
            event_count=len(events),
            version=len(events),
            log_size=log_size,
            last_event_offset=last_event_offset,
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
                "log_size": head.log_size,
                "last_event_offset": head.last_event_offset,
            },
        )

    def _read_all_events(self) -> list[TimelineEvent]:
        self.full_log_reads += 1
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

    def _read_all_events_with_offsets(self) -> tuple[list[TimelineEvent], int, int]:
        """Full-parse the log, also returning ``(log_size, last_event_offset)``."""
        self.full_log_reads += 1
        try:
            with self.events_path.open("rb") as handle:
                events: list[TimelineEvent] = []
                offset = 0
                last_event_offset = 0
                for line in handle:
                    if not line.endswith(b"\n"):
                        raise EventLogError(
                            f"{self.events_path} line {len(events) + 1} is not newline-terminated"
                        )
                    data = json.loads(line.decode("utf-8"))
                    events.append(TimelineEvent.from_dict(data))
                    last_event_offset = offset
                    offset += len(line)
                return events, offset, last_event_offset
        except FileNotFoundError:
            return [], 0, 0
        except json.JSONDecodeError as exc:
            raise EventLogError(f"invalid JSON in {self.events_path}: {exc.msg}") from exc
        except OSError as exc:
            raise EventLogError(f"failed to read {self.events_path}: {exc}") from exc

    def repair_erasure(
        self,
        target_event_ids: list[str],
        *,
        reason: str,
        erased_by: str,
        policy_ref: str | None = None,
    ) -> dict[str, object]:
        """Replace payloads of selected historical events with ErasedPayload envelope.

        This is a backend-level operation that:
        1. Replaces specified event payloads with canonical ErasedPayload.
        2. Recomputes downstream prev_hash/hash for all affected events.
        3. Atomically replaces the event log under the existing file lock.
        4. Rebuilds head and deletes stale compatibility projections.

        Returns a dict with replaced_count, downstream_count, head_event_count,
        head_version, last_event_id, last_hash.
        """
        from astrid.core.timeline.repair import repair_erasure_local_fs
        return repair_erasure_local_fs(
            timeline_home=self.timeline_home,
            events_path=self.events_path,
            head_path=self.head_path,
            target_event_ids=target_event_ids,
            reason=reason,
            erased_by=erased_by,
            policy_ref=policy_ref,
        )

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
