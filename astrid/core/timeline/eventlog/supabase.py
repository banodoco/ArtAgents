"""Provisional Supabase timeline eventlog backend for Astrid-side contract tests."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass

from ..events.schema import TimelineActor, TimelineEvent
from .protocol import SupabaseEventLogTransport
from .types import (
    EventLogAuthRequiredError,
    EventLogHead,
    EventLogMissingConfigError,
    EventLogTransportError,
    EventLogUnsupportedRpcError,
    EventLogVerification,
)


class SupabaseBackend:
    """Opt-in Supabase backend with a mocked-transport contract seam.

    This repo does not ship the owning SQL/RPC implementation. When a transport
    is injected, this backend can exercise append/read/head/verify behavior
    against mocked responses. Without a transport, configured instances fail
    with a typed unsupported-RPC error and unconfigured instances fail with a
    typed missing-config error.
    """

    def __init__(
        self,
        *,
        timeline_id: str,
        supabase_url: str | None = None,
        auth_token: str | None = None,
        enabled: bool = False,
        verified_subject: str | None = None,
        actor_id: str | None = None,
        actor_display: str | None = None,
        rpc_append_name: str = "append_timeline_event",
        transport: SupabaseEventLogTransport | None = None,
    ) -> None:
        self.timeline_id = timeline_id
        self.supabase_url = supabase_url
        self.auth_token = auth_token
        self.enabled = enabled
        self.verified_subject = verified_subject
        self.actor_id = actor_id
        self.actor_display = actor_display
        self.rpc_append_name = rpc_append_name
        self.transport = transport

    def backend_name(self) -> str:
        return "supabase"

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
        self._require_verified_human_subject(actor)
        transport = self._require_transport(operation="append_event")
        raw = transport.append_event(
            timeline_id=timeline_id,
            kind=kind,
            payload=payload,
            actor=actor,
            expected_version=expected_version,
            txn_id=txn_id,
        )
        return self._coerce_timeline_event(raw, operation="append_event")

    def append_imported_event(
        self,
        timeline_id: str,
        source_event: TimelineEvent,
        *,
        idempotency_key: str,
        actor: TimelineActor,
    ) -> TimelineEvent:
        """Import a source event via the transport with idempotency.

        The transport handles RPC-shaped import (not direct table mutation).
        Source identity is preserved in import metadata fields only.
        """
        self._require_verified_human_subject(actor)
        transport = self._require_transport(operation="append_imported_event")
        raw = transport.append_imported_event(
            timeline_id=timeline_id,
            source_event=source_event,
            idempotency_key=idempotency_key,
            actor=actor,
        )
        return self._coerce_timeline_event(raw, operation="append_imported_event")

    def read_events(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[TimelineEvent]:
        transport = self._require_transport(operation="read_events")
        raw = transport.read_events(
            timeline_id=self.timeline_id,
            after=after,
            limit=limit,
        )
        if not isinstance(raw, list):
            raise EventLogTransportError(
                "SupabaseBackend.read_events transport returned a non-list response"
            )
        return [
            self._coerce_timeline_event(item, operation="read_events")
            for item in raw
        ]

    def head(self) -> EventLogHead:
        transport = self._require_transport(operation="head")
        raw = transport.head(timeline_id=self.timeline_id)
        if isinstance(raw, EventLogHead):
            return raw
        if not isinstance(raw, dict):
            raise EventLogTransportError(
                "SupabaseBackend.head transport returned a non-object response"
            )
        return EventLogHead(
            timeline_id=self._require_str(raw.get("timeline_id"), "head.timeline_id"),
            last_event_id=self._optional_str(raw.get("last_event_id"), "head.last_event_id"),
            last_hash=self._optional_str(raw.get("last_hash"), "head.last_hash"),
            event_count=self._require_int(raw.get("event_count"), "head.event_count"),
            version=self._require_int(raw.get("version"), "head.version"),
        )

    def verify_chain(self) -> EventLogVerification:
        transport = self._require_transport(operation="verify_chain")
        raw = transport.verify_chain(timeline_id=self.timeline_id)
        if isinstance(raw, EventLogVerification):
            return raw
        if not isinstance(raw, dict):
            raise EventLogTransportError(
                "SupabaseBackend.verify_chain transport returned a non-object response"
            )
        ok = raw.get("ok")
        if not isinstance(ok, bool):
            raise EventLogTransportError("verify_chain.ok must be a bool")
        return EventLogVerification(
            ok=ok,
            checked_events=self._require_int(
                raw.get("checked_events"), "verify_chain.checked_events"
            ),
            last_event_id=self._optional_str(
                raw.get("last_event_id"), "verify_chain.last_event_id"
            ),
            error=self._optional_str(raw.get("error"), "verify_chain.error"),
        )

    def repair_erasure(
        self,
        target_event_ids: list[str],
        *,
        reason: str,
        erased_by: str,
        policy_ref: str | None = None,
    ) -> dict[str, object]:
        """Replace payloads of selected historical events with ErasedPayload envelope.

        Exposed as transport/RPC capability for Supabase.
        """
        transport = self._require_transport(operation="repair_erasure")
        raw = transport.repair_erasure(
            timeline_id=self.timeline_id,
            target_event_ids=target_event_ids,
            reason=reason,
            erased_by=erased_by,
            policy_ref=policy_ref,
        )
        if not isinstance(raw, dict):
            raise EventLogTransportError(
                "SupabaseBackend.repair_erasure transport returned a non-object response"
            )
        return raw

    def _require_transport(self, *, operation: str) -> SupabaseEventLogTransport:
        if self.transport is not None:
            return self.transport
        if not self._has_config():
            raise EventLogMissingConfigError(
                f"SupabaseBackend.{operation} requires Supabase config or a mocked transport"
            )
        raise EventLogUnsupportedRpcError(
            f"SupabaseBackend.{operation} has no transport in this repo; "
            f"{self.rpc_append_name} SQL/RPC parity remains companion work"
        )

    def _has_config(self) -> bool:
        return bool(self.enabled or self.supabase_url or self.auth_token)

    def _require_verified_human_subject(self, actor: TimelineActor) -> None:
        if actor.type != "human":
            return
        if not self.verified_subject:
            raise EventLogAuthRequiredError(
                "SupabaseBackend human writes require a verified auth subject"
            )
        if actor.id != self.verified_subject:
            raise EventLogAuthRequiredError(
                "SupabaseBackend human actor.id does not match the verified auth subject"
            )

    def _coerce_timeline_event(self, raw: object, *, operation: str) -> TimelineEvent:
        if isinstance(raw, TimelineEvent):
            return raw
        if is_dataclass(raw):
            raw = asdict(raw)
        if not isinstance(raw, dict):
            raise EventLogTransportError(
                f"SupabaseBackend.{operation} transport returned a non-object event"
            )
        try:
            return TimelineEvent.from_dict(raw)
        except Exception as exc:
            raise EventLogTransportError(
                f"SupabaseBackend.{operation} transport returned an invalid event payload"
            ) from exc

    def _require_str(self, value: object, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise EventLogTransportError(f"{field} must be a non-empty string")
        return value

    def _optional_str(self, value: object, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise EventLogTransportError(f"{field} must be a string when present")
        return value

    def _require_int(self, value: object, field: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise EventLogTransportError(f"{field} must be an integer")
        return value
