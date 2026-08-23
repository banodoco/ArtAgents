"""Revert-sensitive regressions for S2 rework16 N4 fail-open marker-read + N5 import boundary.

Covers:
 (a) BackfillError at N1 marker read => typed skip, zero discovered (fail-closed).
 (b) OSError at N1 marker read => typed skip, zero discovered (fail-closed).
 (c) Control positive: unverifiable stream still skipped when reads succeed.
 (d) Legacy unmarked timeline still discovered (no false rejection).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from astrid.packs.timeline.backfill import BackfillError

TID_DEAD = "00000000-0000-4000-8000-00000000dead"
TID_LEGACY = "11111111-2222-4333-8444-555555555555"
ULID_A = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
ULID_B = "01ARZ3NDEKTSV4RRFFQ69G5FB0"
def _write_identity(timeline_dir: Path, tid: str, ulid: str, slug: str = "main") -> None:
    ulid_u = ulid.upper()
    tid_l = tid.lower()
    data = {
        "schema_version": 1,
        "timeline_id": tid_l,
        "timeline_ulid": ulid_u,
        "backend": "local_fs",
        "provenance": "created",
        "display": {"slug": slug, "is_default": True, "name": slug},
    }
    timeline_dir.mkdir(parents=True, exist_ok=True)
    (timeline_dir / "assembly.identity.json").write_text(json.dumps(data), encoding="utf-8")
    (timeline_dir / "display.json").write_text(json.dumps({"slug": slug, "is_default": True}), encoding="utf-8")



def _write_marker(projects_root: Path, tids: list[str]) -> None:
    state = {}
    for tid in tids:
        state[tid] = {
            "backfilled_at": "2026-01-01T00:00:00Z",
            "source": "local_fs",
            "source_head_version": 1,
            "events_sha256": "abc",
            "synthesized_bootstrap": False,
            "identity_sha256": "def",
            "registry_sha256": "",
        }
    p = projects_root / ".astrid" / "backfill-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state), encoding="utf-8")


def _setup_poisoned(root: Path, tid: str = TID_DEAD, ulid: str = ULID_A) -> Path:
    project_dir = root / "proj-a"
    tdir = project_dir / "timelines" / ulid.upper()
    _write_identity(tdir, tid, ulid)
    _write_marker(root, [tid])
    # Ensure no DB file — authority stream unverifiable
    db = root / ".astrid" / "astrid.sqlite3"
    if db.is_file():
        db.unlink()
    return project_dir


def test_r16_backfill_error_at_n1_guard_skips_with_typed_diagnostic():
    """R16-a: BackfillError at N1 marker read => typed skip, zero discovered."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        import astrid.packs.timeline.backfill as bf_mod
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        orig = bf_mod.read_backfill_state

        def fault(projects_root, orig=orig):
            raise BackfillError("backfill authority marker is unreadable: injected BackfillError")

        with mock.patch.object(bf_mod, "read_backfill_state", side_effect=fault):
            timelines, diags = _discover(project_dir)
        assert timelines == [], f"expected zero discovered on BackfillError, got {timelines}"
        assert any("backfill authority marker is unreadable" in d for d in diags), f"expected typed unreadable diagnostic, got {diags}"
        assert any(ULID_A in d or TID_DEAD in d or "unreadable" in d.lower() for d in diags)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r16_os_error_at_n1_guard_skips_with_typed_diagnostic():
    """R16-b: OSError at N1 marker read => typed skip, zero discovered."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        import astrid.packs.timeline.backfill as bf_mod
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        def fault(projects_root):
            raise OSError("injected OSError marker unreadable")

        with mock.patch.object(bf_mod, "read_backfill_state", side_effect=fault):
            timelines, diags = _discover(project_dir)
        assert timelines == [], f"expected zero discovered on OSError, got {timelines}"
        assert any("backfill authority marker is unreadable" in d for d in diags), f"expected typed unreadable diagnostic, got {diags}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r16_control_unverifiable_skipped_when_reads_succeed():
    """R16-c: control positive — unverifiable stream skipped when reads succeed."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        timelines, diags = _discover(project_dir)
        assert timelines == [], f"control should discover zero (unverifiable), got {timelines}"
        # Typed skip diagnostic family: UNVERIFIABLE or unreadable
        assert any("UNVERIFIABLE" in d or "unreadable" in d.lower() for d in diags), f"expected typed skip diagnostic, got {diags}"
        assert any("another/UNVERIFIABLE" in d or "unreadable" in d.lower() for d in diags)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r16_legacy_unmarked_still_discovered():
    """R16-d: legacy unmarked timeline still discovered (no false rejection)."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = tmp / "proj-a"
        tdir = project_dir / "timelines" / ULID_B.upper()
        _write_identity(tdir, TID_LEGACY, ULID_B, slug="legacy")
        # Marker exists but does NOT contain TID_LEGACY — genuinely unmarked
        _write_marker(tmp, [TID_DEAD])
        db = tmp / ".astrid" / "astrid.sqlite3"
        if db.is_file():
            db.unlink()
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        timelines, diags = _discover(project_dir)
        assert len(timelines) == 1, f"legacy unmarked should be discovered, got {timelines} diags={diags}"
        assert timelines[0].timeline_id.lower() == TID_LEGACY.lower()
        assert timelines[0].timeline_ulid == ULID_B.upper()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
