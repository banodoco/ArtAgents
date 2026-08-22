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
        from astrid.core._shared.jsonio import write_json_atomic

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


# Erasure and recovery contract tests retired with cutover (W4).
