# ruff: noqa: E501, F401, F811, I001, BLE001
"""S4 rework-24 — gate reads fail typed; one-boundary heal (no false conflict, no false up_to_date)."""

from __future__ import annotations

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
    proj_id = uuid.uuid4().hex
    tl_id = uuid.uuid4().hex
    ulid = "01J000000000000000000000AA"
    sid = f"{tl_id}:timeline.timeline"

    def _setup(uow: UnitOfWork):
        uow.execute("INSERT INTO projects (id, slug, name, settings_json, event_head_seq, created_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?)", (proj_id, "proj", "P", "{}", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        uow.execute("INSERT INTO event_streams (id, project_id, stream_type, aggregate_id, head_seq, created_at) VALUES (?, ?, ?, ?, 0, ?)", (sid, proj_id, "timeline.timeline", tl_id, "2026-01-01T00:00:00Z"))
        uow.execute("INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (tl_id, proj_id, sid, "T1", json.dumps({"tracks": []}), json.dumps({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))

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


def _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path):
    push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
    conn = sqlite3.connect(str(db_path))
    doc_row = conn.execute("SELECT document_json FROM timelines WHERE id=?", (tl_id,)).fetchone()[0]
    conn.close()
    eid = generate_event_ulid()
    fake.events[eid] = {
        "event_id": eid, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid,
        "seq": 2, "kind": "timeline.saved",
        "payload_json": json.dumps({"data": {"config": {"clips": [], "tracks": []}}, "_integrity": {"event_hash": "h-" + eid[:6], "previous_event_hash": None}}),
        "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(),
        "idempotency_key": f"remote:{eid}", "created_at": "2026-01-01T00:00:02Z",
    }
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


class TestGateReadTransientTyped:
    """Pin 1: gate-read transient failure (doc/provenance/head) under equal docs ⇒ typed, artifacts=0.

    Real transport injection: failures raised via replica/backend transport methods so the
    heal gate's typed wrappers are exercised — reverting those wrappers to swallow makes
    this pin RED (conflict/fork) instead of GREEN (typed).
    """

    def _run_gate_variant(self, tmp_path, fail_target: str):
        import inspect

        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        orig_is_pull = sync_mod._is_pull_resume_already_committed
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        be2 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        if fail_target == "doc":
            orig_fetch = replica.fetch_remote_head

            def flaky_doc(tid):
                # trigger only when inside the heal gate's doc fetch
                stack_names = {f.function for f in inspect.stack()}
                if "_convergent_heal_gate" in stack_names and "_fetch_remote_document_json_strict" in stack_names:
                    raise OSError("transient remote doc fetch failure at gate")
                return orig_fetch(tid)

            replica.fetch_remote_head = flaky_doc  # type: ignore[assignment]
            try:
                try:
                    r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be2, replica=replica)
                except TursoSyncError as exc:
                    print(f"GREEN {fail_target}: raised TursoSyncError {exc} artifacts=0")
                    assert len(_disk_artifacts(home)) == 0
                    return
                assert False, f"{fail_target} should have raised TursoSyncError, got {r.action}"
            finally:
                replica.fetch_remote_head = orig_fetch  # type: ignore[assignment]
                sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
        elif fail_target == "provenance":
            orig_read = be2.read_events

            def flaky_prov(*a, **k):
                stack_names = {f.function for f in inspect.stack()}
                if "_convergent_heal_gate" in stack_names:
                    raise OSError("transient provenance read failure")
                return orig_read(*a, **k)

            be2.read_events = flaky_prov  # type: ignore[assignment]
            try:
                try:
                    r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be2, replica=replica)
                except TursoSyncError as exc:
                    print(f"GREEN {fail_target}: raised TursoSyncError {exc} artifacts=0")
                    assert len(_disk_artifacts(home)) == 0
                    return
                assert False, f"{fail_target} should have raised TursoSyncError, got {r.action}"
            finally:
                be2.read_events = orig_read  # type: ignore[assignment]
                sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
        elif fail_target == "head":
            orig_fetch = replica.fetch_remote_head

            def flaky_head(tid):
                stack_names = {f.function for f in inspect.stack()}
                if "_convergent_heal_gate" in stack_names:
                    raise OSError("transient head snapshot failure")
                return orig_fetch(tid)

            replica.fetch_remote_head = flaky_head  # type: ignore[assignment]
            try:
                try:
                    r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be2, replica=replica)
                except TursoSyncError as exc:
                    print(f"GREEN {fail_target}: raised TursoSyncError {exc} artifacts=0")
                    assert len(_disk_artifacts(home)) == 0
                    return
                assert False, f"{fail_target} should have raised TursoSyncError, got {r.action}"
            finally:
                replica.fetch_remote_head = orig_fetch  # type: ignore[assignment]
                sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]

    def test_doc_fetch_transient_raises_typed(self, tmp_path):
        self._run_gate_variant(tmp_path, "doc")

    def test_provenance_transient_raises_typed(self, tmp_path):
        self._run_gate_variant(tmp_path, "provenance")

    def test_head_snapshot_transient_raises_typed(self, tmp_path):
        self._run_gate_variant(tmp_path, "head")

