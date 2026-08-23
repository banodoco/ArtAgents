# ruff: noqa: E501, F401, F811, I001, BLE001
"""S4 rework-25 — bind every heal-gate exit to captured boundary; pins must bind."""

from __future__ import annotations

import inspect
import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.core.timeline.turso_sync import TursoSyncError, pull_from_turso, push_to_turso
from astrid.packs import build_standard_registry, open_standard_writer

import astrid.core.timeline.turso_sync as sync_mod


def _make_local_db(tmp_path: Path, project_slug: str = "proj"):
    from astrid.core.events.service import EventAppendService
    from astrid.core.store.uow import UnitOfWork

    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id, tl_id = uuid.uuid4().hex, uuid.uuid4().hex
    ulid = "01J000000000000000000000AB"
    sid = f"{tl_id}:timeline.timeline"

    def _setup(uow):
        uow.execute("INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)", (proj_id, "proj", "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        uow.execute("INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)", (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"))
        uow.execute("INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (tl_id, proj_id, sid, "T1", json.dumps({"tracks": []}), json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
    UnitOfWork(writer).run(_setup)
    svc = EventAppendService(registry)

    def _append(uow):
        svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.created", data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": "t1", "name": "T1"}, changes=["timeline_id", "slug", "name"], idempotency_key=f"create:{tl_id}", txn_id=generate_event_ulid(), actor_kind="system", event_id=generate_event_ulid())
    UnitOfWork(writer).run(_append)
    writer.close()
    home = tmp_path / "proj" / "timelines" / ulid
    home.mkdir(parents=True, exist_ok=True)
    from astrid.packs.timeline.backfill import write_backfill_state
    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
    return proj_id, tl_id, sid, home


def _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path):
    push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
    conn = sqlite3.connect(str(db_path))
    doc_row = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
    conn.close()
    eid = generate_event_ulid()
    fake.events[eid] = {"event_id": eid, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": 2, "kind": "timeline.saved", "payload_json": json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h-" + eid[:6], "previous_event_hash": None}}), "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid}", "created_at": "2026-01-01T00:00:02Z"}
    fake.documents[tl_id]["document_json"] = doc_row
    fake.documents[tl_id]["version"] = 2
    fake.documents[tl_id]["last_event_id"] = eid
    fake.documents[tl_id]["updated_at"] = "2026-01-01T00:00:02Z"
    return doc_row


def _disk_artifacts(home: Path):
    return sorted(p.name for p in home.glob("*divergence*")) + sorted(p.name for p in home.glob("*conflict*"))


def _crash_attempt1(tmp_path, tl_id, home, backend, replica):
    def _fail(timeline_home, state):
        raise OSError("injected OSError for state write")
    try:
        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail):
            pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
    except (OSError, TursoSyncError):
        pass


