"""Reigh-compatible event construction helpers for timeline eventlog writes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent, with_event_hash
from astrid.core.timeline.events.schema.payloads._base import TimelineImportSource
from astrid.core.timeline.events.schema.payloads.asset_registry import (
    AssetRegistryReplacedPayload,
)
from astrid.core.timeline.events.schema.payloads.config import TimelineConfigReplacedPayload
from astrid.core.timeline.projection import project_to_assembly
from astrid.core.util.time import utc_now_seconds as utc_now_iso


@dataclass(frozen=True)
class VersionedTimelineEvent:
    """Timeline event plus its external stream version."""

    version: int
    event: TimelineEvent

    def to_append_json_obj(self) -> dict[str, Any]:
        payload = self.event.to_json_obj()
        payload["version"] = self.version
        return payload


@dataclass(frozen=True)
class ReighEventBatch:
    """Canonical event batch plus projected materialization outputs."""

    events: tuple[VersionedTimelineEvent, ...]
    projected_config: dict[str, Any]
    projected_asset_registry: dict[str, Any] | None

    @property
    def inserted_event_ids(self) -> tuple[str, ...]:
        return tuple(item.event.event_id for item in self.events)

    @property
    def tail_hash(self) -> str | None:
        if not self.events:
            return None
        return self.events[-1].event.hash

    @property
    def next_event_version(self) -> int:
        if not self.events:
            return 0
        return self.events[-1].version + 1

    def to_append_json(self) -> list[dict[str, Any]]:
        return [item.to_append_json_obj() for item in self.events]


def construct_reigh_timeline_events(
    *,
    timeline_id: str,
    tail_hash: str | None,
    next_event_version: int,
    actor: TimelineActor,
    source: TimelineImportSource,
    config: dict[str, Any] | None = None,
    asset_registry: dict[str, Any] | None = None,
    current_config: dict[str, Any] | None = None,
    expected_version: int | None = None,
    txn_id: str | None = None,
    ts: str | None = None,
) -> ReighEventBatch:
    """Build the canonical Reigh event batch for one config/registry write."""
    if config is None and asset_registry is None:
        raise ValueError("construct_reigh_timeline_events requires config and/or asset_registry")
    if next_event_version < 1:
        raise ValueError("next_event_version must be >= 1")
    if tail_hash is not None and (not isinstance(tail_hash, str) or tail_hash == ""):
        raise ValueError("tail_hash must be a non-empty string when supplied")
    if config is None and current_config is None:
        raise ValueError("current_config is required when constructing registry-only batches")

    timestamp = ts or utc_now_iso()
    current_hash = tail_hash
    current_version = next_event_version
    built: list[VersionedTimelineEvent] = []

    if config is not None:
        event = TimelineEvent.new(
            timeline_id=timeline_id,
            ts=timestamp,
            actor=actor,
            kind="timeline.config_replaced",
            payload=TimelineConfigReplacedPayload(config=deepcopy(config), source=source),
            prev_hash=current_hash,
            expected_version=expected_version,
            txn_id=txn_id,
        )
        event = with_event_hash(event, prev_hash=current_hash)
        built.append(VersionedTimelineEvent(version=current_version, event=event))
        current_hash = event.hash
        current_version += 1

    if asset_registry is not None:
        event = TimelineEvent.new(
            timeline_id=timeline_id,
            ts=timestamp,
            actor=actor,
            kind="timeline.asset_registry_replaced",
            payload=AssetRegistryReplacedPayload(
                registry=deepcopy(asset_registry),
                source=source,
            ),
            prev_hash=current_hash,
            expected_version=expected_version,
            txn_id=txn_id,
        )
        event = with_event_hash(event, prev_hash=current_hash)
        built.append(VersionedTimelineEvent(version=current_version, event=event))

    if config is not None:
        projected_config = project_to_assembly([item.event for item in built])
    else:
        projected_config = deepcopy(current_config)

    return ReighEventBatch(
        events=tuple(built),
        projected_config=projected_config,
        projected_asset_registry=deepcopy(asset_registry) if asset_registry is not None else None,
    )


def config_to_events(
    config: dict[str, Any],
    asset_registry: dict[str, Any] | None,
    timeline_id: str,
    tail_hash: str | None,
    next_event_version: int,
    actor: TimelineActor,
    source: TimelineImportSource,
    *,
    expected_version: int | None = None,
    txn_id: str | None = None,
    ts: str | None = None,
) -> ReighEventBatch:
    """Build the canonical batch for a full Reigh config replacement."""
    return construct_reigh_timeline_events(
        timeline_id=timeline_id,
        tail_hash=tail_hash,
        next_event_version=next_event_version,
        actor=actor,
        source=source,
        config=config,
        asset_registry=asset_registry,
        expected_version=expected_version,
        txn_id=txn_id,
        ts=ts,
    )


def asset_registry_to_events(
    asset_registry: dict[str, Any],
    current_config: dict[str, Any],
    timeline_id: str,
    tail_hash: str | None,
    next_event_version: int,
    actor: TimelineActor,
    source: TimelineImportSource,
    *,
    expected_version: int | None = None,
    txn_id: str | None = None,
    ts: str | None = None,
) -> ReighEventBatch:
    """Build the canonical batch for an asset-registry replacement only."""
    return construct_reigh_timeline_events(
        timeline_id=timeline_id,
        tail_hash=tail_hash,
        next_event_version=next_event_version,
        actor=actor,
        source=source,
        asset_registry=asset_registry,
        current_config=current_config,
        expected_version=expected_version,
        txn_id=txn_id,
        ts=ts,
    )
