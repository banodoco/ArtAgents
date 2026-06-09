"""Tests for WriterContext: auto-rebind + writer-auth + locked-append plumbing."""

from __future__ import annotations

import json
import inspect
from pathlib import Path
from typing import Any

import pytest

from astrid.core.foundation import project_paths
from astrid.core.session import paths as session_paths
from astrid.core.session.lease import (
    LeaseError,
    bump_epoch_and_swap_session,
    read_lease,
    release_writer_lease,
)
from astrid.core.session.model import Session
from astrid.core.session.writer import (
    NoRunBoundError,
    WriterContext,
    open_task_run_writer,
    writer_context_from_decision,
)
from astrid.core.task.events import (
    NotWriterError,
    StaleEpochError,
    StaleTailError,
    read_events,
    verify_chain,
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


# ----- happy path --------------------------------------------------------


def test_writer_context_happy_path_appends(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    sess = mint_session(env["home"], sid="S-1", project="demo", run_id="01RUN")
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id=sess.id
    )
    with WriterContext(sess) as ctx:
        assert ctx.run_dir == run_dir
        assert ctx.expected_writer_epoch == 0
        ev = ctx.append({"kind": "test", "n": 1})
        assert "hash" in ev
    ok, _, err = verify_chain(run_dir / "events.jsonl")
    assert ok and err is None
    events = read_events(run_dir / "events.jsonl")
    assert len(events) == 1
    assert events[0]["kind"] == "test"


def test_open_task_run_writer_captures_authenticated_lease_state(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    sess = mint_session(env["home"], sid="S-1", project="demo", run_id="01RUN")
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id=sess.id
    )

    writer = open_task_run_writer(sess)

    assert writer.session.id == sess.id
    assert writer.run_dir == run_dir
    assert writer.expected_writer_epoch == 0
    assert writer.plan_hash == read_lease(run_dir)["plan_hash"]


# ----- writer-auth -------------------------------------------------------


def test_writer_context_refuses_reader_session(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    """Reader session (lease names a different session) is rejected at __enter__."""

    writer_sess = mint_session(
        env["home"], sid="S-WRITER", project="demo", run_id="01RUN"
    )
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id=writer_sess.id
    )
    pre_bytes = (run_dir / "events.jsonl").read_bytes()
    reader_sess = mint_session(
        env["home"], sid="S-READER", project="demo", run_id="01RUN"
    )
    with pytest.raises(NotWriterError) as exc_info:
        with WriterContext(reader_sess):
            pass
    assert exc_info.value.session_id == "S-READER"
    assert exc_info.value.writer_id == "S-WRITER"
    # events.jsonl unchanged.
    assert (run_dir / "events.jsonl").read_bytes() == pre_bytes


def test_stop_line_writer_context_missing_lease_is_hard_failure(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    sess = mint_session(env["home"], sid="S-WRITER", project="demo", run_id="01RUN")
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id=sess.id
    )
    (run_dir / "lease.json").unlink()
    before = (run_dir / "events.jsonl").read_bytes()

    with pytest.raises(LeaseError):
        with WriterContext(sess) as ctx:
            ctx.append({"kind": "should-not-write"})

    assert (run_dir / "events.jsonl").read_bytes() == before


def test_stop_line_writer_context_migrates_legacy_state_before_writer_auth() -> None:
    source = inspect.getsource(open_task_run_writer)
    before_lease_read = source.split("read_lease", 1)[0]
    assert "migrate" in before_lease_read.lower()
    assert "active_run" in before_lease_read


def test_writer_context_migrates_legacy_active_run_before_writer_auth(
    env: dict[str, Path], mint_session: Any
) -> None:
    from astrid.core.project.current_run import read_current_run

    sess = mint_session(env["home"], sid="S-MIGRATE", project="demo", run_id=None)
    project = env["projects"] / "demo"
    run_dir = project / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    (project / "active_run.json").write_text(
        json.dumps({"run_id": "01RUN", "plan_hash": "sha256:legacy"}),
        encoding="utf-8",
    )

    with WriterContext(sess, root=env["projects"]) as ctx:
        assert ctx.session.run_id == "01RUN"
        ctx.append({"kind": "after-legacy-migration"})

    assert read_current_run("demo", root=env["projects"]) == "01RUN"
    lease = read_lease(run_dir)
    assert lease["attached_session_id"] == sess.id
    assert lease["plan_hash"] == "sha256:legacy"
    assert not (project / "active_run.json").exists()


def test_orphan_pending_session_refused_then_takeover_promotes(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    """attached_session_id=None → NotWriterError; takeover promotes the claimant."""

    sess = mint_session(env["home"], sid="S-CLAIM", project="demo", run_id="01RUN")
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id="S-OLD"
    )
    release_writer_lease(run_dir)
    assert read_lease(run_dir)["attached_session_id"] is None
    with pytest.raises(NotWriterError) as exc_info:
        with WriterContext(sess):
            pass
    assert exc_info.value.writer_id is None
    # Promote via takeover (claim_orphan_lease is the verb path; either works
    # here — bump+swap also sets attached_session_id):
    from astrid.core.session.lease import claim_orphan_lease

    claim_orphan_lease(run_dir, new_session_id=sess.id)
    with WriterContext(sess) as ctx:
        ev = ctx.append({"kind": "after-claim", "n": 1})
        assert "hash" in ev


# ----- stale-tail / stale-epoch surfacing -------------------------------


def test_stale_epoch_surfaces_when_takeover_intervenes(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    """A takeover after __enter__ but before append → StaleEpochError on append."""

    a = mint_session(env["home"], sid="S-A", project="demo", run_id="01RUN")
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id=a.id
    )
    lease_path = run_dir / "lease.json"
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    lease["timeline_id"] = "01HTIMELINEPASSTHROUGH"
    lease["future_metadata"] = {"kept": True}
    lease_path.write_text(json.dumps(lease), encoding="utf-8")
    with WriterContext(a) as ctx:
        # Simulate a competing tab winning takeover.
        bump_epoch_and_swap_session(
            run_dir, new_session_id="S-B", prev_session_id=a.id, reason="test"
        )
        after_takeover_events = (run_dir / "events.jsonl").read_bytes()
        # The takeover event itself succeeded under its own flock; A's
        # captured epoch (0) no longer matches lease (now 1).
        with pytest.raises(StaleEpochError) as exc_info:
            ctx.append({"kind": "should-reject"})
        assert exc_info.value.expected == 0
        assert exc_info.value.actual == 1
        assert (run_dir / "events.jsonl").read_bytes() == after_takeover_events
        ok, bad_idx, err = verify_chain(run_dir / "events.jsonl")
        assert ok, f"chain broken at event {bad_idx}: {err}"
        updated_lease = read_lease(run_dir)
        assert updated_lease["attached_session_id"] == "S-B"
        assert updated_lease["writer_epoch"] == 1
        assert updated_lease["timeline_id"] == "01HTIMELINEPASSTHROUGH"
        assert updated_lease["future_metadata"] == {"kept": True}


def test_stale_tail_surfaces_when_external_appender_wins_race(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    """If the tail moved between _peek and append (rare under single-thread),
    StaleTailError surfaces. We simulate by reaching past the context to
    write directly under the same lease."""

    sess = mint_session(env["home"], sid="S-A", project="demo", run_id="01RUN")
    run_dir = seed_project_run(
        env["projects"], "demo", "01RUN", writer_session_id=sess.id
    )
    from astrid.core.task.events import ZERO_HASH, append_event_locked

    with WriterContext(sess) as ctx:
        # External (still-valid-writer) append races in and moves the tail.
        first = append_event_locked(
            run_dir,
            {"kind": "external", "n": 1},
            expected_writer_epoch=0,
            expected_prev_hash=ZERO_HASH,
        )
        # ctx.append's _peek_tail_hash now sees `first['hash']` (not ZERO),
        # so the next call chains forward cleanly. Force the race shape
        # explicitly by hand-passing a stale prev_hash:
        with pytest.raises(StaleTailError):
            append_event_locked(
                run_dir,
                {"kind": "stale-test", "n": 2},
                expected_writer_epoch=ctx.expected_writer_epoch,
                expected_prev_hash=ZERO_HASH,  # stale on purpose
            )
        # And the recovered path (peek then append) succeeds:
        ev = ctx.append({"kind": "recovered", "n": 3})
        assert ev["hash"] != first["hash"]


# ----- auto-rebind -------------------------------------------------------


def test_auto_rebind_picks_up_new_run_id_and_rewrites_session_file(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    """Session minted before a run was started → __enter__ rebinds to current_run.json
    and silently rewrites the session file on disk."""

    sess = mint_session(env["home"], sid="S-REBIND", project="demo", run_id=None)
    # A different tab started the run while this session sat detached.
    run_dir = seed_project_run(
        env["projects"], "demo", "01NEWRUN", writer_session_id=sess.id
    )
    with WriterContext(sess) as ctx:
        # Auto-rebind populated session.run_id from current_run.json.
        assert ctx.session.run_id == "01NEWRUN"
        assert ctx.run_dir == run_dir
        ctx.append({"kind": "rebound", "n": 1})
    # The on-disk session file was rewritten as a side effect.
    on_disk = json.loads((env["home"] / "sessions" / "S-REBIND.json").read_text())
    assert on_disk["run_id"] == "01NEWRUN"
    assert on_disk["last_used_at"] != "2026-05-11T00:00:00Z"  # bumped


def test_no_run_bound_raises_when_current_run_absent(
    env: dict[str, Path], mint_session: Any
) -> None:
    sess = mint_session(env["home"], sid="S-NORUN", project="demo", run_id=None)
    # Project exists but no current_run.json / no runs/ subdir.
    (env["projects"] / "demo").mkdir(parents=True)
    (env["projects"] / "demo" / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(NoRunBoundError) as exc_info:
        with WriterContext(sess):
            pass
    assert exc_info.value.session_id == "S-NORUN"
    assert exc_info.value.project == "demo"


# ----- factory ------------------------------------------------------------


def test_writer_context_from_decision_performs_auth_check(
    env: dict[str, Path], mint_session: Any, seed_project_run: Any
) -> None:
    """The factory accepts any object exposing `.session` and gates on entry."""

    class FakeDecision:
        def __init__(self, sess: Session) -> None:
            self.session = sess

    writer = mint_session(env["home"], sid="S-W", project="demo", run_id="01RUN")
    seed_project_run(env["projects"], "demo", "01RUN", writer_session_id=writer.id)
    with writer_context_from_decision(FakeDecision(writer)) as ctx:
        ctx.append({"kind": "via-factory", "n": 1})

    # A reader session via the same factory is refused.
    reader = mint_session(env["home"], sid="S-R", project="demo", run_id="01RUN")
    with pytest.raises(NotWriterError):
        with writer_context_from_decision(FakeDecision(reader)):
            pass


def test_no_run_bound_error_is_local_to_writer_module() -> None:
    """NoRunBoundError lives in writer.py, NOT in events.py (DEC: session-state error)."""

    from astrid.core.session.writer import NoRunBoundError as LocalNRBE
    from astrid.core.task import events as ev_mod

    assert LocalNRBE is NoRunBoundError
    assert not hasattr(ev_mod, "NoRunBoundError")