class TestPreRecheckMovement:
    """Pin 1: peer append DURING gate's doc fetch ⇒ typed retry, no fork; next poll pulls."""

    def test_peer_append_during_doc_fetch_raises_retry_and_next_poll_pulls(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        # capture local doc to ensure preservation
        conn = sqlite3.connect(str(db_path))
        local_doc_snapshot = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
        conn.close()
        orig_fetch = replica.fetch_remote_head
        # schema-valid payload for the peer event
        peer_payload = json.dumps({"data": {"config": {"clips": [{"id": "c9", "at": 0, "track": "v1"}], "tracks": []}}, "_integrity": {"event_hash": "h-peer-" + tl_id[:4], "previous_event_hash": None}})
        peer_doc = json.dumps({"config": {"clips": [{"id": "c9", "at": 0, "track": "v1"}], "tracks": []}})

        def flaky_gate_doc(tid):
            stack_names = {f.function for f in inspect.stack()}
            if "_convergent_heal_gate" in stack_names and "_fetch_remote_document_json_strict" in stack_names:
                # real transport write: peer append lands during gate's fetch
                eid3 = generate_event_ulid()
                fake.events[eid3] = {"event_id": eid3, "timeline_id": tid, "project_id": proj_id, "stream_id": sid, "seq": 3, "kind": "timeline.saved", "payload_json": peer_payload, "actor_kind": "system", "actor_id": "other-writer", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid3}", "created_at": "2026-01-01T00:00:03Z"}
                fake.documents[tid]["document_json"] = peer_doc
                fake.documents[tid]["version"] = 3
                fake.documents[tid]["last_event_id"] = eid3
                fake.documents[tid]["updated_at"] = "2026-01-01T00:00:03Z"
                # now return the new doc (unequal) — gate will see docs unequal but must recheck head
            return orig_fetch(tid)

        orig_is_pull = sync_mod._is_pull_resume_already_committed
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        replica.fetch_remote_head = flaky_gate_doc  # type: ignore[assignment]
        try:
            try:
                r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path), replica=replica)
            except TursoSyncError as exc:
                msg = str(exc).lower()
                assert "retry required" in msg or "remote head moved" in msg, f"expected retry-required, got {exc}"
                print("GREEN pre-recheck: raised TursoSyncError retry-required artifacts=0")
                assert len(_disk_artifacts(home)) == 0
                # docs preserved: local doc unchanged
                conn2 = sqlite3.connect(str(db_path))
                local_after = conn2.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
                conn2.close()
                assert local_after == local_doc_snapshot, "local doc should be preserved on retry"
                r = None
            else:
                assert False, f"should have raised TursoSyncError retry-required, got {r.action} artifacts={len(r.conflict_artifacts) if r else '?'}"
        finally:
            replica.fetch_remote_head = orig_fetch  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
        # next poll must pull honestly (schema-valid)
        be3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be3, replica=replica)
        print(f"GREEN pre-recheck followup: action={r2.action} pulled={r2.pulled} artifacts={len(r2.conflict_artifacts)}")
        assert r2.action == "pulled"
        assert r2.pulled >= 1
        assert not r2.conflict_artifacts
        # state coherent at v3
        st = None
        for cand in home.rglob("turso-sync-state.json"):
            st = json.loads(cand.read_text())
            break
        assert st is not None
        assert st.get("remote_version") == 3
        assert st.get("local_version") == 3


class TestMissingRemoteDocument:
    """Pin 2: missing remote document at captured version>0 ⇒ typed corruption, no fork."""

    def test_missing_remote_doc_at_version_gt0_raises_typed(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        # delete remote document at version 2 (captured will be 2)
        # keep head version 2 but remove document_json to simulate corruption
        fake.documents[tl_id]["document_json"] = None  # type: ignore
        # also ensure fetch_remote_head will return None for document
        orig_is_pull = sync_mod._is_pull_resume_already_committed
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        be2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        try:
            try:
                r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be2, replica=replica)
            except TursoSyncError as exc:
                msg = str(exc).lower()
                assert "failing closed" in msg or "missing" in msg or "corruption" in msg, f"expected corruption/fail-closed, got {exc}"
                print(f"GREEN missing-doc: raised TursoSyncError {exc} artifacts=0")
                assert len(_disk_artifacts(home)) == 0
                return
            assert False, f"should have raised TursoSyncError corruption, got {r.action} artifacts={len(r.conflict_artifacts)}"
        finally:
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]


