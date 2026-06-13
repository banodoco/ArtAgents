from __future__ import annotations

from astrid.core import plan as stable_plan
from astrid.core.verify import json_file as verify_json_file
from astrid.core.orchestrate import (
    OrchestrateDefinitionError,
    attested,
    code,
    compile_to_path,
    compile_to_pipeline,
    dsl as orchestrate_dsl,
    dsl_to_pipeline,
    json_file,
    orchestrator,
    plan,
)
from astrid.core.orchestrate import cli as orchestrate_cli
from astrid.core.orchestrate import compile as orchestrate_compile


def test_authoring_modules_bind_stable_plan_home() -> None:
    assert orchestrate_dsl.TaskPlanError is stable_plan.TaskPlanError
    assert orchestrate_dsl.load_plan is stable_plan.load_plan
    assert orchestrate_dsl.parse_repeat_until_expression is stable_plan.parse_repeat_until_expression

    assert orchestrate_compile.TaskPlan is stable_plan.TaskPlan
    assert orchestrate_compile.load_plan is stable_plan.load_plan

    assert orchestrate_cli.TaskPlan is stable_plan.TaskPlan
    assert orchestrate_cli.TaskPlanError is stable_plan.TaskPlanError
    assert orchestrate_cli.load_plan is stable_plan.load_plan
    assert orchestrate_cli.iter_steps_with_path is stable_plan.iter_steps_with_path


def test_public_orchestrate_authoring_exports_are_preserved() -> None:
    assert OrchestrateDefinitionError is orchestrate_dsl.OrchestrateDefinitionError
    assert code is orchestrate_dsl.code
    assert attested is orchestrate_dsl.attested
    assert orchestrator is orchestrate_dsl.orchestrator
    assert plan is orchestrate_dsl.plan
    assert json_file is verify_json_file

    assert compile_to_path is orchestrate_compile.compile_to_path
    assert compile_to_pipeline is orchestrate_compile.compile_to_pipeline
    assert dsl_to_pipeline is orchestrate_compile.dsl_to_pipeline
