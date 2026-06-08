"""Tests for cmd_sessions_takeover (orphan path, live path, warm-target guard)."""

from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.project import paths as project_paths
from astrid.core.session import cli
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV, SESSION_FILE_NAME
from astrid.core.session.identity import Identity, write_identity
from astrid.core.session.lease import (
    read_lease,
    release_writer_lease,
)
from astrid.core.session.model import Session
from astrid.core.session.paths import session_path
from astrid.core.task.events import ZERO_HASH, append_event_locked, read_events


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _assert_astrid_error(call, *cause_parts: str, recovery: str | None = None) -> AstridError:
    with pytest.raises(AstridError) as raised:
        call()
    error = raised.value
    for part in cause_parts:
        assert part in error.cause
    if recovery is not None:
        assert error.recovery_command == recovery
    return error


def test_takeover_requires_caller_to_be_bound(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="01RUN", force=False), out=StringIO()
        ),
        "takeover:",
        "matches neither",
        recovery="astrid status",
    )
    assert not (env["home"] / "sessions").exists()


def test_stop_line_unbound_takeover_bootstraps_concrete_session(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], "demo", "01RUN", writer_session_id="S-PREV")
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="01RUN", force=True), out=StringIO()
    )

    assert rc == 0
    lease = read_lease(run_dir)
    assert isinstance(lease["attached_session_id"], str)
    assert lease["attached_session_id"]
    assert lease["attached_session_id"] != "S-PREV"
    session = Session.from_json(session_path(lease["attached_session_id"]))
    assert session.project == "demo"
    assert session.run_id == "01RUN"
    assert session.role == "writer"
    assert (
        (env["projects"] / "demo" / SESSION_FILE_NAME).read_text(encoding="utf-8")
        == f"{ASTRID_SESSION_ID_ENV}={session.id}\n"
    )
    events = read_events(run_dir / "events.jsonl")
    assert events[-1]["kind"] == "takeover"
    assert events[-1]["new_session"] == session.id


def test_unbound_takeover_by_target_session_bootstraps_before_mutation(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], "demo", "01RUN", writer_session_id="S-PREV")
    mint_session(
        env["home"],
        "S-PREV",
        project="demo",
        run_id="01RUN",
        agent_id="other-agent",
    )
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc = cli.cmd_sessions_takeover(
        argparse.Namespace(target="S-PREV", force=True), out=StringIO()
    )

    assert rc == 0
    lease = read_lease(run_dir)
    assert lease["attached_session_id"] != "S-PREV"
    session = Session.from_json(session_path(lease["attached_session_id"]))
    assert session.run_id == "01RUN"
    assert session.role == "writer"


def test_unbound_takeover_ambiguous_run_fails_before_session_or_lease_mutation(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project_run: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_a = seed_project_run(env["projects"], "demo-a", "01RUN", writer_session_id="S-A")
    run_b = seed_project_run(env["projects"], "demo-b", "01RUN", writer_session_id="S-B")
    before_a = (run_a / "lease.json").read_bytes()
    before_b = (run_b / "lease.json").read_bytes()
    events_a = (run_a / "events.jsonl").read_bytes()
    events_b = (run_b / "events.jsonl").read_bytes()
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="01RUN", force=True), out=StringIO()
        ),
        "ambiguous",
        recovery="astrid status",
    )

    assert (run_a / "lease.json").read_bytes() == before_a
    assert (run_b / "lease.json").read_bytes() == before_b
    assert (run_a / "events.jsonl").read_bytes() == events_a
    assert (run_b / "events.jsonl").read_bytes() == events_b
    assert not (env["home"] / "sessions").exists()


def test_unbound_takeover_target_session_without_run_fails_before_session_creation(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mint_session(env["home"], "S-DETACHED", project="demo", run_id=None)
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="S-DETACHED", force=True), out=StringIO()
        ),
        "not bound to a run",
        recovery="astrid status",
    )

    assert len(list((env["home"] / "sessions").glob("*.json"))) == 1


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
    before_events = (run_dir / "events.jsonl").read_bytes()
    before_session = session_path(caller.id).read_bytes()
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="S-PREV", force=False), out=StringIO()
        ),
        "wrote within the last 60s",
        recovery="astrid status",
    )
    # Lease still names the previous writer.
    assert read_lease(run_dir)["attached_session_id"] == "S-PREV"
    assert (run_dir / "events.jsonl").read_bytes() == before_events
    assert session_path(caller.id).read_bytes() == before_session


def test_unbound_takeover_refuses_warm_target_before_session_creation(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project_run: Any,
) -> None:
    run_dir = seed_project_run(env["projects"], "demo", "01RUN", writer_session_id="S-PREV")
    append_event_locked(
        run_dir,
        {"kind": "step_dispatched", "plan_step_id": "x", "command": "noop"},
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    before_lease = (run_dir / "lease.json").read_bytes()
    before_events = (run_dir / "events.jsonl").read_bytes()
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="01RUN", force=False), out=StringIO()
        ),
        "wrote within the last 60s",
        recovery="astrid status",
    )

    assert (run_dir / "lease.json").read_bytes() == before_lease
    assert (run_dir / "events.jsonl").read_bytes() == before_events
    assert not (env["home"] / "sessions").exists()
    assert not (env["projects"] / "demo" / SESSION_FILE_NAME).exists()


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
    run_dir = seed_project_run(env["projects"], writer_session_id="S-PREV")
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    before_lease = (run_dir / "lease.json").read_bytes()
    before_events = (run_dir / "events.jsonl").read_bytes()
    before_session = session_path(caller.id).read_bytes()
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)
    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="NONEXISTENT", force=False), out=StringIO()
        ),
        "NONEXISTENT",
        "matches neither",
        recovery="astrid status",
    )
    assert (run_dir / "lease.json").read_bytes() == before_lease
    assert (run_dir / "events.jsonl").read_bytes() == before_events
    assert session_path(caller.id).read_bytes() == before_session


def test_takeover_missing_lease_errors_without_appending(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = seed_project_run(env["projects"], writer_session_id="S-PREV")
    before = (run_dir / "events.jsonl").read_bytes()
    (run_dir / "lease.json").unlink()
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="01RUN", force=True), out=StringIO()
        ),
        "cannot read canonical lease",
        "missing lease",
        recovery="astrid status",
    )

    assert (run_dir / "events.jsonl").read_bytes() == before


def test_takeover_malformed_lease_errors_with_distinct_message(
    env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = seed_project_run(env["projects"], writer_session_id="S-PREV")
    before = (run_dir / "events.jsonl").read_bytes()
    (run_dir / "lease.json").write_text("not-json", encoding="utf-8")
    caller = mint_session(env["home"], "S-NEW", project="demo", run_id="01RUN")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, caller.id)

    _assert_astrid_error(
        lambda: cli.cmd_sessions_takeover(
            argparse.Namespace(target="01RUN", force=True), out=StringIO()
        ),
        "cannot read canonical lease",
        "invalid JSON",
        recovery="astrid status",
    )

    assert (run_dir / "events.jsonl").read_bytes() == before
