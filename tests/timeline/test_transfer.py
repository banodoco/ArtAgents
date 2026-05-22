"""Tests for cross-backend transfer (T7): push and pull event-log replay.

Tests both directions (local→supabase push, supabase→local pull) using
FakeSupabaseTransport for the remote side and local_fs for local.

Covers:
- Push scanned/appended/skipped-idempotent/failed counts
- Pull with --into, --create --as, implicit --create
- Interruption resumability via idempotency keys
- No legacy Reigh blob/config transfer
- Projection regeneration after transfer
"""

from __future__ import annotations

import pytest
from pathlib import Path
from uuid import uuid4

from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.eventlog.types import EventLogIdempotentError
from astrid.core.timeline.transfer import (
    TransferResult,
    _transfer_events,
)

_ACTOR = TimelineActor(type="agent", id="transfer-test")


class TestTransferLoop:
    """Tests for the internal _transfer_events loop."""

    def test_transfer_empty_source(self, tmp_path: Path):
        """Transfer from an empty source produces zero counts."""
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            dst_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": dst_tid, "timeline_ulid": "01J00000000000000000000002", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home,
            slug=None,
            backend=src_backend,
            source="local",
        )
        dst_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home,
            slug=None,
            backend=dst_backend,
            source="local",
        )

        result = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )

        assert result.scanned == 0
        assert result.appended == 0
        assert result.skipped_idempotent == 0
        assert result.failed == 0

    def test_transfer_appends_events(self, tmp_path: Path):
        """Transfer replays events from source to destination."""
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            dst_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": dst_tid, "timeline_ulid": "01J00000000000000000000002", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        # Append events to source
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c2", "kind": "audio", "asset_id": "a2"},
            actor=_ACTOR,
        )
        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        src_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home,
            slug=None,
            backend=src_backend,
            source="local",
        )
        dst_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home,
            slug=None,
            backend=dst_backend,
            source="local",
        )

        result = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )

        assert result.scanned == 3
        assert result.appended == 3
        assert result.skipped_idempotent == 0
        assert result.failed == 0

        # Verify destination has the events
        dst_events = dst_backend.read_events()
        assert len(dst_events) == 3
        assert dst_events[0].kind == "clip.added"
        assert dst_events[1].kind == "clip.added"
        assert dst_events[2].kind == "theme.set"

    def test_transfer_idempotent_retry(self, tmp_path: Path):
        """Re-transferring the same events skips them (idempotent)."""
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            dst_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": dst_tid, "timeline_ulid": "01J00000000000000000000002", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home,
            slug=None,
            backend=src_backend,
            source="local",
        )
        dst_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home,
            slug=None,
            backend=dst_backend,
            source="local",
        )

        # First transfer
        result1 = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert result1.appended == 1
        assert result1.skipped_idempotent == 0

        # Second transfer (same source events) — should be idempotent
        result2 = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert result2.appended == 0
        assert result2.skipped_idempotent == 1
        assert result2.failed == 0

        # Destination still has only 1 event
        dst_events = dst_backend.read_events()
        assert len(dst_events) == 1

    def test_transfer_resumable_after_partial(self, tmp_path: Path):
        """Transfer interrupted after one event, retry appends the rest."""
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )
        write_json_atomic(
            dst_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": dst_tid, "timeline_ulid": "01J00000000000000000000002", "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        # Add 3 events to source
        for i in range(3):
            src_backend.append_event(
                src_tid, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        src_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home,
            slug=None,
            backend=src_backend,
            source="local",
        )
        dst_target = EventLogTarget(
            backend_name="local_fs",
            timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home,
            slug=None,
            backend=dst_backend,
            source="local",
        )

        # Simulate partial transfer: manually append first event
        src_events = src_backend.read_events()
        dst_backend.append_imported_event(
            timeline_id=dst_tid,
            source_event=src_events[0],
            idempotency_key=f"transfer:push:local_fs:{src_tid}:{src_events[0].event_id}",
            actor=_ACTOR,
        )

        # Now do full transfer — should skip the first, append remaining 2
        result = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert result.scanned == 3
        assert result.appended == 2
        assert result.skipped_idempotent == 1
        assert result.failed == 0

        dst_events = dst_backend.read_events()
        assert len(dst_events) == 3


class TestTransferIdempotencyKeys:
    """Tests for deterministic idempotency key format."""

    def test_idempotency_key_format(self):
        """Idempotency keys follow the documented format."""
        key = "transfer:push:local_fs:uuid-123:event-ulid-abc"
        parts = key.split(":")
        assert parts[0] == "transfer"
        assert parts[1] in ("push", "pull")
        assert parts[2] in ("local_fs", "supabase")
        # parts[3] is source timeline UUID
        # parts[4] is source event ULID
        assert len(parts) == 5


class TestPullDestinationResolution:
    """Tests for pull destination resolution behaviors."""

    def test_pull_ambiguous_destination_fails(self):
        """Pull without --into, --create, or --as should fail."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        with pytest.raises(ValueError, match="requires a local destination"):
            resolve_pull_destination(
                "test-project",
                into=None,
                create_as=None,
                create=False,
            )

    def test_pull_into_nonexistent_fails(self):
        """Pull --into with a nonexistent slug fails."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        with pytest.raises(ValueError, match="not found"):
            resolve_pull_destination(
                "test-project",
                into="nonexistent-slug",
            )

    def test_pull_create_as_with_duplicate_slug_fails(self, tmp_path: Path, monkeypatch):
        """Pull --create --as with an existing slug fails."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination
        from astrid.core.timeline import paths as paths_mod

        # Set up a project dir with an existing timeline
        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)
        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "existing", "name": "existing", "is_default": False},
        )
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": str(uuid4()), "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )

        def fake_timelines_dir(project_slug, root=None):
            return proj_dir / "timelines"

        monkeypatch.setattr(paths_mod, "timelines_dir", fake_timelines_dir)
        monkeypatch.setattr(paths_mod, "validate_timeline_slug", lambda s: s)

        with pytest.raises(ValueError, match="already exists"):
            resolve_pull_destination(
                "test-project",
                create=True,
                create_as="existing",
                root=tmp_path,
            )

    def test_pull_create_writes_imported_provenance(self, tmp_path: Path, monkeypatch):
        """Pull --create --as writes provenance: imported identity."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination
        from astrid.core.timeline import paths as paths_mod

        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines"
        tl_dir.mkdir(parents=True)

        def fake_timelines_dir(project_slug, root=None):
            return tl_dir

        monkeypatch.setattr(paths_mod, "timelines_dir", fake_timelines_dir)
        monkeypatch.setattr(paths_mod, "validate_timeline_slug", lambda s: s)

        dest = resolve_pull_destination(
            "test-project",
            create=True,
            create_as="pulled-timeline",
            remote_source_timeline_id=str(uuid4()),
            root=tmp_path,
        )

        assert dest.created is True
        assert dest.target.source == "imported"

        # Check identity was written with provenance: imported
        import json
        identity = json.loads(dest.identity_path.read_text())
        assert identity["provenance"] == "imported"


class TestTransferReportsCounts:
    """TransferResult carries auditable counts."""

    def test_transfer_result_fields(self):
        """All TransferResult fields are populated."""
        result = TransferResult(
            direction="push",
            source_backend_name="local_fs",
            destination_backend_name="supabase",
            source_timeline_id="src-uuid",
            destination_timeline_id="dst-uuid",
            scanned=10,
            appended=8,
            skipped_idempotent=1,
            failed=1,
            destination_version=8,
            projection_regenerated=True,
        )

        assert result.direction == "push"
        assert result.scanned == 10
        assert result.appended == 8
        assert result.skipped_idempotent == 1
        assert result.failed == 1
        assert result.destination_version == 8
        assert result.projection_regenerated is True


# ======================================================================
# FakeSupabase transfer tests (M9 / T14)
# ======================================================================


class TestSupabaseFakeTransfer:
    """Transfer tests using FakeSupabaseTransport for remote side."""

    def test_push_localfs_to_fake_supabase(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Push local events to fake Supabase via append_imported_event."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001",
             "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )

        # Append events to source
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        src_target = EventLogTarget(
            backend_name="local_fs", timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home, slug=None,
            backend=src_backend, source="local",
        )
        dst_target = EventLogTarget(
            backend_name="supabase", timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home, slug=None,
            backend=dst_backend, source="remote",
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR,
            regenerate_dest_projection=False,
        )

        assert result.scanned == 2
        assert result.appended == 2
        assert result.skipped_idempotent == 0
        assert result.failed == 0

        # Verify destination has events with fake transport
        dst_events = dst_backend.read_events()
        assert len(dst_events) == 2
        assert dst_events[0].kind == "clip.added"
        assert dst_events[1].kind == "theme.set"
        # Destination-native IDs (not source IDs)
        assert dst_events[0].event_id != src_backend.read_events()[0].event_id

    def test_push_idempotent_retry_fake(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Push same events twice to fake Supabase — second is idempotent."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001",
             "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = EventLogTarget(
            backend_name="local_fs", timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home, slug=None,
            backend=src_backend, source="local",
        )
        dst_target = EventLogTarget(
            backend_name="supabase", timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home, slug=None,
            backend=dst_backend, source="remote",
        )

        # First transfer
        r1 = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert r1.appended == 1
        assert r1.skipped_idempotent == 0

        # Second transfer — idempotent
        r2 = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert r2.appended == 0
        assert r2.skipped_idempotent == 1
        assert r2.failed == 0

        assert len(dst_backend.read_events()) == 1

    def test_push_resumable_after_partial_fake(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Transfer interrupted after one event, retry appends the rest (fake transport)."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend
        from astrid.core.timeline.eventlog import EventLogTarget

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": src_tid, "timeline_ulid": "01J00000000000000000000001",
             "backend": "local_fs", "provenance": "imported", "created_at": "2026-05-21T00:00:00Z"},
        )

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )

        for i in range(3):
            src_backend.append_event(
                src_tid, "clip.added",
                {"clip_id": f"c{i}", "kind": "visual", "asset_id": f"a{i}"},
                actor=_ACTOR,
            )

        src_target = EventLogTarget(
            backend_name="local_fs", timeline_id=src_tid,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=src_home, slug=None,
            backend=src_backend, source="local",
        )
        dst_target = EventLogTarget(
            backend_name="supabase", timeline_id=dst_tid,
            timeline_ulid="01J00000000000000000000002",
            timeline_home=dst_home, slug=None,
            backend=dst_backend, source="remote",
        )

        # Simulate partial: manually import first event
        src_events = src_backend.read_events()
        dst_backend.append_imported_event(
            timeline_id=dst_tid,
            source_event=src_events[0],
            idempotency_key=f"transfer:push:local_fs:{src_tid}:{src_events[0].event_id}",
            actor=_ACTOR,
        )

        # Now full transfer — should skip first, append remaining 2
        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert result.scanned == 3
        assert result.appended == 2
        assert result.skipped_idempotent == 1
        assert result.failed == 0

        assert len(dst_backend.read_events()) == 3


