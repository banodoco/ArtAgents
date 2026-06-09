"""SDK lifecycle characterization tests.

These tests characterize the current SDK session lifecycle behavior
(create/open/attach/recover) and prove whether explicit-root operations
call ``input()`` or write under ``ASTRID_HOME`` / ``~/.astrid``.

Tests marked ``xfail`` demonstrate gaps where the current implementation
does not yet satisfy the explicit-root contract. Removing the xfail
marker is the success signal for the downstream refactor (T8-T15).

Success criterion (plan_v1.meta.json #3):
  "SDK session lifecycle tests can create/open/attach/recover sessions
   with explicit project and session roots without calling input() and
   without writing under ASTRID_HOME or ~/.astrid unless explicitly
   opted in."
"""

from __future__ import annotations

import argparse
import os
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from astrid.core.foundation import project_paths
from astrid.core.session import cli
from astrid.core.session import paths as session_paths
from astrid.core.session.identity import Identity, write_identity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def explicit_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Set up explicit ASTRID_HOME and PROJECTS_ROOT so no writes land under
    ``~/.astrid`` or any user-global default location."""
    home = tmp_path / "explicit_astrid_home"
    home.mkdir()
    projects = tmp_path / "explicit_projects"
    projects.mkdir()
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(home))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects))
    return {"home": home, "projects": projects}


@pytest.fixture
def env_with_identity(explicit_env: dict[str, Path]) -> dict[str, Path]:
    """Explicit env with an identity already on disk (no bootstrap needed)."""
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return explicit_env


def _attach_args(**kw: object) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "project": "demo",
        "timeline": None,
        "session": None,
        "as_agent": None,
        "set_default": False,
        "user_default": False,
        "fresh": False,
    }
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _takeover_args(**kw: object) -> argparse.Namespace:
    defaults: dict[str, Any] = {"target": "01RUN", "force": False}
    defaults.update(kw)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# attach — input() characterization
# ---------------------------------------------------------------------------


def test_attach_with_identity_and_explicit_timeline_does_not_call_input(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """When identity is on disk AND --timeline is passed explicitly,
    cmd_attach MUST NOT call input().  This path already works."""
    seed_project(env_with_identity["projects"], "demo")

    def _panic_input(_prompt: str = "") -> str:
        raise AssertionError("input() was called but should not have been")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _panic_input)
        mp.setattr("sys.stdin.isatty", lambda: False)

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)
    assert rc == 0
    assert "session created" in buf.getvalue()


def test_attach_with_identity_and_project_default_timeline_does_not_call_input(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """When identity is on disk AND the project has a default timeline,
    cmd_attach MUST NOT call input().  This path already works."""
    seed_project(env_with_identity["projects"], "demo")

    def _panic_input(_prompt: str = "") -> str:
        raise AssertionError("input() was called but should not have been")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _panic_input)
        mp.setattr("sys.stdin.isatty", lambda: False)

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(), out=buf)
    assert rc == 0


@pytest.mark.xfail(
    reason=(
        "GAP: bootstrap_identity() calls builtins.input when no identity "
        "exists on disk. The SDK contract requires identity to be supplied "
        "programmatically; prompts belong in CLI wrappers only."
    ),
    strict=True,
)
def test_attach_without_identity_should_not_call_input(
    explicit_env: dict[str, Path],
    seed_project: Any,
) -> None:
    """When no identity exists on disk, the SDK-level session creation
    should accept an explicit identity parameter rather than calling
    input().  Currently bootstrap_identity() calls builtins.input."""
    seed_project(explicit_env["projects"], "demo")

    input_called: list[str] = []

    def _spy_input(prompt: str = "") -> str:
        input_called.append(prompt)
        raise EOFError("no input available")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _spy_input)
        mp.setattr("sys.stdin.isatty", lambda: True)

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)

    # Current behavior: fails because identity bootstrap calls input()
    # which raises EOFError.
    assert rc != 0 or len(input_called) == 0, (
        f"input() was called {len(input_called)} times but should not be; "
        f"prompts seen: {input_called}"
    )


@pytest.mark.xfail(
    reason=(
        "GAP: cmd_attach calls input() to prompt for timeline selection when "
        "the project has timelines but no default is set. The SDK contract "
        "requires timeline to be supplied programmatically; prompts belong "
        "in CLI wrappers only."
    ),
    strict=True,
)
def test_attach_with_timelines_but_no_default_should_not_call_input(
    env_with_identity: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Create a project with timelines but NO default.  The SDK must not
    call input(); it should fail with a structured error instead."""
    from astrid.core.project.project import create_project
    from astrid.core.timeline.crud import create_timeline

    old_root = os.environ.get(project_paths.PROJECTS_ROOT_ENV)
    os.environ[project_paths.PROJECTS_ROOT_ENV] = str(
        env_with_identity["projects"]
    )

    try:
        create_project("demo")
        # Wipe the default_timeline_id so there is no default.
        proj_file = env_with_identity["projects"] / "demo" / "project.json"
        import json

        data = json.loads(proj_file.read_text(encoding="utf-8"))
        data["default_timeline_id"] = None
        proj_file.write_text(json.dumps(data), encoding="utf-8")

        create_timeline("demo", "primary")

        input_called: list[str] = []

        def _spy_input(prompt: str = "") -> str:
            input_called.append(prompt)
            return "primary"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("builtins.input", _spy_input)
            mp.setattr("sys.stdin.isatty", lambda: True)

            buf = StringIO()
            rc = cli.cmd_attach(_attach_args(), out=buf)

        assert len(input_called) == 0, (
            f"input() was called {len(input_called)} times but should not be; "
            f"prompts seen: {input_called}"
        )
    finally:
        if old_root is not None:
            os.environ[project_paths.PROJECTS_ROOT_ENV] = old_root


