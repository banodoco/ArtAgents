from __future__ import annotations

import inspect
from argparse import Namespace
from pathlib import Path

import pytest

from astrid.core import managed_binding as stable_managed_binding
from astrid.core import plan as stable_plan
from astrid.core.integrations.arnold.host import cli as arnold_host_cli
from astrid.core.integrations.arnold.session import lowering as arnold_lowering
from astrid.core.orchestrate import cli as orchestrate_cli
from astrid.core.orchestrate import dsl as orchestrate_dsl
from astrid.core.task import managed_binding as legacy_managed_binding
from astrid.core.task import plan as legacy_plan
from astrid.packs.editorial.executors.refine import run as refine_run
from astrid.packs.iteration.executors.assemble import run as assemble_run
from astrid.packs.video_editing.executors.cut import run as cut_run


def test_stable_managed_binding_home_reexports_legacy_helper_by_identity() -> None:
    assert stable_managed_binding.is_managed_mode is legacy_managed_binding.is_managed_mode


def test_stable_managed_binding_preserves_behavior() -> None:
    managed_args = Namespace(project="demo", timeline_slug="main")
    unmanaged_args = Namespace(project="demo", timeline_slug=None)

    assert stable_managed_binding.is_managed_mode(managed_args) is True
    assert stable_managed_binding.is_managed_mode(unmanaged_args) is False
    assert stable_managed_binding.is_managed_mode(managed_args) == legacy_managed_binding.is_managed_mode(
        managed_args
    )


def test_migrated_pack_consumers_bind_stable_managed_binding_home() -> None:
    assert refine_run.is_managed_mode is stable_managed_binding.is_managed_mode
    assert assemble_run.is_managed_mode is stable_managed_binding.is_managed_mode
    assert cut_run.is_managed_mode is stable_managed_binding.is_managed_mode


def test_stable_plan_home_reexports_legacy_task_plan_error_by_identity() -> None:
    assert stable_plan.TaskPlanError is legacy_plan.TaskPlanError


def test_stable_plan_error_preserves_behavioral_contract(tmp_path: Path) -> None:
    with pytest.raises(stable_plan.TaskPlanError, match="at least one segment"):
        legacy_plan.step_dir_for_path("demo", "run1", (), root=tmp_path)


def test_migrated_plan_error_consumers_bind_stable_home() -> None:
    assert orchestrate_cli.TaskPlanError is stable_plan.TaskPlanError
    assert orchestrate_dsl.TaskPlanError is stable_plan.TaskPlanError
    assert arnold_lowering.TaskPlanError is stable_plan.TaskPlanError


def test_arnold_host_plan_mutation_imports_stable_plan_error_home() -> None:
    source = inspect.getsource(arnold_host_cli._emit_session_plan_mutation_from_payload)
    assert "from astrid.core.plan import TaskPlanError" in source
