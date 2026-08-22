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


def test_resume_fails_closed_on_source_drift(tmp_path: Path) -> None:
    """W2: appending one event to a completed timeline's source and resuming
    fails closed with NAMED drift — no new kernel rows, marker unchanged."""
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
    from astrid.core.timeline.events.schema import TimelineActor
    from astrid.packs.timeline.backfill import BackfillDiscrepancyError

    root1, db1, tid_a, tid_b, home_a, _home_b = _build_root(tmp_path, "root1")
    # Fresh database gets its project row once.
    w = make_writer(db1)
    try:
        make_project(w)
    finally:
        w.close()
    # One complete uninterrupted run: A and B both commit, checkpoint marks
    # A as the last completed timeline.
    writer, projects, receipts = _open(root1, db1)
    try:
        reports = backfill_project(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            projects_root=root1,
            run_ts=RUN_TS,
        )
        assert set(reports) == {tid_a, tid_b}
    finally:
        writer.close()
    a_stream = f"{tid_a}:{TIMELINE_STREAM_TYPE}"
    marker_before = marker_state(root1)

    # Drift A's source: append one config_replaced event (head 3 -> 4).
    backend = LocalFsBackend(timeline_id=tid_a, timeline_home=home_a)
    backend.append_event(
        tid_a,
        "timeline.config_replaced",
        {"config": {"tracks": [], "clips": []}},
        actor=TimelineActor(type="human", id="actor:human"),
    )

    # Resume with the same checkpoint: the completed prefix is revalidated
    # (W2) and the drifted source fails the resume closed with named drift.
    writer2, projects2, receipts2 = _open(root1, db1)
    try:
        with pytest.raises(BackfillDiscrepancyError) as excinfo:
            backfill_project(
                writer=writer2,
                projects=projects2,
                receipts=receipts2,
                project_slug="proj",
                projects_root=root1,
                run_ts=RUN_TS,
            )
        message = str(excinfo.value)
        assert tid_a in message
        assert "events_sha256" in message
        assert "drifted" in message or "drift" in message
        # No new kernel rows for either timeline.
        assert head_seq(writer2, a_stream) == 3
        assert len(kernel_event_rows(writer2, a_stream)) == 3
        b_stream = f"{tid_b}:{TIMELINE_STREAM_TYPE}"
        assert head_seq(writer2, b_stream) == 5
        assert len(kernel_event_rows(writer2, b_stream)) == 5
        # Marker unchanged: the drift never touched the authority claim.
        assert marker_state(root1) == marker_before
    finally:
        writer2.close()


def test_resume_completes_missing_marker_after_crash(tmp_path: Path) -> None:
    """W1.3/W2: a checkpoint-completed timeline whose marker never landed
    (crash-after-commit) is re-imported on resume and the marker converges —
    zero new rows, receipt replay."""
    import json as _json

    root1, db1, tid_a, tid_b, _home_a, _home_b = _build_root(tmp_path, "root1")
    w = make_writer(db1)
    try:
        make_project(w)
    finally:
        w.close()
    writer, projects, receipts = _open(root1, db1)
    try:
        reports = backfill_project(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            projects_root=root1,
            run_ts=RUN_TS,
        )
        assert set(reports) == {tid_a, tid_b}
    finally:
        writer.close()
    a_stream = f"{tid_a}:{TIMELINE_STREAM_TYPE}"
    assert marker_state(root1)[tid_a]["source_head_version"] == 3
    # Simulate the crash-after-commit-before-marker for A: committed
    # receipt/events exist, the marker entry never landed.
    state_path = root1 / ".astrid" / "backfill-state.json"
    state = _json.loads(state_path.read_text())
    del state[tid_a]
    state_path.write_text(_json.dumps(state))

    # Resume: A is re-imported (receipt replay) and its marker completes;
    # B is untouched; zero new rows anywhere.
    writer2, projects2, receipts2 = _open(root1, db1)
    try:
        reports2 = backfill_project(
            writer=writer2,
            projects=projects2,
            receipts=receipts2,
            project_slug="proj",
            projects_root=root1,
            run_ts=RUN_TS,
        )
        assert set(reports2) == {tid_a}  # only A needed marker completion
        assert reports2[tid_a].replayed is True
        assert reports2[tid_a].marker_written is True
        assert reports2[tid_a].to_dict()["checks"]["count"] is True
        assert head_seq(writer2, a_stream) == 3
        assert len(kernel_event_rows(writer2, a_stream)) == 3
        b_stream = f"{tid_b}:{TIMELINE_STREAM_TYPE}"
        assert head_seq(writer2, b_stream) == 5
        assert marker_state(root1)[tid_a]["source_head_version"] == 3
        assert marker_state(root1)[tid_a]["events_sha256"]
    finally:
        writer2.close()


