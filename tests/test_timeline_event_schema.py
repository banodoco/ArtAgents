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
    ArrangementReplacedPayload,
    AudioBoundPayload,
    AudioUnboundPayload,
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    EffectAddedPayload,
    EffectRemovedPayload,
    EffectTunedPayload,
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineActor,
    TimelineCreatedPayload,
    TimelineEvent,
    TimelineEventSchemaError,
    TimelineImportedPayload,
    TimelineRenamedPayload,
    TrackAddedPayload,
    TrackRemovedPayload,
    TransitionRemovedPayload,
    TransitionSetPayload,
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
        self.assertIn(f'"schema_version":{EVENT_SCHEMA_VERSION}', canonical)

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


class SecondaryPayloadSchemaTest(unittest.TestCase):
    """Validate all m3 secondary payload models: transition, effect, theme, track,
    audio, pool, and arrangement payloads."""

    # ------------------------------------------------------------------
    # TransitionSetPayload
    # ------------------------------------------------------------------

    def test_transition_set_payload_validates_and_serialises(self) -> None:
        payload = TransitionSetPayload(
            left_clip_id="clip-a",
            right_clip_id="clip-b",
            kind="cross-fade",
            duration_seconds=2.5,
        )
        self.assertEqual(payload.left_clip_id, "clip-a")
        self.assertEqual(payload.right_clip_id, "clip-b")
        self.assertEqual(payload.kind, "cross-fade")
        self.assertEqual(payload.duration_seconds, 2.5)
        obj = payload.to_json_obj()
        self.assertEqual(obj["left_clip_id"], "clip-a")
        self.assertEqual(obj["right_clip_id"], "clip-b")
        self.assertEqual(obj["kind"], "cross-fade")
        self.assertEqual(obj["duration_seconds"], 2.5)

    def test_transition_set_rejects_empty_left_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="", right_clip_id="b", kind="cross-fade", duration_seconds=1.0)

    def test_transition_set_rejects_empty_right_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="", kind="cross-fade", duration_seconds=1.0)

    def test_transition_set_rejects_empty_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="", duration_seconds=1.0)

    def test_transition_set_rejects_negative_duration(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="cross-fade", duration_seconds=-1)

    def test_transition_set_rejects_zero_duration(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="cross-fade", duration_seconds=0)

    def test_transition_set_rejects_bool_duration(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="cross-fade", duration_seconds=True)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # TransitionRemovedPayload
    # ------------------------------------------------------------------

    def test_transition_removed_payload_validates(self) -> None:
        payload = TransitionRemovedPayload(left_clip_id="clip-a", right_clip_id="clip-b")
        self.assertEqual(payload.to_json_obj(), {"left_clip_id": "clip-a", "right_clip_id": "clip-b"})

    def test_transition_removed_rejects_empty_ids(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionRemovedPayload(left_clip_id="", right_clip_id="b")
        with self.assertRaises(TimelineEventSchemaError):
            TransitionRemovedPayload(left_clip_id="a", right_clip_id="")

    # ------------------------------------------------------------------
    # EffectAddedPayload
    # ------------------------------------------------------------------

    def test_effect_added_payload_validates(self) -> None:
        payload = EffectAddedPayload(clip_id="c1", effect_id="e1")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1", "effect_id": "e1"})

    def test_effect_added_with_params(self) -> None:
        payload = EffectAddedPayload(clip_id="c1", effect_id="e1", params={"blur": 5, "color": "red"})
        obj = payload.to_json_obj()
        self.assertEqual(obj["params"], {"blur": 5, "color": "red"})

    def test_effect_added_rejects_empty_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectAddedPayload(clip_id="", effect_id="e1")

    def test_effect_added_rejects_empty_effect_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectAddedPayload(clip_id="c1", effect_id="")

    def test_effect_added_rejects_invalid_params_type(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectAddedPayload(clip_id="c1", effect_id="e1", params="not-a-dict")  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # EffectRemovedPayload
    # ------------------------------------------------------------------

    def test_effect_removed_payload_validates(self) -> None:
        payload = EffectRemovedPayload(clip_id="c1", effect_id="e1")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1", "effect_id": "e1"})

    def test_effect_removed_rejects_empty_ids(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectRemovedPayload(clip_id="", effect_id="e1")
        with self.assertRaises(TimelineEventSchemaError):
            EffectRemovedPayload(clip_id="c1", effect_id="")

    # ------------------------------------------------------------------
    # EffectTunedPayload
    # ------------------------------------------------------------------

    def test_effect_tuned_payload_validates(self) -> None:
        payload = EffectTunedPayload(clip_id="c1", effect_id="e1", param="blur", value=10)
        obj = payload.to_json_obj()
        self.assertEqual(obj["clip_id"], "c1")
        self.assertEqual(obj["effect_id"], "e1")
        self.assertEqual(obj["param"], "blur")
        self.assertEqual(obj["value"], 10)

    def test_effect_tuned_with_string_value(self) -> None:
        payload = EffectTunedPayload(clip_id="c1", effect_id="e1", param="mode", value="dark")
        self.assertEqual(payload.value, "dark")

    def test_effect_tuned_with_nested_dict_value(self) -> None:
        payload = EffectTunedPayload(clip_id="c1", effect_id="e1", param="config", value={"a": 1, "b": [2, 3]})
        self.assertEqual(payload.value, {"a": 1, "b": [2, 3]})

    def test_effect_tuned_rejects_empty_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectTunedPayload(clip_id="", effect_id="e1", param="p", value=1)

    def test_effect_tuned_rejects_empty_effect_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectTunedPayload(clip_id="c1", effect_id="", param="p", value=1)

    def test_effect_tuned_rejects_empty_param(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectTunedPayload(clip_id="c1", effect_id="e1", param="", value=1)

    def test_effect_tuned_rejects_unjsonable_value(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            EffectTunedPayload(clip_id="c1", effect_id="e1", param="p", value=object())

    # ------------------------------------------------------------------
    # ThemeSetPayload
    # ------------------------------------------------------------------

    def test_theme_set_payload_validates(self) -> None:
        payload = ThemeSetPayload(theme_id="theme-01")
        self.assertEqual(payload.to_json_obj(), {"theme_id": "theme-01"})

    def test_theme_set_rejects_empty_theme_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ThemeSetPayload(theme_id="")
        with self.assertRaises(TimelineEventSchemaError):
            ThemeSetPayload(theme_id="  ")

    # ------------------------------------------------------------------
    # ThemeOverriddenPayload
    # ------------------------------------------------------------------

    def test_theme_overridden_payload_validates(self) -> None:
        payload = ThemeOverriddenPayload(override_id="visual.brightness", value=0.8)
        obj = payload.to_json_obj()
        self.assertEqual(obj["override_id"], "visual.brightness")
        self.assertEqual(obj["value"], 0.8)

    def test_theme_overridden_with_dict_value(self) -> None:
        payload = ThemeOverriddenPayload(override_id="generation.style", value={"mood": "cinematic"})
        self.assertEqual(payload.value, {"mood": "cinematic"})

    def test_theme_overridden_rejects_empty_override_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ThemeOverriddenPayload(override_id="", value="v")

    def test_theme_overridden_rejects_unjsonable_value(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ThemeOverriddenPayload(override_id="visual", value=object())

    # ------------------------------------------------------------------
    # TrackAddedPayload
    # ------------------------------------------------------------------

    def test_track_added_payload_validates(self) -> None:
        payload = TrackAddedPayload(track_id="trk-1", kind="visual")
        self.assertEqual(payload.to_json_obj(), {"track_id": "trk-1", "kind": "visual"})

    def test_track_added_with_label(self) -> None:
        payload = TrackAddedPayload(track_id="trk-1", kind="audio", label="music")
        obj = payload.to_json_obj()
        self.assertEqual(obj["kind"], "audio")
        self.assertEqual(obj["label"], "music")

    def test_track_added_rejects_empty_track_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(track_id="", kind="visual")

    def test_track_added_rejects_invalid_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(track_id="trk-1", kind="caption")  # type: ignore[arg-type]

    def test_track_added_rejects_empty_label(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(track_id="trk-1", kind="visual", label="")

    # ------------------------------------------------------------------
    # TrackRemovedPayload
    # ------------------------------------------------------------------

    def test_track_removed_payload_validates(self) -> None:
        payload = TrackRemovedPayload(track_id="trk-1")
        self.assertEqual(payload.to_json_obj(), {"track_id": "trk-1"})

    def test_track_removed_rejects_empty_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackRemovedPayload(track_id="")

    # ------------------------------------------------------------------
    # AudioBoundPayload
    # ------------------------------------------------------------------

    def test_audio_bound_payload_validates(self) -> None:
        payload = AudioBoundPayload(clip_id="c1", asset_id="asset-music")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1", "asset_id": "asset-music"})

    def test_audio_bound_rejects_empty_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            AudioBoundPayload(clip_id="", asset_id="a1")

    def test_audio_bound_rejects_empty_asset_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            AudioBoundPayload(clip_id="c1", asset_id="")

    # ------------------------------------------------------------------
    # AudioUnboundPayload
    # ------------------------------------------------------------------

    def test_audio_unbound_payload_validates(self) -> None:
        payload = AudioUnboundPayload(clip_id="c1")
        self.assertEqual(payload.to_json_obj(), {"clip_id": "c1"})

    def test_audio_unbound_rejects_empty_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            AudioUnboundPayload(clip_id="")

    # ------------------------------------------------------------------
    # PoolAssetAddedPayload
    # ------------------------------------------------------------------

    def test_pool_asset_added_payload_validates(self) -> None:
        payload = PoolAssetAddedPayload(asset_id="asset-1")
        self.assertEqual(payload.to_json_obj(), {"asset_id": "asset-1"})

    def test_pool_asset_added_rejects_empty_asset_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            PoolAssetAddedPayload(asset_id="")

    # ------------------------------------------------------------------
    # PoolAssetRemovedPayload
    # ------------------------------------------------------------------

    def test_pool_asset_removed_payload_validates(self) -> None:
        payload = PoolAssetRemovedPayload(asset_id="asset-1")
        self.assertEqual(payload.to_json_obj(), {"asset_id": "asset-1"})

    def test_pool_asset_removed_rejects_empty_asset_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            PoolAssetRemovedPayload(asset_id="")

    # ------------------------------------------------------------------
    # PoolAssetScoredPayload
    # ------------------------------------------------------------------

    def test_pool_asset_scored_payload_validates(self) -> None:
        payload = PoolAssetScoredPayload(asset_id="asset-1", score=0.75)
        obj = payload.to_json_obj()
        self.assertEqual(obj["asset_id"], "asset-1")
        self.assertEqual(obj["score"], 0.75)

    def test_pool_asset_scored_accepts_boundaries(self) -> None:
        p0 = PoolAssetScoredPayload(asset_id="a", score=0.0)
        self.assertEqual(p0.score, 0.0)
        p1 = PoolAssetScoredPayload(asset_id="a", score=1.0)
        self.assertEqual(p1.score, 1.0)

    def test_pool_asset_scored_rejects_empty_asset_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            PoolAssetScoredPayload(asset_id="", score=0.5)

    def test_pool_asset_scored_rejects_out_of_range(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            PoolAssetScoredPayload(asset_id="a", score=-0.1)
        with self.assertRaises(TimelineEventSchemaError):
            PoolAssetScoredPayload(asset_id="a", score=1.1)

    def test_pool_asset_scored_rejects_bool_score(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            PoolAssetScoredPayload(asset_id="a", score=True)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # ArrangementReplacedPayload
    # ------------------------------------------------------------------

    def test_arrangement_replaced_payload_validates(self) -> None:
        arr = {"clips": [{"id": "c1", "start": 0, "duration": 5}]}
        payload = ArrangementReplacedPayload(arrangement=arr)
        obj = payload.to_json_obj()
        self.assertEqual(obj["arrangement"], arr)

    def test_arrangement_replaced_rejects_non_dict(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ArrangementReplacedPayload(arrangement="not-a-dict")  # type: ignore[arg-type]

    def test_arrangement_replaced_rejects_unjsonable_nested(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ArrangementReplacedPayload(arrangement={"bad": object()})  # type: ignore[dict-item]

    # ------------------------------------------------------------------
    # All secondary event kinds round-trip through TimelineEvent
    # ------------------------------------------------------------------

    def test_secondary_event_round_trip_all_kinds(self) -> None:
        """Every m3 kind round-trips through TimelineEvent.new() → to_json_obj() → TimelineEvent.from_dict()."""
        actor = TimelineActor(type="agent", id="tester")
        tid = str(uuid4())

        cases: list[tuple[str, Any]] = [
            ("transition.set", TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="cross-fade", duration_seconds=1.5)),
            ("transition.removed", TransitionRemovedPayload(left_clip_id="a", right_clip_id="b")),
            ("effect.added", EffectAddedPayload(clip_id="c1", effect_id="e1")),
            ("effect.removed", EffectRemovedPayload(clip_id="c1", effect_id="e1")),
            ("effect.tuned", EffectTunedPayload(clip_id="c1", effect_id="e1", param="blur", value=5)),
            ("theme.set", ThemeSetPayload(theme_id="theme-01")),
            ("theme.overridden", ThemeOverriddenPayload(override_id="visual.brightness", value=0.8)),
            ("track.added", TrackAddedPayload(track_id="trk-1", kind="visual")),
            ("track.removed", TrackRemovedPayload(track_id="trk-1")),
            ("audio.bound", AudioBoundPayload(clip_id="c1", asset_id="a1")),
            ("audio.unbound", AudioUnboundPayload(clip_id="c1")),
            ("pool.asset_added", PoolAssetAddedPayload(asset_id="asset-1")),
            ("pool.asset_removed", PoolAssetRemovedPayload(asset_id="asset-1")),
            ("pool.asset_scored", PoolAssetScoredPayload(asset_id="asset-1", score=0.5)),
            ("arrangement.replaced", ArrangementReplacedPayload(arrangement={"clips": []})),
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

    def test_secondary_event_from_dict_coercion(self) -> None:
        """Payloads coerced from raw dicts via TimelineEvent.from_dict()."""
        actor = TimelineActor(type="system", id="sys")
        tid = str(uuid4())

        # transition.set from dict
        event = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="transition.set",
            payload={"left_clip_id": "a", "right_clip_id": "b", "kind": "wipe", "duration_seconds": 2.0},
        )
        self.assertIsInstance(event.payload, TransitionSetPayload)
        p = event.payload
        assert isinstance(p, TransitionSetPayload)
        self.assertEqual(p.left_clip_id, "a")
        self.assertEqual(p.kind, "wipe")
        self.assertEqual(p.duration_seconds, 2.0)

        # effect.added from dict with params
        event2 = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="effect.added",
            payload={"clip_id": "c1", "effect_id": "e1", "params": {"blur": 5}},
        )
        self.assertIsInstance(event2.payload, EffectAddedPayload)
        p2 = event2.payload
        assert isinstance(p2, EffectAddedPayload)
        self.assertEqual(p2.params, {"blur": 5})

        # track.added from dict
        event3 = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="track.added",
            payload={"track_id": "trk-1", "kind": "audio", "label": "music"},
        )
        self.assertIsInstance(event3.payload, TrackAddedPayload)
        p3 = event3.payload
        assert isinstance(p3, TrackAddedPayload)
        self.assertEqual(p3.kind, "audio")
        self.assertEqual(p3.label, "music")

        # pool.asset_scored from dict
        event4 = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="pool.asset_scored",
            payload={"asset_id": "a1", "score": 0.9},
        )
        self.assertIsInstance(event4.payload, PoolAssetScoredPayload)
        p4 = event4.payload
        assert isinstance(p4, PoolAssetScoredPayload)
        self.assertEqual(p4.score, 0.9)

        # arrangement.replaced from dict
        event5 = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="arrangement.replaced",
            payload={"arrangement": {"clips": [{"id": "x"}]}},
        )
        self.assertIsInstance(event5.payload, ArrangementReplacedPayload)
        p5 = event5.payload
        assert isinstance(p5, ArrangementReplacedPayload)
        self.assertEqual(p5.arrangement, {"clips": [{"id": "x"}]})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
