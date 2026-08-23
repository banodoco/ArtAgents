"""Revert-sensitive regressions for S2 rework18 N7 post-read authority-state fault.

Covers the last swallowed-exception acceptance edge in `_discover`:

* (a) marker-state object's ``__contains__`` raising OSError  -> typed skip
* (b) same raising RuntimeError (non-OSError class)        -> typed skip
* (c) control — unfaulted poisoned fixture still UNVERIFIABLE-skip
* (d) legacy unmarked timeline still discovered (no over-rejection)
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

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
            "source": "local_fs",
            "source_head_version": 1,
            "events_sha256": "x" * 64,
            "backfilled_at": "2026-01-01T00:00:00Z",
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
    _write_identity(tdir, tid, ulid, slug="main")
    _write_marker(root, [tid])
    db = root / ".astrid" / "astrid.sqlite3"
    if db.is_file():
        db.unlink()
    return project_dir


class _FaultDictOSError(dict):
    """Dict whose ``in`` check raises OSError — simulates post-read state fault."""

    def __contains__(self, key):  # type: ignore[override]
        raise OSError("injected post-read authority-state fault")


class _FaultDictRuntime(dict):
    """Dict whose ``in`` check raises RuntimeError — non-OSError fault class."""

    def __contains__(self, key):  # type: ignore[override]
        raise RuntimeError("injected post-read authority-state fault (RuntimeError)")


def test_r18_post_read_oserror_skips_with_typed_diagnostic():
    """R18-a: state ``__contains__`` raising OSError => typed skip, zero discovered."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        import astrid.packs.timeline.backfill as bf_mod
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        fault_state = _FaultDictOSError({TID_DEAD: {"source": "local_fs"}})

        def fault(projects_root):
            return fault_state

        with mock.patch.object(bf_mod, "read_backfill_state", side_effect=fault):
            timelines, diags = _discover(project_dir)
        assert timelines == [], f"expected zero discovered on post-read OSError, got {timelines} diags={diags}"
        assert any("could not be verified" in d for d in diags), f"expected typed could-not-be-verified diagnostic, got {diags}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r18_post_read_runtimeerror_skips_with_typed_diagnostic():
    """R18-b: state ``__contains__`` raising RuntimeError => typed skip, zero discovered."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        import astrid.packs.timeline.backfill as bf_mod
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        fault_state = _FaultDictRuntime({TID_DEAD: {"source": "local_fs"}})

        def fault(projects_root):
            return fault_state

        with mock.patch.object(bf_mod, "read_backfill_state", side_effect=fault):
            timelines, diags = _discover(project_dir)
        assert timelines == [], f"expected zero discovered on post-read RuntimeError, got {timelines} diags={diags}"
        assert any("could not be verified" in d for d in diags), f"expected typed could-not-be-verified diagnostic, got {diags}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r18_control_unverifiable_still_skipped():
    """R18-c: control — unfaulted poisoned fixture still skipped with UNVERIFIABLE diagnostic."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        timelines, diags = _discover(project_dir)
        assert timelines == [], f"control should discover zero (unverifiable), got {timelines} diags={diags}"
        assert any("UNVERIFIABLE" in d for d in diags), f"expected UNVERIFIABLE diagnostic, got {diags}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r18_legacy_unmarked_still_discovered():
    """R18-d: legacy unmarked timeline still discovered (no over-rejection)."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = tmp / "proj-a"
        tdir = project_dir / "timelines" / ULID_B.upper()
        _write_identity(tdir, TID_LEGACY, ULID_B, slug="legacy")
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
