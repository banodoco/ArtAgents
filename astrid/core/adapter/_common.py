"""Shared adapter helpers used across multiple adapter modules."""

from __future__ import annotations

from pathlib import Path

from astrid.core.adapter import RunContext
from astrid.core.task.command_render import step_dir_for_context


def _step_dir(run_ctx: RunContext) -> Path:
    """Resolve runs/<run>/steps/<id>/v<N>/[iterations|items]/... for this dispatch."""
    return step_dir_for_context(
        run_ctx.project_root,
        run_ctx.run_id,
        run_ctx.plan_step_path,
        run_ctx.step_version,
        iteration=run_ctx.iteration,
        item_id=run_ctx.item_id,
    )
