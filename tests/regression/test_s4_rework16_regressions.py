"""S4 rework-16 — B2a/b/c + B3 pins (RED→GREEN quoted)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    DOCUMENT_REPLICA_COLUMNS,
    EVENT_REPLICA_COLUMNS,
    FakeTursoTransport,
    TursoReplicaClient,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import (
    pull_from_turso,
    push_to_turso,
    read_turso_sync_state,
    write_turso_sync_state,
)


def _doc_params(timeline_id: str, version: int, doc_json: str, name: str = "My Timeline") -> tuple:
    row = {
        "timeline_id": timeline_id,
        "project_id": "proj-1",
        "event_stream_id": "sid-1",
        "name": name,
        "document_json": doc_json,
        "version": version,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    return tuple(row[c] for c in DOCUMENT_REPLICA_COLUMNS)


def _event_params(
    event_id: str,
    timeline_id: str = "tl-1",
    payload: str = '{"a":1}',
    seq: int = 1,
) -> tuple:
    row = {
        "event_id": event_id,
        "timeline_id": timeline_id,
        "project_id": "proj-1",
        "stream_id": f"{timeline_id}:timeline.timeline",
        "seq": seq,
        "kind": "timeline.saved",
        "payload_json": payload,
        "actor_kind": "system",
        "actor_id": "system",
        "txn_id": "txn-1",
        "idempotency_key": f"ik:{event_id}",
        "created_at": "2026-01-01T00:00:00Z",
    }
    return tuple(row[c] for c in EVENT_REPLICA_COLUMNS)


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    import json as _json

    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.store.uow import UnitOfWork
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
            "event_head_seq, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, ?, ?)",
            (
                proj_id,
                project_slug,
                "P",
                "{}",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, "
            "aggregate_id, head_seq, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
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
                _json.dumps({"tracks": []}),
                _json.dumps({}),
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
            data={
                "timeline_id": tl_id,
                "timeline_ulid": ulid,
                "slug": "t1",
                "name": "T1",
            },
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

    write_backfill_state(
        tmp_path,
        timeline_id=tl_id,
        source="local_fs",
        source_head_version=1,
        events_sha256="abc",
    )
    return proj_id, tl_id, sid, home



def _append_events(tmp_path: Path, proj_id: str, tl_id: str, sid: str, n: int):
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.store.uow import UnitOfWork
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    writer = open_standard_writer(db_path, registry=registry)
    svc = EventAppendService(registry)
    ids = []
    for i in range(n):
        eid = generate_event_ulid()

        def _a(uow, _eid=eid):
            svc.append(
                uow,
                stream_id=sid,
                project_id=proj_id,
                event_kind="timeline.saved",
                data={"config": {"clips": [], "tracks": []}},
                changes=["i"],
                idempotency_key=f"ik:{_eid}",
                txn_id=generate_event_ulid(),
                actor_kind="system",
                event_id=_eid,
            )

        UnitOfWork(writer).run(_a)
        ids.append(eid)
    writer.close()
    return ids

def _seed_remote_event(
    fake: FakeTursoTransport,
    tl_id: str,
    proj_id: str,
    sid: str,
    seq: int,
    payload_json: str,
    event_id: str | None = None,
) -> str:  # noqa: E501
    eid = event_id or generate_event_ulid()
    fake.events[eid] = {
        "event_id": eid,
        "timeline_id": tl_id,
        "project_id": proj_id,
        "stream_id": sid,
        "seq": seq,
        "kind": "timeline.saved",
        "payload_json": payload_json,
        "actor_kind": "human",
        "actor_id": "alice",
        "txn_id": generate_event_ulid(),
        "idempotency_key": f"ik:{eid}",
        "created_at": "2026-01-01T00:00:00Z",
    }
    fake.documents[tl_id] = {
        "timeline_id": tl_id,
        "project_id": proj_id,
        "event_stream_id": sid,
        "name": "T1",
        "document_json": json.dumps({"tracks": []}),
        "version": seq,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    return eid


# ---------------------------------------------------------------------------
# B2a — cursor identity: pull-resume must store REMOTE id
# ---------------------------------------------------------------------------


class TestB2aCursorIdentity:
    def test_pull_resume_stores_remote_identity(self, tmp_path: Path):
        # Local initially empty, remote has 1 event (r1)
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )

        # establish baseline via push
        push_to_turso(  # noqa: E501
            timeline_id=tl_id,  # noqa: E501
            timeline_home=home,  # noqa: E501
            projects_root=tmp_path,  # noqa: E501
            backend=backend,  # noqa: E501
            replica=replica,  # noqa: E501
        )
        payload = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h1", "previous_event_hash": None}}  # noqa: E501
        )
        r1 = _seed_remote_event(fake, tl_id, proj_id, sid, 2, payload)

        # First pull: imports r1 (local remaps id)
        res1 = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend,
            replica=replica,
        )
        assert res1.action == "pulled"
        # Verify local has imported but with different event_id (remap)
        local_ids = [e.event_id for e in backend.read_events()]
        assert r1 not in local_ids  # remapped
        # Check that stored state points to remote id
        st = read_turso_sync_state(home)
        assert st is not None
        assert st.remote_event_id == r1
        assert st.remote_event_id in fake.events

        # Simulate crash-after-apply: add second remote event r2  # noqa: E501
        # Actually we want to test resume path: local has r2 imported  # noqa: E501
        # local has r2 (imported) but state not persisted -> both_advanced with proven check
        # Add r2 remote
        payload2 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h2", "previous_event_hash": "h1"}}  # noqa: E501
        )
        r2 = _seed_remote_event(fake, tl_id, proj_id, sid, 3, payload2)
        # Import r2 locally via pull but simulate write failure  # noqa: E501
        # Do a second pull that would import r2
        res2 = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend,
            replica=replica,
        )
        assert res2.pulled == 1
        st2 = read_turso_sync_state(home)
        assert st2.remote_event_id == r2
        # Now simulate crash: revert state to previous (r1) while local has r2
        old_st = st  # r1 state
        write_turso_sync_state(home, old_st)
        # Local has r2, remote has r2, state stale at r1 -> triggers pull resume committed check
        # Need also to have local suffix that matches remote suffix (proven)
        # Invoke pull again -> should go through resume path and store remote identity
        backend3 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        res3 = pull_from_turso(  # noqa: F841
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend3,
            replica=replica,
        )
        # After resume, remote_event_id must be r2 (remote), not local remapped id
        st3 = read_turso_sync_state(home)
        assert st3 is not None
        assert st3.remote_event_id == r2, (
            f"cursor identity wrong: got {st3.remote_event_id!r} expected remote {r2!r}"
        )
        assert st3.remote_event_id in fake.events
        # And local remapped id must NOT be stored
        assert st3.remote_event_id not in local_ids or st3.remote_event_id == r2


# ---------------------------------------------------------------------------
# B2b — interleaved-append honesty
# ---------------------------------------------------------------------------


class TestB2bInterleavedHonesty:
    def test_pull_resume_not_up_to_date_when_remote_appended(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )

        # establish baseline
        push_to_turso(  # noqa: E501
            timeline_id=tl_id,  # noqa: E501
            timeline_home=home,  # noqa: E501
            projects_root=tmp_path,  # noqa: E501
            backend=backend,  # noqa: E501
            replica=replica,  # noqa: E501
        )
        # Seed remote r1, pull it
        p1 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h1", "previous_event_hash": None}}  # noqa: E501
        )
        r1 = _seed_remote_event(fake, tl_id, proj_id, sid, 2, p1)  # noqa: F841
        res = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend,
            replica=replica,
        )
        assert res.action == "pulled"
        st_before = read_turso_sync_state(home)
        assert st_before is not None
        # Add r2 remote and import locally, then stale state to trigger resume
        p2 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h2", "previous_event_hash": "h1"}}  # noqa: E501
        )
        r2 = _seed_remote_event(fake, tl_id, proj_id, sid, 3, p2)  # noqa: F841
        res2 = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend,
            replica=replica,
        )
        assert res2.pulled == 1
        st_r2 = read_turso_sync_state(home)  # noqa: F841
        # Revert state to r1 to force resume
        write_turso_sync_state(home, st_before)
        # Now local has r1+r2, remote has r1+r2, state at r1
        # Inject unseen r3 during resume's fresh_remote snapshot
        p3 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h3", "previous_event_hash": "h2"}}  # noqa: E501
        )
        r3 = generate_event_ulid()
        import astrid.core.timeline.turso_sync as mod

        orig = mod._remote_head_snapshot
        cnt = {"n": 0}

        def injected(replica_inner, tid_inner):
            cnt["n"] += 1
            if cnt["n"] == 2 and tid_inner == tl_id and r3 not in fake.events:
                fake.events[r3] = {
                    "event_id": r3,
                    "timeline_id": tl_id,
                    "project_id": proj_id,
                    "stream_id": sid,
                    "seq": 3,
                    "kind": "timeline.saved",
                    "payload_json": p3,
                    "actor_kind": "human",
                    "actor_id": "alice",
                    "txn_id": generate_event_ulid(),
                    "idempotency_key": f"ik:{r3}",
                    "created_at": "2026-01-01T00:00:00Z",
                }
                fake.documents[tl_id]["version"] = 4
            return orig(replica_inner, tid_inner)

        with patch.object(mod, "_remote_head_snapshot", side_effect=injected):
            backend2 = SqliteEventLogBackend(
                timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
            )
            res3 = pull_from_turso(
                timeline_id=tl_id,
                timeline_home=home,
                projects_root=tmp_path,
                backend=backend2,
                replica=replica,
            )
        # Must NOT be up_to_date
        assert res3.action != "up_to_date", (
            f"dishonest up_to_date while remote appended r3 missing: {res3!r}"
        )
        # Preferred: remainder fetched in same call (pulled>0). Alternative: next poll fetches.
        if res3.pulled is not None and res3.pulled > 0:
            pass
        else:
            # Alternative honest path: next poll must fetch remainder
            extra = pull_from_turso(
                timeline_id=tl_id,
                timeline_home=home,
                projects_root=tmp_path,
                backend=backend2,
                replica=replica,
            )
            assert extra.pulled is not None and extra.pulled > 0, (  # noqa: E501
                f"next poll should fetch r3, got {extra!r}"  # noqa: E501
            )
            assert extra.action == "pulled"
        # History completes: local contains r3 provenance, no artifacts
        evs = backend2.read_events()
        # Check via source_event_id that r3 is present (imported)
        has_r3 = any(getattr(e, "source_event_id", None) == r3 or e.event_id == r3 for e in evs)
        # For SqliteBackend, imported r3 will have source_event_id == r3, event_id is remapped
        # So check source_event_id
        if not has_r3:
            # fallback: check DB for source_event_id column
            from astrid.core.integrations.reigh.bridge_service import derive_database_path

            dbp = derive_database_path(tmp_path)
            con = sqlite3.connect(str(dbp))
            con.row_factory = sqlite3.Row
            rows = list(
                con.execute("SELECT source_event_id FROM events WHERE stream_id = ?", (sid,))
            )
            con.close()
            has_r3 = any(r["source_event_id"] == r3 for r in rows if r["source_event_id"])
        assert has_r3, "history incomplete: r3 not found locally"
        assert res3.conflict_artifacts is None or len(res3.conflict_artifacts) == 0
        # No unexpected remote writes: remote version should be 3, not mutated by pull
        assert fake.documents[tl_id]["version"] == 4


# ---------------------------------------------------------------------------
# B2c — replay accounting
# ---------------------------------------------------------------------------


class TestB2cReplayAccounting:
    def test_invalid_cursor_fallback_counts_net_new_only(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        backend = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )

        # establish baseline
        push_to_turso(  # noqa: E501
            timeline_id=tl_id,  # noqa: E501
            timeline_home=home,  # noqa: E501
            projects_root=tmp_path,  # noqa: E501
            backend=backend,  # noqa: E501
            replica=replica,  # noqa: E501
        )
        # Seed remote r1, r2, r3; pull r1,r2 (2 already imported)
        p1 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h1", "previous_event_hash": None}}  # noqa: E501
        )
        p2 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h2", "previous_event_hash": "h1"}}  # noqa: E501
        )
        p3 = json.dumps(
            {"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h3", "previous_event_hash": "h2"}}  # noqa: E501
        )
        r1 = _seed_remote_event(fake, tl_id, proj_id, sid, 2, p1)  # noqa: F841
        r2 = _seed_remote_event(fake, tl_id, proj_id, sid, 3, p2)  # noqa: F841
        res = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend,
            replica=replica,
        )
        assert res.pulled == 2
        # Add r3 remote (new)
        _seed_remote_event(fake, tl_id, proj_id, sid, 4, p3, event_id=generate_event_ulid())
        r3 = list(fake.events.keys())[-1]  # noqa: F841
        # consume-1]
        # Force invalid cursor: set state remote_event_id to garbage
        from astrid.core.timeline.turso_sync import TursoSyncState

        st = read_turso_sync_state(home)
        assert st is not None
        bad_state = TursoSyncState(
            timeline_id=tl_id,
            local_version=st.local_version,
            local_event_id=st.local_event_id,
            local_hash=st.local_hash,
            remote_version=st.remote_version,
            remote_event_id="01JINVALID0000000000000000AA",
            remote_hash="bad",
            updated_at=st.updated_at,
            last_pushed_event_id=st.last_pushed_event_id,
        )
        write_turso_sync_state(home, bad_state)
        # Now pull: fetch after garbage returns [], fallback fetches all history (r1,r2,r3)
        # r1,r2 already imported (idempotent), r3 new => pulled must be 1
        backend2 = SqliteEventLogBackend(
            timeline_id=tl_id, timeline_home=home, projects_root=tmp_path
        )
        res2 = pull_from_turso(
            timeline_id=tl_id,
            timeline_home=home,
            projects_root=tmp_path,
            backend=backend2,
            replica=replica,
        )
        assert res2.pulled == 1, f"replay inflated: got {res2.pulled!r} expected 1 net-new"
        assert res2.action == "pulled"
        # History completes
        evs = backend2.read_events()
        assert len(evs) == 4
        assert res2.conflict_artifacts is None or len(res2.conflict_artifacts) == 0
