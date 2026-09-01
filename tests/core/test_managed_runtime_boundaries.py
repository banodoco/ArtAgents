"""Pure managed-write boundary contracts after runtime authority cutover."""

from __future__ import annotations

import pytest

from astrid.core.project.runtime import (
    ProjectRuntimeError,
    project_run_env,
    reject_project_with_out,
)


def test_project_output_is_runtime_owned() -> None:
    reject_project_with_out("demo", None)
    with pytest.raises(ProjectRuntimeError, match="cannot be combined"):
        reject_project_with_out("demo", "/tmp/out")


def test_project_run_environment_contains_hints_only() -> None:
    env = project_run_env("demo")
    assert env["ASTRID_PROJECT_RUN"] == "1"
    assert env["ASTRID_PROJECT_SLUG"] == "demo"
    assert "ASTRID_PROJECTS_ROOT" not in env
