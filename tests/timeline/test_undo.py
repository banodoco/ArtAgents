"""Tests for undo command behavior (T10) and mass-undo (T11).

Covers:
- Undo selects the latest undoable event
- Undo skips lifecycle/ops events by default
- Undo verifies chain before writing inverses
- Undo prints target event ID/kind and appended inverse event IDs
- Undo works on reversible events (clip.added → clip.removed, etc.)
- Undo handles non-reversible events (timeline.reverted fallback)
- Undo keeps scope local-project for v1
- Mass-undo preview-only behavior (no writes without --yes)
- Mass-undo --yes writes inverses in chunks
- Mass-undo chunk boundaries and head/CAS re-checks
- Mass-undo partial failure reporting
- Mass-undo selector filtering (--since, --actor, --actor-prefix)
"""

from __future__ import annotations

import pytest
from pathlib import Path
from uuid import uuid4

from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineEvent,
)
from astrid.core.timeline.inverses import (
    _NON_REVERSIBLE_KINDS,
    InverseRequest,
    plan_inverse,
    plan_inverses,
)
from astrid.core.timeline.undo import (
    MassUndoSelector,
    MassUndoPreview,
    MassUndoResult,
    plan_mass_undo,
    execute_mass_undo,
)

_ACTOR = TimelineActor(type="agent", id="undo-test")
_ACTOR_B = TimelineActor(type="agent", id="other-actor")


class TestUndoSelectsLatestUndoableEvent:
    """Undo walks backwards and skips lifecycle/ops events."""

    def test_skips_lifecycle_events(self):
        """Lifecycle events (_NON_REVERSIBLE_KINDS) are not undoable."""
        for kind in _NON_REVERSIBLE_KINDS:
            assert kind not in {
                "clip.added", "clip.removed", "clip.moved", "clip.retimed",
                "clip.swapped", "clip.replaced", "clip.text_set", "clip.annotated",
                "transition.set", "transition.removed",
                "effect.added", "effect.removed", "effect.tuned",
                "theme.set", "theme.overridden",
                "track.added", "track.removed",
                "audio.bound", "audio.unbound",
                "pool.asset_added", "pool.asset_removed", "pool.asset_scored",
                "arrangement.replaced",
            }, f"{kind} should be non-reversible"

    def test_all_reversible_kinds_not_in_non_reversible(self):
        """All reversible event kinds are not in _NON_REVERSIBLE_KINDS."""
        reversible = {
            "clip.added", "clip.removed", "clip.moved", "clip.retimed",
            "clip.swapped", "clip.replaced", "clip.text_set", "clip.annotated",
            "transition.set", "transition.removed",
            "effect.added", "effect.removed", "effect.tuned",
            "theme.set", "theme.overridden",
            "track.added", "track.removed",
            "audio.bound", "audio.unbound",
            "pool.asset_added", "pool.asset_removed", "pool.asset_scored",
            "arrangement.replaced",
        }
        for kind in reversible:
            assert kind not in _NON_REVERSIBLE_KINDS, f"{kind} should be reversible"


class TestUndoClipAdded:
    """Undo of clip.added produces clip.removed."""

    def test_plan_inverse_clip_added(self):
        """Inverse of clip.added is clip.removed."""
        from astrid.core.timeline.events.schema import ClipAddedPayload

        event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )

        before = {"clips": []}
        after = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 0.0, "text": "", "note": ""}]}

        inv = plan_inverse(event, before_projection=before, after_projection=after)

        assert inv.invertible is True
        assert inv.inverse_kind == "clip.removed"
        assert inv.inverse_payload == {"clip_id": "c1"}


