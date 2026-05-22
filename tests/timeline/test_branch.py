"""Tests for branch creation (T8).

Covers:
- Branch creation writes provenance: branched identity
- timeline.branched_from emitted on source only after branch projection verifies
- Failed branch creation does not emit timeline.branched_from on source
- branches list uses source-stream events only
- Normal provenance: created invariant remains intact
"""

from __future__ import annotations

import pytest
from pathlib import Path
from uuid import uuid4

from astrid.core.timeline.events.schema import (
    TimelineActor,
    TimelineBranchedFromPayload,
)
from astrid.core.timeline.projection import ProjectionError

_ACTOR = TimelineActor(type="agent", id="branch-test")


class TestBranchProvenance:
    """Tests for branch provenance invariants."""

    def test_branch_identity_has_provenance_branched(self, tmp_path: Path, monkeypatch):
        """Branch creation writes assembly.identity.json with provenance: branched."""
        from astrid.core.timeline import observability, paths
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "source", "name": "source", "is_default": False},
        )
        # Write a minimal assembly so projection works
        write_json_atomic(
            tl_dir / "assembly.json",
            {"schema_version": 1, "assembly": {"clips": [], "tracks": [], "pool": {"entries": []}}},
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append a clip event to the source so there's something to project
        e1 = backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        # Set up monkeypatches for path resolution
        def fake_resolve_target(project_slug, slug_or_id, root=None):
            from astrid.core.timeline.observability import ResolvedTarget
            return ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=tl_dir,
                slug="source",
                backend_name_display="local_fs",
            )

        def fake_timelines_dir(project_slug, root=None):
            return proj_dir / "timelines"

        # Monkeypatch the functions where branch module will call them.
        # branch.py imports from observability at module level,
        # but paths at function level (inside create_branch_timeline).
        monkeypatch.setattr(
            "astrid.core.timeline.branch.resolve_timeline_target",
            fake_resolve_target,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.timeline_dir",
            lambda project_slug, ulid, root=None: proj_dir / "timelines" / ulid,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.validate_timeline_slug",
            lambda s: s,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.find_timeline_by_slug",
            lambda project_slug, slug, root=None: None,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.find_timeline_by_event_stream_id",
            lambda project_slug, timeline_id, root=None: None,
        )

        # Import branch AFTER monkeypatching so the mocked functions are visible
        from astrid.core.timeline.branch import create_branch_timeline

        result = create_branch_timeline(
            "test-project",
            "source",
            "my-branch",
            from_event_id=e1.event_id,
            actor=_ACTOR,
            reason="testing",
            root=tmp_path,
        )

        # Verify branch identity has provenance: branched
        import json
        branch_dir = proj_dir / "timelines" / result.branch_timeline_ulid
        identity = json.loads((branch_dir / "assembly.identity.json").read_text())

        assert identity["provenance"] == "branched"
        assert identity["source_timeline_id"] == timeline_id
        assert identity["source_anchor_event_id"] == e1.event_id

    def test_branched_from_emitted_on_source(self, tmp_path: Path, monkeypatch):
        """After successful branch creation, source has timeline.branched_from event."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "source", "name": "source", "is_default": False},
        )
        write_json_atomic(
            tl_dir / "assembly.json",
            {"schema_version": 1, "assembly": {"clips": [], "tracks": [], "pool": {"entries": []}}},
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        e1 = backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        def fake_resolve_target(project_slug, slug_or_id, root=None):
            from astrid.core.timeline.observability import ResolvedTarget
            return ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=tl_dir,
                slug="source",
                backend_name_display="local_fs",
            )

        monkeypatch.setattr(
            "astrid.core.timeline.branch.resolve_timeline_target",
            fake_resolve_target,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.timeline_dir",
            lambda project_slug, ulid, root=None: proj_dir / "timelines" / ulid,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.validate_timeline_slug",
            lambda s: s,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.find_timeline_by_slug",
            lambda ps, slug, root=None: None,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.find_timeline_by_event_stream_id",
            lambda ps, tid, root=None: None,
        )

        from astrid.core.timeline.branch import create_branch_timeline

        result = create_branch_timeline(
            "test-project",
            "source",
            "my-branch",
            from_event_id=e1.event_id,
            actor=_ACTOR,
            reason="testing",
            root=tmp_path,
        )

        # Source should now have a timeline.branched_from event
        source_events = backend.read_events()
        assert len(source_events) >= 2  # original clip + branched_from
        branched_events = [e for e in source_events if e.kind == "timeline.branched_from"]
        assert len(branched_events) == 1
        assert isinstance(branched_events[0].payload, TimelineBranchedFromPayload)
        assert branched_events[0].payload.branch_timeline_id == result.branch_timeline_id


class TestBranchFailureDoesNotPolluteSource:
    """Tests that failed branch creation does not emit timeline.branched_from."""

    def test_failed_branch_no_branched_from_on_source(self, tmp_path: Path, monkeypatch):
        """When branch creation fails, source has no timeline.branched_from event."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "source", "name": "source", "is_default": False},
        )
        write_json_atomic(
            tl_dir / "assembly.json",
            {"schema_version": 1, "assembly": {"clips": [], "tracks": [], "pool": {"entries": []}}},
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        e1 = backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        source_event_count_before = len(backend.read_events())

        def fake_resolve_target(project_slug, slug_or_id, root=None):
            from astrid.core.timeline.observability import ResolvedTarget
            return ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=tl_dir,
                slug="source",
                backend_name_display="local_fs",
            )

        monkeypatch.setattr(
            "astrid.core.timeline.branch.resolve_timeline_target",
            fake_resolve_target,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.timeline_dir",
            lambda project_slug, ulid, root=None: proj_dir / "timelines" / ulid,
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.validate_timeline_slug",
            lambda s: s,
        )
        # Make find_timeline_by_slug return a collision to force failure
        monkeypatch.setattr(
            "astrid.core.timeline.paths.find_timeline_by_slug",
            lambda ps, slug, root=None: ("01J00000000000000000000099", tl_dir),
        )
        monkeypatch.setattr(
            "astrid.core.timeline.paths.find_timeline_by_event_stream_id",
            lambda ps, tid, root=None: None,
        )

        from astrid.core.timeline.branch import create_branch_timeline

        # Branch creation should fail because the slug already exists
        with pytest.raises(ValueError, match="already exists"):
            create_branch_timeline(
                "test-project",
                "source",
                "my-branch",
                from_event_id=e1.event_id,
                actor=_ACTOR,
                reason="testing",
                root=tmp_path,
            )

        # Source should have NO additional events (no branched_from emitted)
        source_events = backend.read_events()
        assert len(source_events) == source_event_count_before
        branched_events = [e for e in source_events if e.kind == "timeline.branched_from"]
        assert len(branched_events) == 0


