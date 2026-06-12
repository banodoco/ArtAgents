from __future__ import annotations

import json
import os
from pathlib import Path

from astrid.core.project.project import create_project
from astrid.core.task import gate as task_gate
from tests.helpers.current_run import seed_current_run
from astrid.core.task.env import (
    TASK_ITEM_ID_ENV,
    TASK_ITERATION_ENV,
    TASK_PROJECT_ENV,
    TASK_RUN_ID_ENV,
    TASK_STEP_ID_ENV,
)
from astrid.core.task.plan import compute_plan_hash, step_dir_for_path


def _clear_task_env() -> None:
    for name in (
        TASK_RUN_ID_ENV,
        TASK_PROJECT_ENV,
        TASK_STEP_ID_ENV,
        TASK_ITEM_ID_ENV,
        TASK_ITERATION_ENV,
    ):
        os.environ.pop(name, None)


def _run_one_step(tmp_projects_root: Path, slug: str, payload: bytes) -> Path:
    """Run one step through gate finalization and return the produces artifact path."""
    plan = {
        "plan_id": "p",
        "version": 2,
        "steps": [
            {
                "id": "step-1",
                "adapter": "local",
                "command": "echo go",
                "cost": {"amount": 0, "currency": "USD", "source": "local"},
                "produces": {
                    "out": {
                        "path": "out.json",
                        "check": {"check_id": "json_file", "params": {}, "sentinel": False},
                    }
                },
            }
        ],
    }
    run_id = "run-1"
    create_project(slug, root=tmp_projects_root)
    plan_path = tmp_projects_root / slug / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    seed_current_run(slug, run_id=run_id, plan_hash=compute_plan_hash(plan_path), root=tmp_projects_root)

    decision = task_gate.gate_command(slug, "echo go", ["echo", "go"], root=tmp_projects_root)
    step_dir = step_dir_for_path(slug, run_id, ("step-1",), root=tmp_projects_root)
    produces_dir = step_dir / "produces"
    produces_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = produces_dir / "out.json"
    artifact_path.write_bytes(payload)
    task_gate.record_dispatch_complete(decision, 0)
    return artifact_path


def test_identical_content_is_not_shared_across_projects(tmp_projects_root: Path) -> None:
    payload = b'{"shared": "bytes"}'

    try:
        artifact_a = _run_one_step(tmp_projects_root, "proj-a", payload)
        artifact_b = _run_one_step(tmp_projects_root, "proj-b", payload)

        # Normal produces path uses identity CAS — the produces artifact is a
        # symlink into .cas/<identity_key>.  Resolve the symlink to discover
        # the actual CAS entry path.
        assert artifact_a.is_symlink(), "produces artifact must be a symlink after identity interning"
        assert artifact_b.is_symlink(), "produces artifact must be a symlink after identity interning"
        cas_a = artifact_a.resolve()
        cas_b = artifact_b.resolve()
        assert cas_a.is_file()
        assert cas_b.is_file()
        # Both projects use the same plan + command, so the identity key
        # (and therefore the CAS entry name) must be identical.
        assert cas_a.name == cas_b.name
        # Two distinct physical files, even though contents are identical.
        assert cas_a.stat().st_ino != cas_b.stat().st_ino
        assert cas_a.read_bytes() == payload
        assert cas_b.read_bytes() == payload

        # No shared CAS at the projects-root level.
        assert not (tmp_projects_root / ".cas").exists()
    finally:
        _clear_task_env()
