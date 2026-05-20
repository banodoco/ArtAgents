"""Timeline eventlog backend protocol."""

from __future__ import annotations

from typing import Protocol

from .types import BackendName, EventLogHead, EventLogVerification
from ..events.schema import TimelineActor, TimelineEvent


class EventLogBackend(Protocol):
    """Stream-bound storage backend for one timeline event stream."""

    def append_event(
        self,
        kind: str,
        payload: dict[str, object],
        *,
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> TimelineEvent: ...

    def read_events(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]: ...

    def head(self) -> EventLogHead: ...

    def verify_chain(self) -> EventLogVerification: ...

    def backend_name(self) -> BackendName: ...
