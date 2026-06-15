"""Stable non-task home for shared task-command rendering helpers.

Release N keeps ``astrid.core.task.command_render`` as the implementation and
fallback surface. This module provides the long-lived import path for
non-task consumers while the behavioral core is being retired.
"""

from astrid.core.task.command_render import (
    INTERNAL_INVOCATION_ENV,
    RenderedTaskCommand,
    render_task_command,
    step_dir_for_context,
    strip_task_env_prefix,
    task_env_for_context,
)

__all__ = [
    "INTERNAL_INVOCATION_ENV",
    "RenderedTaskCommand",
    "render_task_command",
    "step_dir_for_context",
    "strip_task_env_prefix",
    "task_env_for_context",
]