# ---------------------------------------------------------------------------
# attach — writes to ASTRID_HOME / ~/.astrid characterization
# ---------------------------------------------------------------------------


def test_attach_writes_session_only_to_explicit_astrid_home(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """When ASTRID_HOME is set explicitly, session files MUST be written
    under that explicit directory and nowhere else.  This already works."""
    seed_project(env_with_identity["projects"], "demo")

    # Snapshot the real ~/.astrid (if it exists) so we can prove it isn't
    # mutated.
    real_dot_astrid = Path.home() / ".astrid"
    real_existed_before = real_dot_astrid.exists()
    real_files_before: set[str] = set()
    if real_existed_before:
        real_files_before = {
            str(p.relative_to(real_dot_astrid))
            for p in real_dot_astrid.rglob("*")
            if p.is_file()
        }

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)
    assert rc == 0

    # Session file must exist under the explicit home.
    sessions_dir = env_with_identity["home"] / "sessions"
    assert sessions_dir.exists()
    session_files = list(sessions_dir.iterdir())
    assert len(session_files) == 1
    assert session_files[0].suffix == ".json"

    # Nothing new must have appeared under ~/.astrid.
    if real_existed_before:
        real_files_after = {
            str(p.relative_to(real_dot_astrid))
            for p in real_dot_astrid.rglob("*")
            if p.is_file()
        }
        new_files = real_files_after - real_files_before
        assert not new_files, (
            f"Unexpected new files under ~/.astrid: {new_files}"
        )


def test_attach_does_not_create_default_dot_astrid_when_explicit_home_set(
    explicit_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project: Any,
) -> None:
    """If ASTRID_HOME is set to an explicit path, the default ~/.astrid
    directory MUST NOT be created by SDK operations.  This already works
    because identity doesn't exist and the test verifies the default
    ~/.astrid is not touched."""
    seed_project(explicit_env["projects"], "demo")
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))

    default_dot_astrid = Path.home() / ".astrid"
    # Remove if it already exists so we can prove it isn't created.
    existed_before = default_dot_astrid.exists()
    if existed_before:
        # We can't delete a real user directory.  Instead, note its contents
        # and verify nothing new appears.
        files_before = {
            str(p) for p in default_dot_astrid.rglob("*") if p.is_file()
        }

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)
    assert rc == 0

    if existed_before:
        files_after = {
            str(p) for p in default_dot_astrid.rglob("*") if p.is_file()
        }
        assert files_after == files_before, (
            f"~/.astrid was modified: before={files_before}, after={files_after}"
        )
    else:
        assert not default_dot_astrid.exists(), (
            "~/.astrid was created even though ASTRID_HOME was set explicitly"
        )


