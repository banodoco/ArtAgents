"""Task-owned command rendering for code-step dispatch and display."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from astrid.core.task.env import (
    TASK_ITEM_ID_ENV,
    TASK_ITERATION_ENV,
    TASK_PROJECT_ENV,
    TASK_RUN_ID_ENV,
    TASK_STEP_ID_ENV,
)
from astrid.core.task.plan import STEP_PATH_SEP, Step


@dataclass(frozen=True)
class RenderedTaskCommand:
    raw_template: str
    canonical_command: str
    canonical_argv: tuple[str, ...]
    display_command: str
    display_argv: tuple[str, ...]
    task_env: dict[str, str]
    produces_root: Path


def step_dir_for_context(
    project_root: Path,
    run_id: str,
    plan_step_path: tuple[str, ...],
    step_version: int,
    *,
    iteration: int | None = None,
    item_id: str | None = None,
) -> Path:
    base = project_root / "runs" / run_id / "steps"
    for segment in plan_step_path:
        base = base / segment
    base = base / f"v{step_version}"
    if iteration is not None:
        return base / "iterations" / f"{iteration:03d}"
    if item_id is not None:
        return base / "items" / item_id
    return base


def task_env_for_context(
    *,
    slug: str,
    run_id: str,
    plan_step_path: tuple[str, ...],
    iteration: int | None = None,
    item_id: str | None = None,
) -> dict[str, str]:
    env = {
        TASK_PROJECT_ENV: slug,
        TASK_RUN_ID_ENV: run_id,
        TASK_STEP_ID_ENV: STEP_PATH_SEP.join(plan_step_path),
    }
    if item_id is not None:
        env[TASK_ITEM_ID_ENV] = item_id
    if iteration is not None:
        env[TASK_ITERATION_ENV] = f"{int(iteration):03d}"
    return env


def _quote_env_assignment(key: str, value: str) -> str:
    return f"{key}={shlex.quote(value)}"


def render_task_command(
    step: Step,
    *,
    slug: str,
    run_id: str,
    project_root: Path,
    plan_step_path: tuple[str, ...],
    iteration: int | None = None,
    item_id: str | None = None,
    command_text: str | None = None,
) -> RenderedTaskCommand:
    template = command_text if command_text is not None else step.command
    if template is None or not template.strip():
        raise ValueError("task command renderer requires a non-empty command template")
    task_env = task_env_for_context(
        slug=slug,
        run_id=run_id,
        plan_step_path=plan_step_path,
        iteration=iteration,
        item_id=item_id,
    )
    step_dir = step_dir_for_context(
        project_root,
        run_id,
        plan_step_path,
        step.version,
        iteration=iteration,
        item_id=item_id,
    )
    substitutions = {
        "produces_root": str(step_dir / "produces"),
        "step_dir": str(step_dir),
        "item_id": item_id or "",
        "iteration": f"{int(iteration):03d}" if iteration is not None else "",
    }
    canonical_command = template
    for key, value in substitutions.items():
        canonical_command = canonical_command.replace("{" + key + "}", value)
    canonical_argv = tuple(shlex.split(canonical_command))
    canonical_command = shlex.join(canonical_argv)
    env_prefix = " ".join(_quote_env_assignment(k, v) for k, v in task_env.items())
    display_command = f"{env_prefix} {canonical_command}"
    display_argv = tuple(shlex.split(display_command))
    return RenderedTaskCommand(
        raw_template=template,
        canonical_command=canonical_command,
        canonical_argv=canonical_argv,
        display_command=display_command,
        display_argv=display_argv,
        task_env=task_env,
        produces_root=step_dir / "produces",
    )


def strip_task_env_prefix(command: str) -> str:
    """Remove only the leading task-env assignment wrapper emitted by cmd_next."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    task_keys = {
        TASK_PROJECT_ENV,
        TASK_RUN_ID_ENV,
        TASK_STEP_ID_ENV,
        TASK_ITEM_ID_ENV,
        TASK_ITERATION_ENV,
    }
    idx = 0
    while idx < len(parts):
        key, sep, _value = parts[idx].partition("=")
        if sep != "=" or key not in task_keys:
            break
        idx += 1
    if idx == 0:
        return command
    return shlex.join(parts[idx:])
