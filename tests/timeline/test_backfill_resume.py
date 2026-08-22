"""S1 interruption/resume convergence test.

Simulates an import interrupted mid-run (a process kill inside timeline B's
transaction), resumes with the checkpoint machinery from
``astrid/core/timeline/migration.py``, and proves the resumed database state
converges exactly with an uninterrupted run over identical source files:

- timeline A (sorted first) completes and its checkpoint is recorded;
- timeline B's transaction is rolled back (zero partial events, no marker);
- a resume (same run timestamp, same checkpoint) skips A and imports B;
- the final kernel state — event ids, counts, heads, per-kind counts,
  payload data, and authority markers — equals the uninterrupted run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from astrid.core.receipts.canonical import canonical_json
from astrid.packs.timeline.backfill import backfill_project
from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE

from ._backfill_helpers import (
    head_seq,
    kernel_event_rows,
    make_backfill_deps,
    make_project,
    make_source_timeline,
    make_writer,
    marker_state,
    project_root_with_timeline,
)

RUN_TS = "20260822T120000Z"

# Timeline A: 3 events. Timeline B: 5 events, so a hook that explodes on the
# 4th append of a timeline hits B mid-transaction and never touches A.
_SPEC_A = [
    ("timeline.created", {"timeline_id": "X", "slug": "alpha", "name": "Alpha"}, "human"),
    ("timeline.config_replaced", {"config": {"tracks": [], "clips": []}}, "human"),
    ("timeline.asset_registry_replaced", {"registry": {"assets": {"a": {"file": "a.png"}}}}, "agent"),
]
_SPEC_B = _SPEC_A + [
    ("clip.added", {"clip_id": "c1", "kind": "visual", "track_id": "V1", "asset_id": "a", "position": {"mode": "index", "index": 0}}, "agent"),
    ("timeline.custom_note", {"note": "raw dict pass-through"}, "system"),
]


def _build_root(tmp_path: Path, name: str) -> tuple[Path, Path, str, str, Path, Path]:
    """Build one project root with timelines A and B; return identity
    ``(projects_root, db_path, project_id, project_slug, home_a, home_b)``."""
    projects_root = tmp_path / name
    timelines_dir = projects_root / "proj" / "timelines"
    timelines_dir.mkdir(parents=True, exist_ok=True)
    home_a, tid_a, ulid_a = make_source_timeline(
        timelines_dir,
        timeline_id=None,
        timeline_ulid="01J00000000000000000000001",
        slug="alpha",
        name="Alpha",
        events_spec=_SPEC_A,
    )
    home_b, tid_b, ulid_b = make_source_timeline(
        timelines_dir,
        timeline_id=None,
        timeline_ulid="01J00000000000000000000002",
        slug="beta",
        name="Beta",
        events_spec=_SPEC_B,
    )
    (projects_root / "proj" / "project.json").write_text("{}")
    db_path = projects_root / ".astrid" / "astrid.sqlite3"
    return projects_root, db_path, tid_a, tid_b, home_a, home_b


def _open(projects_root: Path, db_path: Path, project_slug: str = "proj"):
    writer = make_writer(db_path)
    projects, receipts, _ = make_backfill_deps(writer)
    return writer, projects, receipts


def _state(writer, tid_a: str, tid_b: str) -> dict:
    """Deterministic kernel-state snapshot for convergence comparison."""
    snap: dict[str, dict] = {}
    for label, tid in (("A", tid_a), ("B", tid_b)):
        stream_id = f"{tid}:{TIMELINE_STREAM_TYPE}"
        rows = kernel_event_rows(writer, stream_id)
        snap[label] = {
            "count": len(rows),
            "head": head_seq(writer, stream_id),
            "kinds": [row["kind"] for row in rows],
            "event_ids": [row["event_id"] for row in rows],
            "data": [canonical_json(row["data"]) for row in rows],
        }
    return snap


def test_interrupted_resume_converges_with_uninterrupted(
    tmp_path: Path,
) -> None:
    root1, db1, tid_a, tid_b, _home_a, _home_b = _build_root(tmp_path, "root1")
    # Identical source files for the uninterrupted control run.
    root2, db2, _a2, _b2, _home_a2, _home_b2 = _build_root(tmp_path, "root2")
    shutil.rmtree(root2)
    shutil.copytree(root1, root2)

    # Fresh databases get their project row once.
    for db in (db1, db2):
        w = make_writer(db)
        try:
            make_project(w)
        finally:
            w.close()

    # --- Run 1: interrupted (B's transaction dies on its 4th append) ------
    writer1, projects1, receipts1 = _open(root1, db1)
    exploded = False
    try:
        def _kill_mid_import(index: int) -> None:
            if index == 4:
                raise RuntimeError("simulated process kill mid-transaction")

        with pytest.raises(RuntimeError, match="simulated process kill"):
            backfill_project(
                writer=writer1,
                projects=projects1,
                receipts=receipts1,
                project_slug="proj",
                projects_root=root1,
                run_ts=RUN_TS,
                on_before_append=_kill_mid_import,
            )
        exploded = True
    finally:
        writer1.close()
    assert exploded

    # A committed; B rolled back completely; the checkpoint records A.
    writer1b, _p, _r = _open(root1, db1)
    try:
        a_stream = f"{tid_a}:{TIMELINE_STREAM_TYPE}"
        b_stream = f"{tid_b}:{TIMELINE_STREAM_TYPE}"
        assert head_seq(writer1b, a_stream) == 3
        assert len(kernel_event_rows(writer1b, a_stream)) == 3
        assert head_seq(writer1b, b_stream) == 0
        assert kernel_event_rows(writer1b, b_stream) == []
        assert marker_state(root1)[tid_a]["source_head_version"] == 3
        assert tid_b not in marker_state(root1)
        checkpoint = (
            root1
            / "proj"
            / "runs"
            / "migrations"
            / RUN_TS
            / "checkpoint.json"
        )
        assert checkpoint.is_file()
        import json

        status = json.loads(checkpoint.read_text())
        assert status["last_completed_timeline_ulid"] == (
            "01J00000000000000000000001"
        )
        assert status["imported_count"] == 1
    finally:
        writer1b.close()

    # --- Run 2: resume with the same checkpoint; A is skipped, B imports --
    writer2, projects2, receipts2 = _open(root1, db1)
    try:
        reports = backfill_project(
            writer=writer2,
            projects=projects2,
            receipts=receipts2,
            project_slug="proj",
            projects_root=root1,
            run_ts=RUN_TS,
        )
        assert set(reports) == {tid_b}  # A skipped via checkpoint
        a_stream = f"{tid_a}:{TIMELINE_STREAM_TYPE}"
        assert head_seq(writer2, a_stream) == 3  # zero new rows for A
        state_resumed = _state(writer2, tid_a, tid_b)
    finally:
        writer2.close()

    # --- Control: uninterrupted run over the identical source files -------
    writer3, projects3, receipts3 = _open(root2, db2)
    try:
        reports_ctrl = backfill_project(
            writer=writer3,
            projects=projects3,
            receipts=receipts3,
            project_slug="proj",
            projects_root=root2,
        )
        assert set(reports_ctrl) == {tid_a, tid_b}
        state_uninterrupted = _state(writer3, tid_a, tid_b)
    finally:
        writer3.close()

    # --- Convergence: identical event ids, counts, heads, kinds, data -----
    assert state_resumed == state_uninterrupted
    # Markers converge (source/head/sha; backfilled_at differs by run time).
    m_resumed = marker_state(root1)
    m_ctrl = marker_state(root2)
    for tid in (tid_a, tid_b):
        assert m_resumed[tid]["source"] == m_ctrl[tid]["source"] == "local_fs"
        assert m_resumed[tid]["source_head_version"] == m_ctrl[tid][
            "source_head_version"
        ]
        assert m_resumed[tid]["events_sha256"] == m_ctrl[tid]["events_sha256"]
    assert state_resumed["B"]["head"] == 5
    assert state_resumed["B"]["count"] == 5
