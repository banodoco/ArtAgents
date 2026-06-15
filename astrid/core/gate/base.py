"""Stable leaf-type aliases for task gate errors and decisions."""

from astrid.core.task.gate.base import (
    GateArtifactIdentity,
    GateDecision,
    InlineCheckResult,
    ITERATE_FEEDBACK_PREFIX,
    TaskRunGateError,
    _reject,
)

__all__ = [
    "GateArtifactIdentity",
    "GateDecision",
    "InlineCheckResult",
    "ITERATE_FEEDBACK_PREFIX",
    "TaskRunGateError",
    "_reject",
]