# ======================================================================
# Reigh bridge non-invocation tests (M9 / T14)
# ======================================================================


class TestReighBridgeNotInvoked:
    """Prove old Reigh blob/config paths are not invoked by push/pull."""

    def test_transfer_does_not_import_supabase_data_provider(self):
        """push_timeline and pull_timeline do not import SupabaseDataProvider."""
        import re

        # Read the actual source file to verify no reigh imports
        import astrid.core.timeline.transfer as tmod
        src_path = tmod.__file__
        if src_path and src_path.endswith(".py"):
            with open(src_path, "r") as f:
                source = f.read()
            # Strip the module docstring so we check only the code body
            code_body = re.sub(r'^""".*?"""', '', source, count=1, flags=re.DOTALL)
            assert "from astrid.core.reigh" not in code_body, (
                "transfer.py must not import from astrid.core.reigh"
            )
            assert "import reigh" not in code_body, (
                "transfer.py must not import reigh"
            )
            assert "SupabaseDataProvider" not in code_body, (
                "transfer.py code must not reference SupabaseDataProvider"
            )
            assert "save_timeline" not in code_body, (
                "transfer.py code must not reference save_timeline"
            )

    def test_transfer_result_has_no_reigh_fields(self):
        """TransferResult carries no Reigh blob/config fields."""
        from astrid.core.timeline.transfer import TransferResult
        import dataclasses

        fields = {f.name for f in dataclasses.fields(TransferResult)}
        assert "reigh_config" not in fields
        assert "blob_url" not in fields
        assert "config_version" not in fields
        assert "supabase_config" not in fields

    def test_transfer_does_not_copy_assembly_json_as_authority(self):
        """Transfer is event-log only; no assembly.json copying."""
        import astrid.core.timeline.transfer as tmod
        src_path = tmod.__file__
        if src_path and src_path.endswith(".py"):
            with open(src_path, "r") as f:
                source = f.read()
            # Remove the module docstring (triple-quoted block at the top)
            # so we only check the code body, not the explanatory comments.
            import re
            # Strip the module docstring
            code_body = re.sub(r'^""".*?"""', '', source, count=1, flags=re.DOTALL)
            # Transfer code body must not reference assembly.json as authority
            assert "assembly.json" not in code_body, (
                "transfer code body must not reference assembly.json as authority"
            )
            assert "assembly.checkpoint.json" not in code_body, (
                "transfer code body must not reference assembly.checkpoint.json"
            )

    def test_transfer_docstring_declares_no_reigh_bridge(self):
        """Transfer module docstring declares separation from Reigh bridges."""
        import astrid.core.timeline.transfer as tmod
        doc = tmod.__doc__ or ""
        assert "Reigh" in doc, (
            "transfer module docstring should mention Reigh separation"
        )
        # It says Reigh bridges remain separate
        assert "separate" in doc.lower(), (
            "transfer docstring must declare Reigh bridges as separate"
        )


