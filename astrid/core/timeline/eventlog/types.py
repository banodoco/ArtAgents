"""Storage-agnostic eventlog transport and result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from astrid.core.timeline.events.schema import TimelineActor

BackendName = Literal["local_fs", "supabase"]


class EventLogError(RuntimeError):
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
    supabase_options: "SupabaseEventLogOptions | None" = None


@dataclass(frozen=True)
class SupabaseEventLogOptions:
    """Optional transport/auth context for the Supabase eventlog backend.

    The LocalFs backend ignores this structure entirely. It exists so callers
    can pass one narrow context object through backend selection without
    fanning separate Supabase kwargs across edit and CRUD call sites.
    """

    url: str | None = None
    auth_token: str | None = None
    verified_subject: str | None = None
    actor_id: str | None = None
    actor_display: str | None = None
    rpc_append_name: str = "append_timeline_event"


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
    backend_name_display: str  # e.g. "local_fs" or "supabase"


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