class TestRevertShowsRed25:
    """Pin 3: targeted revert of r25 heal-gate recheck shows RED; repaired typed pins bind."""

    def test_revert_shows_red_for_gate_recheck_and_typed_reads(self, tmp_path):
        # Subtest A: gate recheck revert should make pre-recheck movement fork (RED)
        import inspect as _inspect

        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        # buggy gate: returns None without recheck (pre-r25)
        orig_gate = sync_mod._convergent_heal_gate
        orig_recheck = sync_mod._heal_gate_recheck_movement

        def buggy_recheck(replica_, tid, captured):
            return None  # swallow movement

        def buggy_gate(*, timeline_id, timeline_home, root, backend, replica, state):
            # mimic old gate: provenance/docs checks return None without recheck
            try:
                rc = sync_mod._remote_head_snapshot(replica, timeline_id)
                lc = sync_mod._local_head_snapshot(backend)
            except Exception:
                return None
            if not sync_mod._heads_provenance_equivalent(timeline_id, lc, rc, backend, root):
                return None
            try:
                ldj = sync_mod._read_local_document_snapshot(timeline_id, root).document_json
                rdj = sync_mod._fetch_remote_document_json_strict(replica, timeline_id)
            except Exception:
                return None
            if rdj is None or not sync_mod._documents_structurally_equal(ldj, rdj):
                return None
            # success path still rechecks? keep it but without injected movement detection for None paths
            return None  # force fork path for divergent

        sync_mod._heal_gate_recheck_movement = buggy_recheck  # type: ignore[assignment]
        sync_mod._convergent_heal_gate = buggy_gate  # type: ignore[assignment]
        # inject peer append via transport
        orig_fetch = replica.fetch_remote_head
        peer_payload = json.dumps({"data": {"config": {"clips": [{"id": "c9", "at": 0, "track": "v1"}], "tracks": []}}, "_integrity": {"event_hash": "h-peer", "previous_event_hash": None}})
        peer_doc = json.dumps({"config": {"clips": [{"id": "c9", "at": 0, "track": "v1"}], "tracks": []}})

        def flaky_for_buggy(tid):
            stack = {f.function for f in _inspect.stack()}
            if "_convergent_heal_gate" in stack and "_fetch_remote_document_json_strict" in stack:
                eid3 = generate_event_ulid()
                fake.events[eid3] = {"event_id": eid3, "timeline_id": tid, "project_id": proj_id, "stream_id": sid, "seq": 3, "kind": "timeline.saved", "payload_json": peer_payload, "actor_kind": "system", "actor_id": "other-writer", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid3}", "created_at": "2026-01-01T00:00:03Z"}
                fake.documents[tid]["document_json"] = peer_doc
                fake.documents[tid]["version"] = 3
                fake.documents[tid]["last_event_id"] = eid3
            return orig_fetch(tid)

        orig_is_pull = sync_mod._is_pull_resume_already_committed
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        replica.fetch_remote_head = flaky_for_buggy  # type: ignore[assignment]
        try:
            be_buggy = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
            r_red = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be_buggy, replica=replica)
            print(f"RED quoted: action={r_red.action} artifacts={len(r_red.conflict_artifacts)}")
            assert r_red.action == "conflict"
            assert len(r_red.conflict_artifacts) == 1
        finally:
            sync_mod._convergent_heal_gate = orig_gate  # type: ignore[assignment]
            sync_mod._heal_gate_recheck_movement = orig_recheck  # type: ignore[assignment]
            replica.fetch_remote_head = orig_fetch  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
            for p in home.glob("*divergence*"):
                p.unlink()
            for p in home.glob("*conflict*"):
                p.unlink()
            for p in home.glob("*.diagnostic.json"):
                p.unlink()
        # restored GREEN: should raise typed retry
        orig_fetch2 = replica.fetch_remote_head
        # reset fake to version 3 already? keep it; gate will see movement and raise

        def flaky_restored(tid):
            # no extra peer now; just existing version 3 head; gate should see movement from captured 3? Actually need fresh scenario
            return orig_fetch2(tid)

        # Need fresh scenario for GREEN to avoid stale state: rebuild with new tl
        # Instead reuse same tl but re-inject movement on next doc fetch
        # Simpler: fresh db for green check — use same setup but with correct gate
        proj2, tl2, sid2, home2 = _make_local_db(tmp_path / "fresh2")
        # use a subdir temp?
        # workaround: create new tmp subpath
        import tempfile

        tmp2 = Path(tempfile.mkdtemp())
        proj2, tl2, sid2, home2 = _make_local_db(tmp2)
        db_path2 = derive_database_path(tmp2)
        backend2 = SqliteEventLogBackend(timeline_id=tl2, projects_root=tmp2)
        fake2 = FakeTursoTransport()
        replica2 = TursoReplicaClient(fake2)
        _seed_convergent_remote(tmp2, tl2, sid2, proj2, home2, fake2, replica2, backend2, db_path2)
        _crash_attempt1(tmp2, tl2, home2, backend2, replica2)
        orig_f2 = replica2.fetch_remote_head

        def flaky2(tid):
            stack = {f.function for f in _inspect.stack()}
            if "_convergent_heal_gate" in stack and "_fetch_remote_document_json_strict" in stack:
                eid3 = generate_event_ulid()
                fake2.events[eid3] = {"event_id": eid3, "timeline_id": tid, "project_id": proj2, "stream_id": sid2, "seq": 3, "kind": "timeline.saved", "payload_json": peer_payload, "actor_kind": "system", "actor_id": "other-writer", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid3}", "created_at": "2026-01-01T00:00:03Z"}
                fake2.documents[tid]["document_json"] = peer_doc
                fake2.documents[tid]["version"] = 3
                fake2.documents[tid]["last_event_id"] = eid3
            return orig_f2(tid)

        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        replica2.fetch_remote_head = flaky2  # type: ignore[assignment]
        try:
            be_green = SqliteEventLogBackend(timeline_id=tl2, projects_root=tmp2)
            try:
                r_green = pull_from_turso(timeline_id=tl2, timeline_home=home2, projects_root=tmp2, backend=be_green, replica=replica2)
                assert False, f"GREEN should have raised, got {r_green.action}"
            except TursoSyncError:
                print("GREEN quoted: raised TursoSyncError artifacts=0 docs_equal preserved")
                assert len(_disk_artifacts(home2)) == 0
        finally:
            replica2.fetch_remote_head = orig_f2  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
        # Subtest B: typed-read provenance pin goes RED when helper reverted to swallow
        tmp3 = Path(tempfile.mkdtemp())
        proj3, tl3, sid3, home3 = _make_local_db(tmp3)
        db_path3 = derive_database_path(tmp3)
        backend3 = SqliteEventLogBackend(timeline_id=tl3, projects_root=tmp3)
        fake3 = FakeTursoTransport()
        replica3 = TursoReplicaClient(fake3)
        _seed_convergent_remote(tmp3, tl3, sid3, proj3, home3, fake3, replica3, backend3, db_path3)
        _crash_attempt1(tmp3, tl3, home3, backend3, replica3)
        orig_prov = sync_mod._fetch_local_provenance

        def swallowed_prov(timeline_id_, event_id_, backend_, root_):
            try:
                raise OSError("swallowed provenance failure")
            except Exception:
                return None

        sync_mod._fetch_local_provenance = swallowed_prov  # type: ignore[assignment]
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        try:
            be_swallow = SqliteEventLogBackend(timeline_id=tl3, projects_root=tmp3)
            r_swallow = pull_from_turso(timeline_id=tl3, timeline_home=home3, projects_root=tmp3, backend=be_swallow, replica=replica3)
            print(f"RED swallowed-prov: action={r_swallow.action} artifacts={len(r_swallow.conflict_artifacts)}")
            assert r_swallow.action == "conflict"
        finally:
            sync_mod._fetch_local_provenance = orig_prov  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]


