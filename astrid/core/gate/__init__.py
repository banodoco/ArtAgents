"""Stable non-task home for gateway-facing task gate primitives.

Release N keeps ``astrid.core.task.gate`` as the implementation and fallback
surface. This package provides the long-lived import path that gateway and
other non-task consumers can target while the behavioral core is being retired.
"""

from astrid.core.task.gate import (
    AttestedArgs,
    CursorPath,
    GateArtifactIdentity,
    GateDecision,
    PeekResult,
    TaskRunGateError,
    command_for_argv,
    derive_cursor,
    gate_command,
    match_attested_command,
    peek_current_step,
    record_dispatch_complete,
    record_nested_entered,
    record_nested_exited,
    validate_attested_identity,
    write_iteration_feedback,
)

__all__ = [
    "AttestedArgs",
    "CursorPath",
    "GateArtifactIdentity",
    "GateDecision",
    "PeekResult",
    "TaskRunGateError",
    "command_for_argv",
    "derive_cursor",
    "gate_command",
    "match_attested_command",
    "peek_current_step",
    "record_dispatch_complete",
    "record_nested_entered",
    "record_nested_exited",
    "validate_attested_identity",
    "write_iteration_feedback",
]
