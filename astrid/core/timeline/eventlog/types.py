"""Storage-agnostic eventlog transport and result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from astrid.core.contracts.event_log_error import EventLogError as _EventLogErrorBase
from astrid.core.timeline.events.schema import TimelineActor

if TYPE_CHECKING:
    from astrid.core.timeline.events.schema.types import TimelineEvent

BackendName = Literal["local_fs"]


class EventLogError(_EventLogErrorBase):
    """Raised when a timeline eventlog operation fails."""


class EventLogNotConfiguredError(EventLogError):
    """Raised when a backend can be constructed but is not configured for use."""


class EventLogNotImplementedError(EventLogError):
    """Raised when a backend shape exists but the implementation is deferred."""


class EventLogMissingConfigError(EventLogNotConfiguredError, EventLogNotImplementedError):
    """Raised when a backend operation needs config that was not supplied."""


class EventLogUnsupportedRpcError(EventLogNotImplementedError):
    """Raised when the target backend lacks the requested RPC capability."""


class EventLogAuthRequiredError(EventLogError):
    """Raised when a write requires a verified auth subject that was not proven."""


class EventLogTransportError(EventLogError):
    """Raised when a backend transport returns malformed or unusable data."""


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
    # Incremental-append offsets (T2.1): crash-reconciled byte extent of the
    # log (``log_size``) and the byte offset where the last complete event
    # line begins (``last_event_offset``).  ``None`` on legacy heads that
    # predate the fields; the backend then rebuilds from a full parse.
    log_size: int | None = None
    last_event_offset: int | None = None


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


class EventLogIdempotentError(EventLogError):
    """Raised when an idempotent import succeeds (event already exists)."""

    def __init__(self, existing_event_id: str) -> None:
        self.existing_event_id = existing_event_id
        super().__init__(
            f"import already exists (destination event {existing_event_id}); "
            f"this is a success, not a failure — callers should unwrap and return the existing event"
        )


@dataclass(frozen=True)
class AppendEventRequest:
    kind: str
    payload: dict[str, object]
    actor: TimelineActor
    expected_version: int | None = None
    txn_id: str | None = None


@dataclass(frozen=True)
class ImportEventRequest:
    """Request to import a source event into a destination backend."""

    source_event: "TimelineEvent"  # forward-ref; resolved at runtime
    idempotency_key: str
    actor: "TimelineActor"


# ============================================================================
# Observability result shapes (m7)
# ============================================================================


@dataclass(frozen=True)
class ResolvedTarget:
    """Fully-resolved timeline target produced by ``resolve_timeline_target()``."""

    backend: BackendName
    timeline_id: str
    timeline_ulid: str
    timeline_home: Path
    slug: str
    backend_name_display: str  # local_fs


@dataclass(frozen=True)
class OpsLogEntry:
    """A single operational failure log entry from ``events_ops.jsonl``."""

    ts: str
    event_id: str | None
    kind: str | None
    error: str
    raw: dict[str, object]


@dataclass(frozen=True)
class HistoryRow:
    """One row returned by ``cmd_history`` for pretty-printing."""

    backend: str
    timeline_id: str
    version: int  # 1-based event index in the stream
    event_id: str
    actor_display: str  # redacted: never includes via/session/token
    kind: str
    ts: str


@dataclass(frozen=True)
class AuditResult:
    """Aggregated result from ``cmd_audit``."""

    chain_ok: bool
    chain_checked: int
    chain_error: str | None
    head_ok: bool
    head_error: str | None
    projection_parity_ok: bool | None  # None when no derived blob exists
    projection_parity_error: str | None
    ops_log_entries: list[OpsLogEntry] | None  # None when --include-ops not given
    ops_log_error: str | None  # "no operational failure logs" or None


@dataclass(frozen=True)
class ActorRollupEntry:
    """One entry in an actor rollup produced by ``cmd_who_edited``."""

    actor_id: str
    actor_display: str  # redacted: never includes via/session/token
    kinds: dict[str, int]  # kind -> count
    total: int