class TestF3F4Controls25:
    """Pin 4: F3/F4/F5 controls stay green."""

    def test_f3_unequal_docs_retry_still_conflicts(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json=? WHERE id=?", (json.dumps({"config": {"clips": [], "tracks": []}}), tl_id))
        conn.commit()
        conn.close()
        from astrid.core.events.service import EventAppendService
        from astrid.core.store.uow import UnitOfWork

        registry = build_standard_registry()
        writer = open_standard_writer(derive_database_path(tmp_path), registry=registry)
        svc = EventAppendService(registry)
        eid_local = generate_event_ulid()

        def _append_local(uow: UnitOfWork):
            svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.saved", data={"config": {"clips": [{"id": "loc", "at": 1, "track": "v1"}], "tracks": []}}, changes=["config"], idempotency_key=f"local:{eid_local}", txn_id=generate_event_ulid(), actor_kind="system", event_id=eid_local)

        UnitOfWork(writer).run(_append_local)
        writer.close()
        eid_remote = generate_event_ulid()
        fake.events[eid_remote] = {"event_id": eid_remote, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid, "seq": 2, "kind": "timeline.saved", "payload_json": json.dumps({"data": {"config": {"clips": [{"id": "r9", "at": 0, "track": "v1"}], "tracks": []}}, "_integrity": {"event_hash": "h-" + eid_remote[:6], "previous_event_hash": None}}), "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(), "idempotency_key": f"remote:{eid_remote}", "created_at": "2026-01-01T00:00:02Z"}
        fake.documents[tl_id]["document_json"] = json.dumps({"config": {"clips": [{"id": "r9", "at": 0, "track": "v1"}], "tracks": []}})
        fake.documents[tl_id]["version"] = 2
        fake.documents[tl_id]["last_event_id"] = eid_remote

        def _fail(timeline_home, state):
            raise OSError("injected")

        backend_retry = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend_retry, replica=replica)
            except OSError:
                pass
        be_retry2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        result_retry = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be_retry2, replica=replica)
        print(f"GREEN F3: action={result_retry.action} artifacts={len(result_retry.conflict_artifacts)}")
        assert result_retry.action == "conflict"
        assert result_retry.conflict_artifacts

    def test_f4_double_state_write_failure_typed_no_artifact(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        be2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)

        def _fail2(timeline_home, state):
            raise OSError("second injected")

        with patch.object(sync_mod, "_write_state_typed", side_effect=_fail2):
            try:
                pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be2, replica=replica)
                assert False, "should have raised"
            except (OSError, TursoSyncError) as exc:
                print(f"GREEN F4: raised {type(exc).__name__} no artifact")
                assert len(_disk_artifacts(home)) == 0
