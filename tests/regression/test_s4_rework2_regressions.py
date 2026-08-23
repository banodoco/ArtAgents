"""S4 rework-2 — P1 zero-artifact, P2 no-seq-coercion, P3 F821."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.foundation.atomic_io import AtomicReadError
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import TursoSyncError, pull_from_turso, push_to_turso


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.timeline.events.schema import generate_event_ulid
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id = uuid.uuid4().hex
    tl_id = uuid.uuid4().hex
    ulid = "01J000000000000000000000AA"
    sid = f"{tl_id}:timeline.timeline"

    def _setup(uow: UnitOfWork):
        uow.execute(
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",  # noqa: E501
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",  # noqa: E501
            (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",  # noqa: E501
            (tl_id, proj_id, sid, "T1", json.dumps({"tracks": []}), json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),  # noqa: E501
        )

    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow: UnitOfWork):
        svc.append(
            uow,
            stream_id=sid,
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
    home = tmp_path / project_slug / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
    return proj_id, tl_id, sid, home


def _append_events(tmp_path: Path, proj_id: str, tl_id: str, sid: str, n: int):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.timeline.events.schema import generate_event_ulid
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    writer = open_standard_writer(db_path, registry=registry)
    svc = EventAppendService(registry)
    ids = []
    for _ in range(n):
        eid = generate_event_ulid()

        def _cb(uow: UnitOfWork, _eid=eid):
            svc.append(
                uow,
                stream_id=sid,
                project_id=proj_id,
                event_kind="timeline.saved",
                data={"config": {"clips": [], "tracks": []}},
                changes=["config"],
                idempotency_key=f"append:{_eid}",
                txn_id=generate_event_ulid(),
                actor_kind="system",
                event_id=_eid,
            )

        UnitOfWork(writer).run(_cb)
        ids.append(eid)
    writer.close()
    return ids


def _bootstrap_sync(tmp_path: Path, tl_id: str, home: Path, replica: TursoReplicaClient):
    backend = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)
    result = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
    assert result.action in ("pushed", "up_to_date")
    return backend


class TestP1ZeroArtifactProhibition:
    def test_write_keep_both_artifact_none_raises_turso_sync_error(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica = TursoReplicaClient(FakeTursoTransport())
        _bootstrap_sync(tmp_path, tl_id, home, replica)
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        from astrid.core.timeline.eventlog.turso import TursoEventRow
        from astrid.core.timeline.turso_sync import _read_local_document_snapshot

        local_doc = _read_local_document_snapshot(tl_id, tmp_path)
        remote_doc = local_doc.__class__(
            timeline_id=local_doc.timeline_id,
            project_id=local_doc.project_id,
            event_stream_id=local_doc.event_stream_id,
            name=local_doc.name,
            document_json=local_doc.document_json,
            version=local_doc.version + 1,
            created_at=local_doc.created_at,
            updated_at=local_doc.updated_at,
        )
        fake_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=999,
            kind="timeline.saved",
            payload_json=json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h2", "previous_event_hash": None}}),  # noqa: E501
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key="k2",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [fake_row], require_document=True)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path)  # noqa: E501
        with patch("astrid.core.timeline.turso_sync.write_keep_both_artifact", return_value=None):
            with pytest.raises(TursoSyncError, match=r"returned None|failing closed"):
                result = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)  # noqa: E501
                assert not (hasattr(result, "conflict_artifacts") and len(result.conflict_artifacts) == 0), "should not return conflict with empty artifacts"  # noqa: E501


class TestP2NoSeqCoercion:
    def test_fetch_seq_none_fails_closed_no_remote_rows_no_cursor_advance(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica = TursoReplicaClient(FakeTursoTransport())
        backend = _bootstrap_sync(tmp_path, tl_id, home, replica)
        from astrid.core.timeline.turso_sync import read_turso_sync_state

        baseline_state = read_turso_sync_state(home)
        assert baseline_state is not None
        baseline_last_pushed = baseline_state.last_pushed_event_id
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        before_rows = replica.fetch_remote_events(tl_id)
        before_count = len(before_rows)
        with patch("astrid.core.timeline.turso_sync._fetch_event_seq", return_value=None):
            with pytest.raises(TursoSyncError, match=r"missing seq|failing closed"):
                push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)  # noqa: E501
        after_rows = replica.fetch_remote_events(tl_id)
        assert len(after_rows) == before_count, f"remote should have no new rows, had {before_count} before, {len(after_rows)} after"  # noqa: E501
        after_state = read_turso_sync_state(home)
        assert after_state is not None
        assert after_state.last_pushed_event_id == baseline_last_pushed


class TestP3AtomicIoF821:
    def test_read_json_directory_raises_typed_not_name_error(self, tmp_path: Path):
        from astrid.core.foundation.atomic_io import read_json

        with pytest.raises((AtomicReadError, OSError)) as ei:
            read_json(tmp_path)
        assert not isinstance(ei.value, NameError)

    def test_read_json_invalid_json_raises_value_error(self, tmp_path: Path):
        from astrid.core.foundation.atomic_io import read_json

        bad = tmp_path / "bad.json"
        bad.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            read_json(bad)

    def test_read_json_os_error_not_name_error(self, tmp_path: Path):
        from astrid.core.foundation.atomic_io import read_json

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        try:
            read_json(subdir)
            assert False, "should have raised"
        except NameError as exc:
            pytest.fail(f"read_json raised NameError (F821 not fixed): {exc}")
        except (AtomicReadError, OSError, ValueError):
            pass

    def test_shared_jsonio_wraps_atomic_read_error(self, tmp_path: Path):
        from astrid.core._shared.jsonio import ProjectJsonError, read_json

        with pytest.raises(ProjectJsonError):
            read_json(tmp_path)
        bad = tmp_path / "bad2.json"
        bad.write_text("{ bad", encoding="utf-8")
        with pytest.raises(ProjectJsonError):
            read_json(bad)
