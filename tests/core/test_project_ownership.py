"""Project ownership tests for managed timelines and experiments."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor
from astrid.core.project.ownership import (
    ProjectOwnershipError,
    require_project_owned_artifact,
)
from astrid.core.project.project import create_project


def test_experiment_must_live_under_owning_project(tmp_path: Path) -> None:
    create_project("plants", root=tmp_path)
    experiment = tmp_path / "plants" / "experiments" / "growth" / "experiment.json"
    experiment.parent.mkdir(parents=True)
    experiment.write_text("{}", encoding="utf-8")

    assert require_project_owned_artifact(
        "plants", "experiment", experiment, root=tmp_path
    ) == experiment.resolve()

    outside = tmp_path / "legacy" / "experiment.json"
    with pytest.raises(ProjectOwnershipError, match="not owned by project"):
        require_project_owned_artifact(
            "plants", "experiment", outside, root=tmp_path
        )


def test_timeline_may_be_managed_or_project_run_artifact(tmp_path: Path) -> None:
    create_project("plants", root=tmp_path)
    managed = tmp_path / "plants" / "timelines" / "timeline.json"
    derived = tmp_path / "plants" / "runs" / "run-id" / "hype.timeline.json"

    assert require_project_owned_artifact(
        "plants", "timeline", managed, root=tmp_path
    ) == managed.resolve()
    assert require_project_owned_artifact(
        "plants", "timeline", derived, root=tmp_path
    ) == derived.resolve()

    with pytest.raises(ProjectOwnershipError, match="not owned by project"):
        require_project_owned_artifact(
            "plants", "timeline", tmp_path / "standalone.timeline.json", root=tmp_path
        )


def test_experiment_runs_dir_must_match_project(tmp_path: Path) -> None:
    create_project("plants", root=tmp_path)

    assert require_project_owned_artifact(
        "plants", "experiment_runs", tmp_path / "plants" / "runs", root=tmp_path
    ) == (tmp_path / "plants" / "runs").resolve()

    with pytest.raises(ProjectOwnershipError, match="not owned by project"):
        require_project_owned_artifact(
            "plants", "experiment_runs", tmp_path / "other" / "runs", root=tmp_path
        )


def test_executor_dispatch_rejects_standalone_timeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path))
    create_project("plants")
    outside = tmp_path / "standalone.timeline.json"
    assets = tmp_path / "standalone.assets.json"

    with pytest.raises(ProjectOwnershipError, match="not owned by project"):
        run_executor(
            ExecutorRunRequest(
                executor_id="rendering.timeline_storyboard",
                out=None,
                project="plants",
                inputs={"timeline": outside, "assets_registry": assets},
            )
        )
