"""Focused regression coverage for project orientation and selection UX."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.projects import ProjectRepository
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.projects import ProjectsService


def _service(tmp_path: Path) -> tuple[ProjectsService, DatabaseWriter]:
    writer = DatabaseWriter(tmp_path / "kernel.sqlite3", core_only_registry())
    receipts = ReceiptService()
    projects = ProjectRepository(
        events=EventAppendService(core_only_registry()), receipts=receipts
    )
    return ProjectsService(writer, projects, receipts, projects_root=tmp_path / "projects"), writer


def test_project_dtos_include_canonical_path_and_current_scope(tmp_path, monkeypatch):
    service, writer = _service(tmp_path)
    try:
        monkeypatch.setenv("ASTRID_HOME", str(tmp_path / "home"))
        workspace = tmp_path / "workspace"
        created = service.create(slug="alpha", name="Alpha")
        assert created.data["path"] == str((tmp_path / "projects" / "alpha").resolve())
        assert service.list().data[0]["path"] == created.data["path"]

        selected = service.select("alpha", cwd=workspace)
        assert selected.data["selection"] == {
            "ref": "alpha",
            "scope": "workspace",
            "path": str((workspace / ".astrid" / "config.json").resolve()),
        }
        current = service.current(cwd=workspace)
        assert current.data["project"]["path"] == created.data["path"]
        assert current.data["selection"]["scope"] == "workspace"
    finally:
        writer.close()


def test_project_name_and_slug_errors_are_actionable(tmp_path):
    service, writer = _service(tmp_path)
    try:
        first = service.create(slug="alpha", name="Same Name")
        second = service.create(slug="beta", name="Same Name")
        assert first.ok and second.ok

        ambiguous = service.show("Same Name")
        assert ambiguous.error.code == "validation_error"
        assert ambiguous.error.details["reason"] == "ambiguous_display_name"
        assert {candidate["slug"] for candidate in ambiguous.error.details["candidates"]} == {"alpha", "beta"}

        duplicate = service.create(slug="alpha", name="Other")
        assert duplicate.error.code == "conflict"
        assert duplicate.error.details["field"] == "slug"
        assert duplicate.error.details["slug"] == "alpha"

        missing = service.show("missing-project")
        assert missing.error.code == "not_found"
        assert "projects list" in missing.error.details["recovery"]
    finally:
        writer.close()


def test_selected_project_routes_omitted_cli_project_without_cross_root_leak(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    projects_root_a = tmp_path / "projects-a"
    projects_root_b = tmp_path / "projects-b"
    home = tmp_path / "home"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    base_env = {
        **os.environ,
        "ASTRID_HOME": str(home),
        "PYTHONPATH": str(repo),
    }
    # The suite's autouse fixture exports a legacy test-only workspace config
    # override. Remove it so ASTRID_PROJECTS_ROOT supplies the documented
    # default workspace boundary and independently isolates both shells.
    base_env.pop("ASTRID_WORKSPACE_CONFIG_DIR", None)

    def run(cwd: Path, projects_root: Path, *args: str) -> dict:
        completed = subprocess.run(
            [sys.executable, "-m", "astrid", *args, "--json"],
            cwd=cwd,
            env={**base_env, "ASTRID_PROJECTS_ROOT": str(projects_root)},
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(completed.stdout)

    run(workspace_a, projects_root_a, "projects", "create", "alpha", "--name", "Alpha")
    run(workspace_b, projects_root_b, "projects", "create", "beta", "--name", "Beta")
    run(workspace_a, projects_root_a, "projects", "select", "alpha")
    run(workspace_b, projects_root_b, "projects", "select", "beta")
    current_a = run(workspace_a, projects_root_a, "projects", "current")
    current_b = run(workspace_b, projects_root_b, "projects", "current")
    assert current_a["data"]["selection"]["scope"] == "workspace"
    assert current_a["data"]["project"]["slug"] == "alpha"
    assert current_b["data"]["project"]["slug"] == "beta"

    run(
        workspace_a,
        projects_root_a,
        "timelines",
        "create",
        "alpha-main",
        "--name",
        "Alpha Main",
        "--config",
        '{"duration":1}',
        "--registry",
        '{"assets":{}}',
    )
    run(
        workspace_b,
        projects_root_b,
        "timelines",
        "create",
        "beta-main",
        "--name",
        "Beta Main",
        "--config",
        '{"duration":1}',
        "--registry",
        '{"assets":{}}',
    )
    alpha = run(workspace_a, projects_root_a, "timelines", "list")
    beta = run(workspace_b, projects_root_b, "timelines", "list")
    assert [row["slug"] for row in alpha["data"]] == ["alpha-main"]
    assert [row["slug"] for row in beta["data"]] == ["beta-main"]


def test_corrupt_selection_fails_closed_with_scope_path_and_recovery(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {
        **os.environ,
        "ASTRID_PROJECTS_ROOT": str(tmp_path / "projects"),
        "ASTRID_HOME": str(tmp_path / "home"),
        "PYTHONPATH": str(repo),
    }
    env.pop("ASTRID_WORKSPACE_CONFIG_DIR", None)

    def run(cwd: Path, *args: str) -> tuple[int, dict]:
        completed = subprocess.run(
            [sys.executable, "-m", "astrid", *args, "--json"],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode, json.loads(completed.stdout)

    assert run(workspace, "projects", "create", "alpha", "--name", "Alpha")[0] == 0
    _, selected = run(workspace, "projects", "select", "alpha")
    preference_path = Path(selected["data"]["selection"]["path"])
    preference_path.write_text("{not valid json", encoding="utf-8")

    code, current = run(workspace, "projects", "current")
    assert code == 1
    assert current["error"]["code"] == "validation_error"
    assert current["error"]["details"] == {
        "field": "project",
        "reason": "invalid_selection_preference",
        "scope": "workspace",
        "path": str(preference_path.resolve()),
        "recovery": "repair or remove the malformed preference, then run `astrid projects select <slug-or-id>`",
    }

    code, timelines = run(workspace, "timelines", "list")
    assert code == 1
    assert timelines["error"]["code"] == "validation_error"
    assert timelines["error"]["details"]["reason"] == "invalid_selection_preference"
    assert timelines["error"]["details"]["scope"] == "workspace"

    code, repaired = run(workspace, "projects", "select", "alpha")
    assert code == 0
    assert repaired["data"]["selection"]["scope"] == "workspace"
    code, current = run(workspace, "projects", "current")
    assert code == 0
    assert current["data"]["project"]["slug"] == "alpha"


def test_timeline_name_and_invalid_ref_errors_are_actionable(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {
        **os.environ,
        "ASTRID_PROJECTS_ROOT": str(tmp_path / "projects"),
        "ASTRID_HOME": str(tmp_path / "home"),
        "PYTHONPATH": str(repo),
    }
    env.pop("ASTRID_WORKSPACE_CONFIG_DIR", None)

    def run(*args: str) -> tuple[int, dict]:
        completed = subprocess.run(
            [sys.executable, "-m", "astrid", *args, "--json"],
            cwd=workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode, json.loads(completed.stdout)

    assert run("projects", "create", "alpha", "--name", "Alpha")[0] == 0
    timeline_args = (
        "--project",
        "alpha",
        "--config",
        '{"duration":1}',
        "--registry",
        '{"assets":{}}',
    )
    assert run("timelines", "create", "primary", "--name", "Human Timeline", *timeline_args)[0] == 0

    code, unambiguous = run("timelines", "show", "Human Timeline", "--project", "alpha")
    assert code == 1
    assert unambiguous["error"]["code"] == "validation_error"
    assert unambiguous["error"]["details"]["reason"] == "display_name_not_addressable"
    assert unambiguous["error"]["details"]["candidates"][0]["slug"] == "primary"
    assert "candidates[0].slug" in unambiguous["error"]["details"]["recovery"]

    assert run("timelines", "create", "secondary", "--name", "Human Timeline", *timeline_args)[0] == 0

    code, ambiguous = run("timelines", "show", "Human Timeline", "--project", "alpha")
    assert code == 1
    assert ambiguous["error"]["code"] == "validation_error"
    assert ambiguous["error"]["details"]["reason"] == "ambiguous_display_name"
    assert {candidate["slug"] for candidate in ambiguous["error"]["details"]["candidates"]} == {
        "primary",
        "secondary",
    }
    assert "candidates[].id" in ambiguous["error"]["details"]["recovery"]

    code, invalid = run("timelines", "show", "not a timeline", "--project", "alpha")
    assert code == 1
    assert invalid["error"]["code"] == "validation_error"
    assert invalid["error"]["details"]["expected"] == [
        "canonical UUID",
        "lowercase ULID",
        "lowercase slug",
    ]
    assert "timelines list" in invalid["error"]["details"]["recovery"]