def test_two_runs_same_second_distinct_checkpoint_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3#2: two runs constructed within the same second get distinct
    checkpoint paths. Without the collision-safe run id both runs would
    share ``runs/migrations/<epoch-second>/`` — the second run would inherit
    the first's checkpoint, and a changed source would enter resume-drift
    handling and render the wrong failure class. The clock is pinned so the
    same-second collision is exercised deterministically."""
    import astrid.packs.timeline.backfill as backfill_mod

    monkeypatch.setattr(backfill_mod.time, "time", lambda: 1750000000.5)

    root1, db1, tid_a, tid_b, _home_a, _home_b = _build_root(tmp_path, "root1")
    w = make_writer(db1)
    try:
        make_project(w)
    finally:
        w.close()
    writer, projects, receipts = _open(root1, db1)
    try:
        reports1 = backfill_project(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            projects_root=root1,
        )
        reports2 = backfill_project(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            projects_root=root1,
        )
        assert set(reports1) == {tid_a, tid_b}
        assert set(reports2) == {tid_a, tid_b}
        # Distinct run ids: the second run did NOT inherit the first's
        # checkpoint (no completed-prefix skip — every timeline re-imports
        # and replays its receipt with zero new rows).
        assert all(report.replayed for report in reports2.values())
    finally:
        writer.close()
    migrations_root = root1 / "proj" / "runs" / "migrations"
    checkpoint_dirs = sorted(p.name for p in migrations_root.iterdir())
    assert len(checkpoint_dirs) == 2, checkpoint_dirs
    assert checkpoint_dirs[0] != checkpoint_dirs[1]
    # Both runs landed in the SAME pinned epoch second and still diverge.
    assert {d.split("-", 1)[0] for d in checkpoint_dirs} == {"1750000000"}
    for name in checkpoint_dirs:
        assert (migrations_root / name / "checkpoint.json").is_file()


def test_exclusive_allocation_retries_on_forced_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3#1: allocation is EXCLUSIVE — the run checkpoint dir is created
    with fail-if-exists semantics and a bounded retry. A forced collision
    (same pinned epoch second AND same uuid4 value on the first attempt)
    is retried with fresh entropy, and both allocations land in distinct
    EXISTING dirs — a filesystem guarantee, not a probability."""
    import astrid.packs.timeline.backfill as backfill_mod
    from astrid.packs.timeline.backfill import allocate_run_checkpoint_id

    monkeypatch.setattr(backfill_mod.time, "time", lambda: 1750000000.5)

    class _FakeUuid:
        def __init__(self, value: str) -> None:
            self.hex = value

    values = iter(
        [
            "a" * 32,  # first allocation creates <epoch>-aaa...
            "a" * 32,  # second allocation COLLIDES with the first dir
            "b" * 32,  # bounded retry: fresh entropy lands here
        ]
    )
    monkeypatch.setattr(
        backfill_mod.uuid, "uuid4", lambda: _FakeUuid(next(values))
    )
    root = tmp_path / "proj-root"
    (root / "proj").mkdir(parents=True)
    ts1 = allocate_run_checkpoint_id("proj", root=root)
    ts2 = allocate_run_checkpoint_id("proj", root=root)
    assert ts1 != ts2
    assert ts1 == f"1750000000-{'a' * 32}"
    assert ts2 == f"1750000000-{'b' * 32}"
    migrations_root = root / "proj" / "runs" / "migrations"
    dirs = sorted(p.name for p in migrations_root.iterdir())
    assert len(dirs) == 2
    for name in dirs:
        assert (migrations_root / name).is_dir()


