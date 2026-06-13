"""Compile TaskPlan segments into Arnold pipelines for session succession."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from astrid.core.integrations.arnold.session import lowering
from astrid.core.task.plan import TaskPlan


CompileResult = lowering.CompileResult
CompileUnsupportedFeature = lowering.CompileUnsupportedFeature
TASK_ADAPTER_EXECUTOR_PREFIX = lowering.TASK_ADAPTER_EXECUTOR_PREFIX


def compile_plan_segment(
    plan: TaskPlan,
    *,
    project: str,
    run_root: str | Path,
    state: dict[str, Any],
    segment_id: str,
) -> CompileResult:
    """Compile a TaskPlan into a fresh Arnold pipeline segment."""

    return lowering.compile_plan_segment(
        plan,
        project=project,
        run_root=run_root,
        state=state,
        segment_id=segment_id,
    )


__all__ = ["CompileResult", "CompileUnsupportedFeature", "TASK_ADAPTER_EXECUTOR_PREFIX", "compile_plan_segment"]
