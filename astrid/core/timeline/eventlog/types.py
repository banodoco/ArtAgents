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