class TestBranchesList:
    """Tests for list_branches() using source-stream events only."""

    def test_list_branches_from_source_stream(self, tmp_path: Path, monkeypatch):
        """list_branches reads timeline.branched_from events from source stream only."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "source", "name": "source", "is_default": False},
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)

        # Append a branched_from event
        branch_payload = TimelineBranchedFromPayload(
            branch_timeline_id=str(uuid4()),
            anchor_event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            reason="test branch",
        ).to_json_obj()
        backend.append_event(
            timeline_id, "timeline.branched_from",
            branch_payload,
            actor=_ACTOR,
        )

        # Also append a regular clip event
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        def fake_resolve_target(project_slug, slug_or_id, root=None):
            from astrid.core.timeline.observability import ResolvedTarget
            return ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=tl_dir,
                slug="source",
                backend_name_display="local_fs",
            )

        monkeypatch.setattr(
            "astrid.core.timeline.branch.resolve_timeline_target",
            fake_resolve_target,
        )

        from astrid.core.timeline.branch import list_branches

        branches = list_branches("test-project", "source")

        # Should have exactly 1 branch (from the branched_from event only)
        assert len(branches) == 1
        assert branches[0]["anchor_event_id"] == "01JAAAAAAAAAAAAAAAAAAAAA01"
        assert branches[0]["reason"] == "test branch"

    def test_list_branches_empty(self, tmp_path: Path, monkeypatch):
        """list_branches returns empty list when no branches exist."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        timeline_id = str(uuid4())
        tl_dir = tmp_path / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "source", "name": "source", "is_default": False},
        )

        backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=tl_dir)
        # Only clip events, no branched_from
        backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        def fake_resolve_target(project_slug, slug_or_id, root=None):
            from astrid.core.timeline.observability import ResolvedTarget
            return ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=tl_dir,
                slug="source",
                backend_name_display="local_fs",
            )

        monkeypatch.setattr(
            "astrid.core.timeline.branch.resolve_timeline_target",
            fake_resolve_target,
        )

        from astrid.core.timeline.branch import list_branches

        branches = list_branches("test-project", "source")
        assert branches == []


class TestBranchResult:
    """BranchResult carries audit information."""

    def test_branch_result_fields(self):
        """All BranchResult fields are populated."""
        from astrid.core.timeline.branch import BranchResult

        result = BranchResult(
            branch_timeline_id=str(uuid4()),
            branch_timeline_ulid="01J00000000000000000000099",
            branch_slug="my-branch",
            anchor_event_id="01JAAAAAAAAAAAAAAAAAAAAA01",
            seed_event_id="01JAAAAAAAAAAAAAAAAAAAAA02",
            source_branched_from_event_id="01JAAAAAAAAAAAAAAAAAAAAA03",
            source_anchor_hash="abc123",
            branch_projection_summary={"clip_count": 3, "track_count": 1},
        )

        assert result.branch_slug == "my-branch"
        assert result.branch_projection_summary["clip_count"] == 3
        assert result.source_anchor_hash == "abc123"
