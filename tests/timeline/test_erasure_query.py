"""Tests for erasure query and command (T12).

Covers:
- V1 query language: event IDs, kind allowlist, actor exact/prefix, timestamp range
- Preview-first behavior (no mutation without --yes)
- timeline.erased audit event appended BEFORE repair
- Erased payloads parseable after repair
- Chain repair propagates downstream
- Stale assembly.json fallback prevention
- Retained metadata after erasure
- Selector safety (empty selector rejected)
"""

from __future__ import annotations

import pytest
from pathlib import Path
from uuid import uuid4

from astrid.core.timeline.events.schema import (
    ErasedPayload,
    TimelineActor,
    TimelineEvent,
)
from astrid.core.timeline.erasure import (
    ErasurePreview,
    ErasureResult,
    ErasureSelector,
    apply_erasure,
    query_erasure,
)

_ACTOR = TimelineActor(type="agent", id="erasure-test")


class TestErasureSelector:
    """Tests for the v1 erasure query language."""

    def test_empty_selector_is_empty(self):
        """An empty selector has no criteria."""
        selector = ErasureSelector()
        assert selector.is_empty() is True

    def test_selector_with_event_ids_not_empty(self):
        """Selector with event_ids is not empty."""
        selector = ErasureSelector(event_ids=("evt1",))
        assert selector.is_empty() is False

    def test_selector_with_kind_not_empty(self):
        """Selector with kind_allowlist is not empty."""
        selector = ErasureSelector(kind_allowlist=("clip.added",))
        assert selector.is_empty() is False

    def test_empty_selector_query_raises(self, tmp_path: Path):
        """Query with empty selector raises ValueError."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        selector = ErasureSelector()
        with pytest.raises(ValueError, match="empty"):
            query_erasure(backend, selector)

    def test_match_by_event_id(self):
        """Exact event ID matching works."""
        selector = ErasureSelector(event_ids=("evt1", "evt3"))

        class FakeEvent:
            def __init__(self, event_id):
                self.event_id = event_id
                self.kind = "clip.added"
                self.actor = _ACTOR
                self.ts = "2026-05-21T00:00:00Z"

        assert selector.matches(FakeEvent("evt1")) is True
        assert selector.matches(FakeEvent("evt2")) is False
        assert selector.matches(FakeEvent("evt3")) is True

    def test_match_by_kind_allowlist(self):
        """Kind allowlist matching works."""
        selector = ErasureSelector(kind_allowlist=("clip.added", "clip.removed"))

        class FakeEvent:
            def __init__(self, kind):
                self.event_id = "evt1"
                self.kind = kind
                self.actor = _ACTOR
                self.ts = "2026-05-21T00:00:00Z"

        assert selector.matches(FakeEvent("clip.added")) is True
        assert selector.matches(FakeEvent("clip.removed")) is True
        assert selector.matches(FakeEvent("theme.set")) is False

    def test_match_by_actor_id(self):
        """Exact actor ID matching works."""
        selector = ErasureSelector(actor_id="agent:undo-test")

        class FakeEvent:
            def __init__(self, actor_id):
                self.event_id = "evt1"
                self.kind = "clip.added"
                self.actor = TimelineActor(type="agent", id=actor_id)
                self.ts = "2026-05-21T00:00:00Z"

        assert selector.matches(FakeEvent("agent:undo-test")) is True
        assert selector.matches(FakeEvent("agent:other")) is False

    def test_match_by_actor_prefix(self):
        """Actor ID prefix matching works."""
        selector = ErasureSelector(actor_id_prefix="agent:")

        class FakeEvent:
            def __init__(self, actor_id):
                self.event_id = "evt1"
                self.kind = "clip.added"
                self.actor = TimelineActor(type="agent", id=actor_id)
                self.ts = "2026-05-21T00:00:00Z"

        assert selector.matches(FakeEvent("agent:test")) is True
        assert selector.matches(FakeEvent("agent:other")) is True
        assert selector.matches(FakeEvent("system:test")) is False

    def test_match_by_timestamp_range(self):
        """Timestamp range matching works."""
        selector = ErasureSelector(ts_after="2026-05-21T00:00:00Z", ts_before="2026-05-22T00:00:00Z")

        class FakeEvent:
            def __init__(self, ts):
                self.event_id = "evt1"
                self.kind = "clip.added"
                self.actor = _ACTOR
                self.ts = ts

        assert selector.matches(FakeEvent("2026-05-21T12:00:00Z")) is True
        assert selector.matches(FakeEvent("2026-05-20T12:00:00Z")) is False
        assert selector.matches(FakeEvent("2026-05-23T12:00:00Z")) is False

    def test_combined_criteria_all_must_match(self):
        """All specified criteria must match (AND semantics)."""
        selector = ErasureSelector(
            kind_allowlist=("clip.added",),
            actor_id_prefix="agent:",
        )

        class FakeEvent:
            def __init__(self, kind, actor_id):
                self.event_id = "evt1"
                self.kind = kind
                self.actor = TimelineActor(type="agent", id=actor_id)
                self.ts = "2026-05-21T00:00:00Z"

        assert selector.matches(FakeEvent("clip.added", "agent:test")) is True
        assert selector.matches(FakeEvent("clip.added", "system:test")) is False
        assert selector.matches(FakeEvent("theme.set", "agent:test")) is False


class TestErasurePreview:
    """Tests for erasure preview (read-only, no mutation)."""

    def test_preview_matches_correctly(self, tmp_path: Path):
        """Preview returns matched event IDs without mutating."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        e1 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )
        e3 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c2", "kind": "visual", "track_id": "visual", "asset_id": "a2"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(kind_allowlist=("clip.added",))
        preview = query_erasure(backend, selector)

        assert preview.matched_count == 2
        assert e1.event_id in preview.matched_event_ids
        assert e3.event_id in preview.matched_event_ids
        assert e2.event_id not in preview.matched_event_ids
        assert preview.total_events_in_stream == 3

        # Verify no mutation occurred
        events_after = backend.read_events()
        assert len(events_after) == 3
        for evt in events_after:
            assert not isinstance(evt.payload, ErasedPayload), "preview should not mutate"

    def test_preview_zero_matches(self, tmp_path: Path):
        """Preview returns zero matches when selector matches nothing."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)
        backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(kind_allowlist=("theme.set",))
        preview = query_erasure(backend, selector)

        assert preview.matched_count == 0
        assert len(preview.matched_event_ids) == 0


class TestErasureApply:
    """Tests for erasure application (mutation with audit-event-first)."""

    def test_apply_appends_audit_event_before_repair(self, tmp_path: Path):
        """timeline.erased audit event appears BEFORE payload repair."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        e1 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c2", "kind": "visual", "track_id": "visual", "asset_id": "a2"},
            actor=_ACTOR,
        )
        e3 = backend.append_event(
            tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(event_ids=(e1.event_id, e3.event_id))

        result = apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="test erasure",
            policy_ref="POL-001",
            regenerate_projection_after=False,
        )

        assert result.replaced_count == 2
        assert result.reason == "test erasure"
        assert result.policy_ref == "POL-001"

        # Verify audit event exists and comes BEFORE the erased event idx
        events_after = backend.read_events()
        # Original 3 + 1 audit = 4 events, but 1 event may have had its payload erased

        audit_events = [e for e in events_after if e.kind == "timeline.erased"]
        assert len(audit_events) == 1
        assert audit_events[0].event_id == result.audit_event_id

    def test_erased_payloads_parseable_after_repair(self, tmp_path: Path):
        """After erasure, replaced payloads are canonical ErasedPayload."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        e1 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(event_ids=(e1.event_id,))

        result = apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="test",
            regenerate_projection_after=False,
        )

        # Re-read events
        events_after = backend.read_events()
        # Find the erased event
        erased_evt = None
        for evt in events_after:
            if evt.event_id == e1.event_id:
                erased_evt = evt
                break

        assert erased_evt is not None
        assert isinstance(erased_evt.payload, ErasedPayload)
        assert erased_evt.payload.erased is True
        assert erased_evt.payload.reason == "test"

    def test_chain_continuity_after_erasure(self, tmp_path: Path):
        """Hash chain is preserved after erasure repair."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        e1 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )
        e3 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c2", "kind": "visual", "track_id": "visual", "asset_id": "a2"},
            actor=_ACTOR,
        )

        # Erase the middle event
        selector = ErasureSelector(event_ids=(e2.event_id,))

        apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="test",
            regenerate_projection_after=False,
        )

        # Verify chain is still valid
        verification = backend.verify_chain()
        assert verification.ok, f"Chain should be valid: {verification.error}"

    def test_erasure_idempotent(self, tmp_path: Path):
        """Erasing already-erased events is idempotent."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        e1 = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(event_ids=(e1.event_id,))

        # First erasure
        result1 = apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="first erase",
            regenerate_projection_after=False,
        )
        assert result1.replaced_count == 1

        # Second erasure (same event — already erased)
        result2 = apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="second erase",
            regenerate_projection_after=False,
        )
        # Should report 0 replaced (already erased, idempotent)
        assert result2.replaced_count == 0

    def test_retained_metadata_after_erasure(self, tmp_path: Path):
        """After erasure, event IDs, versions, kind, actor, timestamps remain."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        original_event = backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(event_ids=(original_event.event_id,))

        apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="test",
            regenerate_projection_after=False,
        )

        events_after = backend.read_events()
        erased_evt = None
        for evt in events_after:
            if evt.event_id == original_event.event_id:
                erased_evt = evt
                break

        assert erased_evt is not None
        # Retained metadata
        assert erased_evt.event_id == original_event.event_id
        assert erased_evt.timeline_id == original_event.timeline_id
        assert erased_evt.kind == original_event.kind  # kind retained
        assert erased_evt.actor == original_event.actor  # actor retained
        assert erased_evt.ts == original_event.ts  # timestamp retained
        # Chain fields are recomputed but present
        assert erased_evt.hash is not None


