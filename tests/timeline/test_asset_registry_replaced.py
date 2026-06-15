"""Focused tests for ``timeline.asset_registry_replaced`` — canonical hashing,
payload preservation, and batching after ``timeline.config_replaced``.

Covers:
- Canonical event serialization and deterministic hashing
- Payload construction, validation, and round-trip preservation
- Projection as a ``non_container_read_model`` no-op
- Batching: config_replaced → asset_registry_replaced in sequence
"""

from __future__ import annotations

import unittest
from copy import deepcopy
from typing import Any
from uuid import uuid4

from astrid.core.timeline.banodoco_schema import canonical_empty_timeline
from astrid.core.timeline.events.schema import (
    EVENT_SCHEMA_VERSION,
    AssetRegistryReplacedPayload,
    TimelineActor,
    TimelineEvent,
    TimelineEventSchemaError,
    canonical_json_text,
    sha256_hex,
    with_event_hash,
)
from astrid.core.timeline.projection import (
    apply_event_to_assembly,
    classify_projector_event_kind,
    project_to_assembly,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _actor(name: str = "tester") -> TimelineActor:
    return TimelineActor(type="agent", id=f"test:{name}", display=name)


def _minimal_registry() -> dict[str, Any]:
    """Minimal valid asset registry dict."""
    return {
        "assets": {
            "a1": {
                "file": "clip.mp4",
                "url": "https://cdn.example.com/clip.mp4",
            }
        }
    }


def _make_event(
    kind: str,
    payload: dict[str, Any],
    *,
    timeline_id: str | None = None,
    event_id: str = "01AAAAAAAAAAAAAAAAAAAAAA00",
    prev_hash: str | None = None,
) -> TimelineEvent:
    return TimelineEvent.from_dict({
        "event_id": event_id,
        "timeline_id": timeline_id or str(uuid4()),
        "ts": "2026-01-01T00:00:00Z",
        "actor": {"type": "system", "id": "test", "display": "Test"},
        "prev_hash": prev_hash,
        "hash": None,
        "kind": kind,
        "payload": payload,
        "expected_version": None,
        "schema_version": EVENT_SCHEMA_VERSION,
        "txn_id": None,
    })


# ── canonical hashing ────────────────────────────────────────────────────────


class AssetRegistryReplacedCanonicalHashingTest(unittest.TestCase):
    """Prove canonical JSON and deterministic SHA-256 for registry events."""

    def test_canonical_json_omits_nulls(self) -> None:
        payload = AssetRegistryReplacedPayload(registry=_minimal_registry())
        event = TimelineEvent.new(
            timeline_id=str(uuid4()),
            ts="2026-01-01T00:00:00Z",
            actor=_actor(),
            kind="timeline.asset_registry_replaced",
            payload=payload,
        )
        canonical = canonical_json_text(event, exclude_hash=True)
        self.assertNotIn('"hash"', canonical)
        self.assertNotIn('"prev_hash"', canonical)
        self.assertNotIn('"source"', canonical)  # source is None → omitted

    def test_canonical_json_includes_source_when_present(self) -> None:
        payload = AssetRegistryReplacedPayload(
            registry=_minimal_registry(), source="editor_save",
        )
        event = TimelineEvent.new(
            timeline_id=str(uuid4()),
            ts="2026-01-01T00:00:00Z",
            actor=_actor(),
            kind="timeline.asset_registry_replaced",
            payload=payload,
        )
        canonical = canonical_json_text(event, exclude_hash=True)
        self.assertIn('"editor_save"', canonical)

    def test_hashing_is_deterministic_same_payload(self) -> None:
        tid = str(uuid4())
        payload = AssetRegistryReplacedPayload(registry=_minimal_registry())
        event_a = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-01-01T00:00:00Z",
            actor=_actor(),
            kind="timeline.asset_registry_replaced",
            payload=payload,
        )
        event_b = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-01-01T00:00:00Z",
            actor=_actor(),
            kind="timeline.asset_registry_replaced",
            payload=payload,
        )
        # Different event_id (ULIDs) but everything else identical — different hashes
        hashed_a = with_event_hash(event_a, prev_hash=None)
        hashed_b = with_event_hash(event_b, prev_hash=None)
        self.assertNotEqual(hashed_a.hash, hashed_b.hash)
        # But re-hashing the SAME event is deterministic
        hash1 = sha256_hex(event_a.to_json_obj(), exclude_hash=True)
        hash2 = sha256_hex(event_a.to_json_obj(), exclude_hash=True)
        self.assertEqual(hash1, hash2)

    def test_hash_differs_for_different_registries(self) -> None:
        tid = str(uuid4())
        p1 = AssetRegistryReplacedPayload(registry={"assets": {"a1": {"file": "a.mp4"}}})
        p2 = AssetRegistryReplacedPayload(registry={"assets": {"b1": {"file": "b.mp4"}}})
        e1 = TimelineEvent.new(
            timeline_id=tid, ts="2026-01-01T00:00:00Z", actor=_actor(),
            kind="timeline.asset_registry_replaced", payload=p1,
        )
        e2 = TimelineEvent.new(
            timeline_id=tid, ts="2026-01-01T00:00:00Z", actor=_actor(),
            kind="timeline.asset_registry_replaced", payload=p2,
        )
        h1 = sha256_hex(e1.to_json_obj(), exclude_hash=True)
        h2 = sha256_hex(e2.to_json_obj(), exclude_hash=True)
        self.assertNotEqual(h1, h2)

    def test_hash_incorporates_prev_hash(self) -> None:
        tid = str(uuid4())
        payload = AssetRegistryReplacedPayload(registry=_minimal_registry())
        event = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-01-01T00:00:00Z",
            actor=_actor(),
            kind="timeline.asset_registry_replaced",
            payload=payload,
        )
        hashed_none = with_event_hash(event, prev_hash=None)
        hashed_abc = with_event_hash(event, prev_hash="abc123")
        self.assertNotEqual(hashed_none.hash, hashed_abc.hash)

    def test_self_hash_matches_canonical_rehash(self) -> None:
        """Verify that event.hash == sha256_hex(event, exclude_hash=True)."""
        tid = str(uuid4())
        payload = AssetRegistryReplacedPayload(registry=_minimal_registry())
        event = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-01-01T00:00:00Z",
            actor=_actor(),
            kind="timeline.asset_registry_replaced",
            payload=payload,
        )
        hashed = with_event_hash(event, prev_hash=None)
        recomputed = sha256_hex(hashed.to_json_obj(), exclude_hash=True)
        self.assertEqual(hashed.hash, recomputed)