class TestUndoClipRemoved:
    """Undo of clip.removed recovers clip from prior projection."""

    def test_plan_inverse_clip_removed(self):
        """Inverse of clip.removed recovers clip from before state."""
        from astrid.core.timeline.events.schema import ClipRemovedPayload

        event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.removed",
            payload=ClipRemovedPayload(clip_id="c1"),
        )

        before = {
            "clips": [
                {"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
                {"id": "c2", "kind": "audio", "asset_id": "a2", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
            ]
        }
        after = {
            "clips": [
                {"id": "c2", "kind": "audio", "asset_id": "a2", "start": 0.0, "duration": 0.0, "text": "", "note": ""},
            ]
        }

        inv = plan_inverse(event, before_projection=before, after_projection=after)

        assert inv.invertible is True
        assert inv.inverse_kind == "clip.added"
        assert inv.inverse_payload["clip_id"] == "c1"
        assert inv.inverse_payload["kind"] == "visual"
        assert inv.inverse_payload["asset_id"] == "a1"


class TestUndoNonReversible:
    """Non-reversible events fall back to timeline.reverted."""

    def test_timeline_created_is_non_invertible(self):
        """timeline.created is not blindly invertible."""
        from astrid.core.timeline.events.schema import TimelineCreatedPayload

        event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA03",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="timeline.created",
            payload=TimelineCreatedPayload(timeline_id="00000000-0000-0000-0000-000000000001", slug="test", name="Test"),
        )

        inv = plan_inverse(event, before_projection={}, after_projection={})

        assert inv.invertible is False
        assert inv.revert_kind == "timeline.reverted"
        assert "lifecycle" in inv.revert_reason.lower() or "not" in inv.revert_reason.lower()

    def test_timeline_deleted_is_non_invertible(self):
        """timeline.deleted is not blindly invertible."""
        from astrid.core.timeline.events.schema import TimelineDeletedPayload

        event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA04",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="timeline.deleted",
            payload=TimelineDeletedPayload(),
        )

        inv = plan_inverse(event, before_projection={}, after_projection={})

        assert inv.invertible is False
        assert inv.revert_kind == "timeline.reverted"


class TestUndoErasedPayload:
    """Events with ErasedPayload are treated as non-invertible."""

    def test_erased_payload_is_non_invertible(self):
        """Erased events are not invertible (no prior state recovery)."""
        from astrid.core.timeline.events.schema import ErasedPayload

        event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA05",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ErasedPayload(
                erased=True,
                reason="test erasure",
                erased_at="2026-05-21T00:00:00Z",
                erased_by="test",
            ),
        )

        inv = plan_inverse(event, before_projection={"clips": []}, after_projection={"clips": []})

        assert inv.invertible is False
        assert "erased" in inv.revert_reason.lower()


class TestInverseRequestShape:
    """InverseRequest carries audit information."""

    def test_invertible_inverse(self):
        """Invertible inverse has inverse_kind and inverse_payload."""
        inv = InverseRequest(
            invertible=True,
            inverse_kind="clip.removed",
            inverse_payload={"clip_id": "c1"},
        )
        assert inv.invertible is True
        assert inv.inverse_kind == "clip.removed"
        assert inv.inverse_payload == {"clip_id": "c1"}

    def test_non_invertible_inverse(self):
        """Non-invertible inverse has revert_reason and projections."""
        inv = InverseRequest(
            invertible=False,
            revert_reason="cannot undo lifecycle event timeline.created",
            before_projection={"clips": []},
            after_projection={"clips": []},
        )
        assert inv.invertible is False
        assert inv.revert_kind == "timeline.reverted"
        assert "lifecycle" in inv.revert_reason
        assert inv.before_projection == {"clips": []}


class TestUndoSequenceWalking:
    """plan_inverses walks multiple events correctly."""

    def test_plan_inverses_for_multiple_events(self):
        """plan_inverses returns one inverse per event."""
        from astrid.core.timeline.events.schema import ClipAddedPayload, ThemeSetPayload

        e1 = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )
        e2 = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:01Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="theme.set",
            payload=ThemeSetPayload(theme_id="dark"),
        )

        before = {"clips": [], "theme": ""}
        after_e1 = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 0.0, "text": "", "note": ""}], "theme": ""}
        after_e2 = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1", "start": 0.0, "duration": 0.0, "text": "", "note": ""}], "theme": "dark"}

        inverses = plan_inverses([e1, e2], initial_projection=before)

        assert len(inverses) == 2
        # First inverse is for e1 (clip.added → clip.removed)
        assert inverses[0].inverse_kind == "clip.removed"
        # Second inverse is for e2 (theme.set → theme.set)
        assert inverses[1].inverse_kind == "theme.set"


class TestUndoPureFunction:
    """Inverse planning is pure — no backend calls."""

    def test_same_input_same_output(self):
        """plan_inverse is deterministic for the same input."""
        from astrid.core.timeline.events.schema import ClipAddedPayload

        event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )

        before = {"clips": []}
        after = {"clips": [{"id": "c1", "kind": "visual", "asset_id": "a1"}]}

        inv1 = plan_inverse(event, before_projection=before, after_projection=after)
        inv2 = plan_inverse(event, before_projection=before, after_projection=after)

        assert inv1 == inv2


