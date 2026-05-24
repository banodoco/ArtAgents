"""First-run status remains discoverable even when identity is absent."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from astrid.core.project import paths as project_paths
from astrid.core.project.project import create_project
from astrid.core.session import cli, paths as session_paths
from astrid.core.session import config
from astrid.core.session.identity import read_identity
from astrid.core.task import lifecycle


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def test_status_does_not_bootstrap_when_identity_absent(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # No identity file exists.
    assert read_identity() is None

    def _trap(_prompt: str) -> str:  # pragma: no cover - asserted by exception
        raise AssertionError("status should not prompt for identity")

    monkeypatch.setattr("builtins.input", _trap)
    buf = StringIO()
    rc = cli.cmd_status(argparse.Namespace(), out=buf)
    assert rc == 0
    output = buf.getvalue()
    assert cli.FIRST_RUN_PROMPT_HEADER not in output
    assert cli.STATUS_UNBOUND_HEADER in output
    assert read_identity() is None
    assert not (env["home"] / "sessions").exists()


def test_status_does_not_bootstrap_when_identity_present(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Seed an identity.
    (env["home"]).mkdir(parents=True, exist_ok=True)
    (env["home"] / "identity.json").write_text(
        '{"agent_id":"codex-1","created_at":"2026-05-11T00:00:00Z"}',
        encoding="utf-8",
    )
    # input() must NOT be called now.
    called = {"yes": False}

    def _trap(_prompt: str) -> str:  # pragma: no cover - asserted via flag
        called["yes"] = True
        return "x"

    monkeypatch.setattr("builtins.input", _trap)
    rc = cli.cmd_status(argparse.Namespace(), out=StringIO())
    assert rc == 0
    assert called["yes"] is False


def test_status_with_default_project_does_not_auto_attach(
    env: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    create_project("demo")
    config.set_default_project("demo")

    buf = StringIO()
    rc = cli.cmd_status(argparse.Namespace(), out=buf)

    assert rc == 0
    assert "default project: demo" in buf.getvalue()
    assert "astrid attach              # attach default project" in buf.getvalue()
    assert not (env["projects"] / "demo" / cli.SESSION_FILE_NAME).exists()
    assert not (env["home"] / "sessions").exists()


def test_unbound_next_prints_one_action_without_bootstrapping(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: pytest.fail("next prompted"))

    buf = StringIO()
    with redirect_stdout(buf):
        rc = lifecycle.cmd_next([], projects_root=env["projects"])

    assert rc == 0
    out = buf.getvalue()
    actions = [
        line.strip()
        for line in out.splitlines()
        if line.strip().startswith("astrid ")
    ]
    assert actions == ["astrid projects create <slug>"]
    assert read_identity() is None
    assert not (env["home"] / "sessions").exists()
