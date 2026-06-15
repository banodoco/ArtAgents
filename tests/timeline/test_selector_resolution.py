"""Tests for eventlog selector resolution (T6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.eventlog.selector import (
    EventLogTarget,
    PullDestination,
    resolve_event_log_target,
    resolve_pull_destination,
)


class TestResolveEventLogTarget:
    """Tests for resolve_event_log_target()."""

    def test_local_resolution_no_supabase_env(
        self, tmp_path: Path, monkeypatch
    ):
        """Local commands work without SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY."""
        # Ensure no Supabase env vars
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        from astrid.core.timeline.observability import ResolvedTarget

        timeline_id = str(uuid4())
        home = tmp_path / "demo" / "timelines" / "01J00000000000000000000001"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000001",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )
        write_json_atomic(
            home / "display.json",
            {
                "schema_version": 1,
                "slug": "test-tl",
                "name": "Test Timeline",
                "timeline_id": timeline_id,
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        # Monkeypatch the local resolver
        import astrid.core.timeline.observability as obs_mod
        monkeypatch.setattr(
            obs_mod,
            "resolve_timeline_target",
            lambda *a, **kw: ResolvedTarget(
                backend="local_fs",
                timeline_id=timeline_id,
                timeline_ulid="01J00000000000000000000001",
                timeline_home=home,
                slug="test-tl",
                backend_name_display="local_fs",
            ),
        )

        # Monkeypatch project_dir to return our tmp_path
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        # Local resolution should work without Supabase env vars
        target = resolve_event_log_target("demo", "test-tl")
        assert isinstance(target, EventLogTarget)
        assert target.backend_name == "local_fs"
        assert target.source == "local"
        assert isinstance(target.backend, LocalFsBackend)

    def test_supabase_target_requires_credentials(
        self, tmp_path: Path, monkeypatch
    ):
        """Explicit Supabase target requires credentials."""
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

        with pytest.raises(ValueError, match="Supabase backend requires"):
            resolve_event_log_target(
                "demo",
                "some-stream-id",
                preferred_backend="supabase",
            )

    def test_supabase_target_with_credentials(
        self, tmp_path: Path, monkeypatch
    ):
        """Explicit Supabase target with credentials builds successfully."""
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        # Note: this will build a SupabaseBackend but not actually connect
        # because there's no transport — we just verify it doesn't crash
        target = resolve_event_log_target(
            "demo",
            "00000000-0000-0000-0000-000000000001",
            preferred_backend="supabase",
        )
        assert target.backend_name == "supabase"
        assert target.source == "supabase"
        # The backend will fail on actual operations (no transport),
        # but construction should succeed
        assert isinstance(target.backend, SupabaseBackend)


class TestResolvePullDestination:
    """Tests for resolve_pull_destination()."""

    def test_into_existing_slug(self, tmp_path: Path, monkeypatch):
        """--into <existing-slug> resolves to existing timeline."""

        timeline_id = str(uuid4())
        home = tmp_path / "demo" / "timelines" / "01J00000000000000000000001"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000001",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )
        write_json_atomic(
            home / "display.json",
            {
                "schema_version": 1,
                "slug": "existing-tl",
                "name": "Existing",
                "timeline_id": timeline_id,
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        dest = resolve_pull_destination("demo", into="existing-tl", root=tmp_path)
        assert isinstance(dest, PullDestination)
        assert dest.created is False
        assert dest.target.backend_name == "local_fs"
        assert dest.target.timeline_id == timeline_id

    def test_create_as_new_slug(self, tmp_path: Path, monkeypatch):
        """--create --as <new-slug> creates a new timeline home."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        dest = resolve_pull_destination(
            "demo",
            create=True,
            create_as="pulled-timeline",
            root=tmp_path,
        )
        assert dest.created is True
        assert dest.target.backend_name == "local_fs"
        assert dest.identity_path is not None
        assert dest.identity_path.exists()

        # Verify provenance: imported
        from astrid.core._shared.jsonio import read_json
        identity = read_json(dest.identity_path)
        assert identity["provenance"] == "imported"
        assert "source_timeline_id" not in identity  # None was passed
        assembly = read_json(dest.target.timeline_home / "assembly.json")
        assert assembly == {"clips": [], "tracks": []}

    def test_create_as_with_source_id(self, tmp_path: Path, monkeypatch):
        """--create --as with remote source timeline_id preserves it as canonical."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        remote_id = "00000000-0000-0000-0000-000000000099"
        dest = resolve_pull_destination(
            "demo",
            create=True,
            create_as="imported-tl",
            remote_source_timeline_id=remote_id,
            root=tmp_path,
        )
        assert dest.created is True

        from astrid.core._shared.jsonio import read_json
        identity = read_json(dest.identity_path)
        assert identity["provenance"] == "imported"
        # Remote UUID is preserved as canonical timeline_id
        assert identity["timeline_id"] == remote_id
        # source_timeline_id is audit provenance (may equal timeline_id per SD1)
        assert identity["source_timeline_id"] == remote_id
        # EventLogTarget reflects the canonical timeline_id
        assert dest.target.timeline_id == remote_id

    def test_create_as_duplicate_slug_fails(self, tmp_path: Path, monkeypatch):
        """--create --as with an existing slug fails before writing."""
        timeline_id = str(uuid4())
        home = tmp_path / "demo" / "timelines" / "01J00000000000000000000001"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "display.json",
            {
                "schema_version": 1,
                "slug": "existing-tl",
                "name": "Existing",
                "timeline_id": timeline_id,
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        with pytest.raises(ValueError, match="already exists"):
            resolve_pull_destination(
                "demo",
                create=True,
                create_as="existing-tl",
                root=tmp_path,
            )

    def test_ambiguous_destination_fails(self, tmp_path: Path, monkeypatch):
        """No --into, --create, or --as fails before writing."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        with pytest.raises(ValueError, match="requires a local destination"):
            resolve_pull_destination("demo", root=tmp_path)

    def test_implicit_create_with_valid_remote_slug(self, tmp_path: Path, monkeypatch):
        """--create with a valid remote slug creates implicitly."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        dest = resolve_pull_destination(
            "demo",
            create=True,
            remote_source_slug="remote-timeline-slug",
            root=tmp_path,
        )
        assert dest.created is True
        assert dest.target.slug == "remote-timeline-slug"

    def test_implicit_create_collision_fails(self, tmp_path: Path, monkeypatch):
        """--create with implicit slug that already exists fails."""
        timeline_id = str(uuid4())
        home = tmp_path / "demo" / "timelines" / "01J00000000000000000000001"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            home / "display.json",
            {
                "schema_version": 1,
                "slug": "remote-tl",
                "name": "Remote TL",
                "timeline_id": timeline_id,
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        with pytest.raises(ValueError, match="already exists"):
            resolve_pull_destination(
                "demo",
                create=True,
                remote_source_slug="remote-tl",
                root=tmp_path,
            )


    def test_implicit_create_preserves_remote_uuid(self, tmp_path: Path, monkeypatch):
        """--create (no --as) with remote_source_timeline_id preserves UUID."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        remote_id = "11111111-1111-1111-1111-111111111111"
        dest = resolve_pull_destination(
            "demo",
            create=True,
            remote_source_slug="remote-slug",
            remote_source_timeline_id=remote_id,
            root=tmp_path,
        )
        assert dest.created is True
        assert dest.target.slug == "remote-slug"

        from astrid.core._shared.jsonio import read_json
        identity = read_json(dest.identity_path)
        assert identity["provenance"] == "imported"
        # Remote UUID is preserved as canonical timeline_id
        assert identity["timeline_id"] == remote_id
        assert identity["source_timeline_id"] == remote_id
        assert dest.target.timeline_id == remote_id

    def test_implicit_create_without_remote_uuid_generates_fresh(
        self, tmp_path: Path, monkeypatch
    ):
        """--create (no --as) without remote_source_timeline_id generates a fresh UUID."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        dest = resolve_pull_destination(
            "demo",
            create=True,
            remote_source_slug="fresh-slug",
            # No remote_source_timeline_id
            root=tmp_path,
        )
        assert dest.created is True

        from uuid import UUID

        from astrid.core._shared.jsonio import read_json
        identity = read_json(dest.identity_path)
        # A fresh UUID is generated
        fresh_id = identity["timeline_id"]
        UUID(fresh_id)  # Must be valid UUID format
        assert "source_timeline_id" not in identity
        assert dest.target.timeline_id == fresh_id

    def test_create_as_without_remote_uuid_generates_fresh(
        self, tmp_path: Path, monkeypatch
    ):
        """--create --as without remote_source_timeline_id generates a fresh UUID."""
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        dest = resolve_pull_destination(
            "demo",
            create=True,
            create_as="fresh-as-slug",
            # No remote_source_timeline_id
            root=tmp_path,
        )
        assert dest.created is True

        from uuid import UUID

        from astrid.core._shared.jsonio import read_json
        identity = read_json(dest.identity_path)
        fresh_id = identity["timeline_id"]
        UUID(fresh_id)
        assert "source_timeline_id" not in identity
        assert dest.target.timeline_id == fresh_id


class TestSelfReferentSourceTimelineId:
    """SD1: source_timeline_id is audit provenance only and may equal
    timeline_id.  These tests verify that identity readers and pull-destination
    creation handle self-referent source_timeline_id correctly.
    """

    def test_identity_with_equal_source_and_timeline_id(
        self, tmp_path: Path, monkeypatch
    ):
        """An identity sidecar where source_timeline_id == timeline_id
        is valid and must not break the resolver.
        """
        timeline_id = str(uuid4())
        home = tmp_path / "demo" / "timelines" / "01J00000000000000000000001"
        home.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
        # Deliberately set source_timeline_id equal to timeline_id (SD1)
        write_json_atomic(
            home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000001",
                "backend": "local_fs",
                "provenance": "imported",
                "source_timeline_id": timeline_id,
                "created_at": "2026-05-21T00:00:00Z",
            },
        )
        write_json_atomic(
            home / "display.json",
            {
                "schema_version": 1,
                "slug": "self-ref",
                "name": "Self Referent",
                "timeline_id": timeline_id,
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        # Resolving a pull destination should work even with self-referent
        # source_timeline_id — no exception, no identity confusion.
        dest = resolve_pull_destination("demo", into="self-ref", root=tmp_path)
        assert dest.target.timeline_id == timeline_id
        assert dest.created is False

    def test_create_as_reads_back_self_referent_identity(
        self, tmp_path: Path, monkeypatch
    ):
        """Create a pull destination with a remote source timeline_id,
        then read back the identity and verify source_timeline_id is present
        and does not confuse any consumer.
        """
        import astrid.core.foundation.project_paths as proj_paths
        monkeypatch.setattr(
            proj_paths,
            "project_dir",
            lambda slug, root=None: tmp_path / slug,
        )

        remote_id = "00000000-0000-0000-0000-000000000042"
        dest = resolve_pull_destination(
            "demo",
            create=True,
            create_as="imported-self-ref",
            remote_source_timeline_id=remote_id,
            root=tmp_path,
        )
        assert dest.created is True

        from astrid.core._shared.jsonio import read_json
        identity = read_json(dest.identity_path)
        assert identity["provenance"] == "imported"
        assert identity["source_timeline_id"] == remote_id
        # With T3, the remote UUID is preserved as the canonical timeline_id
        assert identity["timeline_id"] == remote_id
        # Per SD1, source_timeline_id may equal timeline_id — callers must not break.

        # Verify the EventLogTarget source field reflects imported origin
        assert dest.target.source == "imported"
        assert dest.target.timeline_id == identity["timeline_id"]