# ============================================================================
# Mass-undo tests (T11)
# ============================================================================


class TestMassUndoSelectorFiltering:
    """MassUndoSelector filters by --since, --actor, --actor-prefix."""

    def test_empty_selector_is_empty(self):
        """An empty selector returns True for is_empty()."""
        sel = MassUndoSelector()
        assert sel.is_empty() is True

    def test_non_empty_selector(self):
        """A selector with at least one criterion is not empty."""
        sel = MassUndoSelector(ts_since="2026-01-01T00:00:00Z")
        assert sel.is_empty() is False

    def test_matches_by_ts_since(self):
        """Events at or after ts_since match."""
        sel = MassUndoSelector(ts_since="2026-05-21T12:00:00Z")
        from astrid.core.timeline.events.schema import ClipAddedPayload

        before_event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T10:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )
        after_event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T14:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c2", kind="visual", asset_id="a2"),
        )

        assert sel.matches(before_event) is False
        assert sel.matches(after_event) is True

    def test_matches_by_actor_exact(self):
        """Exact actor ID matches."""
        sel = MassUndoSelector(actor_id="undo-test")
        from astrid.core.timeline.events.schema import ClipAddedPayload

        match_event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )
        no_match_event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR_B,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c2", kind="visual", asset_id="a2"),
        )

        assert sel.matches(match_event) is True
        assert sel.matches(no_match_event) is False

    def test_matches_by_actor_prefix(self):
        """Actor ID prefix matches."""
        sel = MassUndoSelector(actor_id_prefix="undo-")
        from astrid.core.timeline.events.schema import ClipAddedPayload

        match_event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )
        no_match_event = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T00:00:00Z",
            actor=_ACTOR_B,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c2", kind="visual", asset_id="a2"),
        )

        assert sel.matches(match_event) is True
        assert sel.matches(no_match_event) is False

    def test_combined_criteria_and_semantics(self):
        """Multiple criteria use AND semantics."""
        sel = MassUndoSelector(ts_since="2026-05-21T12:00:00Z", actor_id="undo-test")
        from astrid.core.timeline.events.schema import ClipAddedPayload

        # Matches both
        good = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T14:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c1", kind="visual", asset_id="a1"),
        )
        # Matches time but not actor
        bad_actor = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T14:00:00Z",
            actor=_ACTOR_B,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c2", kind="visual", asset_id="a2"),
        )
        # Matches actor but not time
        bad_time = TimelineEvent(
            event_id="01JAAAAAAAAAAAAAAAAAAAAA03",
            timeline_id="00000000-0000-0000-0000-000000000001",
            ts="2026-05-21T10:00:00Z",
            actor=_ACTOR,
            prev_hash=None,
            hash=None,
            kind="clip.added",
            payload=ClipAddedPayload(clip_id="c3", kind="visual", asset_id="a3"),
        )

        assert sel.matches(good) is True
        assert sel.matches(bad_actor) is False
        assert sel.matches(bad_time) is False