def test_exclusive_allocation_hard_errors_after_five_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P3#1: allocation fails CLOSED after 5 collisions (hard error naming
    the bound) — it never silently shares a dir and never loops forever."""
    import astrid.packs.timeline.backfill as backfill_mod
    from astrid.packs.timeline.backfill import (
        BackfillError,
        allocate_run_checkpoint_id,
    )

    monkeypatch.setattr(backfill_mod.time, "time", lambda: 1750000000.5)
    monkeypatch.setattr(
        backfill_mod.uuid,
        "uuid4",
        lambda: type("U", (), {"hex": "a" * 32})(),
    )
    root = tmp_path / "proj-root"
    # Pre-create the exact dir the fixed uuid4 keeps proposing, so every
    # one of the 5 bounded attempts collides.
    migrations = root / "proj" / "runs" / "migrations"
    (migrations / f"1750000000-{'a' * 32}").mkdir(parents=True)
    with pytest.raises(BackfillError, match="after 5 attempts"):
        allocate_run_checkpoint_id("proj", root=root)


def test_crashed_fresh_run_resumable_via_checkpoint_run_ts(
    tmp_path: Path,
) -> None:
    """P3#1/#2: a crashed FRESH run (no explicit run_ts) is resumable
    through the operator surface. The checkpoint JSON round-trips the
    ACTIVE run_ts (writer + reader), and a resume with that run_ts (the
    exact value the CLI ``--run-ts`` passes) reuses the SAME checkpoint dir
    and completes only the unfinished prefix."""
    import json as _json

    root1, db1, tid_a, tid_b, _home_a, _home_b = _build_root(tmp_path, "root1")
    w = make_writer(db1)
    try:
        make_project(w)
    finally:
        w.close()
    writer, projects, receipts = _open(root1, db1)
    exploded = False
    try:
        def _kill_mid_import(index: int) -> None:
            if index == 4:
                raise RuntimeError("simulated process kill mid-transaction")

        with pytest.raises(RuntimeError, match="simulated process kill"):
            backfill_project(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                projects_root=root1,
                on_before_append=_kill_mid_import,
            )
        exploded = True
    finally:
        writer.close()
    assert exploded
    migrations_root = root1 / "proj" / "runs" / "migrations"
    run_dirs = sorted(p.name for p in migrations_root.iterdir())
    assert len(run_dirs) == 1, run_dirs
    active_run_ts = run_dirs[0]
    # A committed; B rolled back; the checkpoint carries the ACTIVE run_ts.
    status = _json.loads(
        (migrations_root / active_run_ts / "checkpoint.json").read_text()
    )
    assert status["run_ts"] == active_run_ts  # round-trips in the JSON
    assert status["last_completed_timeline_ulid"] == (
        "01J00000000000000000000001"
    )
    a_stream = f"{tid_a}:{TIMELINE_STREAM_TYPE}"
    b_stream = f"{tid_b}:{TIMELINE_STREAM_TYPE}"
    writer1b, _p, _r = _open(root1, db1)
    try:
        assert head_seq(writer1b, a_stream) == 3
        assert head_seq(writer1b, b_stream) == 0
    finally:
        writer1b.close()

    # Resume with the checkpoint's run_ts (CLI --run-ts passes it verbatim):
    # SAME dir reused, only the unfinished prefix (B) completes.
    writer2, projects2, receipts2 = _open(root1, db1)
    try:
        reports = backfill_project(
            writer=writer2,
            projects=projects2,
            receipts=receipts2,
            project_slug="proj",
            projects_root=root1,
            run_ts=active_run_ts,
        )
        assert set(reports) == {tid_b}  # A skipped via checkpoint
        assert len(sorted(p.name for p in migrations_root.iterdir())) == 1
        assert (migrations_root / active_run_ts / "checkpoint.json").is_file()
        assert head_seq(writer2, a_stream) == 3  # zero new rows for A
        assert head_seq(writer2, b_stream) == 5
        assert len(kernel_event_rows(writer2, b_stream)) == 5
    finally:
        writer2.close()
