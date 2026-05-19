"""Stub Supabase timeline eventlog backend for m1."""

from __future__ import annotations

from .types import (
    EventLogHead,
    EventLogNotConfiguredError,
    EventLogNotImplementedError,
    EventLogVerification,
)
from ..events.schema import TimelineActor, TimelineEvent


class SupabaseBackend:
    """Constructible but inert until m6 lands the real RPC-backed backend."""

    def __init__(
        self,
        *,
        timeline_id: str,
        supabase_url: str | None = None,
        auth_token: str | None = None,
        enabled: bool = False,
    ) -> None:
        self.timeline_id = timeline_id
        self.supabase_url = supabase_url
        self.auth_token = auth_token
        self.enabled = enabled

    def backend_name(self) -> str:
        return "supabase"

    def append_event(
        self,
        kind: str,
        payload: dict[str, object],
        *,
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> TimelineEvent:
        raise EventLogNotImplementedError(
            "SupabaseBackend.append_event is not implemented in m1; "
            "use LocalFsBackend or land the m6 RPC backend"
        )

    def read_events(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]:
        raise EventLogNotConfiguredError(
            "SupabaseBackend.read_events is not configured in m1; no network calls are available"
        )

    def head(self) -> EventLogHead:
        raise EventLogNotConfiguredError(
            "SupabaseBackend.head is not configured in m1; no network calls are available"
        )

    def verify_chain(self) -> EventLogVerification:
        raise EventLogNotConfiguredError(
            "SupabaseBackend.verify_chain is not configured in m1; no network calls are available"
        )