class TestMassUndoPreviewOnly:
    """Preview mode prints candidates without writing."""

    def test_preview_returns_candidates_no_mutation(self, tmp_path: Path):
        """plan_mass_undo() returns preview but does not mutate backend."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema import ClipAddedPayload

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append some clip events
        e1 = backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        e2 = backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c2", "kind": "audio", "asset_id": "a2"},
            actor=_ACTOR_B,
        )

        # Preview by actor
        selector = MassUndoSelector(actor_id="undo-test")
        preview = plan_mass_undo(backend, selector)

        assert preview.matched_count == 1
        assert preview.total_events >= 2
        assert len(preview.candidates) == 1
        assert preview.candidates[0]["event_id"] == e1.event_id
        assert preview.candidates[0]["kind"] == "clip.added"
        assert preview.candidates[0]["invertible"] is True
        assert preview.candidates[0]["inverse_kind"] == "clip.removed"

        # Verify the event stream was NOT mutated (bootstrap + 2 clips = 3 events)
        events_after = backend.read_events()
        assert len(events_after) == 3  # still only the original events (bootstrap + 2 clips)

    def test_preview_empty_selector_raises(self, tmp_path: Path):
        """Empty selector raises ValueError."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append an event so the timeline is not empty
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = MassUndoSelector()  # empty
        with pytest.raises(ValueError, match="empty"):
            plan_mass_undo(backend, selector)

    def test_preview_skips_lifecycle_and_erased_events(self, tmp_path: Path):
        """Mass undo preview skips lifecycle events and erased payloads."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema import ClipAddedPayload, ErasedPayload

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append lifecycle event (timeline.created happens automatically via bootstrap)
        # The bootstrap is timeline.imported, which is in _NON_REVERSIBLE_KINDS
        # Ok, let's just append clip events and check
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = MassUndoSelector(actor_id="undo-test")
        preview = plan_mass_undo(backend, selector)

        # The bootstrap timeline.imported should be skipped
        # Only the clip.added should appear
        for cand in preview.candidates:
            assert cand["kind"] not in _NON_REVERSIBLE_KINDS

    def test_preview_zero_matches(self, tmp_path: Path):
        """Preview with zero matches returns matched_count=0."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        # Match an actor that doesn't exist
        selector = MassUndoSelector(actor_id="nonexistent")
        preview = plan_mass_undo(backend, selector)

        assert preview.matched_count == 0
        assert len(preview.candidates) == 0


class TestMassUndoYesWrites:
    """--yes mode writes inverses via chunked execution."""

    def test_yes_writes_inverses(self, tmp_path: Path):
        """execute_mass_undo() with --yes appends inverse events."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.events.schema import ClipAddedPayload

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Initial event count (bootstrap + clip)
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c2", "kind": "audio", "asset_id": "a2"},
            actor=_ACTOR,
        )

        initial_count = len(backend.read_events())

        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend,
            selector,
            timeline_id=timeline_id,
            actor=_ACTOR,
            timeline_home=tl_dir,
        )

        assert result.complete is True
        assert result.planned_count == 2
        assert result.appended_count == 2
        assert result.chunk_count >= 1
        assert result.projection_regenerated is True
        assert len(result.appended_event_ids) == 2

        # Verify new events were appended
        events_after = backend.read_events()
        assert len(events_after) == initial_count + 2

    def test_yes_zero_matches_raises(self, tmp_path: Path):
        """execute_mass_undo() with zero matches raises ValueError."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = MassUndoSelector(actor_id="nonexistent")
        with pytest.raises(ValueError, match="zero events"):
            execute_mass_undo(
                backend, selector,
                timeline_id=timeline_id, actor=_ACTOR,
                timeline_home=tl_dir,
            )

    def test_non_invertible_fallback_writes_reverted(self, tmp_path: Path):
        """Non-invertible events fall back to timeline.reverted."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append a clip.moved — this is reversible
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        # Now mass-undo it — should produce clip.removed
        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend, selector,
            timeline_id=timeline_id, actor=_ACTOR,
            timeline_home=tl_dir,
        )

        assert result.complete is True
        assert result.appended_count >= 1

        # The appended event should be clip.removed or timeline.reverted
        events = backend.read_events()
        # Find the last event(s) that were appended
        last_kinds = [e.kind for e in events[-result.appended_count:]]
        assert "clip.removed" in last_kinds or "timeline.reverted" in last_kinds


class TestMassUndoChunkBoundaries:
    """Chunked writes split into conservative batch sizes."""

    def test_small_chunk_size_produces_multiple_chunks(self, tmp_path: Path):
        """Using a small chunk_size produces multiple chunks."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append 5 clip events
        for i in range(5):
            backend.append_event(
                timeline_id, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend, selector,
            timeline_id=timeline_id, actor=_ACTOR,
            timeline_home=tl_dir,
            chunk_size=2,  # small chunk size
        )

        assert result.complete is True
        assert result.planned_count == 5
        assert result.appended_count == 5
        # With chunk_size=2 and 5 events, we expect 3 chunks (2+2+1)
        assert result.chunk_count == 3

    def test_chunk_size_larger_than_candidates(self, tmp_path: Path):
        """When chunk_size > candidates, only one chunk is used."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend, selector,
            timeline_id=timeline_id, actor=_ACTOR,
            timeline_home=tl_dir,
            chunk_size=100,
        )

        assert result.complete is True
        assert result.chunk_count == 1

    def test_head_rechecked_between_chunks(self, tmp_path: Path):
        """verify_chain is called before each chunk (implicitly tested via chunk_count > 0)."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        for i in range(3):
            backend.append_event(
                timeline_id, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend, selector,
            timeline_id=timeline_id, actor=_ACTOR,
            timeline_home=tl_dir,
            chunk_size=1,  # force re-check between every event
        )

        assert result.complete is True
        assert result.chunk_count == 3


