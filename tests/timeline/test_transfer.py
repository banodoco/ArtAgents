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

from pathlib import Path
from uuid import uuid4

import pytest

from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineActor
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

        from astrid.core._shared.jsonio import write_json_atomic
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

        from astrid.core._shared.jsonio import write_json_atomic
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
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c2", "kind": "audio", "track_id": "audio", "asset_id": "a2"},
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

        from astrid.core._shared.jsonio import write_json_atomic
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
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
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
        assert result2.skipped_idempotent == 0
        assert result2.scanned == 0
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

        from astrid.core._shared.jsonio import write_json_atomic
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
                {"clip_id": f"c{i}", "kind": "visual", "track_id": "visual", "asset_id": f"a{i}"},
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
        from astrid.core.timeline.eventlog import EventLogTarget
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core._shared.jsonio import write_json_atomic
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
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
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
        from astrid.core.timeline.eventlog import EventLogTarget
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core._shared.jsonio import write_json_atomic
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
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
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

        # Second transfer is classified up-to-date and no-ops before replay.
        r2 = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR,
            regenerate_dest_projection=False,
        )
        assert r2.appended == 0
        assert r2.skipped_idempotent == 0
        assert r2.scanned == 0
        assert r2.failed == 0

        assert len(dst_backend.read_events()) == 1

    def test_push_resumable_after_partial_fake(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Transfer interrupted after one event, retry appends the rest (fake transport)."""
        from astrid.core.timeline.eventlog import EventLogTarget
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        from astrid.core._shared.jsonio import write_json_atomic
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
                {"clip_id": f"c{i}", "kind": "visual", "track_id": "visual", "asset_id": f"a{i}"},
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
            assert "from astrid.core.integrations.reigh" not in code_body, (
                "transfer.py must not import from astrid.core.integrations.reigh"
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
        import dataclasses

        from astrid.core.timeline.transfer import TransferResult

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
        """Pull with --create --as writes provenance: imported identity
        and preserves the remote UUID as the canonical timeline_id."""
        from astrid.core.timeline import paths as paths_mod
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines"
        tl_dir.mkdir(parents=True)

        def fake_timelines_dir(project_slug, root=None):
            return tl_dir

        monkeypatch.setattr(paths_mod, "timelines_dir", fake_timelines_dir)
        monkeypatch.setattr(paths_mod, "validate_timeline_slug", lambda s: s)

        remote_id = str(uuid4())
        dest = resolve_pull_destination(
            "test-project",
            create=True,
            create_as="pulled-timeline",
            remote_source_timeline_id=remote_id,
            root=tmp_path,
        )

        assert dest.created is True
        assert dest.target.source == "imported"

        import json
        identity = json.loads(dest.identity_path.read_text())
        assert identity["provenance"] == "imported"
        assert identity["backend"] == "local_fs"
        # T3: Remote UUID is preserved as the canonical timeline_id
        assert identity["timeline_id"] == remote_id
        assert identity["source_timeline_id"] == remote_id
        assert dest.target.timeline_id == remote_id

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
        from astrid.core.timeline import paths as paths_mod
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines" / "01J00000000000000000000001"
        tl_dir.mkdir(parents=True)

        from astrid.core._shared.jsonio import write_json_atomic
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

    def test_pull_implicit_create_preserves_remote_uuid(
        self, tmp_path: Path, monkeypatch
    ):
        """Implicit --create with remote_source_timeline_id preserves UUID."""
        from astrid.core.timeline import paths as paths_mod
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

        proj_dir = tmp_path / "test-project"
        tl_dir = proj_dir / "timelines"
        tl_dir.mkdir(parents=True)

        def fake_timelines_dir(project_slug, root=None):
            return tl_dir

        monkeypatch.setattr(paths_mod, "timelines_dir", fake_timelines_dir)
        monkeypatch.setattr(paths_mod, "validate_timeline_slug", lambda s: s)

        remote_id = str(uuid4())
        dest = resolve_pull_destination(
            "test-project",
            create=True,
            remote_source_slug="implicit-remote-slug",
            remote_source_timeline_id=remote_id,
            root=tmp_path,
        )

        assert dest.created is True
        assert dest.target.slug == "implicit-remote-slug"
        assert dest.target.source == "imported"

        import json
        identity = json.loads(dest.identity_path.read_text())
        assert identity["provenance"] == "imported"
        assert identity["backend"] == "local_fs"
        # Remote UUID is preserved as the canonical timeline_id
        assert identity["timeline_id"] == remote_id
        assert identity["source_timeline_id"] == remote_id
        assert dest.target.timeline_id == remote_id

    def test_pull_create_as_without_remote_uuid_generates_fresh(
        self, tmp_path: Path, monkeypatch
    ):
        """--create --as without remote_source_timeline_id generates fresh UUID."""
        from uuid import UUID

        from astrid.core.timeline import paths as paths_mod
        from astrid.core.timeline.eventlog.selector import resolve_pull_destination

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
            create_as="fresh-timeline",
            # No remote_source_timeline_id
            root=tmp_path,
        )

        assert dest.created is True
        assert dest.target.source == "imported"

        import json
        identity = json.loads(dest.identity_path.read_text())
        assert identity["provenance"] == "imported"
        fresh_id = identity["timeline_id"]
        UUID(fresh_id)  # Must be valid UUID
        assert "source_timeline_id" not in identity
        assert dest.target.timeline_id == fresh_id


# ======================================================================
# S5: Transfer sync classification tests (T14)
# ======================================================================


class TestTransferSyncClassification:
    """S5: TransferResult classification integration tests.

    Verifies that _transfer_events populates the new sync classification
    fields (divergent, sync_action, bookmark_error) across all six
    classifier states, stale/corrupt bookmark handling, first-sync
    bootstrap, and the replay gate layered on top of classification.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_identity(timeline_home: Path, timeline_id: str, ulid: str) -> None:
        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            timeline_home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": ulid,
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

    @staticmethod
    def _build_target(
        backend_name: str,
        timeline_id: str,
        ulid: str,
        timeline_home: Path,
        backend,
        slug: str | None = None,
        source: str = "local",
    ):
        from astrid.core.timeline.eventlog import EventLogTarget
        return EventLogTarget(
            backend_name=backend_name,
            timeline_id=timeline_id,
            timeline_ulid=ulid,
            timeline_home=timeline_home,
            slug=slug,
            backend=backend,
            source=source,
        )

    @staticmethod
    def _write_bookmark(
        timeline_home: Path,
        *,
        timeline_id: str,
        spoke: str,
        spoke_version: int,
        spoke_hash: str | None,
        spoke_event_id: str | None,
        hub_version: int,
        hub_hash: str | None,
        hub_event_id: str | None,
    ) -> None:
        from astrid.core._shared.jsonio import write_json_atomic
        bookmark = {
            "timeline_id": timeline_id,
            "spoke": spoke,
            "spoke_version": spoke_version,
            "spoke_hash": spoke_hash,
            "spoke_event_id": spoke_event_id,
            "hub_version": hub_version,
            "hub_hash": hub_hash,
            "hub_event_id": hub_event_id,
            "synced_at": "2026-06-12T00:00:00Z",
        }
        write_json_atomic(timeline_home / "sync_bookmark.json", bookmark)

    @staticmethod
    def _assert_local_bookmark(
        timeline_home: Path,
        *,
        timeline_id: str,
        spoke_version: int,
        spoke_hash: str | None,
        spoke_event_id: str | None,
        hub_version: int,
        hub_hash: str | None,
        hub_event_id: str | None,
    ) -> None:
        from astrid.core.timeline.sync_state import read_local_sync_bookmark

        bookmark = read_local_sync_bookmark(timeline_home)
        assert bookmark is not None
        assert bookmark.timeline_id == timeline_id
        assert bookmark.spoke == "local"
        assert bookmark.spoke_version == spoke_version
        assert bookmark.spoke_hash == spoke_hash
        assert bookmark.spoke_event_id == spoke_event_id
        assert bookmark.hub_version == hub_version
        assert bookmark.hub_hash == hub_hash
        assert bookmark.hub_event_id == hub_event_id

    # ------------------------------------------------------------------
    # Result shape
    # ------------------------------------------------------------------

    def test_transfer_result_has_s5_fields_with_defaults(self):
        """All S5 classification fields exist on TransferResult and default correctly."""
        result = TransferResult(
            direction="push",
            source_backend_name="local_fs",
            destination_backend_name="local_fs",
            source_timeline_id="sid",
            destination_timeline_id="did",
            scanned=0,
            appended=0,
            skipped_idempotent=0,
            failed=0,
            destination_version=0,
            projection_regenerated=False,
        )
        assert result.divergent is False
        assert result.sync_action is None
        assert result.divergence_artifact is None
        assert result.bookmark_error is None

    def test_transfer_result_s5_fields_serializable(self):
        """TransferResult S5 fields survive round-trip attribute access."""
        from astrid.core.timeline.sync_divergence import LocalDivergenceArtifactRef

        ref = LocalDivergenceArtifactRef(
            path="/tmp/divergence-123.json",
            timeline_id="tid-1",
            created_at="2026-06-12T00:00:00Z",
        )
        result = TransferResult(
            direction="pull",
            source_backend_name="supabase",
            destination_backend_name="local_fs",
            source_timeline_id="sid",
            destination_timeline_id="did",
            scanned=5,
            appended=5,
            skipped_idempotent=0,
            failed=0,
            destination_version=5,
            projection_regenerated=True,
            divergent=True,
            sync_action="both_advanced",
            divergence_artifact=ref,
            bookmark_error="bookmark is from a different timeline",
        )
        assert result.divergent is True
        assert result.sync_action == "both_advanced"
        assert result.divergence_artifact is ref
        assert result.divergence_artifact.kind == "local_file"
        assert result.bookmark_error == "bookmark is from a different timeline"

    # ------------------------------------------------------------------
    # First-sync bootstrap (missing bookmark)
    # ------------------------------------------------------------------

    def test_empty_both_sides_bookmark_missing(self, tmp_path: Path):
        """Both sides empty, no bookmark → bookmark_missing, divergent=True, no events."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        result = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )

        assert result.scanned == 0
        assert result.appended == 0
        # Both sides empty → bootstrap-safe missing bookmark
        assert result.sync_action == "bookmark_missing"
        assert result.divergent is True
        assert result.bookmark_error is None

    def test_source_only_no_bookmark_bootstrap(self, tmp_path: Path):
        """Source has events, dest empty, no bookmark → bookmark_missing, divergent=True."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        result = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )

        assert result.scanned == 1
        assert result.appended == 1
        # Dest empty → bootstrap-safe missing bookmark
        assert result.sync_action == "bookmark_missing"
        assert result.divergent is True
        assert result.bookmark_error is None

    def test_dest_only_no_bookmark_bootstrap(self, tmp_path: Path):
        """Dest has events, source empty, no bookmark → bookmark_missing, divergent=True."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        # Only dest has events
        dst_backend.append_event(
            dst_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        result = _transfer_events(
            source=src_target,
            destination=dst_target,
            direction="push",
            actor=_ACTOR,
            regenerate_dest_projection=False,
        )

        assert result.scanned == 0
        assert result.appended == 0
        # Source empty → bootstrap-safe missing bookmark
        assert result.sync_action == "bookmark_missing"
        assert result.divergent is True
        assert result.bookmark_error is None

    def test_both_nonempty_no_bookmark_not_bootstrap_safe(self, tmp_path: Path):
        """Both sides non-empty, no bookmark → bookmark_incompatible, divergent=True."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        dst_backend.append_event(
            dst_tid, "clip.added",
            {"clip_id": "c2", "kind": "audio", "track_id": "audio", "asset_id": "a2"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        from astrid.core.timeline.sync_divergence import TransferFailure

        with pytest.raises(TransferFailure, match="aborting before event replay"):
            _transfer_events(
                source=src_target,
                destination=dst_target,
                direction="push",
                actor=_ACTOR,
                regenerate_dest_projection=False,
            )

    # ------------------------------------------------------------------
    # Up-to-date with bookmark
    # ------------------------------------------------------------------

    def test_up_to_date_with_bookmark(self, tmp_path: Path):
        """Bookmark matches both heads exactly → up_to_date, divergent=False."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # First transfer to sync both sides
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Both sides now have version=1 with same event
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        assert src_head.version == 1
        assert dst_head.version == 1

        # Write bookmark matching both heads (push: spoke=source, hub=dest)
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        # Transfer again — should be up_to_date
        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "up_to_date"
        assert result.divergent is False
        assert result.bookmark_error is None
        assert result.appended == 0
        assert result.skipped_idempotent == 0
        assert result.scanned == 0

    # ------------------------------------------------------------------
    # source_only with bookmark
    # ------------------------------------------------------------------

    def test_source_only_with_bookmark(self, tmp_path: Path):
        """Source advanced past bookmark, dest matches → source_only, divergent=False."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Initial sync: seed dest with one event
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Snapshot heads and write bookmark
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        # Add another event to source (advancing spoke past bookmark)
        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "source_only"
        assert result.divergent is False
        assert result.bookmark_error is None
        assert result.appended == 1  # The new event transfers

        dst_events = dst_backend.read_events()
        assert [event.kind for event in dst_events] == ["clip.added", "theme.set"]
        assert dst_events[1].source_event_id == src_backend.read_events()[-1].event_id

        refreshed_src_head = src_backend.head()
        refreshed_dst_head = dst_backend.head()
        self._assert_local_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke_version=refreshed_src_head.version,
            spoke_hash=refreshed_src_head.last_hash,
            spoke_event_id=refreshed_src_head.last_event_id,
            hub_version=refreshed_dst_head.version,
            hub_hash=refreshed_dst_head.last_hash,
            hub_event_id=refreshed_dst_head.last_event_id,
        )

    # ------------------------------------------------------------------
    # destination_only with bookmark
    # ------------------------------------------------------------------

    def test_destination_only_with_bookmark(self, tmp_path: Path):
        """Dest advanced past bookmark, source matches → destination_only, divergent=False."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Initial sync
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Snapshot and write bookmark
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        # Add an event directly to destination (advancing hub past bookmark)
        dst_backend.append_event(
            dst_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "destination_only"
        assert result.divergent is False
        assert result.bookmark_error is None
        assert result.appended == 0
        assert result.skipped_idempotent == 0
        assert result.scanned == 0

        refreshed_src_head = src_backend.head()
        refreshed_dst_head = dst_backend.head()
        self._assert_local_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke_version=refreshed_src_head.version,
            spoke_hash=refreshed_src_head.last_hash,
            spoke_event_id=refreshed_src_head.last_event_id,
            hub_version=refreshed_dst_head.version,
            hub_hash=refreshed_dst_head.last_hash,
            hub_event_id=refreshed_dst_head.last_event_id,
        )

    # ------------------------------------------------------------------
    # both_advanced
    # ------------------------------------------------------------------

    def test_both_advanced_divergent(self, tmp_path: Path):
        """Both sides advanced beyond bookmark → both_advanced, divergent=True."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Initial sync
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Write bookmark at the synced state
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        # Advance both sides
        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )
        dst_backend.append_event(
            dst_tid, "theme.set",
            {"theme_id": "light"},
            actor=_ACTOR,
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "both_advanced"
        assert result.divergent is True
        assert result.bookmark_error is None

    # ------------------------------------------------------------------
    # Stale / corrupt bookmarks
    # ------------------------------------------------------------------

    def test_stale_bookmark_behind(self, tmp_path: Path):
        """Current head behind bookmark version → bookmark_incompatible, divergent=True."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Initial sync
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Write a bookmark with version HIGHER than actual — simulating stale ref
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=99,
            spoke_hash="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            spoke_event_id="01J00000000000000000000099",
            hub_version=99,
            hub_hash="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            hub_event_id="01J00000000000000000000098",
        )

        from astrid.core.timeline.sync_divergence import TransferFailure

        with pytest.raises(TransferFailure, match="aborting before event replay"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )

    def test_corrupt_bookmark_json(self, tmp_path: Path):
        """Unparseable bookmark JSON aborts before event replay."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Write corrupt JSON as the bookmark
        (src_home / "sync_bookmark.json").write_text("not valid json {{{")

        from astrid.core.timeline.sync_divergence import TransferFailure

        with pytest.raises(TransferFailure, match="failed to read sync bookmark"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )
        assert len(dst_backend.read_events()) == 0

    def test_bookmark_wrong_timeline_id(self, tmp_path: Path):
        """Bookmark with mismatched timeline_id → bookmark_incompatible, divergent=True."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Initial sync so both have events
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Write a bookmark with a different timeline_id
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=str(uuid4()),  # Different!
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        from astrid.core.timeline.sync_divergence import TransferFailure

        with pytest.raises(TransferFailure, match="does not match"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )

    def test_bookmark_missing_fields(self, tmp_path: Path):
        """Bookmark with missing required fields aborts before event replay."""
        from astrid.core._shared.jsonio import write_json_atomic
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Bookmark missing spoke_hash when spoke_version > 0
        write_json_atomic(src_home / "sync_bookmark.json", {
            "timeline_id": src_tid,
            "spoke": "local",
            "spoke_version": 1,
            "spoke_hash": None,
            "spoke_event_id": None,
            "hub_version": 0,
            "hub_hash": None,
            "hub_event_id": None,
            "synced_at": "2026-06-12T00:00:00Z",
        })

        from astrid.core.timeline.sync_divergence import TransferFailure

        with pytest.raises(TransferFailure, match="failed to read sync bookmark"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )

    # ------------------------------------------------------------------
    # Divergent replay is gated by keep-both preservation
    # ------------------------------------------------------------------

    def test_divergent_state_still_replays(self, tmp_path: Path):
        """both_advanced preserves divergence first, then replays the source suffix."""
        import json

        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        # Advance both sides
        src_backend.append_event(
            src_tid, "theme.set", {"theme_id": "dark"}, actor=_ACTOR,
        )
        dst_backend.append_event(
            dst_tid, "theme.set", {"theme_id": "light"}, actor=_ACTOR,
        )

        # Measure dest before transfer
        dst_count_before = len(dst_backend.read_events())

        # Transfer in divergent state — must still replay
        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "both_advanced"
        assert result.divergent is True
        assert result.divergence_artifact is not None
        # Replay proceeds after keep-both preservation.
        assert result.scanned >= 1
        assert result.appended >= 1
        dst_count_after = len(dst_backend.read_events())
        assert dst_count_after > dst_count_before

        divergence_path = Path(result.divergence_artifact.path)
        payload = json.loads(divergence_path.read_text())
        assert payload["timeline_id"] == dst_tid
        assert [event["kind"] for event in payload["source"]["suffix"]] == ["theme.set"]
        assert [event["kind"] for event in payload["destination"]["suffix"]] == ["theme.set"]

    def test_divergent_keep_both_failure_aborts_without_replay(self, tmp_path: Path, monkeypatch):
        """Artifact failure aborts before any LWW replay can append to destination."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.sync_divergence import TransferFailure

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )
        src_backend.append_event(src_tid, "theme.set", {"theme_id": "dark"}, actor=_ACTOR)
        dst_backend.append_event(dst_tid, "theme.set", {"theme_id": "light"}, actor=_ACTOR)

        dst_before = [event.event_id for event in dst_backend.read_events()]
        bookmark_before = (src_home / "sync_bookmark.json").read_text()

        monkeypatch.setattr(
            transfer_mod,
            "write_keep_both_artifact",
            lambda **_: (_ for _ in ()).throw(TransferFailure("artifact write failed")),
        )

        with pytest.raises(TransferFailure, match="artifact write failed"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )

        assert [event.event_id for event in dst_backend.read_events()] == dst_before
        assert (src_home / "sync_bookmark.json").read_text() == bookmark_before

    def test_corrupt_bookmark_blocks_replay(self, tmp_path: Path):
        """Corrupt bookmark blocks event replay before any append."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        # Write corrupt bookmark
        (src_home / "sync_bookmark.json").write_text("garbage {{{not json")

        from astrid.core.timeline.sync_divergence import TransferFailure

        with pytest.raises(TransferFailure, match="failed to read sync bookmark"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )
        assert len(dst_backend.read_events()) == 0

    def test_successful_transfer_verifies_local_chains(self, tmp_path: Path, monkeypatch):
        """Successful local transfer verifies both local chains before returning."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.types import EventLogVerification

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        calls: list[str] = []

        def record_source_verify():
            calls.append("source")
            return EventLogVerification(ok=True, checked_events=1, last_event_id=src_backend.head().last_event_id)

        def record_dest_verify():
            calls.append("destination")
            return EventLogVerification(ok=True, checked_events=1, last_event_id=dst_backend.head().last_event_id)

        monkeypatch.setattr(src_backend, "verify_chain", record_source_verify)
        monkeypatch.setattr(dst_backend, "verify_chain", record_dest_verify)

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.appended == 1
        assert calls == ["source", "destination"]

    # ------------------------------------------------------------------
    # Push vs pull direction mapping
    # ------------------------------------------------------------------

    def test_push_direction_spoke_hub_mapping(self, tmp_path: Path):
        """Push: source head→spoke, dest head→hub; bookmark read from source home."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        # Source has events, dest is empty
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        # Write a bookmark at source home matching: spoke=src head (v1), hub=dest head (v0)
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=None,
            hub_event_id=None,
        )

        src_target = self._build_target("local_fs", src_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", dst_tid, "01J00000000000000000000002", dst_home, dst_backend)

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Push: spoke=source matches bookmark.spoke → up_to_date
        assert result.sync_action == "up_to_date"
        assert result.divergent is False

    def test_pull_direction_spoke_hub_mapping(self, tmp_path: Path):
        """Pull: source head→hub, dest head→spoke; bookmark read from dest home.

        In pull, the destination (local spoke) shares the same timeline_id as
        the source (hub) because pull preserves the remote UUID.  The bookmark
        must use the shared timeline_id so validate_bookmark_matches_timeline
        passes against expected_timeline_id=source.timeline_id.
        """
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

        shared_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, shared_tid, "01J00000000000000000000001")
        self._make_identity(dst_home, shared_tid, "01J00000000000000000000002")

        src_backend = LocalFsBackend(timeline_id=shared_tid, timeline_home=src_home)
        dst_backend = LocalFsBackend(timeline_id=shared_tid, timeline_home=dst_home)

        # Source (hub) has events, dest (spoke) is empty
        src_backend.append_event(
            shared_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        # Write bookmark at dest home matching: spoke=dest head (v0), hub=src head (v1)
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            dst_home,  # Pull reads bookmark from destination (spoke) home
            timeline_id=shared_tid,
            spoke="local",
            spoke_version=dst_head.version,
            spoke_hash=None,
            spoke_event_id=None,
            hub_version=src_head.version,
            hub_hash=src_head.last_hash,
            hub_event_id=src_head.last_event_id,
        )

        src_target = self._build_target("local_fs", shared_tid, "01J00000000000000000000001", src_home, src_backend)
        dst_target = self._build_target("local_fs", shared_tid, "01J00000000000000000000002", dst_home, dst_backend)

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="pull", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Pull: spoke=dest (v0 matches bookmark.spoke), hub=src (v1 matches bookmark.hub)
        assert result.sync_action == "up_to_date"
        assert result.divergent is False

    # ------------------------------------------------------------------
    # Fake Supabase integration
    # ------------------------------------------------------------------

    def test_push_to_fake_supabase_classification(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Push to fake Supabase populates classification fields (bookmark_missing)."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target(
            "local_fs", src_tid, "01J00000000000000000000001",
            src_home, src_backend, source="local",
        )
        dst_target = self._build_target(
            "supabase", dst_tid, "01J00000000000000000000002",
            dst_home, dst_backend, source="remote",
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.scanned == 1
        assert result.appended == 1
        # Fake Supabase dest is empty → bootstrap-safe bookmark_missing
        assert result.sync_action == "bookmark_missing"
        assert result.divergent is True
        assert result.bookmark_error is None

    def test_pull_from_fake_supabase_classification(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Pull from fake Supabase populates classification fields."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(dst_home, dst_tid, "01J00000000000000000000002")

        src_backend = SupabaseBackend(
            timeline_id=src_tid, transport=fake_supabase_transport, enabled=True,
        )
        dst_backend = LocalFsBackend(timeline_id=dst_tid, timeline_home=dst_home)

        # Seed fake Supabase with an event
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target(
            "supabase", src_tid, "01J00000000000000000000001",
            src_home, src_backend, source="remote",
        )
        dst_target = self._build_target(
            "local_fs", dst_tid, "01J00000000000000000000002",
            dst_home, dst_backend, source="local",
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="pull", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.scanned == 1
        assert result.appended == 1
        # Dest (local spoke) is empty → bootstrap-safe bookmark_missing
        assert result.sync_action == "bookmark_missing"
        assert result.divergent is True
        assert result.bookmark_error is None

    def test_push_fake_supabase_with_bookmark(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Push to fake Supabase with matching bookmark → up_to_date."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )

        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target(
            "local_fs", src_tid, "01J00000000000000000000001",
            src_home, src_backend, source="local",
        )
        dst_target = self._build_target(
            "supabase", dst_tid, "01J00000000000000000000002",
            dst_home, dst_backend, source="remote",
        )

        # Initial sync
        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        # Write bookmark matching both heads
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        # Second transfer should be up_to_date
        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "up_to_date"
        assert result.divergent is False
        assert result.bookmark_error is None
        assert result.appended == 0

    def test_push_fake_supabase_refreshes_local_and_db_bookmarks(
        self, tmp_path: Path, fake_supabase_transport
    ):
        """Push updates both the local sidecar and the fake Supabase bookmark row exactly."""
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )
        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        src_target = self._build_target(
            "local_fs", src_tid, "01J00000000000000000000001",
            src_home, src_backend, source="local",
        )
        dst_target = self._build_target(
            "supabase", dst_tid, "01J00000000000000000000002",
            dst_home, dst_backend, source="remote",
        )

        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.appended == 2
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._assert_local_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        db_bookmark = fake_supabase_transport.read_bookmark(
            timeline_id=dst_tid,
            spoke="local",
        )
        assert db_bookmark == {
            "timeline_id": dst_tid,
            "spoke": "local",
            "spoke_version": src_head.version,
            "spoke_hash": src_head.last_hash,
            "spoke_event_id": src_head.last_event_id,
            "hub_version": dst_head.version,
            "hub_hash": dst_head.last_hash,
            "hub_event_id": dst_head.last_event_id,
            "synced_at": db_bookmark["synced_at"],
        }

    def test_retry_after_bookmark_write_failure_is_idempotent(
        self, tmp_path: Path, fake_supabase_transport, monkeypatch
    ):
        """Retry after a post-append bookmark-write failure skips already imported events."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import SupabaseBackend
        from astrid.core.timeline.sync_divergence import TransferFailure

        src_tid = str(uuid4())
        dst_tid = str(uuid4())

        src_home = tmp_path / "src"
        src_home.mkdir()
        dst_home = tmp_path / "dst"
        dst_home.mkdir()

        self._make_identity(src_home, src_tid, "01J00000000000000000000001")

        src_backend = LocalFsBackend(timeline_id=src_tid, timeline_home=src_home)
        dst_backend = SupabaseBackend(
            timeline_id=dst_tid, transport=fake_supabase_transport, enabled=True,
        )
        src_backend.append_event(
            src_tid, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=_ACTOR,
        )

        src_target = self._build_target(
            "local_fs", src_tid, "01J00000000000000000000001",
            src_home, src_backend, source="local",
        )
        dst_target = self._build_target(
            "supabase", dst_tid, "01J00000000000000000000002",
            dst_home, dst_backend, source="remote",
        )

        _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )
        src_head = src_backend.head()
        dst_head = dst_backend.head()
        self._write_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke="local",
            spoke_version=src_head.version,
            spoke_hash=src_head.last_hash,
            spoke_event_id=src_head.last_event_id,
            hub_version=dst_head.version,
            hub_hash=dst_head.last_hash,
            hub_event_id=dst_head.last_event_id,
        )

        src_backend.append_event(
            src_tid, "theme.set",
            {"theme_id": "dark"},
            actor=_ACTOR,
        )

        original_write = transfer_mod.write_local_sync_bookmark
        monkeypatch.setattr(
            transfer_mod,
            "write_local_sync_bookmark",
            lambda *args, **kwargs: (_ for _ in ()).throw(TransferFailure("bookmark sidecar offline")),
        )

        with pytest.raises(TransferFailure, match="bookmark sidecar offline"):
            _transfer_events(
                source=src_target, destination=dst_target,
                direction="push", actor=_ACTOR, regenerate_dest_projection=False,
            )

        assert len(fake_supabase_transport.read_events(timeline_id=dst_tid)) == 2

        monkeypatch.setattr(transfer_mod, "write_local_sync_bookmark", original_write)
        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=_ACTOR, regenerate_dest_projection=False,
        )

        assert result.sync_action == "both_advanced"
        assert result.appended == 0
        assert result.skipped_idempotent == 1
        assert len(fake_supabase_transport.read_events(timeline_id=dst_tid)) == 2
        refreshed_src_head = src_backend.head()
        refreshed_dst_head = dst_backend.head()
        self._assert_local_bookmark(
            src_home,
            timeline_id=src_tid,
            spoke_version=refreshed_src_head.version,
            spoke_hash=refreshed_src_head.last_hash,
            spoke_event_id=refreshed_src_head.last_event_id,
            hub_version=refreshed_dst_head.version,
            hub_hash=refreshed_dst_head.last_hash,
            hub_event_id=refreshed_dst_head.last_event_id,
        )