# ── payload construction and preservation ────────────────────────────────────


class AssetRegistryReplacedPayloadConstructionTest(unittest.TestCase):
    """Prove payload validation, construction, and serialization round-trips."""

    def test_minimal_payload_registry_only(self) -> None:
        payload = AssetRegistryReplacedPayload(registry={"assets": {}})
        self.assertEqual(payload.registry, {"assets": {}})
        self.assertIsNone(payload.source)

    def test_payload_with_source(self) -> None:
        for source in ("legacy_local", "supabase_config", "editor_save", "other"):
            payload = AssetRegistryReplacedPayload(
                registry=_minimal_registry(), source=source,
            )
            self.assertEqual(payload.source, source)

    def test_payload_rejects_non_dict_registry(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            AssetRegistryReplacedPayload(registry="not-a-dict")  # type: ignore[arg-type]

    def test_payload_rejects_invalid_source(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            AssetRegistryReplacedPayload(
                registry=_minimal_registry(), source="invalid_source",  # type: ignore[arg-type]
            )

    def test_payload_rejects_non_jsonable_registry(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            AssetRegistryReplacedPayload(
                registry={"bad": object()},  # type: ignore[dict-item]
            )

    def test_to_json_obj_preserves_registry_deep(self) -> None:
        original = {
            "assets": {
                "a1": {
                    "file": "clip.mp4",
                    "url": "https://cdn.example.com/clip.mp4",
                    "etag": '"abc123"',
                    "content_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "origin": "immutable-public",
                    "derivedFrom": {
                        "assetId": "src-1",
                        "content_sha256": "a" * 64,
                        "role": "proxy",
                    },
                }
            }
        }
        payload = AssetRegistryReplacedPayload(registry=original, source="other")
        obj = payload.to_json_obj()
        self.assertEqual(obj["registry"], original)
        self.assertEqual(obj["source"], "other")
        # Ensure defensive copy — mutate the output, original should be unchanged
        obj["registry"]["assets"]["new"] = {"file": "x.mp4"}
        self.assertNotIn("new", payload.registry["assets"])

    def test_to_json_obj_omits_source_when_none(self) -> None:
        payload = AssetRegistryReplacedPayload(registry=_minimal_registry())
        obj = payload.to_json_obj()
        self.assertNotIn("source", obj)
        self.assertEqual(obj["registry"], _minimal_registry())

    def test_from_dict_event_roundtrip(self) -> None:
        """Build via TimelineEvent.from_dict and confirm payload is typed."""
        tid = str(uuid4())
        raw = {
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAA00",
            "timeline_id": tid,
            "ts": "2026-01-01T00:00:00Z",
            "actor": {"type": "system", "id": "test", "display": "Test"},
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.asset_registry_replaced",
            "payload": {
                "registry": _minimal_registry(),
                "source": "editor_save",
            },
            "expected_version": None,
            "schema_version": EVENT_SCHEMA_VERSION,
            "txn_id": None,
        }
        event = TimelineEvent.from_dict(raw)
        self.assertEqual(event.kind, "timeline.asset_registry_replaced")
        self.assertIsInstance(event.payload, AssetRegistryReplacedPayload)
        self.assertEqual(event.payload.source, "editor_save")
        self.assertEqual(event.payload.registry, _minimal_registry())


# ── projection behaviour ─────────────────────────────────────────────────────


class AssetRegistryReplacedProjectionTest(unittest.TestCase):
    """Prove ``timeline.asset_registry_replaced`` is projected as a no-op
    (``non_container_read_model``), and that batching it after a
    ``timeline.config_replaced`` event leaves the container assembly unchanged."""

    def test_classification_is_non_container_read_model(self) -> None:
        self.assertEqual(
            classify_projector_event_kind("timeline.asset_registry_replaced"),
            "non_container_read_model",
        )

    def test_apply_event_to_assembly_is_noop(self) -> None:
        state = canonical_empty_timeline()
        state["clips"] = [{"id": "c1", "at": 0.0, "track": "v1", "clipType": "media", "asset": "a1"}]
        state["tracks"] = [{"id": "v1", "kind": "visual", "label": "Video"}]

        event = _make_event(
            "timeline.asset_registry_replaced",
            {"registry": _minimal_registry(), "source": "editor_save"},
        )

        result = apply_event_to_assembly(deepcopy(state), event)
        self.assertEqual(result, state)

    def test_apply_event_does_not_mutate_input_state(self) -> None:
        state = canonical_empty_timeline()
        original = deepcopy(state)
        event = _make_event(
            "timeline.asset_registry_replaced",
            {"registry": _minimal_registry()},
        )
        apply_event_to_assembly(state, event)
        self.assertEqual(state, original)

    def test_asset_registry_after_config_replaced_does_not_alter_config(self) -> None:
        """Batching: config_replaced builds the assembly; a following
        asset_registry_replaced is a no-op and leaves it intact."""
        state = canonical_empty_timeline()
        tid = str(uuid4())

        # A valid TimelineConfig container
        new_config = deepcopy(state)
        new_config["clips"] = [{"id": "c1", "at": 0.0, "track": "v1", "clipType": "media", "asset": "a1"}]
        new_config["tracks"] = [{"id": "v1", "kind": "visual", "label": "Video"}]

        config_event = _make_event(
            "timeline.config_replaced",
            {"config": new_config, "source": "editor_save"},
            timeline_id=tid,
        )

        registry_event = _make_event(
            "timeline.asset_registry_replaced",
            {"registry": _minimal_registry(), "source": "editor_save"},
            timeline_id=tid,
        )

        # Apply config_replaced → state becomes new_config
        after_config = apply_event_to_assembly(state, config_event)
        self.assertEqual(after_config["clips"][0]["id"], "c1")

        # Apply asset_registry_replaced → state unchanged
        after_registry = apply_event_to_assembly(after_config, registry_event)
        self.assertEqual(after_registry, after_config)
        self.assertEqual(after_registry["clips"][0]["id"], "c1")

    def test_project_to_assembly_with_config_then_registry_batch(self) -> None:
        """Full batch replay: config_replaced + asset_registry_replaced
        produces the config assembly unchanged."""
        tid = str(uuid4())
        new_config = deepcopy(canonical_empty_timeline())
        new_config["clips"] = [{"id": "c2", "at": 1.0, "track": "v1", "clipType": "media", "asset": "a2"}]
        new_config["tracks"] = [{"id": "v1", "kind": "visual", "label": "Video"}]

        events = [
            _make_event(
                "timeline.config_replaced",
                {"config": new_config, "source": "editor_save"},
                timeline_id=tid,
                event_id="01AAAAAAAAAAAAAAAAAAAAAA01",
            ),
            _make_event(
                "timeline.asset_registry_replaced",
                {"registry": _minimal_registry(), "source": "editor_save"},
                timeline_id=tid,
                event_id="01AAAAAAAAAAAAAAAAAAAAAA02",
            ),
        ]

        result = project_to_assembly(events)
        self.assertEqual(result["clips"][0]["id"], "c2")
        self.assertEqual(result["clips"][0]["at"], 1.0)

    def test_asset_registry_only_batch_is_empty_config(self) -> None:
        """Projecting only an asset_registry event on an initial empty
        assembly yields the canonical empty timeline (no-op)."""
        events = [
            _make_event(
                "timeline.asset_registry_replaced",
                {"registry": _minimal_registry()},
                event_id="01AAAAAAAAAAAAAAAAAAAAAA03",
            ),
        ]
        result = project_to_assembly(events)
        expected = canonical_empty_timeline()
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
