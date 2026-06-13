"""Stable non-task home for shared task-plan contracts.

Release N keeps ``astrid.core.task.plan`` as the implementation and fallback
surface. This module provides the long-lived import path for cross-surface
consumers that need plan types, validators, and helper functions without
binding directly to the task-owned module path.
"""

from astrid.core.task.plan import (
    TaskPlan,
    TaskPlanError,
    RepeatForEach,
    RepeatUntil,
    _strip_astrid_prefix,
    is_attested_kind,
    is_group_step,
    is_legacy_repeat_until_condition,
    iter_steps_with_path,
    load_plan,
    parse_from_ref,
    parse_repeat_until_expression,
)

__all__ = [
    "RepeatForEach",
    "RepeatUntil",
    "TaskPlan",
    "TaskPlanError",
    "_strip_astrid_prefix",
    "is_attested_kind",
    "is_group_step",
    "is_legacy_repeat_until_condition",
    "iter_steps_with_path",
    "load_plan",
    "parse_from_ref",
    "parse_repeat_until_expression",
]