# ============================================================================
# Born-local promotion tests (T18)
# ============================================================================


class TestBornLocalPromotion:
    """S5 Phase 2 Step 10: Born-local promotion preflight, recovery, and idempotency.

    Covers:
    - Same-UUID DB creation via the append service
    - Missing project/user configuration failure messages
    - Not-found vs network/auth failure behavior
    - Existing-row retry / bookmark recovery
    - Partial-promotion recovery continuing into transfer
    - Local identity metadata update (synced_backends, sync_targets)
    - Retry idempotency (second push skips promotion)
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_born_local_identity(timeline_home: Path, timeline_id: str) -> None:
        from astrid.core._shared.jsonio import write_json_atomic

        write_json_atomic(
            timeline_home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000001",
                "backend": "local_fs",
                "provenance": "created",
                "created_at": "2026-05-21T00:00:00Z",
                "display": {"name": "My Born-Local TL"},
            },
        )

    @staticmethod
    def _make_imported_identity(timeline_home: Path, timeline_id: str) -> None:
        from astrid.core._shared.jsonio import write_json_atomic

        write_json_atomic(
            timeline_home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000002",
                "backend": "local_fs",
                "provenance": "imported",
                "created_at": "2026-05-21T00:00:00Z",
            },
        )

    @staticmethod
    def _build_source_target(
        timeline_id: str, timeline_home: Path, backend,
    ):
        from astrid.core.timeline.eventlog import EventLogTarget

        return EventLogTarget(
            backend_name="local_fs",
            timeline_id=timeline_id,
            timeline_ulid="01J00000000000000000000001",
            timeline_home=timeline_home,
            slug="my-timeline",
            backend=backend,
            source="local",
        )

    @staticmethod
    def _assert_identity_has_supabase_sync(
        timeline_home: Path, timeline_id: str, project_id: str, user_id: str,
    ) -> None:
        from astrid.core._shared.jsonio import read_json

        identity = read_json(timeline_home / "assembly.identity.json")
        assert isinstance(identity, dict)
        assert "supabase" in identity.get("synced_backends", [])
        targets = identity.get("sync_targets", {})
        assert isinstance(targets, dict)
        supabase_target = targets.get("supabase")
        assert isinstance(supabase_target, dict)
        assert supabase_target.get("backend") == "supabase"
        assert supabase_target.get("timeline_id") == timeline_id
        assert supabase_target.get("project_id") == project_id
        assert supabase_target.get("user_id") == user_id
        assert supabase_target.get("provenance") == "created"
        assert isinstance(supabase_target.get("synced_at"), str)

    @staticmethod
    def _assert_local_bookmark_written(timeline_home: Path, timeline_id: str) -> dict:
        from astrid.core.timeline.sync_state import read_local_sync_bookmark

        bookmark = read_local_sync_bookmark(timeline_home)
        assert bookmark is not None, "Expected sync_bookmark.json to exist after promotion"
        assert bookmark.timeline_id == timeline_id
        assert bookmark.spoke == "local"
        return {
            "spoke_version": bookmark.spoke_version,
            "hub_version": bookmark.hub_version,
            "hub_hash": bookmark.hub_hash,
            "hub_event_id": bookmark.hub_event_id,
        }

    # ------------------------------------------------------------------
    # Same-UUID DB creation
    # ------------------------------------------------------------------

    def test_born_local_promotion_creates_same_uuid_on_supabase(
        self, tmp_path: Path, monkeypatch,
    ):
        """Born-local not-found preflight → append service creates timeline with same UUID."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import (
            AppendServiceCreateResult,
            TimelineMetadataPreflight,
        )

        timeline_id = "b1e10000-0000-4000-8000-000000000001"
        project_id = "p1e10000-0000-4000-8000-000000000001"
        user_id = "u1e10000-0000-4000-8000-000000000001"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )

        source = self._build_source_target(timeline_id, src_home, src_backend)

        def fake_preflight(*, supabase_url, auth_token, timeline_id, timeout=60.0):
            return TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id)

        monkeypatch.setattr(transfer_mod, "read_timeline_metadata_preflight", fake_preflight)
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": project_id},
        )

        create_calls: list[dict] = []

        def fake_create(*, service_url, bearer_token, project_id, user_id,
                        timeline_id, config, name, timeout=60.0):
            create_calls.append({
                "service_url": service_url,
                "project_id": project_id,
                "user_id": user_id,
                "timeline_id": timeline_id,
                "name": name,
            })
            return AppendServiceCreateResult(
                timeline_id=timeline_id,
                config_version=1,
                inserted_event_ids=("evt-001",),
                head_version=1,
                head_event_id="evt-001",
                head_hash="a" * 64,
                raw_payload={"timeline_id": timeline_id, "inserted_event_ids": ["evt-001"], "config_version": 1, "events": [{"version": 1, "event_id": "evt-001", "hash": "a" * 64}]},
            )

        monkeypatch.setattr(transfer_mod, "create_timeline_via_append_service", fake_create)

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", user_id)
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "internal-token")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )

        assert len(create_calls) == 1
        assert create_calls[0]["timeline_id"] == timeline_id
        assert create_calls[0]["project_id"] == project_id
        assert create_calls[0]["user_id"] == user_id
        assert create_calls[0]["name"] == "My Born-Local TL"

        bookmark_info = self._assert_local_bookmark_written(src_home, timeline_id)
        assert bookmark_info["hub_version"] == 1
        assert bookmark_info["hub_hash"] == "a" * 64
        assert bookmark_info["hub_event_id"] == "evt-001"

        self._assert_identity_has_supabase_sync(
            src_home, timeline_id, project_id, user_id,
        )

    # ------------------------------------------------------------------
    # Missing project/user failure messages
    # ------------------------------------------------------------------

    def test_born_local_promotion_fails_when_project_id_missing(
        self, tmp_path: Path, monkeypatch,
    ):
        """Missing project.json.project_id raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b2e20000-0000-4000-8000-000000000002"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"name": "no-project-id"},
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", "u1")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        with pytest.raises(TransferFailure, match="project.json.project_id"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    def test_born_local_promotion_fails_when_sync_user_id_missing(
        self, tmp_path: Path, monkeypatch,
    ):
        """Missing sync user ID raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b2e30000-0000-4000-8000-000000000003"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": "p1"},
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        with pytest.raises(TransferFailure, match="ASTRID_SYNC_USER_ID|REIGH_SYNC_USER_ID"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    def test_born_local_promotion_fails_when_append_service_url_missing(
        self, tmp_path: Path, monkeypatch,
    ):
        """Missing append service URL raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b2e40000-0000-4000-8000-000000000004"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": "p1"},
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", "u1")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        with pytest.raises(TransferFailure, match="REIGH_APPEND_SERVICE_URL"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    def test_born_local_promotion_fails_when_internal_token_missing(
        self, tmp_path: Path, monkeypatch,
    ):
        """Missing internal token raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b2e50000-0000-4000-8000-000000000005"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": "p1"},
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", "u1")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")

        with pytest.raises(TransferFailure, match="REIGH_APPEND_SERVICE_INTERNAL_TOKEN"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    # ------------------------------------------------------------------
    # Not-found vs network/auth failure behavior
    # ------------------------------------------------------------------

    def test_born_local_not_found_triggers_promotion(
        self, tmp_path: Path, monkeypatch,
    ):
        """Preflight status='not_found' triggers promotion for born-local identity."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight

        timeline_id = "b3e10000-0000-4000-8000-000000000011"
        project_id = "p3e10000-0000-4000-8000-000000000011"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": project_id},
        )

        promotion_called: list[bool] = [False]

        def fake_promote(**kwargs):
            promotion_called[0] = True

        monkeypatch.setattr(transfer_mod, "_promote_born_local_timeline", fake_promote)

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )
        assert promotion_called[0] is True

    def test_born_local_unauthorized_raises_transfer_failure(
        self, tmp_path: Path, monkeypatch,
    ):
        """Preflight status='unauthorized' raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b3e20000-0000-4000-8000-000000000012"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="unauthorized", timeline_id=timeline_id,
                detail="HTTP 401: invalid API key",
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        with pytest.raises(TransferFailure, match="invalid API key"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    def test_born_local_network_failure_raises_transfer_failure(
        self, tmp_path: Path, monkeypatch,
    ):
        """Preflight status='network_failure' raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b3e30000-0000-4000-8000-000000000013"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="network_failure", timeline_id=timeline_id,
                detail="connection refused",
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        with pytest.raises(TransferFailure, match="connection refused"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    def test_imported_identity_not_found_raises_transfer_failure(
        self, tmp_path: Path, monkeypatch,
    ):
        """Non-born-local (imported) identity with not_found raises TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b3e40000-0000-4000-8000-000000000014"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_imported_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        with pytest.raises(TransferFailure, match="not a born-local timeline"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    # ------------------------------------------------------------------
    # Existing-row retry / bookmark recovery
    # ------------------------------------------------------------------

    def test_born_local_exists_recovers_bookmark_when_missing(
        self, tmp_path: Path, monkeypatch,
    ):
        """When preflight='exists' and bookmark missing, recover from DB."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight

        timeline_id = "b4e10000-0000-4000-8000-000000000021"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id="p1", user_id="u1",
                version=2, event_count=2,
                last_event_id="hub-evt-002", last_hash="b" * 64,
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        assert not (src_home / "sync_bookmark.json").exists()

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )

        bookmark_info = self._assert_local_bookmark_written(src_home, timeline_id)
        assert bookmark_info["spoke_version"] == 1
        assert bookmark_info["hub_version"] == 2
        assert bookmark_info["hub_hash"] == "b" * 64
        assert bookmark_info["hub_event_id"] == "hub-evt-002"

    def test_born_local_exists_skips_recovery_when_bookmark_present(
        self, tmp_path: Path, monkeypatch,
    ):
        """When preflight='exists' and bookmark present, do nothing."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_state import (
            HeadSnapshot,
            SyncBookmark,
            write_local_sync_bookmark,
        )

        timeline_id = "b4e20000-0000-4000-8000-000000000022"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        existing_bookmark = SyncBookmark.from_heads(
            timeline_id=timeline_id, spoke="local",
            spoke_head=HeadSnapshot(version=0, last_hash=None, last_event_id=None),
            hub_head=HeadSnapshot(version=1, last_hash="a" * 64, last_event_id="evt-001"),
        )
        write_local_sync_bookmark(src_home, existing_bookmark)

        preflight_called: list[int] = [0]

        def fake_preflight(**kw):
            preflight_called[0] += 1
            return TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id="p1", user_id="u1",
                version=5, event_count=5,
                last_event_id="hub-evt-005", last_hash="c" * 64,
            )

        monkeypatch.setattr(transfer_mod, "read_timeline_metadata_preflight", fake_preflight)
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )

        assert preflight_called[0] == 1
        from astrid.core.timeline.sync_state import read_local_sync_bookmark
        bookmark = read_local_sync_bookmark(src_home)
        assert bookmark is not None
        assert bookmark.hub_version == 1
        assert bookmark.hub_hash == "a" * 64

    def test_born_local_exists_with_mismatched_event_count_raises(
        self, tmp_path: Path, monkeypatch,
    ):
        """When hub event_count cannot be reconciled, raise TransferFailure."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.sync_divergence import TransferFailure

        timeline_id = "b4e30000-0000-4000-8000-000000000023"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )
        src_backend.append_event(
            timeline_id, "theme.set", {"theme_id": "dark"},
            actor=TimelineActor(type="agent", id="test"),
        )
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id="p1", user_id="u1",
                version=10, event_count=10,
                last_event_id="hub-evt-010", last_hash="d" * 64,
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        with pytest.raises(TransferFailure, match="cannot be reconciled"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

    def test_born_local_exists_with_empty_hub_noop(
        self, tmp_path: Path, monkeypatch,
    ):
        """When preflight='exists' and event_count=0, skip recovery."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight

        timeline_id = "b4e40000-0000-4000-8000-000000000024"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id="p1", user_id="u1",
                version=0, event_count=0,
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )
        assert not (src_home / "sync_bookmark.json").exists()

    # ------------------------------------------------------------------
    # Partial-promotion recovery continuing into transfer
    # ------------------------------------------------------------------

    def test_partial_promotion_recovery_continues_into_transfer(
        self, tmp_path: Path, monkeypatch, fake_supabase_transport,
    ):
        """After partial promotion, bookmark recovery allows clean transfer."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import (
            SupabaseBackend,
            TimelineMetadataPreflight,
        )

        timeline_id = "b5e10000-0000-4000-8000-000000000031"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        evt1 = src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )
        evt2 = src_backend.append_event(
            timeline_id, "theme.set", {"theme_id": "dark"},
            actor=TimelineActor(type="agent", id="test"),
        )

        # Seed fake Supabase with first event already imported (partial promotion)
        fake_supabase_transport.append_imported_event(
            timeline_id=timeline_id, source_event=evt1,
            idempotency_key="transfer:push:local_fs:" + timeline_id + ":" + evt1.event_id,
            actor=TimelineActor(type="system", id="transfer:push"),
        )

        src_target = TestTransferSyncClassification._build_target(
            "local_fs", timeline_id, "01J00000000000000000000001",
            src_home, src_backend, source="local",
        )

        dst_home = tmp_path / "dst"
        dst_home.mkdir()
        dst_backend = SupabaseBackend(
            timeline_id=timeline_id, transport=fake_supabase_transport, enabled=True,
        )
        dst_target = TestTransferSyncClassification._build_target(
            "supabase", timeline_id, "01J00000000000000000000002",
            dst_home, dst_backend, source="remote",
        )

        # The imported event in fake transport has its own hash
        imported_events = fake_supabase_transport.read_events(timeline_id=timeline_id)
        assert len(imported_events) == 1
        imported_hash = imported_events[0].hash
        imported_event_id = imported_events[0].event_id

        # Preflight says: timeline exists with just the config_replaced (v1) and
        # no imported events yet.  imported_count=0 → spoke v0.
        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id="p1", user_id="u1",
                version=1, event_count=1,
                last_event_id=imported_event_id, last_hash=imported_hash,
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=src_target, root=None,
        )

        # Bookmark recovered: spoke v0 (no local events imported yet), hub v1
        bookmark_info = self._assert_local_bookmark_written(src_home, timeline_id)
        assert bookmark_info["spoke_version"] == 0
        assert bookmark_info["hub_version"] == 1

        # Now run transfer_events — it should replay local events to fake Supabase.
        # source_only state (source v2 > bookmark spoke v0, hub matches bookmark hub)
        result = _transfer_events(
            source=src_target, destination=dst_target,
            direction="push", actor=TimelineActor(type="agent", id="transfer-test"),
            regenerate_dest_projection=False,
        )

        # Both events are replayed; evt1 is idempotent (already imported), evt2 is appended
        assert result.scanned == 2
        assert result.appended == 1
        assert result.skipped_idempotent == 1
        assert len(fake_supabase_transport.read_events(timeline_id=timeline_id)) == 2

    # ------------------------------------------------------------------
    # Local identity metadata update
    # ------------------------------------------------------------------

    def test_born_local_promotion_updates_identity_metadata(
        self, tmp_path: Path, monkeypatch,
    ):
        """Promotion adds supabase to synced_backends and writes sync_targets."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import (
            AppendServiceCreateResult,
            TimelineMetadataPreflight,
        )

        timeline_id = "b6e10000-0000-4000-8000-000000000041"
        project_id = "p6e10000-0000-4000-8000-000000000041"
        user_id = "u6e10000-0000-4000-8000-000000000041"

        src_home = tmp_path / "src"
        src_home.mkdir()
        from astrid.core._shared.jsonio import write_json_atomic
        write_json_atomic(
            src_home / "assembly.identity.json",
            {
                "schema_version": 1,
                "timeline_id": timeline_id,
                "timeline_ulid": "01J00000000000000000000001",
                "backend": "local_fs",
                "provenance": "created",
                "created_at": "2026-05-21T00:00:00Z",
                "display": {"name": "Test TL"},
                "synced_backends": ["other-backend"],
            },
        )

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        # Add one event so source head version > 0 (skips DB bookmark upsert)
        src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": project_id},
        )
        monkeypatch.setattr(
            transfer_mod, "create_timeline_via_append_service",
            lambda **kw: AppendServiceCreateResult(
                timeline_id=timeline_id,
                config_version=1, inserted_event_ids=("evt-001",),
                head_version=1, head_event_id="evt-001", head_hash="a" * 64,
                raw_payload={"timeline_id": timeline_id, "inserted_event_ids": ["evt-001"], "config_version": 1, "events": [{"version": 1, "event_id": "evt-001", "hash": "a" * 64}]},
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", user_id)
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )

        from astrid.core._shared.jsonio import read_json
        identity = read_json(src_home / "assembly.identity.json")
        assert isinstance(identity, dict)
        synced = identity.get("synced_backends", [])
        assert "other-backend" in synced
        assert "supabase" in synced

        targets = identity.get("sync_targets", {})
        assert isinstance(targets, dict)
        supabase_target = targets.get("supabase")
        assert isinstance(supabase_target, dict)
        assert supabase_target.get("backend") == "supabase"
        assert supabase_target.get("timeline_id") == timeline_id
        assert supabase_target.get("project_id") == project_id
        assert supabase_target.get("user_id") == user_id
        assert supabase_target.get("provenance") == "created"
        assert isinstance(supabase_target.get("synced_at"), str)

    # ------------------------------------------------------------------
    # Retry idempotency
    # ------------------------------------------------------------------

    def test_born_local_promotion_retry_is_idempotent(
        self, tmp_path: Path, monkeypatch,
    ):
        """Re-running promotion preflight after success does not double-create."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import (
            AppendServiceCreateResult,
            TimelineMetadataPreflight,
        )

        timeline_id = "b7e10000-0000-4000-8000-000000000051"
        project_id = "p7e10000-0000-4000-8000-000000000051"
        user_id = "u7e10000-0000-4000-8000-000000000051"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        # Add one event so source head version > 0 (skips DB bookmark upsert)
        src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )
        source = self._build_source_target(timeline_id, src_home, src_backend)

        preflight_calls: list[str] = []

        def fake_preflight_first(**kw):
            preflight_calls.append("not_found")
            return TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id)

        monkeypatch.setattr(transfer_mod, "read_timeline_metadata_preflight", fake_preflight_first)
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": project_id},
        )
        monkeypatch.setattr(
            transfer_mod, "create_timeline_via_append_service",
            lambda **kw: AppendServiceCreateResult(
                timeline_id=timeline_id,
                config_version=1, inserted_event_ids=("evt-001",),
                head_version=1, head_event_id="evt-001", head_hash="a" * 64,
                raw_payload={"timeline_id": timeline_id, "inserted_event_ids": ["evt-001"], "config_version": 1, "events": [{"version": 1, "event_id": "evt-001", "hash": "a" * 64}]},
            ),
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", user_id)
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )
        assert len(preflight_calls) == 1
        assert preflight_calls[0] == "not_found"

        self._assert_local_bookmark_written(src_home, timeline_id)

        def fake_preflight_exists(**kw):
            preflight_calls.append("exists")
            return TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id=project_id, user_id=user_id,
                version=1, event_count=1,
                last_event_id="evt-001", last_hash="a" * 64,
            )

        monkeypatch.setattr(transfer_mod, "read_timeline_metadata_preflight", fake_preflight_exists)

        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )

        assert len(preflight_calls) == 2
        assert preflight_calls[1] == "exists"
        self._assert_local_bookmark_written(src_home, timeline_id)

    def test_born_local_promotion_second_push_skips_preflight(
        self, tmp_path: Path, monkeypatch,
    ):
        """A second full push with existing Supabase row skips promotion."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import (
            AppendServiceCreateResult,
            TimelineMetadataPreflight,
        )

        timeline_id = "b7e20000-0000-4000-8000-000000000052"
        project_id = "p7e20000-0000-4000-8000-000000000052"
        user_id = "u7e20000-0000-4000-8000-000000000052"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        src_backend.append_event(
            timeline_id, "clip.added",
            {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            actor=TimelineActor(type="agent", id="test"),
        )
        source = self._build_source_target(timeline_id, src_home, src_backend)

        create_service_calls: list[dict] = []

        def fake_create(**kw):
            create_service_calls.append(kw)
            return AppendServiceCreateResult(
                timeline_id=timeline_id,
                config_version=1, inserted_event_ids=("evt-001",),
                head_version=1, head_event_id="evt-001", head_hash="a" * 64,
                raw_payload={"timeline_id": timeline_id, "inserted_event_ids": ["evt-001"], "config_version": 1, "events": [{"version": 1, "event_id": "evt-001", "hash": "a" * 64}]},
            )

        monkeypatch.setattr(transfer_mod, "create_timeline_via_append_service", fake_create)
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": project_id},
        )

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", user_id)
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        # First: not_found → promote
        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )
        assert len(create_service_calls) == 1

        # Second: exists → skip
        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(
                status="exists", timeline_id=timeline_id,
                project_id=project_id, user_id=user_id,
                version=1, event_count=1,
                last_event_id="evt-001", last_hash="a" * 64,
            ),
        )
        transfer_mod._preflight_push_destination(
            project_slug="test-project", source=source, root=None,
        )
        assert len(create_service_calls) == 1

    def test_born_local_preflight_handles_app_service_failure(
        self, tmp_path: Path, monkeypatch,
    ):
        """When append service create fails, EventLogTransportError propagates with no bookmark."""
        import astrid.core.timeline.transfer as transfer_mod
        from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
        from astrid.core.timeline.eventlog.supabase import TimelineMetadataPreflight
        from astrid.core.timeline.eventlog.types import EventLogTransportError

        timeline_id = "b7e30000-0000-4000-8000-000000000053"

        src_home = tmp_path / "src"
        src_home.mkdir()
        self._make_born_local_identity(src_home, timeline_id)

        src_backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=src_home)
        source = self._build_source_target(timeline_id, src_home, src_backend)

        monkeypatch.setattr(
            transfer_mod, "read_timeline_metadata_preflight",
            lambda **kw: TimelineMetadataPreflight(status="not_found", timeline_id=timeline_id),
        )
        monkeypatch.setattr(
            transfer_mod, "load_project",
            lambda slug, root=None: {"project_id": "p1"},
        )

        def failing_create(**kw):
            raise EventLogTransportError("append service 502 Bad Gateway")

        monkeypatch.setattr(transfer_mod, "create_timeline_via_append_service", failing_create)

        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sk-test")
        monkeypatch.setenv("ASTRID_SYNC_USER_ID", "u1")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_URL", "https://append.example.com")
        monkeypatch.setenv("REIGH_APPEND_SERVICE_INTERNAL_TOKEN", "tok")

        with pytest.raises(EventLogTransportError, match="502 Bad Gateway"):
            transfer_mod._preflight_push_destination(
                project_slug="test-project", source=source, root=None,
            )

        assert not (src_home / "sync_bookmark.json").exists()