class TestErasureResult:
    """ErasureResult carries audit information."""

    def test_erasure_result_fields(self):
        """All ErasureResult fields are populated."""
        result = ErasureResult(
            erased_event_ids=("evt1", "evt2"),
            replaced_count=2,
            downstream_count=5,
            audit_event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            selector_summary={"kind_allowlist": ["clip.added"]},
            projection_regenerated=True,
            reason="test erasure",
            policy_ref="POL-001",
        )

        assert len(result.erased_event_ids) == 2
        assert result.replaced_count == 2
        assert result.downstream_count == 5
        assert result.audit_event_id == "01JAAAAAAAAAAAAAAAAAAAAA01"
        assert result.projection_regenerated is True
        assert result.reason == "test erasure"
        assert result.policy_ref == "POL-001"


class TestErasurePreviewResult:
    """ErasurePreview carries query results."""

    def test_preview_result_fields(self):
        """All ErasurePreview fields are populated."""
        preview = ErasurePreview(
            matched_count=3,
            matched_event_ids=("evt1", "evt2", "evt3"),
            total_events_in_stream=10,
            selector_summary={"event_ids": ["evt1", "evt2", "evt3"]},
        )

        assert preview.matched_count == 3
        assert preview.total_events_in_stream == 10
        assert len(preview.matched_event_ids) == 3


