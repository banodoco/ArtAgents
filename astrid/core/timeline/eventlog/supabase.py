"""Provisional Supabase timeline eventlog backend for Astrid-side contract tests."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any
from urllib.parse import quote

from astrid.core.timeline.eventlog import reigh_events, supabase_client
from astrid.core.timeline.eventlog.reigh_events import ReighEventBatch

from ..events.schema import TimelineActor, TimelineEvent
from ..events.schema.payloads._base import TimelineImportSource
from .protocol import SupabaseEventLogTransport
from .types import (
    EventLogAuthRequiredError,
    EventLogHead,
    EventLogMissingConfigError,
    EventLogStaleVersionError,
    EventLogTransportError,
    EventLogUnsupportedRpcError,
    EventLogVerification,
    TimelineVersionConflict,
)

_VERSION_MISMATCH_RE = re.compile(r"expected\s+(\d+),\s+found\s+(\d+)", re.IGNORECASE)

SupabaseHTTPError = supabase_client.SupabaseHTTPError
get_json = supabase_client.get_json
post_json = supabase_client.post_json
rpc = supabase_client.rpc


@dataclass(frozen=True)
class TimelineMetadataPreflight:
    """Classified metadata read used by born-local push promotion."""

    status: str
    timeline_id: str
    project_id: str | None = None
    user_id: str | None = None
    version: int = 0
    event_count: int = 0
    last_event_id: str | None = None
    last_hash: str | None = None
    detail: str | None = None



@dataclass(frozen=True)
class SupabaseAppendResult:
    """Materialized result of one live Reigh append RPC call."""

    batch: ReighEventBatch
    config_version: int
    inserted_event_ids: tuple[str, ...]

    @property
    def primary_event(self) -> TimelineEvent:
        return self.batch.events[0].event


@dataclass(frozen=True)
class _TimelineTailState:
    timeline_id: str
    config: dict[str, Any]
    config_version: int
    asset_registry: dict[str, Any] | None
    last_event_id: str | None
    last_event_kind: str | None
    last_hash: str | None
    next_event_version: int


class LiveSupabaseAppendTransport:
    """Live transport for Reigh config/asset-registry appends via Supabase RPC."""

    def __init__(
        self,
        *,
        supabase_url: str,
        auth_token: str,
        rpc_append_name: str = "append_timeline_event",
        timeout: float = 60.0,
    ) -> None:
        self.supabase_url = supabase_url
        self.auth_token = auth_token
        self.rpc_append_name = rpc_append_name
        self.timeout = timeout

    def append_event(
        self,
        *,
        timeline_id: str,
        kind: str,
        payload: dict[str, object],
        actor: TimelineActor,
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> TimelineEvent:
        if kind == "timeline.config_replaced":
            return self.append_config_replaced(
                timeline_id=timeline_id,
                config=self._require_object(payload.get("config"), field="payload.config"),
                asset_registry=self._optional_object(
                    payload.get("asset_registry"),
                    field="payload.asset_registry",
                ),
                actor=actor,
                source=self._coerce_source(payload.get("source")),
                expected_version=expected_version,
                txn_id=txn_id,
            ).primary_event
        if kind == "timeline.asset_registry_replaced":
            return self.append_asset_registry_replaced(
                timeline_id=timeline_id,
                asset_registry=self._require_object(
                    payload.get("registry"),
                    field="payload.registry",
                ),
                actor=actor,
                source=self._coerce_source(payload.get("source")),
                expected_version=expected_version,
                txn_id=txn_id,
            ).primary_event
        raise EventLogUnsupportedRpcError(
            f"{self.rpc_append_name} only supports "
            "timeline.config_replaced and timeline.asset_registry_replaced"
        )

    def append_config_replaced(
        self,
        *,
        timeline_id: str,
        config: dict[str, Any],
        asset_registry: dict[str, Any] | None,
        actor: TimelineActor,
        source: TimelineImportSource = "supabase_config",
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> SupabaseAppendResult:
        state = self._load_tail_state(timeline_id)
        cas_version = state.config_version if expected_version is None else expected_version
        batch = reigh_events.config_to_events(
            config,
            asset_registry,
            timeline_id,
            state.last_hash,
            state.next_event_version,
            actor,
            source,
            expected_version=cas_version,
            txn_id=txn_id,
        )
        return self._append_batch(timeline_id=timeline_id, batch=batch, expected_version=cas_version)

    def append_asset_registry_replaced(
        self,
        *,
        timeline_id: str,
        asset_registry: dict[str, Any],
        actor: TimelineActor,
        source: TimelineImportSource = "supabase_config",
        expected_version: int | None = None,
        txn_id: str | None = None,
    ) -> SupabaseAppendResult:
        state = self._load_tail_state(timeline_id)
        cas_version = state.config_version if expected_version is None else expected_version
        batch = reigh_events.asset_registry_to_events(
            asset_registry,
            state.config,
            timeline_id,
            state.last_hash,
            state.next_event_version,
            actor,
            source,
            expected_version=cas_version,
            txn_id=txn_id,
        )
        return self._append_batch(timeline_id=timeline_id, batch=batch, expected_version=cas_version)

    def write_divergence(
        self,
        *,
        timeline_id: str,
        spoke: str,
        spoke_version: int,
        spoke_hash: str | None,
        spoke_event_id: str | None,
        hub_version: int,
        hub_hash: str | None,
        hub_event_id: str | None,
        spoke_suffix: list[dict[str, object]],
        hub_suffix: list[dict[str, object]],
        chosen_side: str = "undecided",
        artifact_pointer: dict[str, object] | None = None,
    ) -> dict[str, object]:
        endpoint = f"{self.supabase_url.rstrip('/')}/rest/v1/divergence_log"
        payload = {
            "timeline_id": timeline_id,
            "spoke": spoke,
            "spoke_version": spoke_version,
            "spoke_hash": spoke_hash,
            "spoke_event_id": spoke_event_id,
            "hub_version": hub_version,
            "hub_hash": hub_hash,
            "hub_event_id": hub_event_id,
            "spoke_suffix": spoke_suffix,
            "hub_suffix": hub_suffix,
            "chosen_side": chosen_side,
            "artifact_pointer": artifact_pointer,
        }
        try:
            response = post_json(
                endpoint,
                payload,
                auth=("service_role", self.auth_token),
                extra_headers={"Prefer": "return=representation"},
                timeout=self.timeout,
            )
        except SupabaseHTTPError as exc:
            raise EventLogTransportError(
                f"Supabase divergence_log insert failed: {exc}"
            ) from exc
        row = response[0] if isinstance(response, list) and response else response
        if not isinstance(row, dict):
            raise EventLogTransportError(
                "Supabase divergence_log insert returned a non-object response"
            )
        return dict(row)

    def upsert_bookmark(
        self,
        *,
        timeline_id: str,
        spoke: str,
        spoke_version: int,
        spoke_hash: str | None,
        spoke_event_id: str | None,
        hub_version: int,
        hub_hash: str | None,
        hub_event_id: str | None,
        synced_at: str | None = None,
    ) -> dict[str, object]:
        endpoint = (
            f"{self.supabase_url.rstrip('/')}/rest/v1/sync_bookmarks"
            "?on_conflict=timeline_id,spoke"
        )
        payload: dict[str, object] = {
            "timeline_id": timeline_id,
            "spoke": spoke,
            "spoke_version": spoke_version,
            "spoke_hash": spoke_hash,
            "spoke_event_id": spoke_event_id,
            "hub_version": hub_version,
            "hub_hash": hub_hash,
            "hub_event_id": hub_event_id,
        }
        if synced_at is not None:
            payload["synced_at"] = synced_at
        try:
            response = post_json(
                endpoint,
                payload,
                auth=("service_role", self.auth_token),
                extra_headers={
                    "Prefer": "resolution=merge-duplicates,return=representation"
                },
                timeout=self.timeout,
            )
        except SupabaseHTTPError as exc:
            raise EventLogTransportError(
                f"Supabase sync_bookmarks upsert failed: {exc}"
            ) from exc
        row = response[0] if isinstance(response, list) and response else response
        if not isinstance(row, dict):
            raise EventLogTransportError(
                "Supabase sync_bookmarks upsert returned a non-object response"
            )
        return dict(row)


    def _append_batch(
        self,
        *,
        timeline_id: str,
        batch: ReighEventBatch,
        expected_version: int,
    ) -> SupabaseAppendResult:
        try:
            response = rpc(
                self.rpc_append_name,
                {
                    "p_timeline_id": timeline_id,
                    "p_events": batch.to_append_json(),
                    "p_projected_config": batch.projected_config,
                    "p_expected_config_version": expected_version,
                    "p_projected_asset_registry": batch.projected_asset_registry,
                },
                supabase_url=self.supabase_url,
                auth=("service_role", self.auth_token),
                timeout=self.timeout,
            )
        except SupabaseHTTPError as exc:
            if self._looks_like_cas_conflict(exc):
                raise self._translate_cas_conflict(timeline_id, expected_version, exc) from exc
            raise EventLogTransportError(
                f"Supabase append RPC {self.rpc_append_name} failed: {exc}"
            ) from exc
        parsed = self._coerce_rpc_result(response)
        return SupabaseAppendResult(
            batch=batch,
            config_version=parsed["config_version"],
            inserted_event_ids=parsed["inserted_event_ids"],
        )

    def _load_tail_state(self, timeline_id: str) -> _TimelineTailState:
        timeline_url = (
            f"{self.supabase_url.rstrip('/')}/rest/v1/timelines"
            f"?select=id,config,config_version,asset_registry&id=eq.{quote(timeline_id, safe='')}"
            "&limit=1"
        )
        tail_url = (
            f"{self.supabase_url.rstrip('/')}/rest/v1/timeline_events"
            f"?select=event_id,version,hash,kind&timeline_id=eq.{quote(timeline_id, safe='')}"
            "&order=version.desc&limit=1"
        )
        try:
            timeline_rows = get_json(
                timeline_url,
                auth=("service_role", self.auth_token),
                timeout=self.timeout,
            )
            tail_rows = get_json(
                tail_url,
                auth=("service_role", self.auth_token),
                timeout=self.timeout,
            )
        except SupabaseHTTPError as exc:
            raise EventLogTransportError(
                f"Supabase append transport failed to read timeline state: {exc}"
            ) from exc

        if not isinstance(timeline_rows, list) or not timeline_rows or not isinstance(timeline_rows[0], dict):
            raise EventLogTransportError(
                f"Supabase append transport could not find timeline {timeline_id}"
            )
        row = timeline_rows[0]
        config = row.get("config")
        if not isinstance(config, dict):
            raise EventLogTransportError(
                f"Supabase append transport timeline {timeline_id} is missing a config object"
            )
        config_version = row.get("config_version")
        if not isinstance(config_version, int) or isinstance(config_version, bool):
            raise EventLogTransportError(
                f"Supabase append transport timeline {timeline_id} is missing config_version"
            )
        asset_registry_raw = row.get("asset_registry")
        asset_registry = self._optional_object(asset_registry_raw, field="timeline.asset_registry")

        last_event_id: str | None = None
        last_event_kind: str | None = None
        last_hash: str | None = None
        next_event_version = 1
        if isinstance(tail_rows, list) and tail_rows:
            tail = tail_rows[0]
            if not isinstance(tail, dict):
                raise EventLogTransportError("Supabase append transport tail row must be an object")
            version = tail.get("version")
            if not isinstance(version, int) or isinstance(version, bool):
                raise EventLogTransportError("Supabase append transport tail.version must be an integer")
            next_event_version = version + 1
            last_event_id = self._optional_str(tail.get("event_id"))
            last_event_kind = self._optional_str(tail.get("kind"))
            last_hash = self._optional_str(tail.get("hash"))

        return _TimelineTailState(
            timeline_id=timeline_id,
            config=config,
            config_version=config_version,
            asset_registry=asset_registry,
            last_event_id=last_event_id,
            last_event_kind=last_event_kind,
            last_hash=last_hash,
            next_event_version=next_event_version,
        )

    def _translate_cas_conflict(
        self,
        timeline_id: str,
        expected_version: int,
        exc: SupabaseHTTPError,
    ) -> EventLogStaleVersionError:
        state = self._safe_load_tail_state(timeline_id)
        current_version = state.config_version if state is not None else expected_version
        match = _VERSION_MISMATCH_RE.search(exc.body or "")
        if match is not None:
            current_version = int(match.group(2))
        return EventLogStaleVersionError(
            TimelineVersionConflict(
                timeline_id=timeline_id,
                expected_version=expected_version,
                current_version=current_version,
                last_event_id=state.last_event_id if state is not None else None,
                last_event_kind=state.last_event_kind if state is not None else None,
                last_event_summary=(
                    f"{state.last_event_kind}#{state.last_event_id}"
                    if state is not None
                    and state.last_event_kind is not None
                    and state.last_event_id is not None
                    else None
                ),
            )
        )

    def _safe_load_tail_state(self, timeline_id: str) -> _TimelineTailState | None:
        try:
            return self._load_tail_state(timeline_id)
        except EventLogTransportError:
            return None

    def _looks_like_cas_conflict(self, exc: SupabaseHTTPError) -> bool:
        if exc.status == 409:
            return True
        body = (exc.body or "").lower()
        return any(
            marker in body
            for marker in (
                "config_version mismatch",
                "version_conflict",
                "version conflict",
                "expected_version",
            )
        )

    def _coerce_rpc_result(self, response: object) -> dict[str, Any]:
        row = response
        if isinstance(response, list):
            row = response[0] if response else None
        if not isinstance(row, dict):
            raise EventLogTransportError(
                f"Supabase append RPC {self.rpc_append_name} returned a non-object response"
            )
        config_version = row.get("config_version")
        inserted_ids = row.get("inserted_event_ids")
        if not isinstance(config_version, int) or isinstance(config_version, bool):
            raise EventLogTransportError(
                f"Supabase append RPC {self.rpc_append_name} did not return config_version"
            )
        if not isinstance(inserted_ids, list) or not all(isinstance(item, str) for item in inserted_ids):
            raise EventLogTransportError(
                f"Supabase append RPC {self.rpc_append_name} did not return inserted_event_ids"
            )
        return {
            "config_version": config_version,
            "inserted_event_ids": tuple(inserted_ids),
        }

    def _coerce_source(self, raw: object) -> TimelineImportSource:
        if raw is None:
            return "supabase_config"
        if raw in {"legacy_local", "supabase_config", "editor_save", "other"}:
            return raw
        raise EventLogTransportError(
            "Supabase append transport source must be "
            "legacy_local, supabase_config, editor_save, or other"
        )

    def _require_object(self, value: object, *, field: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise EventLogTransportError(f"{field} must be a JSON object")
        return dict(value)

    def _optional_object(self, value: object, *, field: str) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise EventLogTransportError(f"{field} must be a JSON object when present")
        return dict(value)

    def _optional_str(self, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise EventLogTransportError("Supabase append transport expected a string field")
        return value


def read_timeline_metadata_preflight(
    *,
    supabase_url: str,
    auth_token: str,
    timeline_id: str,
    timeout: float = 60.0,
) -> TimelineMetadataPreflight:
    """Read timeline row + head metadata with classified failure reasons."""

    timeline_url = (
        f"{supabase_url.rstrip('/')}/rest/v1/timelines"
        f"?select=id,project_id,user_id&id=eq.{quote(timeline_id, safe='')}&limit=1"
    )
    head_url = (
        f"{supabase_url.rstrip('/')}/rest/v1/timeline_events"
        f"?select=event_id,version,hash&timeline_id=eq.{quote(timeline_id, safe='')}"
        "&order=version.desc&limit=1"
    )
    try:
        timeline_rows = get_json(
            timeline_url,
            auth=("service_role", auth_token),
            timeout=timeout,
        )
        if not isinstance(timeline_rows, list):
            return TimelineMetadataPreflight(
                status="network_failure",
                timeline_id=timeline_id,
                detail="timeline metadata read returned a non-list payload",
            )
        if not timeline_rows:
            return TimelineMetadataPreflight(
                status="not_found",
                timeline_id=timeline_id,
            )
        row = timeline_rows[0]
        if not isinstance(row, dict):
            return TimelineMetadataPreflight(
                status="network_failure",
                timeline_id=timeline_id,
                detail="timeline metadata row was not an object",
            )
        head_rows = get_json(
            head_url,
            auth=("service_role", auth_token),
            timeout=timeout,
        )
    except SupabaseHTTPError as exc:
        status = "unauthorized" if exc.status in {401, 403} else "network_failure"
        return TimelineMetadataPreflight(
            status=status,
            timeline_id=timeline_id,
            detail=str(exc),
        )

    version = 0
    event_count = 0
    last_event_id: str | None = None
    last_hash: str | None = None
    if isinstance(head_rows, list) and head_rows:
        head = head_rows[0]
        if not isinstance(head, dict):
            return TimelineMetadataPreflight(
                status="network_failure",
                timeline_id=timeline_id,
                detail="timeline head row was not an object",
            )
        raw_version = head.get("version")
        if not isinstance(raw_version, int) or isinstance(raw_version, bool):
            return TimelineMetadataPreflight(
                status="network_failure",
                timeline_id=timeline_id,
                detail="timeline head.version was not an integer",
            )
        version = raw_version
        event_count = raw_version
        raw_event_id = head.get("event_id")
        raw_hash = head.get("hash")
        if raw_event_id is not None and not isinstance(raw_event_id, str):
            return TimelineMetadataPreflight(
                status="network_failure",
                timeline_id=timeline_id,
                detail="timeline head.event_id was not a string",
            )
        if raw_hash is not None and not isinstance(raw_hash, str):
            return TimelineMetadataPreflight(
                status="network_failure",
                timeline_id=timeline_id,
                detail="timeline head.hash was not a string",
            )
        last_event_id = raw_event_id
        last_hash = raw_hash

    project_id = row.get("project_id")
    user_id = row.get("user_id")
    return TimelineMetadataPreflight(
        status="exists",
        timeline_id=timeline_id,
        project_id=project_id if isinstance(project_id, str) else None,
        user_id=user_id if isinstance(user_id, str) else None,
        version=version,
        event_count=event_count,
        last_event_id=last_event_id,
        last_hash=last_hash,
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
        transport = self._resolve_append_transport()
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

    def write_divergence(
        self,
        *,
        spoke: str,
        spoke_version: int,
        spoke_hash: str | None,
        spoke_event_id: str | None,
        hub_version: int,
        hub_hash: str | None,
        hub_event_id: str | None,
        spoke_suffix: list[dict[str, object]],
        hub_suffix: list[dict[str, object]],
        chosen_side: str = "undecided",
        artifact_pointer: dict[str, object] | None = None,
    ) -> dict[str, object]:
        transport = self._resolve_append_transport()
        raw = transport.write_divergence(
            timeline_id=self.timeline_id,
            spoke=spoke,
            spoke_version=spoke_version,
            spoke_hash=spoke_hash,
            spoke_event_id=spoke_event_id,
            hub_version=hub_version,
            hub_hash=hub_hash,
            hub_event_id=hub_event_id,
            spoke_suffix=spoke_suffix,
            hub_suffix=hub_suffix,
            chosen_side=chosen_side,
            artifact_pointer=artifact_pointer,
        )
        if not isinstance(raw, dict):
            raise EventLogTransportError(
                "SupabaseBackend.write_divergence transport returned a non-object response"
            )
        return dict(raw)

    def upsert_bookmark(
        self,
        *,
        spoke: str,
        spoke_version: int,
        spoke_hash: str | None,
        spoke_event_id: str | None,
        hub_version: int,
        hub_hash: str | None,
        hub_event_id: str | None,
        synced_at: str | None = None,
    ) -> dict[str, object]:
        transport = self._resolve_append_transport()
        raw = transport.upsert_bookmark(
            timeline_id=self.timeline_id,
            spoke=spoke,
            spoke_version=spoke_version,
            spoke_hash=spoke_hash,
            spoke_event_id=spoke_event_id,
            hub_version=hub_version,
            hub_hash=hub_hash,
            hub_event_id=hub_event_id,
            synced_at=synced_at,
        )
        if not isinstance(raw, dict):
            raise EventLogTransportError(
                "SupabaseBackend.upsert_bookmark transport returned a non-object response"
            )
        return dict(raw)

    def _resolve_append_transport(self) -> SupabaseEventLogTransport | LiveSupabaseAppendTransport:
        if self.transport is not None:
            return self.transport
        if not self._has_config():
            raise EventLogMissingConfigError(
                "SupabaseBackend.append_event requires Supabase config or a mocked transport"
            )
        if not self.supabase_url or not self.auth_token:
            raise EventLogMissingConfigError(
                "SupabaseBackend.append_event requires both supabase_url and auth_token"
            )
        return LiveSupabaseAppendTransport(
            supabase_url=self.supabase_url,
            auth_token=self.auth_token,
            rpc_append_name=self.rpc_append_name,
        )

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
