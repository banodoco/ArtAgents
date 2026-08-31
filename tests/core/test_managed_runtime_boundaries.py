"""Pure managed-write boundary contracts after runtime authority cutover."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.project.runtime import (
    ProjectRuntimeError,
    project_run_env,
    reject_project_with_out,
    step_dir_for,
)


def test_project_output_is_runtime_owned() -> None:
    reject_project_with_out("demo", None)
    with pytest.raises(ProjectRuntimeError, match="cannot be combined"):
        reject_project_with_out("demo", "/tmp/out")


def test_runtime_staging_requires_explicit_root_and_never_falls_back_to_cwd(tmp_path: Path) -> None:
    with pytest.raises(ProjectRuntimeError, match="explicit projects root"):
        step_dir_for("demo", "01ARZ3NDEKTSV4RRFFQ69G5FAV", "01ARZ3NDEKTSV4RRFFQ69G5FAW")
    staging = step_dir_for(
        "demo", "01ARZ3NDEKTSV4RRFFQ69G5FAV", "01ARZ3NDEKTSV4RRFFQ69G5FAW", root=tmp_path
    )
    assert staging == tmp_path.resolve() / ".astrid-runtime-staging" / "demo" / "01ARZ3NDEKTSV4RRFFQ69G5FAV" / "steps" / "01ARZ3NDEKTSV4RRFFQ69G5FAW" / "v1"
    assert not staging.exists()


def test_project_run_environment_contains_hints_only() -> None:
    env = project_run_env("demo", root="/tmp/projects")
    assert env["ASTRID_PROJECT_RUN"] == "1"
    assert env["ASTRID_PROJECT_SLUG"] == "demo"
    assert Path(env["ASTRID_PROJECTS_ROOT"]) == Path("/tmp/projects").resolve()
