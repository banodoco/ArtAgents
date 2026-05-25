"""Backend contract tests for timeline eventlog backends.

Exercises both ``LocalFsBackend`` and ``SupabaseBackend`` (with fake
in-memory transport) through the same contract surface:

- append_event → read_events round-trip
- head() accuracy
- verify_chain() integrity
- expected_version CAS enforcement
- post-deleted rejection
- tamper detection (fake transport only)
"""

from __future__ import annotations

import pytest

from astrid.core.timeline.eventlog.types import (
    EventLogError,
    EventLogStaleVersionError,
)
from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineConfigReplacedPayload,
    TimelineEvent,
)

# Shared actor for most tests
_ACTOR = TimelineActor(type="agent", id="codex:contract-test")


# ======================================================================
# LocalFsBackend contract tests
# ======================================================================


class TestLocalFsBackendContract:
    """Contract tests for LocalFsBackend."""

    def test_append_and_read_round_trip(self, local_fs_backend):
        """append_event → read_events returns the stored event."""
        backend = local_fs_backend
        event = backend.append_event(
            backend.timeline_id,
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        events = backend.read_events()
        assert len(events) == 1
        assert events[0].event_id == event.event_id
        assert events[0].kind == "clip.added"
        assert events[0].hash == event.hash

    def test_head_after_append(self, local_fs_backend):
        """head() reflects the last appended event."""
        backend = local_fs_backend
        event1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        event2 = backend.append_event(
            backend.timeline_id, "clip.moved",
            {"clip_id": "c1", "position": {"mode": "index", "index": 5}},
            actor=_ACTOR,
        )
        head = backend.head()
        assert head.last_event_id == event2.event_id
        assert head.last_hash == event2.hash
        assert head.event_count == 2
        assert head.version == 2

    def test_verify_chain_passes(self, local_fs_backend):
        """verify_chain() passes for a valid event chain."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        backend.append_event(
            backend.timeline_id, "clip.removed",
            {"clip_id": "c1"},
            actor=_ACTOR,
        )
        result = backend.verify_chain()
        assert result.ok is True
        assert result.checked_events == 2
        assert result.error is None

    def test_expected_version_cas(self, local_fs_backend):
        """Appending with stale expected_version raises EventLogStaleVersionError."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        with pytest.raises(EventLogStaleVersionError) as excinfo:
            backend.append_event(
                backend.timeline_id, "clip.moved",
                {"clip_id": "c1", "position": {"mode": "index", "index": 5}},
                actor=_ACTOR,
                expected_version=0,  # stale: current version is 1
            )
        conflict = excinfo.value.conflict
        assert conflict.expected_version == 0
        assert conflict.current_version == 1
        assert conflict.timeline_id == backend.timeline_id

    def test_cas_does_not_mutate_state(self, local_fs_backend):
        """Failed CAS write leaves events and head unchanged."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        events_before = backend.read_events()
        head_before = backend.head()

        with pytest.raises(EventLogStaleVersionError):
            backend.append_event(
                backend.timeline_id, "clip.moved",
                {"clip_id": "c1", "position": {"mode": "index", "index": 5}},
                actor=_ACTOR,
                expected_version=0,
            )

        events_after = backend.read_events()
        head_after = backend.head()
        assert len(events_after) == len(events_before)
        assert events_after[0].event_id == events_before[0].event_id
        assert head_after.version == head_before.version

    def test_rejects_append_after_deleted(self, local_fs_backend):
        """Appending after timeline.deleted raises EventLogError."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "timeline.deleted", {},
            actor=_ACTOR,
        )
        with pytest.raises(EventLogError, match="rejects appends"):
            backend.append_event(
                backend.timeline_id, "clip.added",
                {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
                actor=_ACTOR,
            )

    def test_hash_chain_links_events(self, local_fs_backend):
        """Each event's prev_hash links to the previous event's hash."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t1", "kind": "visual", "label": "Track 1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t2", "kind": "audio", "label": "Track 2"},
            actor=_ACTOR,
        )
        assert e1.prev_hash is None  # first event
        assert e2.prev_hash == e1.hash  # links to previous

    def test_config_replaced_round_trips_and_verifies(self, local_fs_backend):
        """timeline.config_replaced stores a validated raw TimelineConfig payload."""
        backend = local_fs_backend
        event = backend.append_event(
            backend.timeline_id,
            "timeline.config_replaced",
            {"config": {"tracks": [], "clips": []}},
            actor=_ACTOR,
        )

        events = backend.read_events()
        assert events[0].event_id == event.event_id
        assert events[0].kind == "timeline.config_replaced"
        assert isinstance(events[0].payload, TimelineConfigReplacedPayload)
        assert events[0].payload.config == {"tracks": [], "clips": []}
        assert backend.verify_chain().ok is True


# ======================================================================
# SupabaseBackend (fake transport) contract tests
# ======================================================================


class TestSupabaseBackendFakeContract:
    """Contract tests for SupabaseBackend with fake in-memory transport."""

    def test_append_and_read_round_trip(self, supabase_backend_with_fake):
        """append_event → read_events returns the stored event."""
        backend = supabase_backend_with_fake
        event = backend.append_event(
            backend.timeline_id,
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        events = backend.read_events()
        assert len(events) == 1
        assert events[0].event_id == event.event_id
        assert events[0].kind == "clip.added"
        assert events[0].hash == event.hash

    def test_config_replaced_round_trips_and_verifies(self, supabase_backend_with_fake):
        """timeline.config_replaced is accepted by the backend contract fake."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id,
            "timeline.config_replaced",
            {"config": {"tracks": [], "clips": []}},
            actor=_ACTOR,
        )

        events = backend.read_events()
        assert len(events) == 1
        assert isinstance(events[0].payload, TimelineConfigReplacedPayload)
        assert backend.verify_chain().ok is True

    def test_head_after_append(self, supabase_backend_with_fake):
        """head() reflects the last appended event."""
        backend = supabase_backend_with_fake
        e1 = backend.append_event(
            backend.timeline_id, "transition.set",
            {"left_clip_id": "c1", "right_clip_id": "c2",
             "kind": "crossfade", "duration_seconds": 1.5},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "transition.removed",
            {"left_clip_id": "c1", "right_clip_id": "c2"},
            actor=_ACTOR,
        )
        head = backend.head()
        assert head.last_event_id == e2.event_id
        assert head.last_hash == e2.hash
        assert head.event_count == 2
        assert head.version == 2

    def test_verify_chain_passes(self, supabase_backend_with_fake):
        """verify_chain() passes for a valid event chain."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "effect.added",
            {"clip_id": "c1", "effect_id": "blur"},
            actor=_ACTOR,
        )
        backend.append_event(
            backend.timeline_id, "effect.removed",
            {"clip_id": "c1", "effect_id": "blur"},
            actor=_ACTOR,
        )
        result = backend.verify_chain()
        assert result.ok is True
        assert result.checked_events == 2
        assert result.error is None

    def test_expected_version_cas(self, supabase_backend_with_fake):
        """Appending with stale expected_version raises EventLogStaleVersionError."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )
        with pytest.raises(EventLogStaleVersionError) as excinfo:
            backend.append_event(
                backend.timeline_id, "theme.overridden",
                {"override_id": "dark.colors", "value": {"bg": "#111"}},
                actor=_ACTOR,
                expected_version=0,
            )
        conflict = excinfo.value.conflict
        assert conflict.expected_version == 0
        assert conflict.current_version == 1

    def test_cas_does_not_mutate_state(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Failed CAS write leaves events and head unchanged."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "pool.asset_added",
            {"asset_id": "a1"},
            actor=_ACTOR,
        )
        events_before = backend.read_events()
        head_before = backend.head()

        with pytest.raises(EventLogStaleVersionError):
            backend.append_event(
                backend.timeline_id, "pool.asset_removed",
                {"asset_id": "a1"},
                actor=_ACTOR,
                expected_version=0,
            )

        events_after = backend.read_events()
        head_after = backend.head()
        assert len(events_after) == len(events_before)
        assert head_after.version == head_before.version

    def test_rejects_append_after_deleted(self, supabase_backend_with_fake):
        """Appending after timeline.deleted raises EventLogError."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "timeline.deleted", {},
            actor=_ACTOR,
        )
        with pytest.raises(EventLogError, match="rejects appends"):
            backend.append_event(
                backend.timeline_id, "arrangement.replaced",
                {"arrangement": {"clips": []}},
                actor=_ACTOR,
            )

    def test_hash_chain_links_events(self, supabase_backend_with_fake):
        """Each event's prev_hash links to the previous event's hash."""
        backend = supabase_backend_with_fake
        e1 = backend.append_event(
            backend.timeline_id, "audio.bound",
            {"clip_id": "c1", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "audio.unbound",
            {"clip_id": "c1"},
            actor=_ACTOR,
        )
        assert e1.prev_hash is None
        assert e2.prev_hash == e1.hash

    def test_verify_chain_detects_tampered_payload(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """verify_chain() fails when a stored event payload is tampered."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        backend.append_event(
            backend.timeline_id, "clip.moved",
            {"clip_id": "c1", "position": {"mode": "index", "index": 5}},
            actor=_ACTOR,
        )

        # Verify chain is clean before tampering
        assert backend.verify_chain().ok is True

        # Tamper the payload of event 0
        fake_supabase_transport.tamper_event(
            backend.timeline_id, 0,
            {"clip_id": "c1", "kind": "audio", "track_id": "audio", "asset_id": "a99"},
        )

        result = backend.verify_chain()
        assert result.ok is False
        assert "hash mismatch" in (result.error or "")

    def test_verify_chain_detects_tampered_hash(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """verify_chain() fails when a stored event hash is tampered."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "clip.text_set",
            {"clip_id": "c1", "text": "hello"},
            actor=_ACTOR,
        )

        # Tamper the hash directly
        fake_supabase_transport.tamper_hash(
            backend.timeline_id, 0,
            "deadbeef00000000000000000000000000000000000000000000000000000000",
        )

        result = backend.verify_chain()
        assert result.ok is False
        assert "hash mismatch" in (result.error or "")


# ======================================================================
# Golden fixture round-trip tests (T7)
# ======================================================================

import json
from pathlib import Path as _Path

_GOLDEN_DIR = _Path(__file__).resolve().parent.parent / "golden"
_GOLDEN_FILES = sorted(_GOLDEN_DIR.glob("fixture_*.json"))


def _load_fixture(path: _Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _events_from_fixture(fixture: dict) -> list:
    """Parse event dicts from a fixture into TimelineEvent objects."""
    from astrid.core.timeline.events.schema import TimelineEvent

    events: list = []
    for raw in fixture["events"]:
        events.append(TimelineEvent.from_dict(raw))
    return events


def _strip_none_values(obj: Any) -> Any:
    """Recursively strip dict entries whose value is None.

    This mirrors the canonical JSON normalizer which drops ``None``-valued keys
    during storage.  Runtime golden fixtures should not depend on this for
    legacy no-label tracks; those belong only in explicit rejection or migration
    fixtures.  Normalising both sides keeps backend round-trips faithful to the
    real storage behaviour for optional fields.
    """
    if isinstance(obj, dict):
        return {
            key: _strip_none_values(val)
            for key, val in obj.items()
            if val is not None
        }
    if isinstance(obj, list):
        return [_strip_none_values(item) for item in obj]
    return obj


class TestGoldenFixtureRoundTrip:
    """Round-trip every tests/golden/fixture_*.json through both backends."""

    @pytest.mark.parametrize("fixture_path", _GOLDEN_FILES, ids=lambda p: p.stem)
    def test_localfs_round_trip(self, local_fs_backend, fixture_path):
        """Load fixture, append events via LocalFsBackend, read back, project,
        assert projected assembly == expected_assembly."""
        fixture = _load_fixture(fixture_path)
        events = _events_from_fixture(fixture)
        if not events:
            pytest.skip("Fixture has no events")
        expects_runtime_rejection = any(
            e.kind == "timeline.imported"
            or e.kind == "arrangement.replaced"
            for e in events
        )

        backend = local_fs_backend
        timeline_id = events[0].timeline_id

        # Recreate backend with the fixture's timeline_id
        from astrid.core.timeline.eventlog import LocalFsBackend
        from astrid.core.project.jsonio import write_json_atomic

        # Build a fresh identity matching the fixture
        home = backend.timeline_home
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000000",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )
        be = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)

        # Append events one by one
        for event in events:
            payload_dict = (
                event.payload.to_json_obj()
                if hasattr(event.payload, 'to_json_obj')
                else dict(event.payload)
            )
            be.append_event(
                timeline_id,
                event.kind,
                payload_dict,
                actor=event.actor,
            )

        # Read back and project
        stored = be.read_events()
        assert len(stored) == len(events)

        from astrid.core.timeline.projection import project_to_assembly
        if expects_runtime_rejection:
            with pytest.raises(Exception, match="migration-only legacy|not a TimelineConfig"):
                project_to_assembly(stored)
            assert be.verify_chain().ok is True
            return

        projected = project_to_assembly(stored)

        expected = fixture["expected_assembly"]
        # Normalise both sides: the canonical JSON serialiser strips None
        # values during storage, so projected assembly will never contain
        # None-valued keys.  Strip them from expected_assembly too to keep
        # the golden files read-only while making the comparison faithful.
        expected_normalised = _strip_none_values(expected)
        projected_normalised = _strip_none_values(projected)
        assert projected_normalised == expected_normalised, (
            f"Fixture {fixture_path.stem}: projected assembly does not match "
            f"expected_assembly"
        )

        # Verify chain passes
        verification = be.verify_chain()
        assert verification.ok is True, (
            f"Fixture {fixture_path.stem}: verify_chain() failed: {verification.error}"
        )

        # Head matches
        head = be.head()
        assert head.event_count == len(events)
        assert head.version == len(events)

    @pytest.mark.parametrize("fixture_path", _GOLDEN_FILES, ids=lambda p: p.stem)
    def test_supabase_fake_round_trip(
        self, supabase_backend_with_fake, fake_supabase_transport, fixture_path
    ):
        """Load fixture, append events via fake Supabase transport, read back,
        project, assert projected assembly == expected_assembly."""
        fixture = _load_fixture(fixture_path)
        events = _events_from_fixture(fixture)
        if not events:
            pytest.skip("Fixture has no events")
        expects_runtime_rejection = any(
            e.kind == "timeline.imported"
            or e.kind == "arrangement.replaced"
            for e in events
        )

        timeline_id = events[0].timeline_id

        # Build a fresh backend with the fixture's timeline_id
        from astrid.core.timeline.eventlog import SupabaseBackend
        # Some fixtures use human actors; set verified_subject to a value
        # that matches the first human actor in the fixture (if any) so
        # the auth check passes in the fake transport.
        human_actor_id = next(
            (e.actor.id for e in events if e.actor.type == "human"), None
        )
        be = SupabaseBackend(
            timeline_id=timeline_id,
            transport=fake_supabase_transport,
            enabled=True,
            verified_subject=human_actor_id or "system",
        )

        # Append events one by one
        for event in events:
            payload_dict = (
                event.payload.to_json_obj()
                if hasattr(event.payload, 'to_json_obj')
                else dict(event.payload)
            )
            be.append_event(
                timeline_id,
                event.kind,
                payload_dict,
                actor=event.actor,
            )

        # Read back and project
        stored = be.read_events()
        assert len(stored) == len(events)

        from astrid.core.timeline.projection import project_to_assembly
        if expects_runtime_rejection:
            with pytest.raises(Exception, match="migration-only legacy|not a TimelineConfig"):
                project_to_assembly(stored)
            assert be.verify_chain().ok is True
            return

        projected = project_to_assembly(stored)

        expected = fixture["expected_assembly"]
        # Normalise both sides (see comment in localfs variant)
        expected_normalised = _strip_none_values(expected)
        projected_normalised = _strip_none_values(projected)
        assert projected_normalised == expected_normalised, (
            f"Fixture {fixture_path.stem}: projected assembly does not match "
            f"expected_assembly"
        )

        # Verify chain passes
        verification = be.verify_chain()
        assert verification.ok is True, (
            f"Fixture {fixture_path.stem}: verify_chain() failed: {verification.error}"
        )

        # Head matches
        head = be.head()
        assert head.event_count == len(events)
        assert head.version == len(events)


# ======================================================================
# LocalFs tamper/integrity contract tests (T10)
# ======================================================================


class TestLocalFsTamperContract:
    """Contract-level tamper-detection tests for LocalFsBackend."""

    def test_localfs_verify_chain_detects_tampered_payload(
        self, local_fs_backend
    ):
        """verify_chain() fails when a stored event payload is tampered in JSONL."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        backend.append_event(
            backend.timeline_id, "clip.retimed",
            {"clip_id": "c1", "start": 1.0, "duration": 5.0},
            actor=_ACTOR,
        )

        # Verify chain is clean before tampering
        assert backend.verify_chain().ok is True

        # Tamper the JSONL file — change payload of event 0
        jsonl_path = backend.events_path
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["payload"]["kind"] = "audio"
        jsonl_path.write_text(
            json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n"
            + "\n".join(lines[1:]) + ("\n" if len(lines) > 1 else "")
        )

        result = backend.verify_chain()
        assert result.ok is False
        assert "hash mismatch" in (result.error or "")

    def test_localfs_verify_chain_detects_tampered_hash(
        self, local_fs_backend
    ):
        """verify_chain() fails when a stored event hash is tampered in JSONL."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        assert backend.verify_chain().ok is True

        # Tamper the hash in the JSONL file
        jsonl_path = backend.events_path
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["hash"] = "deadbeef00000000000000000000000000000000000000000000000000000000"
        jsonl_path.write_text(
            json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n"
        )

        result = backend.verify_chain()
        assert result.ok is False
        assert "hash mismatch" in (result.error or "")

    def test_localfs_verify_chain_detects_tampered_prev_hash(
        self, local_fs_backend
    ):
        """verify_chain() fails when prev_hash link is broken in JSONL."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t1", "kind": "visual", "label": "Track 1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t2", "kind": "audio", "label": "Track 2"},
            actor=_ACTOR,
        )

        assert backend.verify_chain().ok is True
        assert e2.prev_hash == e1.hash

        # Tamper prev_hash of event 1 (index 1)
        jsonl_path = backend.events_path
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[1])
        tampered["prev_hash"] = "deadbeef00000000000000000000000000000000000000000000000000000000"
        jsonl_path.write_text(
            lines[0] + "\n"
            + json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n"
        )

        result = backend.verify_chain()
        assert result.ok is False
        assert "prev_hash mismatch" in (result.error or "")


