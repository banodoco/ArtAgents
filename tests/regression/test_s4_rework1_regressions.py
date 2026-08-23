"""S4 rework-1 regressions — O1–O4 + O6.

RED at START via fault injection; GREEN after fixes.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import (
    TursoOwnershipError,
    TursoSyncError,
    pull_from_turso,
    push_to_turso,
)


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
            "INSERT INTO projects (id, slug, name, settings_json, "
            "event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, "
            "aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, "
            "document_json, asset_registry_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tl_id,
                proj_id,
                sid,
                "T1",
                json.dumps({"tracks": []}),
                json.dumps({}),
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
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
    result = push_to_turso(
        timeline_id=tl_id,
        timeline_home=home,
        projects_root=tmp_path,
        backend=backend,
        replica=replica,
    )
    assert result.action in ("pushed", "up_to_date")
    return backend


class TestO1ForkGuarantee:
    def test_both_artifact_writes_faulted_raises_typed_never_zero_artifacts(self, tmp_path: Path):
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
            payload_json=json.dumps(
                {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h2", "previous_event_hash": None}}  # noqa: E501
            ),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key="k2",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [fake_row], require_document=True)
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        with patch(
            "astrid.core.timeline.sync_divergence.write_json_atomic", side_effect=OSError("fault")
        ):
            with patch(
                "astrid.core._shared.jsonio.write_json_atomic", side_effect=OSError("fault")
            ):
                with pytest.raises(TursoSyncError):
                    pull_from_turso(
                        timeline_id=tl_id,
                        timeline_home=home,
                        projects_root=tmp_path,
                        backend=backend2,
                        replica=replica,
                    )

    def test_malformed_remote_row_carries_skipped_rows_diagnostic(self, tmp_path: Path):
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
        good_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=10,
            kind="timeline.saved",
            payload_json=json.dumps(
                {
                    "data": {"ok": 1},
                    "_integrity": {"event_hash": "hgood", "previous_event_hash": None},
                }
            ),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key="k-good",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [good_row], require_document=True)
        transport = replica._transport  # type: ignore[attr-defined]
        bad = {
            "event_id": "BAD-EVENT-ID",
            "timeline_id": tl_id,
            "project_id": proj_id,
            "stream_id": sid,
            "seq": 11,
            "kind": "timeline.saved",
            "payload_json": "NOT JSON {",
            "actor_kind": "system",
            "actor_id": "remote",
            "txn_id": "bad",
            "idempotency_key": "k-bad",
            "created_at": "2026-01-02T00:00:01Z",
        }
        try:
            transport._events_by_timeline[tl_id].append(bad)  # type: ignore[attr-defined]
        except Exception:
            transport.execute_batch(
                [
                    (
                        "INSERT INTO events (event_id, timeline_id, project_id, stream_id, seq, kind, payload_json, actor_kind, actor_id, txn_id, idempotency_key, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",  # noqa: E501
                        (
                            bad["event_id"],
                            tl_id,
                            proj_id,
                            sid,
                            11,
                            "timeline.saved",
                            bad["payload_json"],
                            "system",
                            "remote",
                            "bad",
                            "k-bad",
                            "2026-01-02T00:00:01Z",
                        ),
                    )
                ]
            )
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        result = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend2,
            replica=replica,
        )
        assert result.action == "conflict"
        assert len(result.conflict_artifacts) == 1
        art_path = Path(str(result.conflict_artifacts[0].path))
        assert art_path.exists()
        raw = json.loads(art_path.read_text())
        assert "skipped_rows" in raw
        skipped = raw["skipped_rows"]
        assert any(s.get("event_id") == "BAD-EVENT-ID" for s in skipped)

    def test_clean_both_advanced_produces_both_suffixes(self, tmp_path: Path):
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
        remote_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=20,
            kind="timeline.saved",
            payload_json=json.dumps(
                {
                    "data": {"config": {"clips": [], "tracks": []}},
                    "_integrity": {"event_hash": "hrem", "previous_event_hash": None},
                }
            ),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key="k-remote",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [remote_row], require_document=True)
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        result = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend2,
            replica=replica,
        )
        assert result.action == "conflict"
        assert len(result.conflict_artifacts) == 1
        art_path = Path(str(result.conflict_artifacts[0].path))
        raw = json.loads(art_path.read_text())
        assert "source" in raw and "destination" in raw
        src_suffix = raw["source"]["suffix"]
        dst_suffix = raw["destination"]["suffix"]
        assert len(src_suffix) >= 1
        assert len(dst_suffix) >= 1
        for entry in src_suffix + dst_suffix:
            assert "payload" in entry
            assert isinstance(entry["payload"], dict)


class TestO2PrimaryForkPattern:
    def test_pull_both_advanced_artifact_has_full_payloads(self, tmp_path: Path):
        """End-to-end through pull_from_turso; artifact carries full payloads."""
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
        remote_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=30,
            kind="timeline.saved",
            payload_json=json.dumps(
                {
                    "data": {"config": {"clips": [], "tracks": []}},
                    "_integrity": {"event_hash": "h3", "previous_event_hash": None},
                }
            ),
            actor_kind="system",
            actor_id="remote-actor",
            txn_id=generate_event_ulid(),
            idempotency_key="k3",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [remote_row], require_document=True)
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        result = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend2,
            replica=replica,
        )
        assert result.action == "conflict"
        art_path = Path(str(result.conflict_artifacts[0].path))
        raw = json.loads(art_path.read_text())
        src_suffix = raw["source"]["suffix"]
        dst_suffix = raw["destination"]["suffix"]
        assert len(src_suffix) >= 1 and len(dst_suffix) >= 1
        for entry in src_suffix + dst_suffix:
            assert "payload" in entry
            assert isinstance(entry["payload"], dict)


class TestO3TypedOwnership:
    def test_non_ownership_error_with_owned_in_message_is_not_ownership(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica = TursoReplicaClient(FakeTursoTransport())
        _bootstrap_sync(tmp_path, tl_id, home, replica)
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
        remote_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=40,
            kind="timeline.saved",
            payload_json=json.dumps(
                {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h4", "previous_event_hash": None}}  # noqa: E501
            ),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key="k4",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [remote_row], require_document=True)
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )

        def _raise_generic(*args, **kwargs):
            raise RuntimeError("something owned by someone else but not lock")

        with patch.object(backend2, "append_imported_event", side_effect=_raise_generic):
            with pytest.raises(TursoSyncError) as ei:
                pull_from_turso(
                    timeline_id=tl_id,
                    timeline_home=home,
                    projects_root=tmp_path,
                    backend=backend2,
                    replica=replica,
                )
            assert not isinstance(ei.value, TursoOwnershipError)

    def test_owner_lock_error_maps_to_ownership(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica = TursoReplicaClient(FakeTursoTransport())
        _bootstrap_sync(tmp_path, tl_id, home, replica)
        from astrid.core.store.ownership import OwnerLockError
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
        remote_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=50,
            kind="timeline.saved",
            payload_json=json.dumps(
                {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h5", "previous_event_hash": None}}  # noqa: E501
            ),
            actor_kind="system",
            actor_id="remote",
            txn_id=generate_event_ulid(),
            idempotency_key="k5",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [remote_row], require_document=True)
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )

        def _raise_owner(*args, **kwargs):
            raise OwnerLockError("database is already owned")

        with patch.object(backend2, "append_imported_event", side_effect=_raise_owner):
            with pytest.raises(TursoOwnershipError):
                pull_from_turso(
                    timeline_id=tl_id,
                    timeline_home=home,
                    projects_root=tmp_path,
                    backend=backend2,
                    replica=replica,
                )


class TestO4PushFailsClosed:
    def test_faulted_ro_read_during_push_fails_typed_no_remote_rows(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica = TursoReplicaClient(FakeTursoTransport())
        backend = _bootstrap_sync(tmp_path, tl_id, home, replica)
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        with patch(
            "astrid.core.timeline.turso_sync._fetch_event_seq", side_effect=TursoSyncError("fault")
        ):
            with pytest.raises(TursoSyncError):
                push_to_turso(
                    timeline_id=tl_id,
                    timeline_home=home,
                    projects_root=tmp_path,
                    backend=backend,
                    replica=replica,
                )
        from astrid.core.timeline.turso_sync import read_turso_sync_state

        state = read_turso_sync_state(home)
        assert state is not None
        head = replica.fetch_remote_head(tl_id)
        assert head is not None
        local_events = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        ).read_events()
        newest = local_events[-1].event_id
        assert state.last_pushed_event_id != newest


class TestAttributionCollapsed:
    def test_pulled_events_attributed_to_sync_agent(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        replica = TursoReplicaClient(FakeTursoTransport())
        _bootstrap_sync(tmp_path, tl_id, home, replica)
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
        remote_row = TursoEventRow(
            event_id=generate_event_ulid(),
            timeline_id=tl_id,
            project_id=proj_id,
            stream_id=sid,
            seq=60,
            kind="timeline.saved",
            payload_json=json.dumps(
                {
                    "data": {"config": {"clips": [], "tracks": []}},
                    "_integrity": {"event_hash": "h6", "previous_event_hash": None},
                }
            ),
            actor_kind="executor",
            actor_id="original-actor",
            txn_id=generate_event_ulid(),
            idempotency_key="k6",
            created_at="2026-01-02T00:00:00Z",
        )
        replica.push_timeline_updates(remote_doc, [remote_row], require_document=True)
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        result = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend2,
            replica=replica,
        )
        assert result.pulled >= 1
        events = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        ).read_events()
        # attribution collapses to sync agent: last imported event's actor is turso-sync:pull
        assert events[-1].actor.id != "original-actor"
        assert events[-1].actor.id == "system"  # collapsed to system (turso-sync:pull)
