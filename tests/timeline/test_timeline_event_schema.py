from __future__ import annotations

import json
import unittest
from uuid import uuid4

from astrid.core.timeline.eventlog import (
    LocalFsBackend,
    SupabaseBackend,
    build_timeline_backend,
    select_timeline_backend,
    select_timeline_stream,
)
from astrid.core.timeline.eventlog.types import (
    EventLogAuthRequiredError,
    EventLogMissingConfigError,
    EventLogUnsupportedRpcError,
    SupabaseEventLogOptions,
)
from astrid.core.timeline.events.schema import (
    EVENT_SCHEMA_VERSION,
    ArrangementReplacedPayload,
    AssetRegistryReplacedPayload,
    AudioBoundPayload,
    AudioUnboundPayload,
    ClipAddedPayload,
    ClipAnnotatedPayload,
    ClipMovedPayload,
    ClipPosition,
    ClipRemovedPayload,
    ClipReplacedPayload,
    ClipRetimedPayload,
    ClipRetrackedPayload,
    ClipSwappedPayload,
    ClipTextSetPayload,
    EffectAddedPayload,
    EffectRemovedPayload,
    EffectTunedPayload,
    ErasedPayload,
    PoolAssetAddedPayload,
    PoolAssetRemovedPayload,
    PoolAssetScoredPayload,
    ThemeOverriddenPayload,
    ThemeSetPayload,
    TimelineActor,
    TimelineBranchedFromPayload,
    TimelineConfigReplacedPayload,
    TimelineCreatedPayload,
    TimelineErasedPayload,
    TimelineEvent,
    TimelineEventSchemaError,
    TimelineImportedPayload,
    TimelineRecoveredPayload,
    TimelineRenamedPayload,
    TimelineRevertedPayload,
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
    class _FakeSupabaseTransport:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def append_event(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(("append_event", dict(kwargs)))
            actor = kwargs["actor"]
            assert isinstance(actor, TimelineActor)
            return {
                "schema_version": EVENT_SCHEMA_VERSION,
                "event_id": generate_event_ulid(),
                "timeline_id": kwargs["timeline_id"],
                "kind": kwargs["kind"],
                "ts": "2026-05-21T00:00:00Z",
                "actor": actor.to_json_obj(),
                "payload": kwargs["payload"],
                "prev_hash": None,
                "hash": "abc123",
                "txn_id": kwargs.get("txn_id"),
            }

        def append_imported_event(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(("append_imported_event", dict(kwargs)))
            source = kwargs["source_event"]
            assert isinstance(source, TimelineEvent)
            actor_raw = kwargs["actor"]
            return {
                "schema_version": EVENT_SCHEMA_VERSION,
                "event_id": generate_event_ulid(),
                "timeline_id": kwargs["timeline_id"],
                "kind": source.kind,
                "ts": "2026-05-21T00:00:00Z",
                "actor": actor_raw.to_json_obj() if hasattr(actor_raw, "to_json_obj") else actor_raw,
                "payload": source.payload.to_json_obj() if hasattr(source.payload, "to_json_obj") else dict(source.payload),
                "prev_hash": None,
                "hash": "def456",
                "source_backend": source.source_backend or "unknown",
                "source_timeline_id": source.timeline_id,
                "source_event_id": source.event_id,
                "source_version": source.source_version,
                "source_hash": source.hash,
                "txn_id": kwargs.get("txn_id"),
            }

        def read_events(self, **kwargs: object) -> list[dict[str, object]]:
            self.calls.append(("read_events", dict(kwargs)))
            return []

        def head(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(("head", dict(kwargs)))
            return {
                "timeline_id": kwargs["timeline_id"],
                "last_event_id": None,
                "last_hash": None,
                "event_count": 0,
                "version": 0,
            }

        def verify_chain(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(("verify_chain", dict(kwargs)))
            return {"ok": True, "checked_events": 0, "last_event_id": None, "error": None}

        def repair_erasure(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(("repair_erasure", dict(kwargs)))
            return {
                "replaced_count": 0,
                "downstream_count": 0,
                "head_event_count": 0,
                "head_version": 0,
                "last_event_id": None,
                "last_hash": None,
            }

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

    def test_timeline_backend_selector_builds_supabase_backend_from_options(self) -> None:
        timeline_id = str(uuid4())
        options = SupabaseEventLogOptions(
            url="https://example.supabase.co",
            auth_token="pat-token",
            verified_subject="user-1",
            actor_id="agent:codex",
            actor_display="Codex",
            rpc_append_name="append_timeline_event_v2",
        )
        stream, backend = select_timeline_backend(
            timeline_id=timeline_id,
            timeline_home="/tmp/timeline-home",
            preferred_backend="supabase",
            supabase_options=options,
        )
        self.assertEqual(stream.backend, "supabase")
        self.assertEqual(stream.source, "preferred_backend")
        self.assertEqual(stream.supabase_options, options)
        self.assertIsInstance(backend, SupabaseBackend)
        self.assertEqual(backend.backend_name(), "supabase")
        self.assertEqual(backend.supabase_url, "https://example.supabase.co")
        self.assertEqual(backend.auth_token, "pat-token")
        self.assertEqual(backend.verified_subject, "user-1")
        self.assertEqual(backend.actor_id, "agent:codex")
        self.assertEqual(backend.actor_display, "Codex")
        self.assertEqual(backend.rpc_append_name, "append_timeline_event_v2")
        self.assertTrue(backend.enabled)

    def test_build_timeline_backend_preserves_full_supabase_options_payload(self) -> None:
        options = SupabaseEventLogOptions(
            url="https://example.supabase.co",
            auth_token="pat-token",
            verified_subject="user-1",
            actor_id="agent:codex",
            actor_display="Codex",
            rpc_append_name="append_timeline_event_v2",
        )
        stream = select_timeline_stream(
            timeline_id=str(uuid4()),
            preferred_backend="supabase",
            supabase_options=options,
        )

        backend = build_timeline_backend(stream)

        assert isinstance(backend, SupabaseBackend)
        self.assertEqual(backend.supabase_url, options.url)
        self.assertEqual(backend.auth_token, options.auth_token)
        self.assertEqual(backend.verified_subject, options.verified_subject)
        self.assertEqual(backend.actor_id, options.actor_id)
        self.assertEqual(backend.actor_display, options.actor_display)
        self.assertEqual(backend.rpc_append_name, options.rpc_append_name)

    def test_supabase_backend_missing_config_raises_typed_errors(self) -> None:
        tid = str(uuid4())
        backend = SupabaseBackend(timeline_id=tid)

        self.assertEqual(backend.backend_name(), "supabase")

        with self.assertRaises(TimelineEventSchemaError):
            TimelineActor(type="agent", id="")

        with self.assertRaises(EventLogMissingConfigError):
            backend.append_event(
                tid,
                "timeline.renamed",
                {"old_slug": "before", "new_slug": "after"},
                actor=TimelineActor(type="agent", id="codex:run-1"),
            )

        with self.assertRaises(EventLogMissingConfigError):
            backend.read_events()

        with self.assertRaises(EventLogMissingConfigError):
            backend.head()

        with self.assertRaises(EventLogMissingConfigError):
            backend.verify_chain()

    def test_supabase_backend_without_transport_raises_typed_unsupported_rpc(self) -> None:
        tid = str(uuid4())
        backend = SupabaseBackend(
            timeline_id=tid,
            supabase_url="https://example.supabase.co",
            auth_token="pat-token",
            enabled=True,
        )
        with self.assertRaises(EventLogUnsupportedRpcError):
            backend.head()

    def test_supabase_backend_mocked_transport_supports_append_read_head_and_verify(self) -> None:
        tid = str(uuid4())
        transport = self._FakeSupabaseTransport()
        backend = SupabaseBackend(
            timeline_id=tid,
            transport=transport,
            verified_subject="user-1",
        )

        event = backend.append_event(
            tid,
            "timeline.renamed",
            {"old_slug": "before", "new_slug": "after"},
            actor=TimelineActor(type="human", id="user-1", display="Maker"),
            txn_id=generate_event_ulid(),
        )

        self.assertIsInstance(event, TimelineEvent)
        self.assertEqual(event.kind, "timeline.renamed")
        self.assertEqual(backend.read_events(), [])
        self.assertEqual(backend.head().event_count, 0)
        self.assertTrue(backend.verify_chain().ok)
        self.assertEqual(
            [name for name, _kwargs in transport.calls],
            ["append_event", "read_events", "head", "verify_chain"],
        )

    def test_supabase_backend_rejects_unverified_human_writes(self) -> None:
        tid = str(uuid4())
        backend = SupabaseBackend(timeline_id=tid, transport=self._FakeSupabaseTransport())
        with self.assertRaises(EventLogAuthRequiredError):
            backend.append_event(
                tid,
                "timeline.renamed",
                {"old_slug": "before", "new_slug": "after"},
                actor=TimelineActor(type="human", id="user-2", display="Maker"),
            )


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
            track_id="visual",
            position=ClipPosition(mode="index", index=0),
        )
        self.assertEqual(payload.clip_id, "clip-1")
        self.assertEqual(payload.kind, "visual")
        self.assertEqual(payload.asset_id, "asset-1")
        self.assertEqual(payload.track_id, "visual")
        obj = payload.to_json_obj()
        self.assertEqual(obj["clip_id"], "clip-1")
        self.assertEqual(obj["kind"], "visual")
        self.assertEqual(obj["track_id"], "visual")
        self.assertEqual(obj["position"], {"mode": "index", "index": 0})

    def test_clip_added_payload_accepts_explicit_track_id(self) -> None:
        payload = ClipAddedPayload(
            clip_id="clip-1",
            kind="text",
            asset_id="asset-1",
            track_id="captions",
        )
        self.assertEqual(payload.to_json_obj()["track_id"], "captions")

    def test_clip_added_rejects_empty_track_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a", track_id="")

    def test_clip_added_payload_position_from_dict(self) -> None:
        payload = ClipAddedPayload(
            clip_id="clip-2",
            kind="audio",
            asset_id="asset-2",
            track_id="audio",
            position={"mode": "after", "ref_clip_id": "c0"},
        )
        self.assertIsInstance(payload.position, ClipPosition)
        self.assertEqual(payload.position.mode, "after")

    def test_clip_added_rejects_empty_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="", kind="visual", asset_id="a", track_id="visual")

    def test_clip_added_rejects_invalid_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="c1", kind="invalid", asset_id="a", track_id="visual")  # type: ignore[arg-type]

    def test_clip_added_rejects_empty_asset_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ClipAddedPayload(clip_id="c1", kind="visual", asset_id="", track_id="visual")

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
            ("clip.added", ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1", track_id="visual")),
            ("clip.removed", ClipRemovedPayload(clip_id="c1")),
            ("clip.moved", ClipMovedPayload(clip_id="c1", position=ClipPosition(mode="index", index=0))),
            ("clip.retracked", ClipRetrackedPayload(clip_id="c1", track_id="v2")),
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

    def test_transition_set_payload_canonicalizes_alias_kind(self) -> None:
        payload = TransitionSetPayload(
            left_clip_id="clip-a",
            right_clip_id="clip-b",
            kind="crossfade",
            duration_seconds=2.5,
        )
        self.assertEqual(payload.kind, "cross-fade")

    def test_transition_set_rejects_empty_left_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="", right_clip_id="b", kind="cross-fade", duration_seconds=1.0)

    def test_transition_set_rejects_empty_right_clip_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="", kind="cross-fade", duration_seconds=1.0)

    def test_transition_set_rejects_empty_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="", duration_seconds=1.0)

    def test_transition_set_rejects_unknown_kind(self) -> None:
        with self.assertRaisesRegex(TimelineEventSchemaError, "transition kind must be one of"):
            TransitionSetPayload(left_clip_id="a", right_clip_id="b", kind="wipe", duration_seconds=1.0)

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
        payload = TrackAddedPayload(track_id="trk-1", kind="visual", label="Track")
        self.assertEqual(
            payload.to_json_obj(),
            {"track_id": "trk-1", "kind": "visual", "label": "Track"},
        )

    def test_track_added_with_label(self) -> None:
        payload = TrackAddedPayload(track_id="trk-1", kind="audio", label="music")
        obj = payload.to_json_obj()
        self.assertEqual(obj["kind"], "audio")
        self.assertEqual(obj["label"], "music")

    def test_track_added_rejects_empty_track_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(track_id="", kind="visual", label="Track")

    def test_track_added_rejects_invalid_kind(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TrackAddedPayload(track_id="trk-1", kind="caption", label="Track")  # type: ignore[arg-type]

    def test_track_added_rejects_missing_label_from_runtime_dict(self) -> None:
        with self.assertRaises(TypeError):
            TrackAddedPayload(track_id="trk-1", kind="visual")  # type: ignore[call-arg]

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
            ("track.added", TrackAddedPayload(track_id="trk-1", kind="visual", label="Track")),
            ("track.removed", TrackRemovedPayload(track_id="trk-1")),
            ("audio.bound", AudioBoundPayload(clip_id="c1", asset_id="a1")),
            ("audio.unbound", AudioUnboundPayload(clip_id="c1")),
            ("pool.asset_added", PoolAssetAddedPayload(asset_id="asset-1")),
            ("pool.asset_removed", PoolAssetRemovedPayload(asset_id="asset-1")),
            ("pool.asset_scored", PoolAssetScoredPayload(asset_id="asset-1", score=0.5)),
            ("arrangement.replaced", ArrangementReplacedPayload(arrangement={"clips": []})),
            ("timeline.config_replaced", TimelineConfigReplacedPayload(config={"tracks": [], "clips": []})),
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
            payload={"left_clip_id": "a", "right_clip_id": "b", "kind": "crossfade", "duration_seconds": 2.0},
        )
        self.assertIsInstance(event.payload, TransitionSetPayload)
        p = event.payload
        assert isinstance(p, TransitionSetPayload)
        self.assertEqual(p.left_clip_id, "a")
        self.assertEqual(p.kind, "cross-fade")
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

        # timeline.config_replaced from dict
        event6 = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="timeline.config_replaced",
            payload={"config": {"tracks": [], "clips": []}},
        )
        self.assertIsInstance(event6.payload, TimelineConfigReplacedPayload)
        p6 = event6.payload
        assert isinstance(p6, TimelineConfigReplacedPayload)
        self.assertEqual(p6.config, {"tracks": [], "clips": []})

        # timeline.asset_registry_replaced from dict
        event7 = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-20T12:00:00Z",
            actor=actor,
            kind="timeline.asset_registry_replaced",
            payload={"registry": {"assets": {"a1": {"file": "a.mp4"}}}, "source": "editor_save"},
        )
        self.assertIsInstance(event7.payload, AssetRegistryReplacedPayload)
        p7 = event7.payload
        assert isinstance(p7, AssetRegistryReplacedPayload)
        self.assertEqual(p7.registry, {"assets": {"a1": {"file": "a.mp4"}}})
        self.assertEqual(p7.source, "editor_save")


