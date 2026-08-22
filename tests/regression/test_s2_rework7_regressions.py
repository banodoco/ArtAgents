"""Revert-sensitive regressions for S2 rework7 I1 corrupt-marker fail-closed + I2 lint — targeted."""

import json
import uuid
from pathlib import Path

from astrid.core.events.service import EventAppendService
from astrid.core.integrations.reigh.bridge_service import derive_database_path
from astrid.core.store.uow import UnitOfWork
from astrid.core.timeline.events.schema import generate_event_ulid
from astrid.packs import build_standard_registry, open_standard_writer
from astrid.packs.timeline.backfill import write_backfill_state


def _seed_kernel_with_backfill(tmp_path: Path, project_slug: str = "proj", timeline_slug: str = "t1"):
    registry = build_standard_registry()
    db_path = derive_database_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    proj_id = uuid.uuid4().hex
    tl_id = str(uuid.uuid4())
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
            data={"timeline_id": tl_id, "timeline_ulid": ulid, "slug": timeline_slug, "name": "T1"},
            changes=["timeline_id", "slug", "name"],
            idempotency_key=f"create:{tl_id}",
            txn_id=generate_event_ulid(),
            actor_kind="system",
            event_id=generate_event_ulid(),
        )

    UnitOfWork(writer).run(_append)
    from astrid.core.receipts.canonical import canonical_json as _cj

    def _ensure_timeline_row(uow: UnitOfWork):
        row = uow.query_one("SELECT id FROM timelines WHERE id = ?", (tl_id,))
        if row is None:
            uow.execute(
                "INSERT INTO timelines (id, project_id, event_stream_id, name, document_json, asset_registry_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tl_id, proj_id, stream_id, "T1", _cj({"tracks": [], "clips": []}), _cj({}), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )

    UnitOfWork(writer).run(_ensure_timeline_row)
    write_backfill_state(tmp_path, timeline_id=tl_id, source="local_fs", source_head_version=1, events_sha256="abc")
    proj_dir = tmp_path / project_slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    if not (proj_dir / "project.json").exists():
        (proj_dir / "project.json").write_text(json.dumps({"slug": project_slug, "created_at": "2026-01-01T00:00:00Z", "name": project_slug, "schema_version": 1, "updated_at": "2026-01-01T00:00:00Z", "default_timeline_id": None}), encoding="utf-8")
    tdir = proj_dir / "timelines" / ulid
    tdir.mkdir(parents=True, exist_ok=True)
    # close writer and unregister to avoid lock leak in tests
    try:
        writer.close()
    except Exception:
        pass
    try:
        from astrid.packs import _unregister_active_writer

        _unregister_active_writer(db_path)
    except Exception:
        pass
    try:
        from astrid.core.store.writer import _release_owner_lock  # type: ignore

        _release_owner_lock(db_path)  # type: ignore
    except Exception:
        pass
    # also try DatabaseOwnerLock release
    try:
        from astrid.core.store.owner_lock import DatabaseOwnerLock

        DatabaseOwnerLock(db_path).release()
    except Exception:
        pass
    return proj_id, tl_id, ulid, stream_id, db_path, tdir


def _corrupt_marker_and_fake_sidecar(tmp_path: Path, tdir: Path, ulid: str, fake_id: str = "00000000-0000-4000-a000-000000000000"):
    marker = tmp_path / ".astrid" / "backfill-state.json"
    marker.write_text("corrupt!!! { not json", encoding="utf-8")
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "assembly.identity.json").write_text(json.dumps({"timeline_id": fake_id, "timeline_ulid": ulid, "backend": "local_fs"}), encoding="utf-8")
    (tdir / "display.json").write_text(json.dumps({"slug": "t1", "is_default": False}), encoding="utf-8")
    return marker


