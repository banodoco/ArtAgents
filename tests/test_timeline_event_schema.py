from __future__ import annotations

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
        backend = SupabaseBackend(timeline_id=str(uuid4()))

        self.assertEqual(backend.backend_name(), "supabase")

        with self.assertRaises(TimelineEventSchemaError):
            TimelineActor(type="agent", id="")

        with self.assertRaises(EventLogNotImplementedError):
            backend.append_event(
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
