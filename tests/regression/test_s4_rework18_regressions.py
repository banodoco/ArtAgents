# ruff: noqa: E501
"""S4 rework-18 — D1-D5 document-identity seam pins (RED→GREEN quoted)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import (
    FakeTursoTransport,
    TursoReplicaClient,
    TursoSyncError,
)
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import (
    TursoSyncState,
    pull_from_turso,
    push_to_turso,
    read_turso_sync_state,
    write_turso_sync_state,
)
from astrid.packs import build_standard_registry, open_standard_writer


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    import json as _json

    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.store.uow import UnitOfWork

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
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tl_id, proj_id, sid, "T1", _json.dumps({"tracks": []}), _json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )

    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow: UnitOfWork):
        svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.created", data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"}, changes=["timeline_id", "slug", "name"], idempotency_key=f"create:{tl_id}", txn_id=generate_event_ulid(), actor_kind="system", event_id=generate_event_ulid())

    UnitOfWork(writer).run(_append)
    writer.close()
    home = tmp_path / project_slug / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
    return proj_id, tl_id, sid, home


def _make_v0_db(tmp_path: Path, project_slug: str = "proj"):
    import json as _json

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
            "INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (proj_id, project_slug, "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)",
            (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"),
        )
        uow.execute(
            "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tl_id, proj_id, sid, "T1", _json.dumps({"tracks": []}), _json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )

    UnitOfWork(writer).run(_setup)
    writer.close()
    home = tmp_path / project_slug / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state

    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=0, events_sha256="abc")
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
    for _ in range(n):
        eid = generate_event_ulid()

        def _ap(uow: UnitOfWork, eid=eid):
            svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.archived", data={"timeline_id": tl_id, "archived_at": "2026-01-02T00:00:00Z"}, changes=["archived_at"], idempotency_key=f"ik:{eid}", txn_id=generate_event_ulid(), actor_kind="system", event_id=eid)

        UnitOfWork(writer).run(_ap)
        ids.append(eid)
    writer.close()
    return ids


# 1. cosmetic-equality-no-fork
class TestCosmeticEqualityNoFork:
    def test_cosmetic_json_equal_is_up_to_date(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # cosmetic variant: same structure different bytes (key order/whitespace)
        orig = json.loads(fake.documents[tl_id]["document_json"])
        # re-serialize with sorted keys + different indent
        variant = json.dumps(orig, sort_keys=True, indent=4)
        # ensure variant differs byte-wise but structurally equal
        assert variant != fake.documents[tl_id]["document_json"]
        assert json.loads(variant) == orig
        fake.documents[tl_id]["document_json"] = variant
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "up_to_date", f"cosmetic forked incorrectly: {r2!r}"
        r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r3.action == "up_to_date", f"pull cosmetic forked: {r3!r}"
        assert not r2.conflict_artifacts

    def test_cosmetic_unparseable_forks(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        fake.documents[tl_id]["document_json"] = "not-json {{{"
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict", f"unparseable should fork: {r2!r}"


# 2. read-failure-fail-closed
class TestReadFailureFailClosed:
    def test_second_doc_read_failure_not_up_to_date(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # make docs diverge
        fake.documents[tl_id]["document_json"] = json.dumps({"tampered": True})
        # flaky second head read: first succeeds, second fails
        orig_fetch = replica.fetch_remote_head
        calls = {"n": 0}

        def flaky(tid):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("flaky injected")
            return orig_fetch(tid)

        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        with patch.object(replica, "fetch_remote_head", side_effect=flaky):
            try:
                r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
            except TursoSyncError as e:
                # fail-closed via typed error is acceptable
                assert "remote document fetch failed" in str(e) or "failing closed" in str(e)
                return
            # if not raised, must be conflict, not up_to_date
            assert r2.action != "up_to_date", f"fail-open on flaky read: {r2!r}"
            assert r2.action == "conflict" or isinstance(r2.action, str) and r2.action != "up_to_date"

        # same for pull
        calls["n"] = 0
        backend3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        with patch.object(replica, "fetch_remote_head", side_effect=flaky):
            try:
                r3 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend3, replica=replica)
            except TursoSyncError:
                return
            assert r3.action != "up_to_date", f"pull fail-open: {r3!r}"


# 3. empty-head-divergence-fork
class TestEmptyHeadDivergenceFork:
    def test_v0_divergent_docs_forks(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_v0_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        # push v0 document to remote (for v0, push may be no-op, so seed manually if needed)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        if tl_id not in fake.documents:
            # seed remote with local doc (v0 bootstrap)
            import sqlite3

            from astrid.core.integrations.reigh.bridge_service import derive_database_path
            db_path = derive_database_path(tmp_path)
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,))
            lj = cur.fetchone()[0]
            conn.close()
            fake.documents[tl_id] = {"timeline_id": tl_id, "project_id": proj_id, "event_stream_id": sid, "name": "T1", "document_json": lj, "version": 0, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
        # wipe state to simulate state-wiped v0 shape
        p = home / "turso-sync-state.json"
        if p.exists():
            p.unlink()
        # diverge docs at v0 (both heads 0 after wipe)
        fake.documents[tl_id]["document_json"] = json.dumps({"v0": "remote"})
        # local doc is {"tracks": []} initially
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict", f"v0 divergent should fork, got {r2!r}"
        assert r2.conflict_artifacts

    def test_v0_equal_docs_stays_up_to_date(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_v0_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        p = home / "turso-sync-state.json"
        if p.exists():
            p.unlink()
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "up_to_date"


# 4. crash-resume-with-doc-divergence-not-masked
class TestCrashResumeWithDocDivergenceNotMasked:
    def test_resume_path_checks_doc_before_cursor_write(self, tmp_path: Path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        # add one more event to have version 2
        _append_events(tmp_path, proj_id, tl_id, sid, 1)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        # initial push to create sync at version 2
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        # capture state after push (should be at version 2)
        st = read_turso_sync_state(home)
        assert st is not None
        # append one more local event (version 3) without pushing, and also inject same event into remote to simulate crash-after-commit
        new_ids = _append_events(tmp_path, proj_id, tl_id, sid, 1)
        new_eid = new_ids[0]
        # seed remote with same event
        import sqlite3

        from astrid.core.integrations.reigh.bridge_service import derive_database_path

        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = conn.execute("SELECT payload_json, seq FROM events WHERE event_id=?", (new_eid,)).fetchone()
        payload_json = row[0]
        seq = row[1]
        conn.close()
        # inject into fake events with matching payload
        fake.events[new_eid] = {
            "event_id": new_eid,
            "timeline_id": tl_id,
            "project_id": fake.documents[tl_id]["project_id"],
            "stream_id": f"{tl_id}:timeline.timeline",
            "seq": seq,
            "kind": "timeline.saved",
            "payload_json": payload_json,
            "actor_kind": "system",
            "actor_id": "system",
            "txn_id": "txn-x",
            "idempotency_key": f"ik:{new_eid}",
            "created_at": "2026-01-02T00:00:00Z",
        }
        # also bump remote document version to 3 with divergent content
        # read local doc
        import sqlite3 as _sq3

        conn2 = _sq3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn2.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,))
        local_doc_json = cur.fetchone()[0]
        conn2.close()
        # diverge remote doc
        fake.documents[tl_id]["document_json"] = json.dumps({"diverged": True, "orig": local_doc_json})
        fake.documents[tl_id]["version"] = 3
        # move state back to version 2 to force resume path (bookmark at 2, both at 3)
        st2 = TursoSyncState(
            timeline_id=tl_id,
            local_version=st.local_version,
            local_event_id=st.local_event_id,
            local_hash=st.local_hash,
            remote_version=st.remote_version,
            remote_event_id=st.remote_event_id,
            remote_hash=st.remote_hash,
            updated_at=st.updated_at,
            last_pushed_event_id=st.local_event_id,
        )
        write_turso_sync_state(home, st2)
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # count doc reads
        calls = {"c": 0}
        orig_fetch = replica.fetch_remote_head

        def counting_fetch(tid):
            calls["c"] += 1
            return orig_fetch(tid)

        with patch.object(replica, "fetch_remote_head", side_effect=counting_fetch):
            r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        # should have performed doc identity check (at least one remote doc read)
        assert calls["c"] >= 1, "resume path did not read remote document (masked divergence)"
        assert r2.action == "conflict", f"resume masked doc divergence: {r2!r} calls={calls}"


# 5. artifact-contains-both-documents
class TestArtifactContainsBothDocuments:
    def test_doc_fork_artifact_embeds_both_payloads(self, tmp_path: Path):
        _, tl_id, _sid, home = _make_local_db(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        r1 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        assert r1.action in ("pushed", "up_to_date")
        fake.documents[tl_id]["document_json"] = json.dumps({"tampered": 123})
        backend2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        # need local doc json
        import sqlite3

        from astrid.core.integrations.reigh.bridge_service import derive_database_path

        db_path = derive_database_path(tmp_path)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,))
        local_json = cur.fetchone()[0]
        conn.close()
        r2 = push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend2, replica=replica)
        assert r2.action == "conflict"
        arts = list(Path(home).glob("divergence-*.json"))
        arts = [p for p in arts if not p.name.endswith(".diagnostic.json")]
        assert arts, "no divergence artifact"
        # pick latest
        latest = sorted(arts)[-1]
        data = json.loads(latest.read_text())
        # must contain both document payloads
        has_local = ("local_document" in data and data["local_document"] is not None) or ("local_document_json" in data and data["local_document_json"] is not None)
        has_remote = ("remote_document" in data and data["remote_document"] is not None) or ("remote_document_json" in data and data["remote_document_json"] is not None)
        # also check documents wrapper
        has_wrapper = "documents" in data and isinstance(data["documents"], dict) and data["documents"].get("local") is not None and data["documents"].get("remote") is not None
        assert has_local and has_remote or has_wrapper, f"artifact missing documents: {data.keys()} {data}"
        # verify payloads match expected
        if "local_document_json" in data:
            assert json.loads(data["local_document_json"]) == json.loads(local_json)
        if "remote_document_json" in data:
            assert json.loads(data["remote_document_json"]) == {"tampered": 123}
        # diagnostic also
        diag = latest.with_name(latest.stem + ".diagnostic.json")
        if diag.exists():
            ddata = json.loads(diag.read_text())
            assert ddata.get("local_document") is not None or ddata.get("local_document_json") is not None
            assert ddata.get("remote_document") is not None or ddata.get("remote_document_json") is not None