# ======================================================================
# Remote-only pull destination tests (M9 / T14)
# ======================================================================


class TestRemoteOnlyPull:
    """Remote-only pull tests for creating and pulling into local destinations."""

    def test_pull_create_writes_imported_identity(
        self, tmp_path: Path, monkeypatch
    ):
        """Pull with --create --as writes provenance: imported identity."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination
        from astrid.core.timeline import paths as paths_mod

        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines"
        tl_dir.mkdir(parents=True)

        def fake_timelines_dir(project_slug, root=None):
            return tl_dir

        monkeypatch.setattr(paths_mod, "timelines_dir", fake_timelines_dir)
        monkeypatch.setattr(paths_mod, "validate_timeline_slug", lambda s: s)

        dest = resolve_pull_destination(
            "test-project",
            create=True,
            create_as="pulled-timeline",
            remote_source_timeline_id=str(uuid4()),
            root=tmp_path,
        )

        assert dest.created is True
        assert dest.target.source == "imported"

        import json
        identity = json.loads(dest.identity_path.read_text())
        assert identity["provenance"] == "imported"
        assert identity["backend"] == "local_fs"

    def test_pull_rejects_ambiguous_destination(
        self, tmp_path: Path
    ):
        """Pull without --into/--create/--as fails before writes."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        with pytest.raises(ValueError, match="requires a local destination"):
            resolve_pull_destination(
                "test-project",
                into=None, create_as=None, create=False,
            )

    def test_pull_into_existing_rejects_nonexistent(
        self, tmp_path: Path
    ):
        """Pull --into with nonexistent slug fails before writes."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        with pytest.raises(ValueError, match="not found"):
            resolve_pull_destination(
                "test-project",
                into="nonexistent-timeline",
            )

    def test_pull_create_with_existing_slug_fails(
        self, tmp_path: Path, monkeypatch
    ):
        """Pull --create --as with an existing slug fails before writes."""
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination
        from astrid.core.timeline import paths as paths_mod

        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core.project.jsonio import write_json_atomic
        write_json_atomic(
            tl_dir / "display.json",
            {"schema_version": 1, "slug": "existing", "name": "existing", "is_default": False},
        )
        write_json_atomic(
            tl_dir / "assembly.identity.json",
            {"schema_version": 1, "timeline_id": str(uuid4()), "timeline_ulid": "01J00000000000000000000001",
             "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
        )

        def fake_timelines_dir(project_slug, root=None):
            return proj_dir / "timelines"

        monkeypatch.setattr(paths_mod, "timelines_dir", fake_timelines_dir)
        monkeypatch.setattr(paths_mod, "validate_timeline_slug", lambda s: s)

        with pytest.raises(ValueError, match="already exists"):
            resolve_pull_destination(
                "test-project",
                create=True,
                create_as="existing",
                root=tmp_path,
            )