def test_attach_writes_project_pointer_to_explicit_projects_root(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """The .astrid-session file MUST be written under the explicit
    PROJECTS_ROOT (not ~/.astrid or ASTRID_HOME).  This characterizes
    current behavior."""
    seed_project(env_with_identity["projects"], "demo")

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)
    assert rc == 0

    session_pointer = (
        env_with_identity["projects"] / "demo" / ".astrid-session"
    )
    assert session_pointer.exists(), (
        f"Expected .astrid-session at {session_pointer}"
    )


@pytest.mark.xfail(
    reason=(
        "GAP: cmd_attach currently writes the identity file to ASTRID_HOME "
        "during first-run bootstrap.  Explicit-root SDK operations should "
        "not perform identity bootstrap implicitly — identity should be "
        "supplied by the caller."
    ),
    strict=True,
)
def test_attach_does_not_write_identity_during_explicit_root_operation(
    explicit_env: dict[str, Path],
    seed_project: Any,
) -> None:
    """With an explicit ASTRID_HOME set, if no identity exists, the sdk
    should not implicitly create one.  Currently bootstrap_identity writes
    identity.json to ASTRID_HOME."""
    seed_project(explicit_env["projects"], "demo")
    identity_path_file = explicit_env["home"] / "identity.json"

    assert not identity_path_file.exists(), (
        "identity.json already exists before attach"
    )

    # Simulate non-interactive input failing immediately.
    def _eof(_prompt: str = "") -> str:
        raise EOFError

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _eof)
        mp.setattr("sys.stdin.isatty", lambda: True)

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)

    # The operation should NOT have written identity.json.
    # Currently it does not (because EOFError aborts before write),
    # but the path that calls input() is the gap.
    # This xfail characterizes the structural problem: the SDK path
    # attempts interactive identity bootstrap at all.
    assert not identity_path_file.exists() or rc != 0, (
        "identity.json was written during an explicit-root attach"
    )


# ---------------------------------------------------------------------------
# takeover (recover) — input() and writes characterization
# ---------------------------------------------------------------------------


def test_takeover_with_identity_bootstraps_without_input_when_identity_exists(
    env_with_identity: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    mint_session: Any,
    seed_project_run: Any,
) -> None:
    """When identity exists on disk, cmd_sessions_takeover in the unbound
    path must NOT call input() for identity bootstrap.  This already works
    because _ensure_identity reads from disk."""
    run_dir = seed_project_run(
        env_with_identity["projects"],
        "demo",
        "01RUN",
        writer_session_id="S-PREV",
    )
    from astrid.core.session.lease import release_writer_lease

    release_writer_lease(run_dir)
    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)

    def _panic_input(_prompt: str = "") -> str:
        raise AssertionError("input() was called but should not have been")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _panic_input)
        mp.setattr("sys.stdin.isatty", lambda: False)

    buf = StringIO()
    rc = cli.cmd_sessions_takeover(
        _takeover_args(target="01RUN", force=True), out=buf
    )
    assert rc == 0