def test_a_resolver_raises_on_corrupt_marker(tmp_path: Path):
    _proj_id, tl_id, ulid, _sid, _db, tdir = _seed_kernel_with_backfill(tmp_path)
    fake_id = "00000000-0000-4000-a000-000000000000"
    assert fake_id != tl_id
    _corrupt_marker_and_fake_sidecar(tmp_path, tdir, ulid, fake_id)
    from astrid.core.timeline.authority import resolve_authoritative_timeline_id
    from astrid.packs.timeline.backfill import BackfillError

    try:
        result = resolve_authoritative_timeline_id(tdir, tmp_path)
    except BackfillError:
        return
    except Exception as exc:
        # Any BackfillError subclass is ok, but other exception is not the expected fail-closed
        # Check if it's a BackfillError wrapped
        if "backfill" in str(exc).lower() or "authority marker" in str(exc).lower():
            return
        assert False, f"expected BackfillError, got {type(exc).__name__}: {exc}"
    assert False, f"expected BackfillError but got result {result!r} (fake? {result==fake_id})"


def test_b_canonical_id_propagates_on_corrupt_marker(tmp_path: Path):
    _proj_id, tl_id, ulid, _sid, _db, tdir = _seed_kernel_with_backfill(tmp_path)
    fake_id = "00000000-0000-4000-a000-000000000000"
    _corrupt_marker_and_fake_sidecar(tmp_path, tdir, ulid, fake_id)
    from astrid.core.integrations.reigh.local_bridge import _load_canonical_timeline_id
    from astrid.packs.timeline.backfill import BackfillError

    try:
        result = _load_canonical_timeline_id(tdir, ulid)
    except BackfillError:
        return
    except RuntimeError as exc:
        if "backfill" in str(exc).lower():
            return
        assert False, f"expected BackfillError/RuntimeError marker, got RuntimeError: {exc}"
    except Exception as exc:
        if "backfill" in str(exc).lower():
            return
        assert False, f"expected BackfillError, got {type(exc).__name__}: {exc}"
    # If it returned, it must not be the fake id nor silent ulid
    assert result != fake_id, f"returned fake stale sidecar id {fake_id!r} — fail-open"
    assert False, f"expected BackfillError but returned {result!r}"


def test_c_visualize_never_selects_stale_on_corrupt_marker(tmp_path: Path):
    _proj_id, tl_id, ulid, _sid, _db, tdir = _seed_kernel_with_backfill(tmp_path)
    fake_id = "00000000-0000-4000-a000-000000000000"
    _corrupt_marker_and_fake_sidecar(tmp_path, tdir, ulid, fake_id)
    from astrid.packs.rendering.executors.timeline_visualize.select import select_timeline

    project_dir = tmp_path / "proj"
    selected, diagnostics = select_timeline(project_dir)
    # Must never select the stale fake id
    for t in selected:
        assert t.timeline_id != fake_id, f"visualize selected stale fake id {fake_id!r}"
        assert str(t.timeline_id).lower() != fake_id.lower()
    # Must report diagnostics about unreadable marker (fail-closed)
    diag_text = " ".join(diagnostics).lower()
    assert "backfill" in diag_text or "authority" in diag_text or "unreadable" in diag_text, f"expected marker diagnostics, got {diagnostics!r}"
    # Also, if a slug is explicitly requested, it should also not select stale
    selected2, diagnostics2 = select_timeline(project_dir, slug="t1")
    for t in selected2:
        assert t.timeline_id != fake_id
    diag2 = " ".join(diagnostics2).lower()
    # diagnostics should still mention marker failure
    assert "backfill" in diag2 or "authority" in diag2 or "unreadable" in diag2 or len(selected2) == 0


def test_pure_legacy_sidecar_unchanged_when_no_db(tmp_path: Path):
    """Pure-legacy (no DB) projects still consult sidecar."""
    project_slug = "legacy-proj"
    ulid = "01J0000000000000000000000B"
    proj_dir = tmp_path / project_slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    tdir = proj_dir / "timelines" / ulid
    tdir.mkdir(parents=True, exist_ok=True)
    fake_id = "11111111-1111-4111-a111-111111111111"
    (tdir / "assembly.identity.json").write_text(json.dumps({"timeline_id": fake_id, "timeline_ulid": ulid}), encoding="utf-8")
    from astrid.core.timeline.authority import resolve_authoritative_timeline_id

    result = resolve_authoritative_timeline_id(tdir, tmp_path)
    assert result == fake_id
