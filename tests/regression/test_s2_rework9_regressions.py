"""Revert-sensitive regressions for S2 rework9 K1 selector kernel-first + K2 fresh bind."""

import json
import sqlite3
import tempfile
import uuid
from pathlib import Path

from astrid.packs.timeline.backfill import write_backfill_state


def _head_seq(db: Path, timeline_id: str) -> int:
    sid = f"{timeline_id}:timeline.timeline"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT head_seq FROM event_streams WHERE id = ?", (sid,)).fetchone()
        return int(row["head_seq"]) if row else 0
    finally:
        conn.close()


def _jsonl_lines(tdir: Path) -> int:
    p = tdir / "assembly.jsonl"
    if not p.is_file():
        return 0
    return len([ln for ln in p.read_text().splitlines() if ln.strip()])


def _tdir(tmp: Path, project_slug: str, ulid: str) -> Path:
    d = tmp / project_slug / "timelines" / ulid.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d

def test_k2_fresh_bind_managed_timeline_ok():
    """K2: fresh bind_managed_timeline on project without that slug returns (ulid, slug, kernel_id) end-to-end."""
    from astrid.core.project.project import create_project
    from astrid.core.project.run import bind_managed_timeline

    tmp = Path(tempfile.mkdtemp(prefix="k2-fresh-"))
    try:
        create_project("proj-k2", root=str(tmp), name="Proj K2")
        # Fresh bind: project exists but timeline slug does not
        ulid, slug, tid = bind_managed_timeline("proj-k2", "t-fresh", root=str(tmp))
        assert isinstance(ulid, str) and len(ulid) == 26, f"ulid {ulid}"
        assert slug == "t-fresh"
        assert isinstance(tid, str) and len(tid) > 10
        # Second call: existing path
        ulid2, slug2, tid2 = bind_managed_timeline("proj-k2", "t-fresh", root=str(tmp))
        assert ulid2 == ulid
        assert tid2 == tid
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def _seed_marked(tmp: Path, proj: str = "proj-k1", slug: str = "t1"):
    from astrid.core.project.project import create_project
    from astrid.core.timeline.crud import rename_timeline
    from astrid.core.timeline.paths import timelines_dir

    create_project(proj, root=str(tmp), name="Proj K1")
    from astrid.application import compose_standard_application

    app = compose_standard_application(projects_root=str(tmp))
    app.projects_service.create(slug=proj, name="Proj K1")
    created = app.timelines_service.create(project=proj, slug=slug, name="T1", idempotency_key="k-k1")
    tid_real = created.data["timeline_id"]
    ulid = created.data["timeline_ulid"]
    # Ensure timeline home dir exists for filesystem probes (marker + display repair)
    tdir = timelines_dir(proj, root=str(tmp)) / ulid.upper()
    tdir.mkdir(parents=True, exist_ok=True)
    write_backfill_state(tmp, timeline_id=tid_real, source="local_fs", source_head_version=1, events_sha256="abc")
    rename_timeline(proj, slug, "t2", root=str(tmp))
    return app, tid_real, ulid