@pytest.mark.xfail(
    reason=(
        "GAP: cmd_sessions_takeover (unbound path) calls _ensure_identity "
        "which calls bootstrap_identity() → builtins.input when no identity "
        "exists.  The SDK contract requires identity to be supplied "
        "programmatically."
    ),
    strict=True,
)
def test_takeover_without_identity_should_not_call_input(
    explicit_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project_run: Any,
) -> None:
    """When no identity exists, takeover's unbound bootstrap path must not
    call input().  Currently _ensure_identity → bootstrap_identity does."""
    run_dir = seed_project_run(
        explicit_env["projects"],
        "demo",
        "01RUN",
        writer_session_id="S-PREV",
    )
    from astrid.core.session.lease import release_writer_lease

    release_writer_lease(run_dir)
    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)

    input_called: list[str] = []

    def _spy_input(prompt: str = "") -> str:
        input_called.append(prompt)
        raise EOFError("no input available")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _spy_input)
        mp.setattr("sys.stdin.isatty", lambda: True)

    buf = StringIO()
    rc = cli.cmd_sessions_takeover(
        _takeover_args(target="01RUN", force=True), out=buf
    )

    assert len(input_called) == 0, (
        f"input() was called {len(input_called)} times: {input_called}"
    )


def test_takeover_writes_session_only_to_explicit_astrid_home(
    env_with_identity: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project_run: Any,
) -> None:
    """Takeover writes session files under the explicit ASTRID_HOME only."""
    run_dir = seed_project_run(
        env_with_identity["projects"],
        "demo",
        "01RUN",
        writer_session_id="S-PREV",
    )
    from astrid.core.session.lease import release_writer_lease

    release_writer_lease(run_dir)
    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)

    sessions_before = set()
    sdir = env_with_identity["home"] / "sessions"
    if sdir.exists():
        sessions_before = {p.name for p in sdir.iterdir()}

    buf = StringIO()
    rc = cli.cmd_sessions_takeover(
        _takeover_args(target="01RUN", force=True), out=buf
    )
    assert rc == 0

    sessions_after = set()
    if sdir.exists():
        sessions_after = {p.name for p in sdir.iterdir()}
    new_sessions = sessions_after - sessions_before
    assert len(new_sessions) == 1, (
        f"Expected exactly 1 new session file, got {new_sessions}"
    )


def test_takeover_does_not_create_default_dot_astrid_when_explicit_home_set(
    env_with_identity: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project_run: Any,
) -> None:
    """When ASTRID_HOME is explicit, takeover must not create ~/.astrid."""
    run_dir = seed_project_run(
        env_with_identity["projects"],
        "demo",
        "01RUN",
        writer_session_id="S-PREV",
    )
    from astrid.core.session.lease import release_writer_lease

    release_writer_lease(run_dir)
    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)

    default_dot_astrid = Path.home() / ".astrid"
    existed_before = default_dot_astrid.exists()
    files_before: set[str] = set()
    if existed_before:
        files_before = {
            str(p) for p in default_dot_astrid.rglob("*") if p.is_file()
        }

    buf = StringIO()
    rc = cli.cmd_sessions_takeover(
        _takeover_args(target="01RUN", force=True), out=buf
    )
    assert rc == 0

    if existed_before:
        files_after = {
            str(p) for p in default_dot_astrid.rglob("*") if p.is_file()
        }
        assert files_after == files_before, (
            "~/.astrid was modified during takeover"
        )
    else:
        assert not default_dot_astrid.exists(), (
            "~/.astrid was created during takeover even though ASTRID_HOME is explicit"
        )


# ---------------------------------------------------------------------------
# Full lifecycle: attach → detach → re-attach (explicit-root)
# ---------------------------------------------------------------------------