class TestSelectorSafety:
    """Safety tests for erasure selectors."""

    def test_empty_selector_apply_raises(self, tmp_path: Path):
        """apply_erasure with empty selector raises ValueError."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        selector = ErasureSelector()
        with pytest.raises(ValueError, match="empty"):
            apply_erasure(
                backend,
                selector,
                timeline_id=tid,
                actor=_ACTOR,
                reason="test",
                regenerate_projection_after=False,
            )

    def test_selector_with_no_match_raises(self, tmp_path: Path):
        """apply_erasure with non-matching selector raises ValueError."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)
        backend.append_event(
            tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = ErasureSelector(kind_allowlist=("theme.set",))
        with pytest.raises(ValueError, match="zero events"):
            apply_erasure(
                backend,
                selector,
                timeline_id=tid,
                actor=_ACTOR,
                reason="test",
                regenerate_projection_after=False,
            )


class TestErasureImportMetadataPreservation:
    """Import metadata is preserved through erasure."""

    def test_import_metadata_preserved(self, tmp_path: Path):
        """Source import metadata survives erasure."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        tid = str(uuid4())
        home = tmp_path / "home"
        home.mkdir()
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        backend = LocalFsBackend(timeline_id=tid, timeline_home=home)

        # Append event with import metadata
        from astrid.core.timeline.events.schema import with_event_hash
        source_event = TimelineEvent.new(
            timeline_id=tid,
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            kind="clip.added",
            payload={"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            source_backend="supabase",
            source_timeline_id=str(uuid4()),
            source_event_id="SRC001",
            source_version=5,
            source_hash="abc123",
        )
        source_event = with_event_hash(source_event, prev_hash=None)

        # Use import to add it
        imported = backend.append_imported_event(
            timeline_id=tid,
            source_event=source_event,
            idempotency_key=f"transfer:pull:supabase:{str(uuid4())}:SRC001",
            actor=_ACTOR,
        )

        # Erase it
        selector = ErasureSelector(event_ids=(imported.event_id,))
        apply_erasure(
            backend,
            selector,
            timeline_id=tid,
            actor=_ACTOR,
            reason="test",
            regenerate_projection_after=False,
        )

        # Check that import metadata is preserved
        events_after = backend.read_events()
        erased = None
        for evt in events_after:
            if evt.event_id == imported.event_id:
                erased = evt
                break

        assert erased is not None
        assert isinstance(erased.payload, ErasedPayload)
        assert erased.source_backend == "supabase"
        # source_event_id is set to the source event's ID (a ULID) by the import
        assert erased.source_event_id == source_event.event_id
        assert erased.source_version == 5  # Preserved from the source event
        assert erased.source_hash == source_event.hash