def test_k1_selector_by_renamed_slug_fake_sidecar_hits_sqlite():
    """K1: marked+renamed timeline + FAKE sidecar, resolve_event_log_target by RENAMED slug => sqlite with KERNEL id."""
    from astrid.core.timeline.eventlog.selector import resolve_event_log_target

    tmp = Path(tempfile.mkdtemp(prefix="k1-sel-renamed-"))
    try:
        app, tid_real, ulid = _seed_marked(tmp)
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-k1", "t2", root=str(tmp))
        assert found is not None
        tdir = found[1]
        fake_id = str(uuid.uuid4())
        id_path = tdir / "assembly.identity.json"
        raw = json.loads(id_path.read_text()) if id_path.is_file() else {}
        raw["timeline_id"] = fake_id
        raw["timeline_ulid"] = ulid
        id_path.write_text(json.dumps(raw))
        # Also poison timeline_id in display? not needed
        target = resolve_event_log_target("proj-k1", "t2", root=str(tmp))
        assert target.backend_name == "sqlite", f"expected sqlite got {target.backend_name}"
        assert target.timeline_id == tid_real, f"expected kernel {tid_real} got {target.timeline_id}"
        assert fake_id not in target.timeline_id
        # Backend should be SqliteEventLogBackend
        assert "Sqlite" in type(target.backend).__name__
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_k1_selector_by_ulid_fake_sidecar_hits_sqlite():
    """K1: by ULID with fake sidecar => sqlite kernel resolution."""
    from astrid.core.timeline.eventlog.selector import resolve_event_log_target

    tmp = Path(tempfile.mkdtemp(prefix="k1-sel-ulid-"))
    try:
        app, tid_real, ulid = _seed_marked(tmp)
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-k1", "t2", root=str(tmp))
        assert found is not None
        tdir = found[1]
        fake_id = str(uuid.uuid4())
        id_path = tdir / "assembly.identity.json"
        raw = json.loads(id_path.read_text()) if id_path.is_file() else {}
        raw["timeline_id"] = fake_id
        id_path.write_text(json.dumps(raw))
        target = resolve_event_log_target("proj-k1", ulid, root=str(tmp))
        assert target.backend_name == "sqlite"
        assert target.timeline_id == tid_real
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_k1_selector_by_uuid_fake_sidecar_hits_sqlite():
    """K1: by UUID (event_stream_id) with fake sidecar dir sanity => sqlite."""
    from astrid.core.timeline.eventlog.selector import resolve_event_log_target

    tmp = Path(tempfile.mkdtemp(prefix="k1-sel-uuid-"))
    try:
        app, tid_real, ulid = _seed_marked(tmp)
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-k1", "t2", root=str(tmp))
        assert found is not None
        tdir = found[1]
        fake_id = str(uuid.uuid4())
        id_path = tdir / "assembly.identity.json"
        raw = json.loads(id_path.read_text()) if id_path.is_file() else {}
        raw["timeline_id"] = fake_id
        id_path.write_text(json.dumps(raw))
        target = resolve_event_log_target("proj-k1", tid_real, root=str(tmp))
        assert target.backend_name == "sqlite"
        assert target.timeline_id == tid_real
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_k1_selector_corrupt_marker_raises_typed():
    """Corrupt marker via selector path => typed BackfillError / EventLogError fail-closed, never LocalFS with fake."""
    from astrid.core.timeline.eventlog.selector import resolve_event_log_target

    tmp = Path(tempfile.mkdtemp(prefix="k1-corrupt-"))
    try:
        app, tid_real, ulid = _seed_marked(tmp)
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-k1", "t2", root=str(tmp))
        assert found is not None
        tdir = found[1]
        fake_id = str(uuid.uuid4())
        id_path = tdir / "assembly.identity.json"
        raw = json.loads(id_path.read_text()) if id_path.is_file() else {}
        raw["timeline_id"] = fake_id
        id_path.write_text(json.dumps(raw))
        marker = tmp / ".astrid" / "backfill-state.json"
        marker.write_text("{ not json")
        raised = False
        try:
            resolve_event_log_target("proj-k1", "t2", root=str(tmp))
        except Exception as exc:  # noqa: BLE001
            raised = True
            msg = str(exc).lower()
            assert "backfill" in msg or "marker" in msg or "unreadable" in msg, f"expected backfill error, got {exc!r}"
            # Ensure not LocalFS with fake
            assert fake_id not in str(exc)
        assert raised, "expected typed BackfillError/EventLogError"
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_k1_unbackfilled_legacy_selector_unchanged():
    """Unbackfilled legacy dir: selector still returns LocalFS with sidecar semantics."""
    tmp = Path(tempfile.mkdtemp(prefix="k1-legacy-"))
    try:
        from astrid.core.project.project import create_project
        from astrid.core.timeline.crud import create_timeline
        from astrid.core.timeline.eventlog.selector import resolve_event_log_target

        create_project("proj-leg", root=str(tmp), name="Proj Leg")
        created = create_timeline("proj-leg", "t-leg", root=str(tmp))
        ulid = created["ulid"]
        from astrid.core._shared.jsonio import read_json
        from astrid.core.timeline.paths import assembly_identity_path

        tid = read_json(assembly_identity_path("proj-leg", ulid, root=str(tmp))).get("timeline_id")
        # Do NOT write backfill marker — remains legacy
        target = resolve_event_log_target("proj-leg", "t-leg", root=str(tmp))
        assert target.backend_name == "local_fs"
        assert target.timeline_id == tid
        # By ULID
        target2 = resolve_event_log_target("proj-leg", ulid, root=str(tmp))
        assert target2.backend_name == "local_fs"
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_find_timeline_by_event_stream_id_marked_fake_sidecar_skipped():
    """find_timeline_by_event_stream_id for marked timeline ignores fake sidecar, returns kernel ULID."""
    from astrid.core.timeline.paths import find_timeline_by_event_stream_id

    tmp = Path(tempfile.mkdtemp(prefix="k1-fes-"))
    try:
        app, tid_real, ulid = _seed_marked(tmp)
        from astrid.core.timeline.paths import find_timeline_by_slug

        found = find_timeline_by_slug("proj-k1", "t2", root=str(tmp))
        assert found is not None
        tdir = found[1]
        fake_id = str(uuid.uuid4())
        id_path = tdir / "assembly.identity.json"
        raw = json.loads(id_path.read_text()) if id_path.is_file() else {}
        raw["timeline_id"] = fake_id
        id_path.write_text(json.dumps(raw))
        res = find_timeline_by_event_stream_id("proj-k1", tid_real, root=str(tmp))
        assert res is not None, "kernel UUID should be found even with fake sidecar"
        assert res[0].lower() == ulid.lower()
        # Fake UUID should not be found (no marked entry)
        res_fake = find_timeline_by_event_stream_id("proj-k1", fake_id, root=str(tmp))
        assert res_fake is None
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
