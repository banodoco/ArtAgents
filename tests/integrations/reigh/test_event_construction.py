"""Focused tests for shared Reigh event-construction helpers."""

from __future__ import annotations

from astrid.core.integrations.reigh.event_construction import (
    asset_registry_to_events,
    config_to_events,
)
from astrid.core.integrations.reigh.local_bridge import REIGH_LOCAL_EDITOR_ACTOR


def test_config_to_events_builds_versioned_hash_linked_batch_with_projection() -> None:
    config = {
        "clips": [{"id": "c1", "at": 0, "track": "V1", "clipType": "media", "asset": "a1"}],
        "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
    }
    registry = {"assets": {"a1": {"file": "intro.mp4", "type": "video/mp4"}}}

    batch = config_to_events(
        config,
        registry,
        "11111111-1111-1111-1111-111111111111",
        "prev-hash-1",
        7,
        REIGH_LOCAL_EDITOR_ACTOR,
        "editor_save",
        expected_version=6,
        ts="2026-06-12T12:00:00Z",
    )

    assert [item.version for item in batch.events] == [7, 8]
    assert [item.event.kind for item in batch.events] == [
        "timeline.config_replaced",
        "timeline.asset_registry_replaced",
    ]
    assert batch.events[0].event.prev_hash == "prev-hash-1"
    assert batch.events[1].event.prev_hash == batch.events[0].event.hash
    assert batch.events[0].event.hash is not None
    assert batch.events[1].event.hash is not None
    assert batch.events[0].event.expected_version == 6
    assert batch.events[1].event.expected_version == 6
    assert batch.projected_config == config
    assert batch.projected_asset_registry == registry
    assert batch.tail_hash == batch.events[-1].event.hash
    assert batch.next_event_version == 9
    assert batch.to_append_json()[0]["version"] == 7
    assert batch.to_append_json()[1]["payload"]["registry"] == registry


def test_asset_registry_to_events_preserves_existing_projection() -> None:
    current_config = {
        "clips": [{"id": "existing", "at": 10, "track": "V1", "clipType": "media"}],
        "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
    }
    registry = {"assets": {"existing": {"file": "nested/existing.mp4"}}}

    batch = asset_registry_to_events(
        registry,
        current_config,
        "22222222-2222-2222-2222-222222222222",
        None,
        1,
        REIGH_LOCAL_EDITOR_ACTOR,
        "editor_save",
        expected_version=0,
        ts="2026-06-12T12:05:00Z",
    )

    assert [item.version for item in batch.events] == [1]
    assert batch.events[0].event.kind == "timeline.asset_registry_replaced"
    assert batch.events[0].event.prev_hash is None
    assert batch.events[0].event.expected_version == 0
    assert batch.projected_config == current_config
    assert batch.projected_asset_registry == registry
