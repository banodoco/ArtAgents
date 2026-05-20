from __future__ import annotations

import json
import unittest
from uuid import uuid4

from astrid.core.timeline.eventlog import (
    EventLogNotConfiguredError,
    EventLogNotImplementedError,
    LocalFsBackend,
    SupabaseBackend,
    select_timeline_backend,
    select_timeline_stream,
)
from astrid.core.timeline.events.schema import (
    EVENT_SCHEMA_VERSION,
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    TimelineActor,
    TimelineCreatedPayload,
    TimelineEvent,
    TimelineEventSchemaError,
    TimelineImportedPayload,
    TimelineRenamedPayload,
    canonical_json_text,
    generate_event_ulid,
    is_event_ulid,
    sha256_hex,
    with_event_hash,
)


class TimelineEventSchemaTest(unittest.TestCase):
    def test_timeline_event_canonical_json_omits_nulls_and_hash(self) -> None:
        actor = TimelineActor(type="agent", id="codex:run-1", display=None)
        event = TimelineEvent.new(
            timeline_id=str(uuid4()),
            ts="2026-05-19T20:44:00Z",
            actor=actor,
            kind="timeline.renamed",
            payload=TimelineRenamedPayload(old_slug="before", new_slug="after"),
            prev_hash=None,
            expected_version=None,
            txn_id=None,
        )

        canonical = canonical_json_text(event, exclude_hash=True)
        self.assertNotIn('"hash"', canonical)
        self.assertNotIn('"prev_hash"', canonical)
        self.assertNotIn('"display"', canonical)
        self.assertNotIn('"expected_version"', canonical)
        self.assertNotIn('"txn_id"', canonical)
        self.assertIn('"schema_version":1', canonical)

    def test_timeline_event_hashing_is_deterministic(self) -> None:
        actor = TimelineActor(type="human", id="maker")
        event = TimelineEvent.new(
            timeline_id=str(uuid4()),
            ts="2026-05-19T20:44:00Z",
            actor=actor,
            kind="timeline.created",
            payload=TimelineCreatedPayload(
                timeline_id=str(uuid4()),
                slug="launch-cut",
                name="Launch Cut",
            ),
        )

        hashed_a = with_event_hash(event, prev_hash=None)
        hashed_b = with_event_hash(event, prev_hash=None)
        self.assertEqual(hashed_a.hash, hashed_b.hash)
        self.assertEqual(hashed_a.hash, sha256_hex(hashed_a.to_json_obj(), exclude_hash=True))

    def test_timeline_event_validates_ids_and_actor_shape(self) -> None:
        actor = TimelineActor(type="system", id="migration:m1")
        event = TimelineEvent.new(
            timeline_id=str(uuid4()),
            ts="2026-05-19T20:44:00Z",
            actor=actor,
            kind="timeline.deleted",
            payload={},
            txn_id=generate_event_ulid(),
        )

        self.assertTrue(is_event_ulid(event.event_id))
        self.assertTrue(is_event_ulid(event.txn_id))
        self.assertEqual(event.schema_version, EVENT_SCHEMA_VERSION)

        with self.assertRaises(TimelineEventSchemaError):
            TimelineActor(type="robot", id="bad")  # type: ignore[arg-type]

        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.new(
                timeline_id="not-a-uuid",
                ts="2026-05-19T20:44:00Z",
                actor=actor,
                kind="timeline.deleted",
                payload={},
            )

    def test_timeline_import_payload_accepts_json_snapshot(self) -> None:
        payload = TimelineImportedPayload(
            snapshot={"slug": "legacy-cut", "display": None, "clips": [1, {"ok": True}]},
            source="legacy_local",
        )
        self.assertEqual(
            canonical_json_text(payload),
            '{"snapshot":{"clips":[1,{"ok":true}],"slug":"legacy-cut"},"source":"legacy_local"}',
        )

    def test_timeline_stream_selector_prefers_explicit_supabase(self) -> None:
        stream = select_timeline_stream(
            timeline_id=str(uuid4()),
            timeline_home="/tmp/timeline-home",
            preferred_backend="supabase",
        )
        self.assertEqual(stream.backend, "supabase")
        self.assertIsNone(stream.home)
        self.assertEqual(stream.source, "preferred_backend")

    def test_timeline_backend_selector_builds_local_fs_from_timeline_home(self) -> None:
        timeline_id = str(uuid4())
        stream, backend = select_timeline_backend(
            timeline_id=timeline_id,
            timeline_home="/tmp/timeline-home",
        )
        self.assertEqual(stream.backend, "local_fs")
        self.assertEqual(stream.source, "timeline_home")
        self.assertIsInstance(backend, LocalFsBackend)
        self.assertEqual(backend.backend_name(), "local_fs")

    def test_timeline_backend_selector_builds_inert_supabase_stub_explicitly(self) -> None:
        timeline_id = str(uuid4())
        stream, backend = select_timeline_backend(
            timeline_id=timeline_id,
            timeline_home="/tmp/timeline-home",
            preferred_backend="supabase",
        )
        self.assertEqual(stream.backend, "supabase")
        self.assertEqual(stream.source, "preferred_backend")
        self.assertIsInstance(backend, SupabaseBackend)
        self.assertEqual(backend.backend_name(), "supabase")

    def test_supabase_backend_stub_is_constructible_and_inert(self) -> None:
        tid = str(uuid4())
        backend = SupabaseBackend(timeline_id=tid)

        self.assertEqual(backend.backend_name(), "supabase")

        with self.assertRaises(TimelineEventSchemaError):
            TimelineActor(type="agent", id="")

        with self.assertRaises(EventLogNotImplementedError):
            backend.append_event(
                tid,
                "timeline.renamed",
                {"old_slug": "before", "new_slug": "after"},
                actor=TimelineActor(type="agent", id="codex:run-1"),
            )

        with self.assertRaises(EventLogNotConfiguredError):
            backend.read_events()

        with self.assertRaises(EventLogNotConfiguredError):
            backend.head()

        with self.assertRaises(EventLogNotConfiguredError):
            backend.verify_chain()