class TestOneBoundaryHealTOCTOU:
    """Pin 2: single SCHEMA-VALID interleaved append between equality check and refreshed-head read ⇒ NOT up_to_date, coherent, next poll pulls."""

    def test_interleaved_append_not_up_to_date(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        # interleave on second remote_head capture (recheck)
        orig_snap = sync_mod._remote_head_snapshot
        armed = {"calls": 0}

        def interleave(replica_, tid):
            armed["calls"] += 1
            if armed["calls"] == 3:  # recheck inside heal gate (entry 1, captured 2, recheck 3)
                eid3 = generate_event_ulid()
                fake.events[eid3] = {
                    "event_id": eid3, "timeline_id": tid, "project_id": proj_id, "stream_id": sid,
                    "seq": 3, "kind": "timeline.saved",
                    "payload_json": json.dumps({"data": {"config": {"clips": [{"id": "c9", "at": 0, "track": "v1"}], "tracks": []}}, "_integrity": {"event_hash": "h-" + eid3[:6], "previous_event_hash": None}}),
                    "actor_kind": "system", "actor_id": "other-writer", "txn_id": generate_event_ulid(),
                    "idempotency_key": f"remote:{eid3}", "created_at": "2026-01-01T00:00:03Z",
                }
                fake.documents[tid]["document_json"] = json.dumps({"config": {"clips": [{"id": "c9", "at": 0, "track": "v1"}], "tracks": []}})
                fake.documents[tid]["version"] = 3
                fake.documents[tid]["last_event_id"] = eid3
                fake.documents[tid]["updated_at"] = "2026-01-01T00:00:03Z"
            return orig_snap(replica_, tid)

        orig_is_pull = sync_mod._is_pull_resume_already_committed
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        sync_mod._remote_head_snapshot = interleave  # type: ignore[assignment]
        try:
            try:
                r = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path), replica=replica)
            except TursoSyncError as exc:
                print(f"GREEN B2: raised TursoSyncError on moved head {exc} artifacts=0")
                assert len(_disk_artifacts(home)) == 0
                # persisted state must not be incoherent (2,2) when actual is 3
                st = None
                for cand in home.rglob("turso-sync-state.json"):
                    st = json.loads(cand.read_text())
                    break
                actual_v = fake.documents[tl_id]["version"]
                if st is not None:
                    assert st.get("remote_version") != 2 or actual_v != 3 or st.get("remote_version") == actual_v, f"incoherent state {st} actual {actual_v}"
                r = None
            else:
                # if not raised, must NOT be up_to_date
                assert r is not None
                assert r.action != "up_to_date", f"should not be up_to_date after moved head, got {r.action}"
                print(f"GREEN B2: action={r.action} not up_to_date")
        finally:
            sync_mod._remote_head_snapshot = orig_snap  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
        # NEXT POLL completes pull honestly
        be3 = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        r2 = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be3, replica=replica)
        print(f"GREEN B2 followup: action={r2.action} pulled={r2.pulled} artifacts={len(r2.conflict_artifacts)}")
        assert r2.action == "pulled"
        assert r2.pulled >= 1
        assert not r2.conflict_artifacts
        # state coherent
        st2 = None
        for cand in home.rglob("turso-sync-state.json"):
            st2 = json.loads(cand.read_text())
            break
        assert st2 is not None
        assert st2.get("remote_version") == fake.documents[tl_id]["version"] == 3
        assert st2.get("local_version") == 3


