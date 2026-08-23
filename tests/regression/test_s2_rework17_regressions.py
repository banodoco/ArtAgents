"""Revert-sensitive regressions for S2 rework17 N6 authority-root derivation fault.

Covers:
 (a) OSError on second Path.resolve(project_dir) => typed skip, zero discovered.
 (b) Same fault plus ambient resolve_projects_root OSError => typed skip, no crash.
 (c) Control: unfaulted poisoned fixture still skipped with UNVERIFIABLE diagnostic.
 (d) Legacy unmarked timeline still discovered (no over-rejection).
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
        state[tid] = {"backfilled_at": "2026-08-23T00:00:00Z"}
    p = projects_root / ".astrid" / "backfill-state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state), encoding="utf-8")


def _setup_poisoned(root: Path, tid: str = TID_DEAD, ulid: str = ULID_A) -> Path:
    project_dir = root / "proj-a"
    tdir = project_dir / "timelines" / ulid.upper()
    _write_identity(tdir, tid, ulid)
    _write_marker(root, [tid])
    db = root / ".astrid" / "astrid.sqlite3"
    if db.is_file():
        db.unlink()
    return project_dir


def _poisoned_resolve_fault(project_dir: Path):
    """Return a Path.resolve mock that raises OSError on SECOND call for project_dir."""
    orig = Path.resolve
    calls = {"n": 0}

    def fake(self, *args, **kwargs):
        try:
            is_target = Path(self) == Path(project_dir)
        except Exception:
            is_target = str(self) == str(project_dir)
        if is_target:
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("injected N6 derivation fault")
        return orig(self, *args, **kwargs)

    return fake


def test_r17_n6_root_fault_produces_typed_skip_zero_discovered():
    """R17-a: OSError on second Path.resolve(project_dir) => typed skip, zero discovered."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        fake = _poisoned_resolve_fault(project_dir)
        with mock.patch.object(Path, "resolve", fake):
            timelines, diags = _discover(project_dir)
        assert timelines == [], f"expected zero discovered on N6 derivation fault, got {timelines} diags={diags}"
        assert any("could not be determined" in d for d in diags), f"expected typed could-not-be-determined diagnostic, got {diags}"
        assert not any(getattr(t, "timeline_id", "") == TID_DEAD for t in timelines)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r17_n6_root_fault_plus_ambient_fault_still_typed_skip_no_crash():
    """R17-b: same derivation fault PLUS ambient resolve_projects_root OSError => typed skip, no crash."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        import astrid.core.foundation.project_paths as pp
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover


        fake = _poisoned_resolve_fault(project_dir)

        def ambient_fault(*a, **kw):
            raise OSError("injected ambient fault")

        with mock.patch.object(Path, "resolve", fake):
            with mock.patch.object(pp, "resolve_projects_root", side_effect=ambient_fault):
                timelines, diags = _discover(project_dir)
        assert timelines == [], f"expected zero discovered when both roots fault, got {timelines} diags={diags}"
        assert any("could not be determined" in d for d in diags), f"expected typed skip, got {diags}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r17_control_unverifiable_still_skipped():
    """R17-c: control — unfaulted poisoned fixture still skipped with UNVERIFIABLE diagnostic."""
    tmp = Path(tempfile.mkdtemp())
    try:
        project_dir = _setup_poisoned(tmp, TID_DEAD, ULID_A)
        from astrid.packs.rendering.executors.timeline_visualize.select import _discover

        timelines, diags = _discover(project_dir)
        assert timelines == [], f"control should discover zero (unverifiable), got {timelines} diags={diags}"
        assert any("UNVERIFIABLE" in d or "unreadable" in d.lower() for d in diags), f"expected typed skip, got {diags}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_r17_legacy_unmarked_still_discovered():
    """R17-d: legacy unmarked timeline still discovered (no over-rejection)."""
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
