"""Tests for cmd_attach + cmd_sessions_detach + cmd_sessions_ls."""

from __future__ import annotations

import argparse
import json
from io import StringIO
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.foundation import project_paths
from astrid.core.project.current_run import write_current_run
from astrid.core.cli import session as cli
from astrid.core.session import paths as session_paths
from astrid.core.session.identity import Identity, write_identity
from astrid.core.session.lease import release_writer_lease, write_lease_init


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _args(**kw: object) -> argparse.Namespace:
    defaults = {
        "project": "demo",
        "timeline": None,
        "session": None,
        "as_agent": None,
        "set_default": False,
        "user_default": False,
    }
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _assert_astrid_error(call, *cause_parts: str, recovery: str | None = None) -> AstridError:
    with pytest.raises(AstridError) as raised:
        call()
    error = raised.value
    for part in cause_parts:
        assert part in error.cause
    if recovery is not None:
        assert error.recovery_command == recovery
    return error


# ----- cmd_attach -------------------------------------------------------


def test_attach_no_current_run_role_is_writer(
    env: dict[str, Path], seed_project
) -> None:
    seed_project(env["projects"], "demo")
    buf = StringIO()
    rc = cli.cmd_attach(_args(), out=buf)
    assert rc == 0
    output = buf.getvalue()
    assert cli.ATTACH_HEADER in output
    assert "export ASTRID_SESSION_ID=" in output
    assert "role: writer" in output
    assert "run: (none)" in output
    # A session file was written.
    sessions = list((env["home"] / "sessions").iterdir())
    assert len(sessions) == 1