# ======================================================================
# Import append contract tests (M9 / T2)
# ======================================================================


def _make_source_event(
    kind: str,
    payload: dict,
    *,
    timeline_id: str = "00000000-0000-0000-0000-000000000099",
    event_id: str = "01BBBBBBBBBBBBBBBBBBBBBB99",
    source_backend: str = "supabase",
) -> TimelineEvent:
    """Build a minimal source TimelineEvent for import testing."""
    from astrid.core.timeline.events.schema import with_event_hash
    event = TimelineEvent.from_dict({
        "event_id": event_id,
        "timeline_id": timeline_id,
        "ts": "2026-01-01T00:00:00Z",
        "actor": {"type": "system", "id": "import-test", "display": "Import Test"},
        "prev_hash": None,
        "hash": None,  # will be computed
        "kind": kind,
        "payload": payload,
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
        "source_backend": source_backend,
        "source_timeline_id": timeline_id,
        "source_event_id": event_id,
        "source_version": 5,
        "source_hash": None,
    })
    return with_event_hash(event, prev_hash=None)


_IMPORT_ACTOR = TimelineActor(type="agent", id="codex:import-test")
_SRC_TID = "00000000-0000-0000-0000-000000000099"


class TestLocalFsImportContract:
    """Contract tests for LocalFsBackend.append_imported_event()."""

    def test_import_append_creates_destination_native_event(self, local_fs_backend):
        """Import creates a new event with destination-native ID and hash."""
        backend = local_fs_backend
        source = _make_source_event("clip.added", {
            "clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1",
        })

        imported = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:pull:supabase:src-tid:src-eid-1",
            actor=_IMPORT_ACTOR,
        )

        # Destination-native identity
        assert imported.event_id != source.event_id
        assert imported.timeline_id == backend.timeline_id
        assert imported.hash is not None
        assert imported.hash != source.hash
        assert imported.prev_hash is None  # first event

        # Source identity preserved in import metadata
        assert imported.source_backend == "supabase"
        assert imported.source_timeline_id == _SRC_TID
        assert imported.source_event_id == source.event_id
        assert imported.source_version == 5
        assert imported.source_hash is not None

    def test_import_retry_returns_same_event(self, local_fs_backend):
        """Retrying with the same idempotency key returns the already-appended event."""
        backend = local_fs_backend
        source = _make_source_event("theme.set", {"theme_id": "dark"})

        first = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:pull:supabase:src-tid:src-eid-2",
            actor=_IMPORT_ACTOR,
        )

        # Retry with same key
        second = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:pull:supabase:src-tid:src-eid-2",
            actor=_IMPORT_ACTOR,
        )

        # Same event returned (not a duplicate)
        assert second.event_id == first.event_id
        assert second.hash == first.hash

        # Stream only has one event
        events = backend.read_events()
        assert len(events) == 1

    def test_import_hash_chain_links(self, local_fs_backend):
        """Imported events link into the destination hash chain."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_IMPORT_ACTOR,
        )

        source = _make_source_event("track.added", {
            "track_id": "t1", "kind": "visual", "label": "Track 1",
        })
        imported = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:pull:supabase:src-tid:src-eid-3",
            actor=_IMPORT_ACTOR,
        )

        assert imported.prev_hash == e1.hash
        assert imported.hash is not None

        # Chain verification passes
        result = backend.verify_chain()
        assert result.ok is True
        assert result.checked_events == 2

    def test_import_rejects_after_deleted(self, local_fs_backend):
        """Import after timeline.deleted raises EventLogError."""
        backend = local_fs_backend
        backend.append_event(
            backend.timeline_id, "timeline.deleted", {},
            actor=_IMPORT_ACTOR,
        )

        source = _make_source_event("clip.added", {
            "clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1",
        })
        with pytest.raises(EventLogError, match="rejects appends"):
            backend.append_imported_event(
                backend.timeline_id,
                source,
                idempotency_key="transfer:pull:supabase:src-tid:src-eid-4",
                actor=_IMPORT_ACTOR,
            )


class TestSupabaseFakeImportContract:
    """Contract tests for SupabaseBackend (fake transport) append_imported_event()."""

    def test_import_append_creates_destination_native_event(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Import creates a new event with destination-native ID and hash."""
        backend = supabase_backend_with_fake
        source = _make_source_event("clip.added", {
            "clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1",
        }, source_backend="local_fs")

        imported = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:push:local_fs:src-tid:src-eid-10",
            actor=_IMPORT_ACTOR,
        )

        assert imported.event_id != source.event_id
        assert imported.timeline_id == backend.timeline_id
        assert imported.hash is not None
        assert imported.hash != source.hash
        assert imported.source_backend == "local_fs"

    def test_import_retry_returns_same_event(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Retrying with the same idempotency key returns the same event."""
        backend = supabase_backend_with_fake
        source = _make_source_event("pool.asset_added", {"asset_id": "img1.png"},
                                    source_backend="local_fs")

        first = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:push:local_fs:src-tid:src-eid-11",
            actor=_IMPORT_ACTOR,
        )

        second = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:push:local_fs:src-tid:src-eid-11",
            actor=_IMPORT_ACTOR,
        )

        assert second.event_id == first.event_id
        assert len(backend.read_events()) == 1

    def test_import_hash_chain_links(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Imported events link into the destination hash chain."""
        backend = supabase_backend_with_fake
        e1 = backend.append_event(
            backend.timeline_id, "arrangement.replaced",
            {"arrangement": {"clips": []}},
            actor=_IMPORT_ACTOR,
        )

        source = _make_source_event("effect.added", {
            "clip_id": "c1", "effect_id": "blur",
        }, source_backend="local_fs")
        imported = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:push:local_fs:src-tid:src-eid-12",
            actor=_IMPORT_ACTOR,
        )

        assert imported.prev_hash == e1.hash
        result = backend.verify_chain()
        assert result.ok is True
        assert result.checked_events == 2

    def test_import_rejects_after_deleted(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Import after timeline.deleted raises EventLogError."""
        backend = supabase_backend_with_fake
        backend.append_event(
            backend.timeline_id, "timeline.deleted", {},
            actor=_IMPORT_ACTOR,
        )

        source = _make_source_event("clip.added", {
            "clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1",
        }, source_backend="local_fs")
        with pytest.raises(EventLogError, match="rejects appends"):
            backend.append_imported_event(
                backend.timeline_id,
                source,
                idempotency_key="transfer:push:local_fs:src-tid:src-eid-13",
                actor=_IMPORT_ACTOR,
            )


# ======================================================================
# Erasure repair contract tests
# ======================================================================


class TestLocalFsErasureRepairContract:
    """Contract tests for LocalFsBackend.repair_erasure()."""

    def test_repair_erasure_replaces_payloads(self, local_fs_backend):
        """Erased events get canonical ErasedPayload; chain continuity preserved."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "clip.moved",
            {"clip_id": "c1", "position": {"mode": "index", "index": 0}},
            actor=_ACTOR,
        )
        e3 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t1", "kind": "visual", "label": "Track 1"},
            actor=_ACTOR,
        )

        result = backend.repair_erasure(
            target_event_ids=[e1.event_id],
            reason="policy test",
            erased_by="test-script",
        )
        assert result["replaced_count"] == 1
        assert result["downstream_count"] == 3  # all 3 events recomputed (e1 erased + e2,e3 downstream)

        # Verify chain still passes
        verification = backend.verify_chain()
        assert verification.ok is True
        assert verification.checked_events == 3

        # Verify e1 now has ErasedPayload
        events = backend.read_events()
        from astrid.core.timeline.events.schema import ErasedPayload
        assert isinstance(events[0].payload, ErasedPayload)
        assert events[0].payload.erased is True
        assert events[0].payload.reason == "policy test"

        # Verify TimelineEvent.from_dict() still parses erased events
        e1_dict = events[0].to_json_obj()
        reparsed = TimelineEvent.from_dict(e1_dict)
        assert isinstance(reparsed.payload, ErasedPayload)
        assert reparsed.event_id == e1.event_id

    def test_repair_erasure_middle_event(self, local_fs_backend):
        """Erasure of a middle event recomputes only downstream hashes."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t1", "kind": "visual", "label": "Track 1"},
            actor=_ACTOR,
        )
        e3 = backend.append_event(
            backend.timeline_id, "pool.asset_added",
            {"asset_id": "img1.png"},
            actor=_ACTOR,
        )
        e4 = backend.append_event(
            backend.timeline_id, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        result = backend.repair_erasure(
            target_event_ids=[e2.event_id],
            reason="middle test",
            erased_by="test-script",
        )
        assert result["replaced_count"] == 1
        # e1 remains unchanged, e2 payload replaced, e3+e4 downstream from e2
        assert result["downstream_count"] == 3  # e2, e3, e4

        events = backend.read_events()
        from astrid.core.timeline.events.schema import ErasedPayload
        # e1 unchanged
        assert not isinstance(events[0].payload, ErasedPayload)
        # e2 erased
        assert isinstance(events[1].payload, ErasedPayload)
        # e3, e4 are domain events (not erased)
        assert not isinstance(events[2].payload, ErasedPayload)
        assert not isinstance(events[3].payload, ErasedPayload)

        # Chain still continuous
        verification = backend.verify_chain()
        assert verification.ok is True

    def test_repair_erasure_multiple_events(self, local_fs_backend):
        """Multiple events can be erased in one operation."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t1", "kind": "visual", "label": "Track 1"},
            actor=_ACTOR,
        )
        e3 = backend.append_event(
            backend.timeline_id, "pool.asset_added",
            {"asset_id": "img1.png"},
            actor=_ACTOR,
        )

        result = backend.repair_erasure(
            target_event_ids=[e1.event_id, e3.event_id],
            reason="multi test",
            erased_by="test-script",
        )
        assert result["replaced_count"] == 2

        events = backend.read_events()
        from astrid.core.timeline.events.schema import ErasedPayload
        assert isinstance(events[0].payload, ErasedPayload)
        assert not isinstance(events[1].payload, ErasedPayload)
        assert isinstance(events[2].payload, ErasedPayload)

        # Chain still continuous
        verification = backend.verify_chain()
        assert verification.ok is True

    def test_repair_erasure_idempotent(self, local_fs_backend):
        """Re-erasing already-erased events is idempotent."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        # First erasure
        result1 = backend.repair_erasure(
            target_event_ids=[e1.event_id],
            reason="first pass",
            erased_by="test-script",
        )
        assert result1["replaced_count"] == 1

        # Second erasure of same event — idempotent
        result2 = backend.repair_erasure(
            target_event_ids=[e1.event_id],
            reason="second pass",
            erased_by="test-script",
        )
        assert result2["replaced_count"] == 0  # No new erasures

        # Chain still continuous
        verification = backend.verify_chain()
        assert verification.ok is True

    def test_repair_erasure_unknown_event_id(self, local_fs_backend):
        """Unknown event IDs are silently ignored."""
        backend = local_fs_backend
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        result = backend.repair_erasure(
            target_event_ids=["01JJJJJJJJJJJJJJJJJJJJJJJJ"],  # nonexistent ULID
            reason="unknown test",
            erased_by="test-script",
        )
        assert result["replaced_count"] == 0
        assert result["head_event_count"] == 1

        # Chain still continuous
        verification = backend.verify_chain()
        assert verification.ok is True

    def test_repair_erasure_preserves_import_metadata(self, local_fs_backend):
        """Erasure preserves import metadata (source_*) on affected events."""
        backend = local_fs_backend
        import_actor = TimelineActor(type="agent", id="importer")
        source = _make_source_event(
            "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            source_backend="supabase",
        )
        imported = backend.append_imported_event(
            backend.timeline_id,
            source,
            idempotency_key="transfer:pull:supabase:src-tid:src-eid-repair-1",
            actor=import_actor,
        )

        result = backend.repair_erasure(
            target_event_ids=[imported.event_id],
            reason="metadata test",
            erased_by="test-script",
        )
        assert result["replaced_count"] == 1

        events = backend.read_events()
        erased_evt = events[0]
        from astrid.core.timeline.events.schema import ErasedPayload
        assert isinstance(erased_evt.payload, ErasedPayload)
        # Import metadata preserved
        assert erased_evt.source_backend == "supabase"
        assert erased_evt.source_timeline_id is not None
        assert erased_evt.source_event_id == source.event_id


class TestSupabaseFakeErasureRepairContract:
    """Contract tests for SupabaseBackend (fake transport) repair_erasure()."""

    def test_repair_erasure_fake_transport(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Fake transport repair replaces payloads with ErasedPayload."""
        backend = supabase_backend_with_fake
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            backend.timeline_id, "track.added",
            {"track_id": "t1", "kind": "audio", "label": "Track 1"},
            actor=_ACTOR,
        )

        result = backend.repair_erasure(
            target_event_ids=[e1.event_id],
            reason="fake test",
            erased_by="fake-script",
        )
        assert result["replaced_count"] == 1

        # Verify chain
        verification = backend.verify_chain()
        assert verification.ok is True
        assert verification.checked_events == 2

        # Verify e1 erased
        events = backend.read_events()
        from astrid.core.timeline.events.schema import ErasedPayload
        assert isinstance(events[0].payload, ErasedPayload)

    def test_repair_erasure_fake_chain_continuity(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """After erasure, the hash chain is continuous in fake transport."""
        backend = supabase_backend_with_fake
        for i in range(5):
            backend.append_event(
                backend.timeline_id, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "track_id": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        events_before = backend.read_events()
        mid_event_id = events_before[2].event_id

        result = backend.repair_erasure(
            target_event_ids=[mid_event_id],
            reason="chain test",
            erased_by="fake-script",
        )
        assert result["replaced_count"] == 1

        verification = backend.verify_chain()
        assert verification.ok is True
        assert verification.checked_events == 5

    def test_repair_erasure_fake_idempotent(
        self, supabase_backend_with_fake, fake_supabase_transport
    ):
        """Re-erasing in fake transport is idempotent."""
        backend = supabase_backend_with_fake
        e1 = backend.append_event(
            backend.timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        r1 = backend.repair_erasure(
            target_event_ids=[e1.event_id],
            reason="first",
            erased_by="test",
        )
        assert r1["replaced_count"] == 1

        r2 = backend.repair_erasure(
            target_event_ids=[e1.event_id],
            reason="second",
            erased_by="test",
        )
        assert r2["replaced_count"] == 0

        verification = backend.verify_chain()
        assert verification.ok is True


# ======================================================================
# Recovery contract tests (M9 / T14)
# ======================================================================


class TestLocalFsRecoveryContract:
    """Contract tests for recovery on LocalFsBackend."""

    def test_recover_to_event_appends_timeline_recovered(
        self, local_fs_backend, monkeypatch
    ):
        """Recover to an anchor: chain verified, timeline.recovered appended."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.observability import ResolvedTarget
        from astrid.core.timeline.operations import recover_to_event, RecoveryResult

        backend = local_fs_backend
        timeline_id = backend.timeline_id
        home = backend.timeline_home

        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": {"tracks": [], "clips": []}},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod, "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs", timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000000",
                timeline_home=home, slug="rcv-test",
                backend_name_display="local_fs",
            ),
        )

        # Write minimal assembly so projection can work
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.json",
            {"clips": [], "tracks": []},
        )

        result = recover_to_event(
            "test-project", "rcv-test", e1.event_id,
            _ACTOR, "contract recovery",
        )

        assert isinstance(result, RecoveryResult)
        assert result.anchor_event_id == e1.event_id
        assert result.anchor_type == "event"
        assert result.new_version == 2

        events = backend.read_events()
        assert len(events) == 2
        assert events[-1].kind == "timeline.recovered"

    def test_recover_refuses_broken_chain(
        self, local_fs_backend, monkeypatch
    ):
        """Recovery refused when chain is broken."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline.observability import ResolvedTarget
        from astrid.core.timeline.operations import recover_to_event
        from astrid.core.timeline.projection import ProjectionError

        backend = local_fs_backend
        timeline_id = backend.timeline_id
        home = backend.timeline_home

        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": {"tracks": [], "clips": []}},
            actor=_ACTOR,
        )

        monkeypatch.setattr(
            obs_mod, "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs", timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000000",
                timeline_home=home, slug="rcv-broken",
                backend_name_display="local_fs",
            ),
        )

        # Tamper: append bad event directly to break chain
        import json
        events_path = home / "assembly.jsonl"
        with open(events_path, "a") as f:
            f.write(
                json.dumps({
                    "event_id": "01J0000000000000000000000Y",
                    "timeline_id": timeline_id,
                    "ts": "2026-05-21T00:00:00Z",
                    "actor": {"type": "agent", "id": "x"},
                    "prev_hash": "wrong-hash",
                    "hash": "also-wrong",
                    "kind": "clip.added",
                    "payload": {"clip_id": "bad", "kind": "visual", "track_id": "visual", "asset_id": "x"},
                    "schema_version": 2,
                })
                + "\n"
            )

        with pytest.raises(ProjectionError, match="recovery refused"):
            recover_to_event(
                "test-project", "rcv-broken", e1.event_id,
                _ACTOR, "should fail",
            )


class TestSupabaseFakeRecoveryContract:
    """Contract tests for recovery on SupabaseBackend (fake transport)."""

    def test_recover_to_event_fake_transport(
        self, supabase_backend_with_fake, fake_supabase_transport, monkeypatch
    ):
        """Recover through fake transport appends timeline.recovered."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline import eventlog as evlog_mod
        from astrid.core.timeline import paths as paths_mod
        from astrid.core.timeline.observability import ResolvedTarget
        from astrid.core.timeline.operations import recover_to_event, RecoveryResult

        backend = supabase_backend_with_fake
        timeline_id = backend.timeline_id

        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": {"tracks": [], "clips": []}},
            actor=_ACTOR,
        )

        tl_ulid = "01JSUPABASEBASEEXAMPLE001"

        monkeypatch.setattr(
            obs_mod, "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="supabase", timeline_id=timeline_id,
                timeline_ulid=tl_ulid,
                timeline_home=None, slug="rcv-fake",
                backend_name_display="supabase",
            ),
        )
        # Inject the fake transport into the backend selection path
        monkeypatch.setattr(
            evlog_mod, "build_timeline_backend",
            lambda stream: backend,
        )
        monkeypatch.setattr(
            evlog_mod, "select_timeline_stream",
            lambda *a, **kw: (backend, None),
        )
        # Also patch timeline_dir to avoid filesystem issues
        import tempfile
        tmp_dir = _Path(tempfile.mkdtemp())
        monkeypatch.setattr(
            paths_mod, "timeline_dir",
            lambda project_slug, ulid, root=None: tmp_dir,
        )

        result = recover_to_event(
            "test-project", "rcv-fake", e1.event_id,
            _ACTOR, "fake recovery test",
        )

        assert isinstance(result, RecoveryResult)
        assert result.anchor_event_id == e1.event_id
        assert result.new_version == 2

        events = backend.read_events()
        assert len(events) == 2
        assert events[-1].kind == "timeline.recovered"

    def test_recover_refuses_broken_chain_fake(
        self, supabase_backend_with_fake, fake_supabase_transport, monkeypatch
    ):
        """Recovery on fake transport refuses broken chain."""
        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline import eventlog as evlog_mod
        from astrid.core.timeline import paths as paths_mod
        from astrid.core.timeline.observability import ResolvedTarget
        from astrid.core.timeline.operations import recover_to_event
        from astrid.core.timeline.projection import ProjectionError

        backend = supabase_backend_with_fake
        timeline_id = backend.timeline_id

        e1 = backend.append_event(
            timeline_id, "timeline.config_replaced",
            {"config": {"tracks": [], "clips": []}},
            actor=_ACTOR,
        )

        tl_ulid = "01JSUPABASEBASEEXAMPLE002"

        monkeypatch.setattr(
            obs_mod, "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="supabase", timeline_id=timeline_id,
                timeline_ulid=tl_ulid,
                timeline_home=None, slug="rcv-broken-fake",
                backend_name_display="supabase",
            ),
        )
        # Inject the fake transport into the backend selection path
        monkeypatch.setattr(
            evlog_mod, "build_timeline_backend",
            lambda stream: backend,
        )
        monkeypatch.setattr(
            evlog_mod, "select_timeline_stream",
            lambda *a, **kw: (backend, None),
        )
        # Also patch timeline_dir to avoid filesystem issues
        import tempfile
        tmp_dir = _Path(tempfile.mkdtemp())
        monkeypatch.setattr(
            paths_mod, "timeline_dir",
            lambda project_slug, ulid, root=None: tmp_dir,
        )

        # Tamper via fake transport
        fake_supabase_transport.tamper_hash(
            timeline_id, 0,
            "deadbeef00000000000000000000000000000000000000000000000000000000",
        )

        with pytest.raises(ProjectionError, match="recovery refused"):
            recover_to_event(
                "test-project", "rcv-broken-fake", e1.event_id,
                _ACTOR, "should fail",
            )
