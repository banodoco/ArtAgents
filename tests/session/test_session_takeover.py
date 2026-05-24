"""Tests for cmd_sessions_takeover (orphan path, live path, warm-target guard)."""

from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from astrid.core.project import paths as project_paths
from astrid.core.session import cli
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.identity import Identity, write_identity
from astrid.core.session.lease import (
    read_lease,
    release_writer_lease,
)
from astrid.core.task.events import ZERO_HASH, append_event_locked, read_events


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def test_takeover_requires_caller_to_be_bound(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="01RUN", force=False), out=StringIO()
    )
    assert rc == 2


def test_takeover_orphan_path_claims_lease_and_bumps_epoch(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], writer_session_id="S-OLD")
    release_writer_lease(run_dir)
    caller = mint_session(env["home"], "S-CLAIM", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    buf = StringIO()
    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="01RUN", force=False), out=buf
    )
    assert rc == 0
    assert "claimed orphan lease" in buf.getvalue()
    lease = read_lease(run_dir)
    assert lease["attached_session_id"] == caller.id
    assert lease["writer_epoch"] == 1
    events = read_events(run_dir / "events.jsonl")
    assert events[-1]["kind"] == "takeover"
    assert events[-1]["new_session"] == caller.id


def test_takeover_live_path_bumps_epoch_and_swaps(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], writer_session_id="S-PREV")
    mint_session(env["home"], "S-PREV", project="demo", run_id="01RUN")
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="S-PREV", force=False), out=StringIO()
    )
    # The target has no events written → not warm; takeover proceeds.
    assert rc == 0
    lease = read_lease(run_dir)
    assert lease["attached_session_id"] == caller.id
    assert lease["writer_epoch"] == 1
    events = read_events(run_dir / "events.jsonl")
    takeover = events[-1]
    assert takeover["kind"] == "takeover"
    assert takeover["prev_session"] == "S-PREV"
    assert takeover["new_session"] == caller.id


def test_takeover_refuses_warm_target_without_force(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], writer_session_id="S-PREV")
    # Write a recent event so the target is "warm".
    append_event_locked(
        run_dir,
        {"kind": "step_dispatched", "plan_step_id": "x", "command": "noop"},
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    mint_session(env["home"], "S-PREV", project="demo", run_id="01RUN")
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="S-PREV", force=False), out=StringIO()
    )
    assert rc == 2
    # Lease still names the previous writer.
    assert read_lease(run_dir)["attached_session_id"] == "S-PREV"


def test_takeover_force_overrides_warm_guard(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], writer_session_id="S-PREV")
    append_event_locked(
        run_dir,
        {"kind": "step_dispatched", "plan_step_id": "x", "command": "noop"},
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    mint_session(env["home"], "S-PREV", project="demo", run_id="01RUN")
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="S-PREV", force=True), out=StringIO()
    )
    assert rc == 0
    assert read_lease(run_dir)["attached_session_id"] == caller.id


def test_takeover_unknown_target_errors(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    seed_project_run(env["projects"], writer_session_id="S-PREV")
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)
    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="NONEXISTENT", force=False), out=StringIO()
    )
    assert rc == 2