def test_attach_noninteractive_identity_bootstrap_errors_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    seed_project,
) -> None:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    seed_project(tmp_path / "projects", "demo")

    def eof_input(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", eof_input)
    _assert_astrid_error(
        lambda: cli.cmd_attach(_args(), out=StringIO()),
        "attach: agent identity is not configured",
    )
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err


def test_attach_without_project_uses_default(
    env: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seed_project,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    seed_project(env["projects"], "demo")
    (env["home"] / "config.json").write_text(json.dumps({"default_project": "demo"}), encoding="utf-8")
    buf = StringIO()
    rc = cli.cmd_attach(_args(project=None), out=buf)
    assert rc == 0
    output = buf.getvalue()
    assert "project: demo" in output
    assert "export ASTRID_SESSION_ID=" in output


def test_attach_without_project_rejects_missing_default(
    env: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    seed_project,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    seed_project(env["projects"], "demo")
    (workspace / ".astrid").mkdir()
    monkeypatch.setenv(session_paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, str(workspace / ".astrid"))
    (workspace / ".astrid" / "config.json").write_text(
        json.dumps({"default_project": "missing"}), encoding="utf-8"
    )
    error = _assert_astrid_error(
        lambda: cli.cmd_attach(_args(project=None), out=StringIO()),
        "configured default project 'missing' was not found",
    )
    assert error.recovery_command == "astrid projects default demo"


def test_attach_requires_explicit_timeline_when_default_sentinel_is_none(
    env: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    from astrid.core.project.project import create_project
    from astrid.core.timeline.crud import create_timeline

    create_project("demo")
    create_timeline("demo", "main")
    buf = StringIO()
    _assert_astrid_error(
        lambda: cli.cmd_attach(_args(), out=buf),
        "no default timeline; pass --timeline <slug>",
    )
    assert not (env["projects"] / "demo" / cli.SESSION_FILE_NAME).exists()


def test_attach_with_default_flag_writes_workspace_default(
    env: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seed_project,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(session_paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, str(tmp_path / ".astrid"))
    seed_project(env["projects"], "demo")
    buf = StringIO()
    rc = cli.cmd_attach(_args(set_default=True), out=buf)
    assert rc == 0
    assert "saved default project (workspace): demo" in buf.getvalue()
    config_path = tmp_path / ".astrid" / "config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["default_project"] == "demo"


def test_attach_to_held_run_yields_reader_role_with_takeover_hint(
    env: dict[str, Path], seed_project
) -> None:
    pdir = seed_project(env["projects"], "demo")
    run_dir = pdir / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="S-WRITER", plan_hash="")
    write_current_run("demo", "01RUN")
    buf = StringIO()
    rc = cli.cmd_attach(_args(), out=buf)
    assert rc == 0
    output = buf.getvalue()
    assert "role: reader" in output
    assert "astrid sessions takeover 01RUN" in output
    assert "S-WRITER" in output


def test_attach_to_orphan_lease_yields_orphan_pending_role(
    env: dict[str, Path], seed_project
) -> None:
    pdir = seed_project(env["projects"], "demo")
    run_dir = pdir / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").touch()
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="")
    release_writer_lease(run_dir)
    write_current_run("demo", "01RUN")
    buf = StringIO()
    rc = cli.cmd_attach(_args(), out=buf)
    assert rc == 0
    output = buf.getvalue()
    assert "role: orphan-pending" in output
    assert "astrid sessions takeover 01RUN" in output


def test_attach_with_session_resumes_existing(
    env: dict[str, Path], seed_project
) -> None:
    seed_project(env["projects"], "demo")
    # Create an initial session.
    buf = StringIO()
    cli.cmd_attach(_args(), out=buf)
    first_sid = next(iter((env["home"] / "sessions").iterdir())).stem

    # Re-attach with --session.
    buf2 = StringIO()
    rc = cli.cmd_attach(_args(session=first_sid), out=buf2)
    assert rc == 0
    assert f"export ASTRID_SESSION_ID={first_sid}" in buf2.getvalue()
    # Still exactly one session file.
    assert len(list((env["home"] / "sessions").iterdir())) == 1


def test_attach_delegates_create_to_sdk_helper(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, seed_project
) -> None:
    seed_project(env["projects"], "demo")
    original_attach = cli.attach_session
    calls: list[dict[str, object]] = []

    def _spy_attach_session(**kwargs: object):
        calls.append(dict(kwargs))
        return original_attach(**kwargs)

    monkeypatch.setattr(cli, "attach_session", _spy_attach_session)

    buf = StringIO()
    rc = cli.cmd_attach(_args(timeline="primary"), out=buf)

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["project_slug"] == "demo"
    assert calls[0]["timeline"] == "primary"
    assert "session_id" not in calls[0]
    assert calls[0]["write_project_pointer"] is True
    assert "export ASTRID_SESSION_ID=" in buf.getvalue()


def test_attach_resume_delegates_open_to_sdk_helper(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, seed_project
) -> None:
    seed_project(env["projects"], "demo")
    cli.cmd_attach(_args(timeline="primary"), out=StringIO())
    first_sid = next(iter((env["home"] / "sessions").iterdir())).stem

    original_attach = cli.attach_session
    calls: list[dict[str, object]] = []

    def _spy_attach_session(**kwargs: object):
        calls.append(dict(kwargs))
        return original_attach(**kwargs)

    monkeypatch.setattr(cli, "attach_session", _spy_attach_session)

    buf = StringIO()
    rc = cli.cmd_attach(_args(session=first_sid), out=buf)

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["project_slug"] == "demo"
    assert calls[0]["session_id"] == first_sid
    assert calls[0]["write_project_pointer"] is True
    assert f"export ASTRID_SESSION_ID={first_sid}" in buf.getvalue()


def test_attach_resume_missing_id_errors(
    env: dict[str, Path], seed_project
) -> None:
    seed_project(env["projects"], "demo")
    buf = StringIO()
    _assert_astrid_error(
        lambda: cli.cmd_attach(_args(session="NONEXISTENT"), out=buf),
        "no session file for id 'NONEXISTENT'",
    )


def test_attach_as_agent_overrides_identity(
    env: dict[str, Path], seed_project
) -> None:
    seed_project(env["projects"], "demo")
    buf = StringIO()
    rc = cli.cmd_attach(_args(as_agent="agent:codex-1"), out=buf)
    assert rc == 0
    sess_file = next(iter((env["home"] / "sessions").iterdir()))
    payload = json.loads(sess_file.read_text())
    assert payload["agent_id"] == "codex-1"


def test_attach_as_agent_rejects_malformed(
    env: dict[str, Path], seed_project
) -> None:
    seed_project(env["projects"], "demo")
    buf = StringIO()
    _assert_astrid_error(
        lambda: cli.cmd_attach(_args(as_agent="codex-1"), out=buf),  # missing "agent:" prefix
        "--as must be of form 'agent:<slug>'",
    )


def test_status_honors_attach_as_override(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, seed_project
) -> None:
    """Fix 2: `attach --as agent:<slug>` must win over the on-disk
    identity record when ``status`` reports the actor. The identity
    fixture seeds ``agent_id=claude-1``; we attach as ``foo`` and assert
    ``status`` prints ``agent: foo``, not the seeded identity."""
    seed_project(env["projects"], "demo")
    attach_buf = StringIO()
    rc = cli.cmd_attach(_args(as_agent="agent:foo"), out=attach_buf)
    assert rc == 0
    # Pull the new session id from the file so we can bind the env var.
    sess_file = next(iter((env["home"] / "sessions").iterdir()))
    payload = json.loads(sess_file.read_text())
    assert payload["agent_id"] == "foo"
    monkeypatch.setenv("ASTRID_SESSION_ID", payload["id"])

    status_buf = StringIO()
    rc = cli.cmd_status(argparse.Namespace(), out=status_buf)
    assert rc == 0
    assert "agent: foo" in status_buf.getvalue()
    assert "agent: claude-1" not in status_buf.getvalue()


# ----- cmd_sessions_ls --------------------------------------------------


def test_sessions_ls_empty(env: dict[str, Path]) -> None:
    buf = StringIO()
    rc = cli.cmd_sessions_ls(argparse.Namespace(), out=buf)
    assert rc == 0
    assert "no sessions" in buf.getvalue()


def test_sessions_ls_lists_all(env: dict[str, Path], seed_project) -> None:
    seed_project(env["projects"], "demo")
    seed_project(env["projects"], "other")
    cli.cmd_attach(_args(project="demo"), out=StringIO())
    cli.cmd_attach(_args(project="other"), out=StringIO())
    buf = StringIO()
    cli.cmd_sessions_ls(argparse.Namespace(), out=buf)
    lines = [ln for ln in buf.getvalue().splitlines() if ln]
    assert len(lines) == 2
    assert any("project=demo" in ln for ln in lines)
    assert any("project=other" in ln for ln in lines)


def test_sessions_ls_delegates_to_store_iteration(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, seed_project
) -> None:
    seed_project(env["projects"], "demo")
    cli.cmd_attach(_args(project="demo", timeline="primary"), out=StringIO())
    original_iter = cli.SessionStore.iter_sessions
    calls: list[bool] = []

    def _spy_iter_sessions(self, *, skip_malformed: bool = False):
        calls.append(skip_malformed)
        return original_iter(self, skip_malformed=skip_malformed)

    monkeypatch.setattr(cli.SessionStore, "iter_sessions", _spy_iter_sessions)

    buf = StringIO()
    rc = cli.cmd_sessions_ls(argparse.Namespace(), out=buf)

    assert rc == 0
    assert calls == [True]
    assert "project=demo" in buf.getvalue()


# ----- cmd_sessions_detach ----------------------------------------------


def test_detach_by_id_removes_session_file(
    env: dict[str, Path], seed_project
) -> None:
    seed_project(env["projects"], "demo")
    cli.cmd_attach(_args(), out=StringIO())
    sid = next(iter((env["home"] / "sessions").iterdir())).stem
    rc = cli.cmd_sessions_detach(argparse.Namespace(session_id=sid), out=StringIO())
    assert rc == 0
    assert not (env["home"] / "sessions" / f"{sid}.json").exists()


def test_detach_delegates_to_store_delete(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, seed_project
) -> None:
    seed_project(env["projects"], "demo")
    cli.cmd_attach(_args(timeline="primary"), out=StringIO())
    sid = next(iter((env["home"] / "sessions").iterdir())).stem
    original_delete = cli.SessionStore.delete
    calls: list[str] = []

    def _spy_delete(self, session_id: str):
        calls.append(session_id)
        return original_delete(self, session_id)

    monkeypatch.setattr(cli.SessionStore, "delete", _spy_delete)

    rc = cli.cmd_sessions_detach(argparse.Namespace(session_id=sid), out=StringIO())

    assert rc == 0
    assert calls == [sid]


def test_detach_without_id_uses_env(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, seed_project
) -> None:
    seed_project(env["projects"], "demo")
    cli.cmd_attach(_args(), out=StringIO())
    sid = next(iter((env["home"] / "sessions").iterdir())).stem
    monkeypatch.setenv("ASTRID_SESSION_ID", sid)
    rc = cli.cmd_sessions_detach(argparse.Namespace(session_id=None), out=StringIO())
    assert rc == 0
    assert not (env["home"] / "sessions" / f"{sid}.json").exists()


def test_detach_without_id_or_env_errors(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
    _assert_astrid_error(
        lambda: cli.cmd_sessions_detach(argparse.Namespace(session_id=None), out=StringIO()),
        "no session bound",
        "pass a session id",
    )


def test_detach_missing_session_errors(env: dict[str, Path]) -> None:
    _assert_astrid_error(
        lambda: cli.cmd_sessions_detach(
            argparse.Namespace(session_id="NONEXISTENT"), out=StringIO()
        ),
        "no session file for id 'NONEXISTENT'",
    )