class RecoveryAndErasureSchemaTest(unittest.TestCase):
    """Validate new recovery/lifecycle/erasure event kinds and ErasedPayload envelope."""

    def setUp(self) -> None:
        self.actor = TimelineActor(type="system", id="migration:m9")
        self.tid = str(uuid4())

    # ------------------------------------------------------------------
    # ErasedPayload direct construction and validation
    # ------------------------------------------------------------------

    def test_erased_payload_constructs_with_required_fields(self) -> None:
        p = ErasedPayload(
            erased=True,
            reason="gdpr-request",
            erased_at="2026-05-21T12:00:00Z",
            erased_by="agent:codex",
        )
        self.assertTrue(p.erased)
        self.assertEqual(p.reason, "gdpr-request")
        self.assertEqual(p.erased_at, "2026-05-21T12:00:00Z")
        self.assertEqual(p.erased_by, "agent:codex")
        self.assertIsNone(p.policy_ref)

    def test_erased_payload_with_policy_ref(self) -> None:
        p = ErasedPayload(
            erased=True,
            reason="compliance",
            erased_at="2026-05-21T12:00:00Z",
            erased_by="system:auto",
            policy_ref="POL-001",
        )
        self.assertEqual(p.policy_ref, "POL-001")

    def test_erased_payload_to_json(self) -> None:
        p = ErasedPayload(
            erased=True,
            reason="gdpr-request",
            erased_at="2026-05-21T12:00:00Z",
            erased_by="agent:codex",
        )
        obj = p.to_json_obj()
        self.assertEqual(obj["erased"], True)
        self.assertEqual(obj["reason"], "gdpr-request")
        self.assertEqual(obj["erased_at"], "2026-05-21T12:00:00Z")
        self.assertEqual(obj["erased_by"], "agent:codex")
        self.assertNotIn("policy_ref", obj)

    def test_erased_payload_to_json_with_policy_ref(self) -> None:
        p = ErasedPayload(
            erased=True,
            reason="compliance",
            erased_at="2026-05-21T12:00:00Z",
            erased_by="system:auto",
            policy_ref="POL-001",
        )
        obj = p.to_json_obj()
        self.assertEqual(obj["policy_ref"], "POL-001")

    def test_erased_payload_rejects_false_erased(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ErasedPayload(erased=False, reason="x", erased_at="t", erased_by="y")  # type: ignore[arg-type]

    def test_erased_payload_rejects_empty_reason(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ErasedPayload(erased=True, reason="", erased_at="t", erased_by="y")

    def test_erased_payload_rejects_empty_erased_at(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ErasedPayload(erased=True, reason="x", erased_at="", erased_by="y")

    def test_erased_payload_rejects_empty_erased_by(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ErasedPayload(erased=True, reason="x", erased_at="t", erased_by="")

    def test_erased_payload_rejects_empty_policy_ref(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            ErasedPayload(erased=True, reason="x", erased_at="t", erased_by="y", policy_ref="")

    # ------------------------------------------------------------------
    # ErasedPayload accepted by TimelineEvent.from_dict() for any event kind
    # ------------------------------------------------------------------

    def test_erased_envelope_parses_for_strict_domain_kind_clip_added(self) -> None:
        """Erased clip.added event round-trips through from_dict."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "clip.added",
            "payload": {
                "erased": True,
                "reason": "gdpr-request",
                "erased_at": "2026-05-21T12:00:00Z",
                "erased_by": "agent:codex",
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        event = TimelineEvent.from_dict(raw)
        self.assertEqual(event.kind, "clip.added")
        self.assertIsInstance(event.payload, ErasedPayload)
        p = event.payload
        assert isinstance(p, ErasedPayload)
        self.assertTrue(p.erased)
        self.assertEqual(p.reason, "gdpr-request")

    def test_erased_envelope_parses_for_transition_set(self) -> None:
        """Erased transition.set event round-trips through from_dict."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "transition.set",
            "payload": {
                "erased": True,
                "reason": "policy-violation",
                "erased_at": "2026-05-21T13:00:00Z",
                "erased_by": "human:admin",
                "policy_ref": "POL-002",
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        event = TimelineEvent.from_dict(raw)
        self.assertEqual(event.kind, "transition.set")
        self.assertIsInstance(event.payload, ErasedPayload)

    def test_erased_envelope_parses_for_unknown_kind(self) -> None:
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "completely.unknown.future.kind",
            "payload": {
                "erased": True,
                "reason": "policy-violation",
                "erased_at": "2026-05-21T13:00:00Z",
                "erased_by": "human:admin",
            },
            "schema_version": 1,
        }
        event = TimelineEvent.from_dict(raw)
        self.assertEqual(event.kind, "completely.unknown.future.kind")
        self.assertIsInstance(event.payload, ErasedPayload)

    def test_erased_envelope_parses_for_arrangement_replaced(self) -> None:
        """Erased arrangement.replaced event round-trips through from_dict."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "arrangement.replaced",
            "payload": {
                "erased": True,
                "reason": "cleanup",
                "erased_at": "2026-05-21T14:00:00Z",
                "erased_by": "system:sweep",
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        event = TimelineEvent.from_dict(raw)
        self.assertEqual(event.kind, "arrangement.replaced")
        self.assertIsInstance(event.payload, ErasedPayload)

    def test_erased_envelope_round_trips_through_canonical_json(self) -> None:
        """Erased event survives canonical_json_text → from_dict round-trip."""
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="clip.added",
            payload=ErasedPayload(
                erased=True,
                reason="gdpr-request",
                erased_at="2026-05-21T12:00:00Z",
                erased_by="agent:codex",
            ),
        )
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.kind, "clip.added")
        self.assertIsInstance(restored.payload, ErasedPayload)
        p = restored.payload
        assert isinstance(p, ErasedPayload)
        self.assertEqual(p.reason, "gdpr-request")

    # ------------------------------------------------------------------
    # Reject mixed erased-plus-domain payloads
    # ------------------------------------------------------------------

    def test_rejects_mixed_erased_and_domain_fields(self) -> None:
        """Payload with both erased:true and domain fields like clip_id must fail."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "clip.added",
            "payload": {
                "erased": True,
                "reason": "bad",
                "erased_at": "t",
                "erased_by": "x",
                "clip_id": "c1",  # domain field mixed in
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.from_dict(raw)

    def test_rejects_mixed_erased_and_domain_fields_transition(self) -> None:
        """Mixed payload for transition.set must also fail."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "transition.set",
            "payload": {
                "erased": True,
                "reason": "bad",
                "erased_at": "t",
                "erased_by": "x",
                "left_clip_id": "a",  # domain field mixed in
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.from_dict(raw)

    def test_rejects_malformed_erased_missing_reason(self) -> None:
        """Erased payload missing required 'reason' field must fail."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "clip.added",
            "payload": {
                "erased": True,
                # reason missing
                "erased_at": "2026-05-21T12:00:00Z",
                "erased_by": "agent:codex",
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        with self.assertRaises((TimelineEventSchemaError, KeyError)):
            TimelineEvent.from_dict(raw)

    def test_rejects_malformed_erased_missing_erased_at(self) -> None:
        """Erased payload missing required 'erased_at' field must fail."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "clip.added",
            "payload": {
                "erased": True,
                "reason": "gdpr",
                # erased_at missing
                "erased_by": "agent:codex",
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        with self.assertRaises((TimelineEventSchemaError, KeyError)):
            TimelineEvent.from_dict(raw)

    def test_rejects_malformed_erased_missing_erased_by(self) -> None:
        """Erased payload missing required 'erased_by' field must fail."""
        raw = {
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "clip.added",
            "payload": {
                "erased": True,
                "reason": "gdpr",
                "erased_at": "2026-05-21T12:00:00Z",
                # erased_by missing
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        }
        with self.assertRaises((TimelineEventSchemaError, KeyError)):
            TimelineEvent.from_dict(raw)

    # ------------------------------------------------------------------
    # timeline.erased audit event
    # ------------------------------------------------------------------

    def test_timeline_erased_payload_constructs_and_serialises(self) -> None:
        p = TimelineErasedPayload(
            selector_summary={"kind_filter": ["clip.added"], "count": 3},
            reason="gdpr-request",
            affected_count=3,
            affected_event_ids=["E1", "E2", "E3"],
        )
        obj = p.to_json_obj()
        self.assertEqual(obj["reason"], "gdpr-request")
        self.assertEqual(obj["affected_count"], 3)
        self.assertEqual(obj["affected_event_ids"], ["E1", "E2", "E3"])

    def test_timeline_erased_event_round_trips(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.erased",
            payload=TimelineErasedPayload(
                selector_summary={"kind_filter": ["clip.added"]},
                reason="gdpr-request",
                affected_count=1,
            ),
        )
        self.assertEqual(event.kind, "timeline.erased")
        self.assertIsInstance(event.payload, TimelineErasedPayload)
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.kind, "timeline.erased")
        self.assertIsInstance(restored.payload, TimelineErasedPayload)

    def test_timeline_erased_rejects_negative_affected_count(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineErasedPayload(
                selector_summary={},
                reason="x",
                affected_count=-1,
            )

    def test_timeline_erased_rejects_bool_affected_count(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineErasedPayload(
                selector_summary={},
                reason="x",
                affected_count=True,  # type: ignore[arg-type]
            )

    def test_timeline_erased_rejects_empty_affected_event_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineErasedPayload(
                selector_summary={},
                reason="x",
                affected_count=1,
                affected_event_ids=[""],
            )

    # ------------------------------------------------------------------
    # timeline.config_replaced
    # ------------------------------------------------------------------

    def test_timeline_config_replaced_payload_validates_and_deep_copies(self) -> None:
        config = {
            "tracks": [{"id": "v1", "kind": "visual", "label": "Video"}],
            "clips": [],
        }
        payload = TimelineConfigReplacedPayload(config=config)
        payload.config["tracks"][0]["label"] = "Changed"

        self.assertEqual(config["tracks"][0]["label"], "Video")
        obj = payload.to_json_obj()
        obj["config"]["tracks"][0]["label"] = "Again"
        self.assertEqual(payload.config["tracks"][0]["label"], "Changed")

    def test_timeline_config_replaced_payload_serializes_optional_editor_save_source(self) -> None:
        payload = TimelineConfigReplacedPayload(
            config={"tracks": [], "clips": []},
            source="editor_save",
        )

        self.assertEqual(
            canonical_json_text(payload),
            '{"config":{"clips":[],"tracks":[]},"source":"editor_save"}',
        )

    def test_timeline_config_replaced_event_round_trips(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.config_replaced",
            payload=TimelineConfigReplacedPayload(
                config={"tracks": [], "clips": []},
                source="editor_save",
            ),
        )
        self.assertEqual(event.kind, "timeline.config_replaced")
        self.assertIsInstance(event.payload, TimelineConfigReplacedPayload)
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.kind, "timeline.config_replaced")
        self.assertIsInstance(restored.payload, TimelineConfigReplacedPayload)
        assert isinstance(restored.payload, TimelineConfigReplacedPayload)
        self.assertEqual(restored.payload.source, "editor_save")

    def test_timeline_config_replaced_legacy_event_without_source_still_round_trips(self) -> None:
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
            "schema_version": 2,
        }

        restored = TimelineEvent.from_dict(raw)

        self.assertIsInstance(restored.payload, TimelineConfigReplacedPayload)
        assert isinstance(restored.payload, TimelineConfigReplacedPayload)
        self.assertIsNone(restored.payload.source)
        self.assertEqual(restored.to_json_obj()["payload"], {"config": {"tracks": [], "clips": []}})

    def test_timeline_config_replaced_preserves_editor_save_source(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.config_replaced",
            payload={
                "config": {"tracks": [], "clips": []},
                "source": "editor_save",
            },
        )

        self.assertIsInstance(event.payload, TimelineConfigReplacedPayload)
        assert isinstance(event.payload, TimelineConfigReplacedPayload)
        self.assertEqual(event.payload.source, "editor_save")
        restored = TimelineEvent.from_dict(event.to_json_obj())
        self.assertIsInstance(restored.payload, TimelineConfigReplacedPayload)
        assert isinstance(restored.payload, TimelineConfigReplacedPayload)
        self.assertEqual(restored.payload.source, "editor_save")

    def test_timeline_asset_registry_replaced_preserves_editor_save_source(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.asset_registry_replaced",
            payload={
                "registry": {
                    "assets": {
                        "intro": {
                            "file": "intro.mp4",
                            "type": "video/mp4",
                        },
                    },
                },
                "source": "editor_save",
            },
        )

        self.assertEqual(event.kind, "timeline.asset_registry_replaced")
        restored = TimelineEvent.from_dict(event.to_json_obj())
        self.assertEqual(restored.kind, "timeline.asset_registry_replaced")
        self.assertEqual(restored.payload.to_json_obj()["source"], "editor_save")

    def test_from_dict_accepts_older_schema_version(self) -> None:
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
            "schema_version": 1,
        }

        restored = TimelineEvent.from_dict(raw)

        self.assertEqual(restored.schema_version, 1)
        self.assertIsInstance(restored.payload, TimelineConfigReplacedPayload)

    def test_from_dict_accepts_schema_version_zero(self) -> None:
        """Minimum valid schema_version (0) is accepted."""
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
            "schema_version": 0,
        }

        restored = TimelineEvent.from_dict(raw)

        self.assertEqual(restored.schema_version, 0)
        self.assertIsInstance(restored.payload, TimelineConfigReplacedPayload)

    def test_from_dict_accepts_current_schema_version(self) -> None:
        """Current EVENT_SCHEMA_VERSION is accepted."""
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
            "schema_version": EVENT_SCHEMA_VERSION,
        }

        restored = TimelineEvent.from_dict(raw)

        self.assertEqual(restored.schema_version, EVENT_SCHEMA_VERSION)
        self.assertIsInstance(restored.payload, TimelineConfigReplacedPayload)

    def test_from_dict_rejects_missing_schema_version(self) -> None:
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
        }

        with self.assertRaisesRegex(TimelineEventSchemaError, "schema_version must be an integer"):
            TimelineEvent.from_dict(raw)

    def test_from_dict_rejects_future_schema_version(self) -> None:
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
            "schema_version": EVENT_SCHEMA_VERSION + 1,
        }

        with self.assertRaisesRegex(
            TimelineEventSchemaError,
            rf"schema_version must be <= {EVENT_SCHEMA_VERSION}",
        ):
            TimelineEvent.from_dict(raw)

    def test_from_dict_rejects_non_integer_schema_version(self) -> None:
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "timeline.config_replaced",
            "payload": {"config": {"tracks": [], "clips": []}},
            "schema_version": "2",
        }

        with self.assertRaisesRegex(TimelineEventSchemaError, "schema_version must be an integer"):
            TimelineEvent.from_dict(raw)

    def test_from_dict_preserves_unknown_kind_raw_payload(self) -> None:
        raw_payload = {"surprise": {"nested": [1, 2, 3]}, "source": "db"}
        raw = {
            "event_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "completely.unknown.future.kind",
            "payload": raw_payload,
            "schema_version": 1,
        }

        restored = TimelineEvent.from_dict(raw)

        self.assertEqual(restored.kind, "completely.unknown.future.kind")
        self.assertEqual(restored.payload, raw_payload)
        self.assertIsNot(restored.payload, raw_payload)
        self.assertEqual(restored.to_json_obj()["payload"], raw_payload)

    def test_timeline_config_replaced_rejects_wrappers_and_legacy_keys(self) -> None:
        invalid_configs = [
            {"schema_version": 1, "assembly": {"tracks": [], "clips": []}},
            {"tracks": [], "clips": [], "pool": {"entries": []}},
            {"tracks": [], "clips": [], "arrangement": {"clips": []}},
        ]
        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(TimelineEventSchemaError):
                    TimelineConfigReplacedPayload(config=config)

    # ------------------------------------------------------------------
    # timeline.recovered
    # ------------------------------------------------------------------

    def test_timeline_recovered_payload_constructs_and_serialises(self) -> None:
        p = TimelineRecoveredPayload(
            anchor_event_id=generate_event_ulid(),
            anchor_type="event",
            reason="manual-repair",
        )
        obj = p.to_json_obj()
        self.assertEqual(obj["anchor_type"], "event")
        self.assertEqual(obj["reason"], "manual-repair")

    def test_timeline_recovered_event_round_trips(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.recovered",
            payload=TimelineRecoveredPayload(
                anchor_event_id=generate_event_ulid(),
                anchor_type="snapshot",
                reason="restore-from-checkpoint",
                projected_state_summary={"tracks": [], "clips": []},
            ),
        )
        self.assertEqual(event.kind, "timeline.recovered")
        self.assertIsInstance(event.payload, TimelineRecoveredPayload)
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.kind, "timeline.recovered")

    def test_timeline_recovered_rejects_invalid_anchor_type(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineRecoveredPayload(
                anchor_event_id=generate_event_ulid(),
                anchor_type="bad",  # type: ignore[arg-type]
                reason="x",
            )

    def test_timeline_recovered_rejects_empty_reason(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineRecoveredPayload(
                anchor_event_id=generate_event_ulid(),
                anchor_type="event",
                reason="",
            )

    def test_timeline_recovered_rejects_wrappers_and_legacy_configs(self) -> None:
        invalid_configs = [
            {},
            {"schema_version": 1, "assembly": {"tracks": [], "clips": []}},
            {"tracks": [], "clips": [], "pool": {"entries": []}},
            {"tracks": [], "clips": [], "arrangement": {"clips": []}},
            {"tracks": [], "clips": [{"id": "old", "kind": "visual", "asset_id": "a1"}]},
        ]
        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(TimelineEventSchemaError):
                    TimelineRecoveredPayload(
                        anchor_event_id=generate_event_ulid(),
                        anchor_type="event",
                        reason="bad-state",
                        projected_state_summary=config,
                    )

    # ------------------------------------------------------------------
    # timeline.reverted
    # ------------------------------------------------------------------

    def test_timeline_reverted_payload_constructs_and_serialises(self) -> None:
        p = TimelineRevertedPayload(
            target_event_id=generate_event_ulid(),
            reason="rollback",
        )
        obj = p.to_json_obj()
        self.assertEqual(obj["reason"], "rollback")

    def test_timeline_reverted_event_round_trips(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.reverted",
            payload=TimelineRevertedPayload(
                target_event_id=generate_event_ulid(),
                reason="undo-batch",
                before_projection={"clips": ["a"]},
                after_projection={"clips": []},
            ),
        )
        self.assertEqual(event.kind, "timeline.reverted")
        self.assertIsInstance(event.payload, TimelineRevertedPayload)
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.kind, "timeline.reverted")

    def test_timeline_reverted_rejects_empty_reason(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineRevertedPayload(
                target_event_id=generate_event_ulid(),
                reason="",
            )

    # ------------------------------------------------------------------
    # timeline.branched_from
    # ------------------------------------------------------------------

    def test_timeline_branched_from_payload_constructs_and_serialises(self) -> None:
        p = TimelineBranchedFromPayload(
            branch_timeline_id=str(uuid4()),
            anchor_event_id=generate_event_ulid(),
            reason="explore-variant",
        )
        obj = p.to_json_obj()
        self.assertEqual(obj["reason"], "explore-variant")

    def test_timeline_branched_from_event_round_trips(self) -> None:
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="timeline.branched_from",
            payload=TimelineBranchedFromPayload(
                branch_timeline_id=str(uuid4()),
                anchor_event_id=generate_event_ulid(),
            ),
        )
        self.assertEqual(event.kind, "timeline.branched_from")
        self.assertIsInstance(event.payload, TimelineBranchedFromPayload)
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.kind, "timeline.branched_from")

    def test_timeline_branched_from_rejects_invalid_branch_timeline_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineBranchedFromPayload(
                branch_timeline_id="not-a-uuid",
                anchor_event_id=generate_event_ulid(),
            )

    # ------------------------------------------------------------------
    # Import metadata fields
    # ------------------------------------------------------------------

    def test_timeline_event_with_import_metadata(self) -> None:
        """Import metadata fields serialize and deserialize correctly."""
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1", track_id="visual"),
            source_backend="supabase",
            source_timeline_id=str(uuid4()),
            source_event_id=generate_event_ulid(),
            source_version=42,
            source_hash="abc123def456",
        )
        self.assertEqual(event.source_backend, "supabase")
        self.assertEqual(event.source_version, 42)
        self.assertEqual(event.source_hash, "abc123def456")

        obj = event.to_json_obj()
        self.assertEqual(obj["source_backend"], "supabase")
        self.assertEqual(obj["source_version"], 42)
        self.assertEqual(obj["source_hash"], "abc123def456")

        # Round-trip through from_dict
        text = canonical_json_text(event, exclude_hash=True)
        restored = TimelineEvent.from_dict(json.loads(text))
        self.assertEqual(restored.source_backend, "supabase")
        self.assertEqual(restored.source_version, 42)
        self.assertEqual(restored.source_hash, "abc123def456")

    def test_timeline_event_without_import_metadata_omits_fields(self) -> None:
        """Import metadata fields are omitted from JSON when None."""
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1", track_id="visual"),
        )
        obj = event.to_json_obj()
        self.assertNotIn("source_backend", obj)
        self.assertNotIn("source_timeline_id", obj)
        self.assertNotIn("source_event_id", obj)
        self.assertNotIn("source_version", obj)
        self.assertNotIn("source_hash", obj)

    def test_import_metadata_rejects_empty_source_backend(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.new(
                timeline_id=self.tid,
                ts="2026-05-21T12:00:00Z",
                actor=self.actor,
                kind="clip.added",
                payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1", track_id="visual"),
                source_backend="",
            )

    def test_import_metadata_rejects_invalid_source_timeline_id(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.new(
                timeline_id=self.tid,
                ts="2026-05-21T12:00:00Z",
                actor=self.actor,
                kind="clip.added",
                payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1", track_id="visual"),
                source_timeline_id="not-a-uuid",
            )

    def test_import_metadata_rejects_bool_source_version(self) -> None:
        with self.assertRaises(TimelineEventSchemaError):
            TimelineEvent.new(
                timeline_id=self.tid,
                ts="2026-05-21T12:00:00Z",
                actor=self.actor,
                kind="clip.added",
                payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1", track_id="visual"),
                source_version=True,  # type: ignore[arg-type]
            )

    # ------------------------------------------------------------------
    # ErasedPayload as a raw dict also accepted by from_dict
    # ------------------------------------------------------------------

    def test_erased_payload_dict_coerced_via_new_factory(self) -> None:
        """TimelineEvent.new() with erased dict payload coerces to ErasedPayload."""
        event = TimelineEvent.new(
            timeline_id=self.tid,
            ts="2026-05-21T12:00:00Z",
            actor=self.actor,
            kind="clip.added",
            payload={
                "erased": True,
                "reason": "gdpr-request",
                "erased_at": "2026-05-21T12:00:00Z",
                "erased_by": "agent:codex",
            },
        )
        self.assertIsInstance(event.payload, ErasedPayload)

    def test_erased_payload_skips_kind_registration_check(self) -> None:
        """ErasedPayload events do not require the kind to be registered in _PAYLOAD_TYPES
        for the erased check, but the kind must still be registered for normal validation."""
        # An erased clip.added is fine because clip.added IS registered
        event = TimelineEvent.from_dict({
            "event_id": generate_event_ulid(),
            "timeline_id": self.tid,
            "ts": "2026-05-21T12:00:00Z",
            "actor": self.actor.to_json_obj(),
            "prev_hash": None,
            "hash": None,
            "kind": "clip.added",
            "payload": {
                "erased": True,
                "reason": "cleanup",
                "erased_at": "2026-05-21T12:00:00Z",
                "erased_by": "system:sweep",
            },
            "schema_version": EVENT_SCHEMA_VERSION,
        })
        self.assertIsInstance(event.payload, ErasedPayload)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