class TestF3F4Controls:
    """Pin 3: F3 unequal-docs retry still conflicts; F4 double state-write failure still typed."""

    def test_f3_unequal_docs_retry_still_conflicts(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        push_to_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=backend, replica=replica)
        # local divergent doc with unequal payload - use valid config
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE timelines SET document_json=? WHERE id=?", (json.dumps({"config": {"clips": [], "tracks": []}}), tl_id))
        conn.commit()
        conn.close()
        from astrid.core.events.service import EventAppendService
        from astrid.core.store.uow import UnitOfWork
        from astrid.packs import build_standard_registry, open_standard_writer
        registry = build_standard_registry()
        writer = open_standard_writer(derive_database_path(tmp_path), registry=registry)
        svc = EventAppendService(registry)
        eid_local = generate_event_ulid()

        def _append_local(uow: UnitOfWork):
            svc.append(uow, stream_id=sid, project_id=proj_id, event_kind="timeline.saved", data={"config": {"clips": [{"id": "loc", "at": 1, "track": "v1"}], "tracks": []}}, changes=["config"], idempotency_key=f"local:{eid_local}", txn_id=generate_event_ulid(), actor_kind="system", event_id=eid_local)

        UnitOfWork(writer).run(_append_local)
        writer.close()
        eid_remote = generate_event_ulid()
        fake.events[eid_remote] = {
            "event_id": eid_remote, "timeline_id": tl_id, "project_id": proj_id, "stream_id": sid,
            "seq": 2, "kind": "timeline.saved",
            "payload_json": json.dumps({"data": {"config": {"clips": [{"id": "r9", "at": 0, "track": "v1"}], "tracks": []}}, "_integrity": {"event_hash": "h-" + eid_remote[:6], "previous_event_hash": None}}),
            "actor_kind": "system", "actor_id": "system", "txn_id": generate_event_ulid(),
            "idempotency_key": f"remote:{eid_remote}", "created_at": "2026-01-01T00:00:02Z",
        }
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


class TestRevertShowsRed24:
    """Pin 4: targeted revert of r24 heal gate shows RED, restored GREEN."""

    def test_revert_shows_red(self, tmp_path):
        proj_id, tl_id, sid, home = _make_local_db(tmp_path)
        db_path = derive_database_path(tmp_path)
        backend = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        fake = FakeTursoTransport()
        replica = TursoReplicaClient(fake)
        _seed_convergent_remote(tmp_path, tl_id, sid, proj_id, home, fake, replica, backend, db_path)
        _crash_attempt1(tmp_path, tl_id, home, backend, replica)
        be_red = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        orig_gate = sync_mod._convergent_heal_gate

        def buggy_heal_swallow(*, timeline_id, timeline_home, root, backend, replica, state):
            try:
                raise OSError("swallowed")
            except Exception:
                return None

        sync_mod._convergent_heal_gate = buggy_heal_swallow  # type: ignore[assignment]
        orig_fetch = sync_mod._fetch_remote_document_json_strict
        cnt = {"n": 0}

        def flaky_fetch_conditional(replica_, tid):
            cnt["n"] += 1
            if cnt["n"] == 1:
                return orig_fetch(replica_, tid)
            raise OSError("transient gate doc fetch")

        sync_mod._fetch_remote_document_json_strict = flaky_fetch_conditional  # type: ignore[assignment]
        orig_is_pull = sync_mod._is_pull_resume_already_committed
        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        try:
            r_red = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be_red, replica=replica)
            print(f"RED quoted: action={r_red.action} artifacts={len(r_red.conflict_artifacts)} docs_equal=True")
            assert r_red.action == "conflict"
            assert len(r_red.conflict_artifacts) == 1
        finally:
            sync_mod._convergent_heal_gate = orig_gate  # type: ignore[assignment]
            sync_mod._fetch_remote_document_json_strict = orig_fetch  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
            for p in home.glob("*divergence*"):
                p.unlink()
            for p in home.glob("*conflict*"):
                p.unlink()
            for p in home.glob("*.diagnostic.json"):
                p.unlink()
        be_green = SqliteEventLogBackend(timeline_id=tl_id, projects_root=tmp_path)
        cnt2 = {"n": 0}

        def flaky_fetch_always(replica_, tid):
            cnt2["n"] += 1
            if cnt2["n"] == 1:
                return orig_fetch(replica_, tid)
            raise OSError("transient gate doc fetch")

        sync_mod._is_pull_resume_already_committed = lambda *a, **k: False  # type: ignore[assignment]
        sync_mod._fetch_remote_document_json_strict = flaky_fetch_always  # type: ignore[assignment]
        try:
            try:
                r_green = pull_from_turso(timeline_id=tl_id, timeline_home=home, projects_root=tmp_path, backend=be_green, replica=replica)
                assert False, f"GREEN should have raised, got {r_green.action}"
            except TursoSyncError:
                print("GREEN quoted: raised TursoSyncError artifacts=0 docs_equal=True")
                assert len(_disk_artifacts(home)) == 0
        finally:
            sync_mod._fetch_remote_document_json_strict = orig_fetch  # type: ignore[assignment]
            sync_mod._is_pull_resume_already_committed = orig_is_pull  # type: ignore[assignment]
