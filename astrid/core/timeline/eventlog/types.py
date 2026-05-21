"""Storage-agnostic eventlog transport and result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent

BackendName = Literal["local_fs", "supabase"]


class EventLogError(RuntimeError):
    """Raised when a timeline eventlog operation fails."""


class EventLogNotConfiguredError(EventLogError):
    """Raised when a backend can be constructed but is not configured for use."""


class EventLogNotImplementedError(EventLogError):
    """Raised when a backend shape exists but the implementation is deferred."""


@dataclass(frozen=True)
class TimelineVersionConflict:
    """Structured optimistic-concurrency mismatch details."""

    timeline_id: str
    expected_version: int
    current_version: int
    last_event_id: str | None
    last_event_kind: str | None = None
    last_event_summary: str | None = None


class EventLogStaleVersionError(EventLogError):
    """Raised when ``expected_version`` does not match the current stream head."""

    def __init__(self, conflict: TimelineVersionConflict) -> None:
        self.conflict = conflict
        message = (
            f"stale timeline version for {conflict.timeline_id}: "
            f"expected {conflict.expected_version}, current {conflict.current_version}"
        )
        if conflict.last_event_kind:
            message += f" (last event: {conflict.last_event_kind}"
            if conflict.last_event_id:
                message += f" {conflict.last_event_id}"
            message += ")"
        elif conflict.last_event_id:
            message += f" (last event id: {conflict.last_event_id})"
        super().__init__(message)


@dataclass(frozen=True)
class EventLogHead:
    timeline_id: str
    last_event_id: str | None
    last_hash: str | None
    event_count: int
    version: int


@dataclass(frozen=True)
class EventLogVerification:
    ok: bool
    checked_events: int
    last_event_id: str | None
    error: str | None = None


@dataclass(frozen=True)
class TimelineStreamRef:
    backend: BackendName
    timeline_id: str
    home: Path | None = None
    source: str = "timeline_home"


@dataclass(frozen=True)
class AppendEventRequest:
    kind: str
    payload: dict[str, object]
    actor: TimelineActor
    expected_version: int | None = None
    txn_id: str | None = None