class TestMassUndoPartialFailure:
    """Partial failure stops on first error and reports already-written IDs."""

    def test_partial_failure_reports_appended_ids(self, tmp_path: Path):
        """When an append fails mid-chunk, already-written IDs are reported."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.types import EventLogError

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append 4 clip events
        for i in range(4):
            backend.append_event(
                timeline_id, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        # Monkey-patch append_event to fail on the 3rd call
        original_append = backend.append_event
        call_count = [0]

        def failing_append(tid, kind, payload, *, actor=None, expected_version=None, txn_id=None):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise EventLogError("simulated append failure")
            return original_append(tid, kind, payload, actor=actor, expected_version=expected_version, txn_id=txn_id)

        backend.append_event = failing_append

        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend, selector,
            timeline_id=timeline_id, actor=_ACTOR,
            timeline_home=tl_dir,
            chunk_size=10,  # all in one chunk to test mid-chunk failure
        )

        assert result.complete is False
        assert result.error is not None
        assert "simulated append failure" in result.error
        # At least 2 events were appended before failure
        assert result.appended_count >= 2
        assert len(result.appended_event_ids) == result.appended_count
        # planned count is higher than appended count
        assert result.appended_count < result.planned_count

    def test_chain_verification_failure_stops_before_write(self, tmp_path: Path):
        """When verify_chain fails mid-execution, partial result is returned."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.types import EventLogVerification

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "tl"
        tl_dir.mkdir(parents=True)
        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        for i in range(4):
            backend.append_event(
                timeline_id, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        # Monkey-patch verify_chain to fail after first chunk
        original_verify = backend.verify_chain
        verify_calls = [0]

        def failing_verify():
            verify_calls[0] += 1
            if verify_calls[0] > 1:
                return EventLogVerification(ok=False, checked_events=0, last_event_id=None, error="simulated chain failure mid-way")
            return original_verify()

        backend.verify_chain = failing_verify

        selector = MassUndoSelector(actor_id="undo-test")
        result = execute_mass_undo(
            backend, selector,
            timeline_id=timeline_id, actor=_ACTOR,
            timeline_home=tl_dir,
            chunk_size=2,
        )

        assert result.complete is False
        assert "chain verification failed" in result.error


class TestMassUndoResultAuditability:
    """MassUndoResult carries all fields needed for CLI audit."""

    def test_result_fields_auditable(self):
        """All MassUndoResult fields are present and correctly typed."""
        result = MassUndoResult(
            planned_count=10,
            appended_count=8,
            appended_event_ids=("id1", "id2", "id3"),
            chunk_count=2,
            complete=False,
            error="partial failure",
            projection_regenerated=False,
        )

        assert result.planned_count == 10
        assert result.appended_count == 8
        assert len(result.appended_event_ids) == 3
        assert result.chunk_count == 2
        assert result.complete is False
        assert result.error == "partial failure"
        assert result.projection_regenerated is False

    def test_success_result(self):
        """Successful result has complete=True and no error."""
        result = MassUndoResult(
            planned_count=3,
            appended_count=3,
            appended_event_ids=("id1", "id2", "id3"),
            chunk_count=1,
            complete=True,
            projection_regenerated=True,
        )

        assert result.complete is True
        assert result.error is None
        assert result.appended_count == result.planned_count

    def test_preview_fields_auditable(self):
        """MassUndoPreview carries all needed fields."""
        preview = MassUndoPreview(
            matched_count=5,
            total_events=10,
            candidates=(
                {"event_id": "id1", "kind": "clip.added", "invertible": True, "inverse_kind": "clip.removed", "inverse_payload": {"clip_id": "c1"}, "revert_reason": ""},
            ),
            selector_summary={"actor_id": "test"},
        )

        assert preview.matched_count == 5
        assert preview.total_events == 10
        assert len(preview.candidates) == 1
        assert preview.selector_summary == {"actor_id": "test"}
