"""Kernel preference seam tests (m4 plan step 5, task T6B).

Proves :mod:`astrid.core.preferences` is the canonical, kernel-owned,
file-side, non-authoritative home for the retained user/workspace
``config.json`` preference read/write, and that
:mod:`astrid.core.session.config` delegates to it until m6 teardown:

- resolution precedence is exactly **explicit option > workspace > user**;
- ``set_default_project`` persists **only** ``default_project`` (unknown
  keys are preserved additively) and is restart-durable (a fresh read —
  no in-process cache — returns the persisted value);
- the retained session-layer import paths keep working through the
  delegate (``load_user_config``/``load_workspace_config``/
  ``resolve_default_project``/``resolve_default_timeline``/
  ``set_default_project``/``ConfigError``);
- malformed preference files fail closed with ``ConfigError``;
- there is no database, receipt, or sidecar authority involved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core import preferences
from astrid.core.session import config, paths


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sandbox ``ASTRID_HOME`` so user config never touches the real home."""
    home_dir = tmp_path / "home"
    monkeypatch.setenv(paths.ASTRID_HOME_ENV, str(home_dir))
    monkeypatch.delenv(paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, raising=False)
    home_dir.mkdir(parents=True, exist_ok=True)
    return home_dir


def _write_user(home: Path, payload: object) -> None:
    paths.user_config_path().write_text(json.dumps(payload), encoding="utf-8")


def _write_workspace(cwd: Path, payload: object) -> None:
    ws_dir = cwd / ".astrid"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "config.json").write_text(json.dumps(payload), encoding="utf-8")


def test_resolve_precedence_explicit_over_workspace_over_user(
    home: Path, tmp_path: Path
) -> None:
    _write_user(home, {"default_project": "user-pick"})
    ws = tmp_path / "ws"
    _write_workspace(ws, {"default_project": "workspace-pick"})

    # Explicit option always wins, regardless of either config scope.
    assert (
        preferences.resolve_default_project(ws, explicit="explicit-pick")
        == "explicit-pick"
    )
    # Without an explicit option, workspace wins over user.
    assert preferences.resolve_default_project(ws) == "workspace-pick"
    # With no workspace config, the user default is used.
    assert preferences.resolve_default_project(tmp_path / "other") == "user-pick"


def test_resolve_returns_none_when_nothing_configured(home: Path) -> None:
    assert preferences.resolve_default_project() is None
    assert preferences.resolve_default_timeline() is None


def test_set_default_project_persists_only_default_project(
    home: Path, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    # Pre-seed an unrelated key: it must survive (additive, unknown keys
    # preserved) while select only ever writes default_project.
    _write_workspace(ws, {"unrelated": {"keep": True}})

    written = preferences.set_default_project("demo", scope="workspace", cwd=ws)
    assert written == ws / ".astrid" / "config.json"

    on_disk = json.loads(written.read_text(encoding="utf-8"))
    assert on_disk["default_project"] == "demo"
    assert on_disk["unrelated"] == {"keep": True}

    # Clearing removes only default_project and keeps the unknown key.
    preferences.set_default_project(None, scope="workspace", cwd=ws)
    on_disk = json.loads(written.read_text(encoding="utf-8"))
    assert "default_project" not in on_disk
    assert on_disk["unrelated"] == {"keep": True}


def test_set_default_project_is_restart_durable(home: Path, tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    preferences.set_default_project("demo", scope="workspace", cwd=ws)

    # A fresh read (no in-process cache exists) resolves the persisted slug,
    # exactly what a later process invocation observes after a restart.
    assert preferences.resolve_default_project(ws) == "demo"
    assert preferences.load_workspace_config(ws)["default_project"] == "demo"


def test_set_default_project_user_scope(home: Path) -> None:
    written = preferences.set_default_project("user-demo", scope="user")
    assert written == paths.user_config_path()
    assert preferences.resolve_default_project() == "user-demo"
    preferences.set_default_project(None, scope="user")
    assert preferences.resolve_default_project() is None


def test_delegate_session_config_re_exports_preferences(home: Path, tmp_path: Path) -> None:
    # The session layer delegates to the kernel preference seam until m6.
    assert config.ConfigError is preferences.ConfigError
    assert config.load_user_config is preferences.load_user_config
    assert config.load_workspace_config is preferences.load_workspace_config
    assert config.resolve_default_project is preferences.resolve_default_project
    assert config.resolve_default_timeline is preferences.resolve_default_timeline
    assert config.set_default_project is preferences.set_default_project

    _write_user(home, {"default_project": "user-pick"})
    ws = tmp_path / "ws"
    _write_workspace(ws, {"default_project": "workspace-pick"})
    # The delegate exposes the same frozen precedence, including the
    # explicit-option keyword.
    assert config.resolve_default_project(ws) == "workspace-pick"
    assert config.resolve_default_project(ws, explicit="flag-wins") == "flag-wins"


def test_malformed_preference_files_fail_closed(home: Path, tmp_path: Path) -> None:
    _write_user(home, ["not", "an", "object"])
    with pytest.raises(preferences.ConfigError, match="JSON object"):
        preferences.load_user_config()
    with pytest.raises(config.ConfigError, match="JSON object"):
        config.load_user_config()


def test_non_string_default_project_rejected(home: Path, tmp_path: Path) -> None:
    # A non-string default_project value is rejected before it can be
    # surfaced to a caller (the user config stays clean here).
    _write_workspace(tmp_path / "bad", {"default_project": 42})
    with pytest.raises(preferences.ConfigError, match="non-empty string"):
        preferences.resolve_default_project(tmp_path / "bad")