class ClipPayloadSchemaTest(unittest.TestCase):
    """Validate all clip.* payload models, position normalization, and invalid-payload rejection."""

    # ------------------------------------------------------------------
    # ClipPosition
    # ------------------------------------------------------------------

    def test_position_index_requires_integer_index(self) -> None:
        pos = ClipPosition(mode="index", index=0)
        self.assertEqual(pos.to_json_obj(), {"mode": "index", "index": 0})

        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition(mode="index")
        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition(mode="index", index="not-an-int")  # type: ignore[arg-type]

    def test_position_after_requires_nonempty_ref_clip_id(self) -> None:
        pos = ClipPosition(mode="after", ref_clip_id="clip-1")
        self.assertEqual(pos.to_json_obj(), {"mode": "after", "ref_clip_id": "clip-1"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition(mode="after")
        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition(mode="after", ref_clip_id="")

    def test_position_before_requires_nonempty_ref_clip_id(self) -> None:
        pos = ClipPosition(mode="before", ref_clip_id="clip-1")
        self.assertEqual(pos.to_json_obj(), {"mode": "before", "ref_clip_id": "clip-1"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition(mode="before", ref_clip_id="")

    def test_position_rejects_invalid_mode(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition(mode="invalid", ref_clip_id="x")  # type: ignore[arg-type]

    def test_position_from_dict(self) -> None:
        pos = ClipPosition.from_dict({"mode": "index", "index": 5})
        self.assertEqual(pos.mode, "index")
        self.assertEqual(pos.index, 5)

        pos2 = ClipPosition.from_dict({"mode": "after", "ref_clip_id": "c1"})
        self.assertEqual(pos2.mode, "after")
        self.assertEqual(pos2.ref_clip_id, "c1")

        with self.assertRaises(TimelineEventSchemaError):
            ClipPosition.from_dict("not-a-dict")

    def test_position_normalizes_extra_fields(self) -> None:
        """When mode is `after`/`before`, `index` must be stripped to None."""
        pos = ClipPosition(mode="after", ref_clip_id="c1", index=99)
        self.assertIsNone(pos.index)

    # ------------------------------------------------------------------
    # ClipAddedPayload
    # ------------------------------------------------------------------

    def test_clip_added_payload_validates_and_serialises(self) -> None:
        payload = ClipAddedPayload(
            clip_id="clip-1",
            kind="visual",
            asset_id="asset-1",
            position=ClipPosition(mode="index", index=0),
        )
        self.assertEqual(payload.clip_id, "clip-1")
        self.assertEqual(payload.kind, "visual")
        self.assertEqual(payload.asset_id, "asset-1")
        obj = payload.to_json_obj()
        self.assertEqual(obj["clip_id"], "clip-1")
        self.assertEqual(obj["kind"], "visual")
        self.assertEqual(obj["position"], {"mode": "index", "index": 0})

    def test_clip_added_payload_position_from_dict(self) -> None:
        payload = ClipAddedPayload(
            clip_id="clip-2",
            kind="audio",
            asset_id="asset-2",
            position={"mode": "after", "ref_clip_id": "c0"},
        )
        self.assertIsInstance(payload.position, ClipPosition)
        self.assertEqual(payload.position.mode, "after")

    def test_clip_added_rejects_empty_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="", kind="visual", asset_id="a")

    def test_clip_added_rejects_invalid_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="c1", kind="invalid", asset_id="a")  # type: ignore[arg-type]

    def test_clip_added_rejects_empty_asset_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="c1", kind="visual", asset_id="")

    # ------------------------------------------------------------------
    # ClipRemovedPayload
    # ------------------------------------------------------------------

    def test_clip_removed_payload_validates(self) -> None:
        payload = ClipRemovedPayload(clip_id="clip-1")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "clip-1"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipRemovedPayload(clip_id="")

    # ------------------------------------------------------------------
    # ClipMovedPayload
    # ------------------------------------------------------------------

    def test_clip_moved_payload_validates(self) -> None:
        payload = ClipMovedPayload(clip_id="clip-1", position=ClipPosition(mode="before", ref_clip_id="c2"))
        obj = payload.to_json_obj()
        self.assertEqual(obj["clip_id"], "clip-1")
        self.assertEqual(obj["position"]["mode"], "before")

        with self.assertRaises(TimelineEventSchemaError):
            ClipMovedPayload(clip_id="clip-1", position=None)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # ClipRetimedPayload
    # ------------------------------------------------------------------

    def test_clip_retimed_payload_normalises_floats(self) -> None:
        payload = ClipRetimedPayload(clip_id="c1", start=1, duration=5)
        obj = payload.to_json_obj()
        self.assertEqual(obj["start"], 1.0)
        self.assertEqual(obj["duration"], 5.0)

    def test_clip_retimed_rejects_negative_start(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipRetimedPayload(clip_id="c1", start=-1, duration=5)

    def test_clip_retimed_rejects_non_positive_duration(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipRetimedPayload(clip_id="c1", start=0, duration=0)
        with self.assertRaises(TimelineEventSchemaError):
            ClipRetimedPayload(clip_id="c1", start=0, duration=-1)

    def test_clip_retimed_rejects_bool_args(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipRetimedPayload(clip_id="c1", start=True, duration=5)  # type: ignore[arg-type]
        with self.assertRaises(TimelineEventSchemaError):
            ClipRetimedPayload(clip_id="c1", start=0, duration=True)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # ClipSwappedPayload
    # ------------------------------------------------------------------

    def test_clip_swapped_payload_validates(self) -> None:
        payload = ClipSwappedPayload(clip_a_id="a", clip_b_id="b")
        self.assertEqual(payload.to_json_obj(), {"clip_a_id": "a", "clip_b_id": "b"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipSwappedPayload(clip_a_id="", clip_b_id="b")
        with self.assertRaises(TimelineEventSchemaError):
            ClipSwappedPayload(clip_a_id="a", clip_b_id="")

    # ------------------------------------------------------------------
    # ClipReplacedPayload
    # ------------------------------------------------------------------

    def test_clip_replaced_payload_validates(self) -> None:
        payload = ClipReplacedPayload(clip_id="c1", with_asset_id="a2")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1", "with_asset_id": "a2"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipReplacedPayload(clip_id="", with_asset_id="a2")
        with self.assertRaises(TimelineEventSchemaError):
            ClipReplacedPayload(clip_id="c1", with_asset_id="")

    # ------------------------------------------------------------------
    # ClipTextSetPayload
    # ------------------------------------------------------------------

    def test_clip_text_set_payload_validates(self) -> None:
        payload = ClipTextSetPayload(clip_id="c1", text="hello world")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1", "text": "hello world"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipTextSetPayload(clip_id="", text="x")
        with self.assertRaises(TimelineEventSchemaError):
            ClipTextSetPayload(clip_id="c1", text=123)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # ClipAnnotatedPayload
    # ------------------------------------------------------------------

    def test_clip_annotated_payload_validates(self) -> None:
        payload = ClipAnnotatedPayload(clip_id="c1", note="a note")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1", "note": "a note"})

        with self.assertRaises(TimelineEventSchemaError):
            ClipAnnotatedPayload(clip_id="", note="x")
        with self.assertRaises(TimelineEventSchemaError):
            ClipAnnotatedPayload(clip_id="c1", note=456)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # clip.* events round-trip through TimelineEvent
    # ------------------------------------------------------------------

    def test_clip_event_round_trip_all_kinds(self) -> None:
        """Every clip.* kind round-trips through TimelineEvent.new() → canonical_json_text() → TimelineEvent.from_dict()."""
        actor = TimelineActor(type="agent", id="tester")
        tid = str(uuid4())

        cases = [
            ("clip.added", ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1")),
            ("clip.removed", ClipRemovedPayload(clip_id="c1")),
            ("clip.moved", ClipMovedPayload(clip_id="c1", position=ClipPosition(mode="index", index=0))),
            ("clip.retimed", ClipRetimedPayload(clip_id="c1", start=0.0, duration=5.0)),
            ("clip.swapped", ClipSwappedPayload(clip_a_id="a", clip_b_id="b")),
            ("clip.replaced", ClipReplacedPayload(clip_id="c1", with_asset_id="a2")),
            ("clip.text_set", ClipTextSetPayload(clip_id="c1", text="hello")),
            ("clip.annotated", ClipAnnotatedPayload(clip_id="c1", note="my note")),
        ]

        for kind, payload in cases:
            with self.subTest(kind=kind):
                event = TimelineEvent.new(
                    timeline_id=tid,
                    ts="2026-05-20T12:00:00Z",
                    actor=actor,
                    kind=kind,  # type: ignore[arg-type]
                    payload=payload,
                )
                self.assertEqual(event.kind, kind)
                # canonical JSON → from_dict
                text = canonical_json_text(event, exclude_hash=True)
                restored = TimelineEvent.from_dict(json.loads(text))
                self.assertEqual(restored.kind, kind)
                self.assertEqual(restored.event_id, event.event_id)

    def test_clip_event_invalid_kind_rejects(self) -> None:
        """Unregistered event kinds fail TimelineEvent.new()."""
        actor = TimelineActor(type="agent", id="tester")
        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.new(
                timeline_id=str(uuid4()),
                ts="2026-05-20T12:00:00Z",
                actor=actor,
                kind="clip.nonexistent",  # type: ignore[arg-type]
                payload=ClipRemovedPayload(clip_id="c1"),
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
