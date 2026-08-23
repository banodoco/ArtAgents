from __future__ import annotations

import os
from pathlib import Path

import pytest

from astrid.core.foundation import project_paths


def test_passed_test_sandboxes_are_function_scoped(
    tmp_path: Path,
    pytestconfig: pytest.Config,
) -> None:
    """Keep successful per-test sandboxes eligible for immediate cleanup."""

    assert pytestconfig.getini("tmp_path_retention_policy") == "failed"

    roots = {
        Path(os.environ["ASTRID_HOME"]),
        Path(os.environ["ASTRID_WORKSPACE_CONFIG_DIR"]),
        Path(os.environ[project_paths.PROJECTS_ROOT_ENV]),
    }
    assert roots == {
        tmp_path / "astrid-home",
        tmp_path / "workspace-config",
        tmp_path / "projects",
    }
    assert all(root.is_dir() for root in roots)
