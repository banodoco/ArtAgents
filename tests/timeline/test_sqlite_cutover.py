"""W5 cutover: selector + sqlite backend + no-mixed authority."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.eventlog.selector import select_timeline_backend
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent, generate_event_ulid, with_event_hash


def _ensure_db(tmp_path: Path, project_slug: str = "proj") -> tuple[str, str]:
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id = uuid.uuid4().hex
    tl_id = uuid.uuid4().hex
    ulid = "01J0000000000000000000000A"
    stream_id = f"{tl_id}:timeline.timeline"

    def _setup(uow: UnitOfWork):
        uow.execute(
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (stream_id, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )

    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow: UnitOfWork):
        svc.append(
            uow,
            stream_id=stream_id,
            project_id=proj_id,
            event_kind="timeline.created",
            data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"},
            changes=["timeline_id", "slug", "name"],
            idempotency_key=f"create:{tl_id}",
            txn_id=generate_event_ulid(),
            actor_kind="system",
            event_id=generate_event_ulid(),
        )

    UnitOfWork(writer).run(_append)
    writer.close()
    return proj_id, tl_id


class TestSelectorResolutionMatrix:
    def test_backfilled_returns_sqlite(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
        home = tmp_path / "proj" / "timelines" / "01J0000000000000000000000A"
        home.mkdir(parents=True, exist_ok=True)
        stream, backend = select_timeline_backend(timeline_id=tl_id, timeline_home=home)
        assert backend.backend_name() == "sqlite"
        assert isinstance(backend, SqliteEventLogBackend)

    def test_unbackfilled_returns_localfs(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        home = tmp_path / "proj" / "timelines" / "01J0000000000000000000000A"
        home.mkdir(parents=True, exist_ok=True)
        stream, backend = select_timeline_backend(timeline_id=tl_id, timeline_home=home)
        assert backend.backend_name() == "local_fs"
        assert isinstance(backend, LocalFsBackend)

    def test_garbage_marker_fail_closed(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        marker_path = tmp_path / ".astrid" / "backfill-state.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("{ not json")
        home = tmp_path / "proj" / "timelines" / "01J0000000000000000000000A"
        home.mkdir(parents=True, exist_ok=True)
        with pytest.raises(Exception, match="unreadable"):
            select_timeline_backend(timeline_id=tl_id, timeline_home=home)

    def test_supabase_preferred_unchanged(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
        home = tmp_path / "proj" / "timelines" / "01J0000000000000000000000A"
        home.mkdir(parents=True, exist_ok=True)
        from astrid.core.timeline.eventlog.types import SupabaseEventLogOptions

        opts = SupabaseEventLogOptions(url="https://example.supabase.co", auth_token="tok")
        stream, backend = select_timeline_backend(timeline_id=tl_id, timeline_home=home, preferred_backend="supabase", supabase_options=opts)
        assert backend.backend_name() == "supabase"


class TestSqliteBackendRoundTrip:
    def test_append_imported_then_read_head_verify(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        actor = TimelineActor(type="system", id="tester", display="tester")
        source = TimelineEvent.new(
            timeline_id=tl_id,
            ts="2026-01-02T00:00:00Z",
            actor=actor,
            kind="clip.added",
            payload={"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"},
            prev_hash=None,
        )
        source = with_event_hash(source, prev_hash=None)
        imported = backend.append_imported_event(tl_id, source, idempotency_key="transfer:test:local_fs:src-tl:src-e1", actor=actor)
        assert imported.kind == source.kind
        events = backend.read_events()
        assert len(events) >= 2
        head = backend.head()
        assert head.version == len(events)
        v = backend.verify_chain()
        assert v.ok is True
        assert v.checked_events == len(events)


class TestNoMixedAuthority:
    def test_same_timeline_never_mixes(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        from astrid.packs.timeline.backfill import write_backfill_state

        write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
        home = tmp_path / "proj" / "timelines" / "01J0000000000000000000000A"
        home.mkdir(parents=True, exist_ok=True)
        (home / "assembly.jsonl").write_text('{"event_id":"01JAAAAAAAAAAAAAAAAAAAAAAAAA","timeline_id":"%s","ts":"2026-01-03T00:00:00Z","actor":{"type":"system","id":"x"},"prev_hash":null,"hash":"h","kind":"clip.added","payload":{"clip_id":"evil"},"schema_version":2}\n' % tl_id)
        stream, backend = select_timeline_backend(timeline_id=tl_id, timeline_home=home)
        assert backend.backend_name() == "sqlite"
        events = backend.read_events()
        assert all(e.event_id != "01JAAAAAAAAAAAAAAAAAAAAAAAAA" for e in events)

class TestProvenanceRoundTrip:
    def test_import_persists_provenance_and_idempotent_retry(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        # Ensure migration columns exist: run timeline migration 3
        from astrid.core.schema_packs.standard import build_standard_registry
        from astrid.core.migrations.runner import apply_pending_migrations
        from astrid.packs import build_standard_registry as build_reg
        import sqlite3
        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        # Apply pending migrations on this tmp db (already at v3, but ensure)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        actor = TimelineActor(type="system", id="tester", display="tester")
        source = TimelineEvent.new(timeline_id=tl_id, ts="2026-01-02T00:00:00Z", actor=actor, kind="clip.added", payload={"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, prev_hash=None)
        source = with_event_hash(source, prev_hash=None)
        imported = backend.append_imported_event(tl_id, source, idempotency_key="transfer:test:local_fs:src-tl:src-e1", actor=actor)
        # Reread via read_events
        events = backend.read_events()
        persisted = [e for e in events if e.event_id == imported.event_id][0]
        # First return and reread should have same provenance fields
        assert getattr(imported, "source_backend", None) is not None
        assert getattr(persisted, "source_backend", None) == getattr(imported, "source_backend", None)
        # Retry with same key returns same event with same provenance, no duplicate
        retry = backend.append_imported_event(tl_id, source, idempotency_key="transfer:test:local_fs:src-tl:src-e1", actor=actor)
        assert retry.event_id == imported.event_id
        assert getattr(retry, "source_backend", None) == getattr(imported, "source_backend", None)
        events2 = backend.read_events()
        assert len(events2) == len(events)

class TestVerifyChainCorruption:
    def test_head_seq_tamper_fails(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        import sqlite3
        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE event_streams SET head_seq = 99 WHERE id = ?", (f"{tl_id}:timeline.timeline",))
        conn.commit()
        conn.close()
        v = backend.verify_chain()
        assert v.ok is False
        assert "head seq" in (v.error or "").lower()

    def test_seq_gap_fails(self, tmp_path: Path):
        _, tl_id = _ensure_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        from astrid.core.integrations.reigh.bridge_service import derive_database_path
        import sqlite3
        db_path = derive_database_path(tmp_path)
        actor = TimelineActor(type="system", id="tester", display="tester")
        backend.append_event(tl_id, "clip.added", {"clip_id": "c2", "kind": "visual", "track_id": "visual", "asset_id": "a1"}, actor=actor)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE events SET seq = 99 WHERE stream_id = ? AND seq = 2", (f"{tl_id}:timeline.timeline",))
        conn.commit()
        conn.close()
        v = backend.verify_chain()
        assert v.ok is False
class TestSnapshotEvilFileProbe:
    def test_kernel_snapshot_ignores_evil_jsonl_and_uses_project_dir_root(self, tmp_path: Path):
        # Real repository timeline via TimelineRepository would be complex; simulate via _ensure_db + backfill marker + evil file
        proj_id, tl_id = _ensure_db(tmp_path)
        from astrid.packs.timeline.backfill import write_backfill_state
        write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
        # Create project/timelines layout
        project_dir = tmp_path / "proj"
        timeline_home = project_dir / "timelines" / "01J0000000000000000000000A"
        timeline_home.mkdir(parents=True, exist_ok=True)
        # Place evil assembly.jsonl that would be served if legacy path taken
        (timeline_home / "assembly.jsonl").write_text('{"event_id":"01JAAAAAAAAAAAAAAAAAAAAAAAAA","timeline_id":"'+tl_id+'","ts":"2026-01-03T00:00:00Z","actor":{"type":"system","id":"x"},"prev_hash":null,"hash":"h","kind":"clip.added","payload":{"clip_id":"evil"},"schema_version":2}\n')
        # Delete sidecars (ensure none exist)
        for name in ["display.json", "registry.json", "assembly.head.json", "assembly.identity.json", "assembly.checkpoint.json"]:
            p = timeline_home / name
            if p.exists():
                p.unlink()
        # Snapshot with project_root as project directory (live renderer behavior)
        from astrid.core.timeline.snapshot import acquire_snapshot
        # This should use kernel, not evil file, and not raise AttributeError
        snap = acquire_snapshot(timeline_home, project_slug="proj", project_root=project_dir)
        # Must not contain evil track
        assert "evil" not in str(snap.assembly)
        # Version matches kernel head
        from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
        be = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        head = be.head()
        assert snap.head_version == head.version