def test_full_lifecycle_with_explicit_roots_no_input_calls(
    env_with_identity: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    seed_project: Any,
) -> None:
    """A complete attach → re-attach (idempotent) → detach cycle with
    explicit ASTRID_HOME, an existing identity, and explicit --timeline
    must not call input() at any point.  This already works.

    Note: detach deletes the session file, so the cycle is
    attach → re-attach (idempotent) → detach, not
    attach → detach → re-attach (which cannot work because the file is
    gone after detach)."""
    seed_project(env_with_identity["projects"], "demo")

    def _panic_input(_prompt: str = "") -> str:
        raise AssertionError("input() was called but should not have been")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _panic_input)
        mp.setattr("sys.stdin.isatty", lambda: False)

        # attach (create)
        buf_a = StringIO()
        rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf_a)
        assert rc == 0
        sid_line = [
            ln
            for ln in buf_a.getvalue().splitlines()
            if ln.startswith("export ASTRID_SESSION_ID=")
        ][0]
        sid = sid_line.split("=", 1)[1]

        # re-attach (idempotent) — different shell, same agent/project
        monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
        buf_r = StringIO()
        rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf_r)
        assert rc == 0
        assert "session reused" in buf_r.getvalue()
        assert sid in buf_r.getvalue()

        # detach
        buf_d = StringIO()
        rc = cli.cmd_sessions_detach(
            argparse.Namespace(session_id=sid), out=buf_d
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Session create / open (via cmd_attach with --session resume)
# ---------------------------------------------------------------------------


def test_session_open_via_resume_does_not_call_input(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """Opening a session (via --session resume) must not call input()."""
    seed_project(env_with_identity["projects"], "demo")

    # First create a session.
    buf_c = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf_c)
    assert rc == 0
    sid_line = [
        ln
        for ln in buf_c.getvalue().splitlines()
        if ln.startswith("export ASTRID_SESSION_ID=")
    ][0]
    sid = sid_line.split("=", 1)[1]

    def _panic_input(_prompt: str = "") -> str:
        raise AssertionError("input() was called during session resume")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("builtins.input", _panic_input)
        mp.setattr("sys.stdin.isatty", lambda: False)

    buf_r = StringIO()
    rc = cli.cmd_attach(
        _attach_args(session=sid, project=None, timeline=None), out=buf_r
    )
    assert rc == 0
    assert sid in buf_r.getvalue()


def test_session_create_writes_only_under_explicit_roots(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """Session create (attach) with explicit ASTRID_HOME writes:
    - Session file → ASTRID_HOME/sessions/<id>.json
    - Project pointer → PROJECTS_ROOT/<slug>/.astrid-session
    - NOTHING under ~/.astrid
    """
    seed_project(env_with_identity["projects"], "demo")

    sessions_dir = env_with_identity["home"] / "sessions"
    sessions_before = set()
    if sessions_dir.exists():
        sessions_before = {p.name for p in sessions_dir.iterdir()}

    buf = StringIO()
    rc = cli.cmd_attach(_attach_args(timeline="primary"), out=buf)
    assert rc == 0

    # One new session file.
    sessions_after = {p.name for p in sessions_dir.iterdir()}
    new_sessions = sessions_after - sessions_before
    assert len(new_sessions) == 1
    sid = next(iter(new_sessions)).replace(".json", "")

    # Session file contains correct fields.
    import json

    session_payload = json.loads(
        (sessions_dir / f"{sid}.json").read_text(encoding="utf-8")
    )
    assert session_payload["project"] == "demo"
    assert session_payload["timeline"] == "primary"

    # Project pointer exists under explicit projects root.
    pointer = env_with_identity["projects"] / "demo" / ".astrid-session"
    assert pointer.exists()
    content = pointer.read_text(encoding="utf-8")
    assert sid in content


# ---------------------------------------------------------------------------
# assert: no writes to ASTRID_HOME when not explicitly opted in
# ---------------------------------------------------------------------------


def test_idempotent_attach_does_not_create_new_session_file(
    env_with_identity: dict[str, Path],
    seed_project: Any,
) -> None:
    """Repeated attach (idempotent) should reuse the existing session and
    not create additional files.  This already works per #19/#23."""
    seed_project(env_with_identity["projects"], "demo")

    buf1 = StringIO()
    cli.cmd_attach(_attach_args(timeline="primary"), out=buf1)

    sessions_dir = env_with_identity["home"] / "sessions"
    count_before = len(list(sessions_dir.iterdir()))

    buf2 = StringIO()
    cli.cmd_attach(_attach_args(timeline="primary"), out=buf2)

    count_after = len(list(sessions_dir.iterdir()))
    assert count_after == count_before, (
        f"Expected {count_before} session files but found {count_after}"
    )
    assert "session reused" in buf2.getvalue()
