"""Revert-sensitive regressions for S2 rework8 J1 rename single-authority + sweep closure."""

import json
import sqlite3
import tempfile
from pathlib import Path

from astrid.core.integrations.reigh.bridge_service import derive_database_path
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


def test_j1_rename_marked_fake_sidecar_hits_sqlite_zero_jsonl():
    """J1: marked timeline + FAKE sidecar id -> rename hits SQLite, zero JSONL, no fake id in event, show/find reflect new slug."""
    from astrid.application import compose_standard_application
    from astrid.core.timeline.crud import find_timeline_by_slug, rename_timeline, show_timeline

    tmp = Path(tempfile.mkdtemp(prefix="j1-rename-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        app.projects_service.create(slug="proj-j1", name="Proj J1")
        created = app.timelines_service.create(project="proj-j1", slug="t1", name="T1", idempotency_key="k-j1")
        tid_real = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-j1", ulid)
        write_backfill_state(tmp, timeline_id=tid_real, source="local_fs", source_head_version=1, events_sha256="abc")
        found = find_timeline_by_slug("proj-j1", "t1", root=str(tmp))
        assert found is not None, "timeline should be found before rename"
        tdir_real = found[1]
        db = derive_database_path(tmp)
        head_before = _head_seq(db, tid_real)
        fake_id = "00000000-0000-4000-a000-000000000000"
        id_path = tdir_real / "assembly.identity.json"
        if id_path.is_file():
            raw = json.loads(id_path.read_text())
            raw["timeline_id"] = fake_id
            id_path.write_text(json.dumps(raw))
        else:
            id_path.write_text(json.dumps({"timeline_id": fake_id, "timeline_ulid": ulid, "backend": "local_fs"}))
        lines_before = _jsonl_lines(tdir_real)
        result = rename_timeline("proj-j1", "t1", "t2", root=str(tmp))
        assert result["slug"] == "t2"
        head_after = _head_seq(db, tid_real)
        assert head_after == head_before + 1, f"head should increment 1: {head_before} -> {head_after}"
        lines_after = _jsonl_lines(tdir_real)
        assert lines_after == lines_before, f"JSONL lines should stay {lines_before}, got {lines_after}"
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT payload_json FROM events WHERE kind='timeline.renamed' ORDER BY seq DESC LIMIT 1").fetchone()
            assert row is not None, "renamed event should exist in sqlite"
            payload_str = row["payload_json"]
            assert fake_id not in payload_str, f"fake id {fake_id} leaked into sqlite payload"
        finally:
            conn.close()
        found_new = find_timeline_by_slug("proj-j1", "t2", root=str(tmp))
        assert found_new is not None, "find by new slug should succeed"
        assert found_new[0].lower() == ulid.lower()
        found_old = find_timeline_by_slug("proj-j1", "t1", root=str(tmp))
        assert found_old is None, "old slug should not be found"
        rec = show_timeline("proj-j1", "t2", root=str(tmp))
        assert rec is not None
        assert rec["display"].slug == "t2"
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_j1_rename_unbackfilled_legacy_unchanged():
    """Unbackfilled legacy dir: rename still uses JSONL + display.json (behavior unchanged)."""

    tmp = Path(tempfile.mkdtemp(prefix="j1-legacy-"))
    try:
        from astrid.core.timeline.crud import (
            create_timeline,
            find_timeline_by_slug,
            rename_timeline,
            show_timeline,
        )

        proj_dir = tmp / "proj-leg"
        proj_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "project.json").write_text(
            json.dumps(
                {
                    "slug": "proj-leg",
                    "name": "Proj Leg",
                    "schema_version": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "default_timeline_id": None,
                }
            )
        )
        create_timeline("proj-leg", "oldslug", root=str(tmp))
        found = find_timeline_by_slug("proj-leg", "oldslug", root=str(tmp))
        assert found is not None
        _ulid, tdir = found
        lines_before = _jsonl_lines(tdir)
        result = rename_timeline("proj-leg", "oldslug", "newslug", root=str(tmp))
        assert result["slug"] == "newslug"
        lines_after = _jsonl_lines(tdir)
        assert lines_after == lines_before + 1, f"legacy rename should append JSONL line: {lines_before}->{lines_after}"
        found_new = find_timeline_by_slug("proj-leg", "newslug", root=str(tmp))
        assert found_new is not None
        rec = show_timeline("proj-leg", "newslug", root=str(tmp))
        assert rec is not None and rec["display"].slug == "newslug"
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_j1_rename_corrupt_marker_raises_typed():
    """Corrupt backfill marker + fake sidecar -> rename raises typed BackfillError via TimelineCrudError."""
    from astrid.application import compose_standard_application
    from astrid.core.timeline.crud import TimelineCrudError, find_timeline_by_slug, rename_timeline
    from astrid.packs.timeline.backfill import BackfillError

    tmp = Path(tempfile.mkdtemp(prefix="j1-corrupt-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        app.projects_service.create(slug="proj-corr", name="Proj Corr")
        created = app.timelines_service.create(project="proj-corr", slug="t1", name="T1", idempotency_key="k-corr")
        tid_real = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-corr", ulid)
        write_backfill_state(tmp, timeline_id=tid_real, source="local_fs", source_head_version=1, events_sha256="abc")
        found = find_timeline_by_slug("proj-corr", "t1", root=str(tmp))
        assert found is not None
        tdir_real = found[1]
        marker = tmp / ".astrid" / "backfill-state.json"
        marker.write_text("{ not json", encoding="utf-8")
        id_path = tdir_real / "assembly.identity.json"
        fake_id = "00000000-0000-4000-a000-000000000000"
        if id_path.is_file():
            raw = json.loads(id_path.read_text())
            raw["timeline_id"] = fake_id
            id_path.write_text(json.dumps(raw))
        try:
            rename_timeline("proj-corr", "t1", "t2", root=str(tmp))
            assert False, "expected TimelineCrudError with backfill marker unreadable"
        except TimelineCrudError as exc:
            msg = str(exc).lower()
            assert "backfill" in msg and "unreadable" in msg, f"expected backfill unreadable, got {exc}"
            assert exc.__cause__ is not None and isinstance(exc.__cause__, BackfillError)
        except BackfillError:
            pass
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_j1_rename_preserves_cas():
    """CAS semantics preserved: expected_version mismatch raises, correct version succeeds."""
    from astrid.application import compose_standard_application
    from astrid.core.timeline.crud import rename_timeline

    tmp = Path(tempfile.mkdtemp(prefix="j1-cas-"))
    try:
        app = compose_standard_application(projects_root=str(tmp))
        app.projects_service.create(slug="proj-cas", name="Proj Cas")
        created = app.timelines_service.create(project="proj-cas", slug="t1", name="T1", idempotency_key="k-cas")
        tid_real = created.data["timeline_id"]
        ulid = created.data["timeline_ulid"]
        _tdir(tmp, "proj-cas", ulid)
        write_backfill_state(tmp, timeline_id=tid_real, source="local_fs", source_head_version=1, events_sha256="abc")
        db = derive_database_path(tmp)
        head = _head_seq(db, tid_real)
        try:
            rename_timeline("proj-cas", "t1", "t2", expected_version=head + 10, root=str(tmp))
            assert False, "expected version conflict"
        except Exception as exc:
            msg = str(exc).lower()
            assert "version" in msg or "conflict" in msg or "head" in msg or "stale" in msg
        result = rename_timeline("proj-cas", "t1", "t2", expected_version=head, root=str(tmp))
        assert result["slug"] == "t2"
        head2 = _head_seq(db, tid_real)
        assert head2 == head + 1
        app.close()
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
