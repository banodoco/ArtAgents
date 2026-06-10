"""Shared helpers for the agent-facing task CLI contract.

This module stays intentionally small: it shapes the common lifecycle JSON
fields, emits exactly one newline-terminated JSON object, and adapts
``AstridArgumentError`` into the canonical ``AstridError`` envelope.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from astrid.core.cli_choices import AstridArgumentError
from astrid.core.contracts.errors import AstridError, build_state_snapshot, render_astrid_error

_LIFECYCLE_FIELD_DEFAULTS: dict[str, Any] = {
    "schema_version": 1,
    "project": None,
    "run_id": None,
    "state": "",
}


def shape_lifecycle_payload(
    *,
    project: str | None,
    run_id: str | None,
    state: str,
    **fields: Any,
) -> dict[str, Any]:
    """Return a payload with the shared lifecycle fields first."""

    payload = dict(_LIFECYCLE_FIELD_DEFAULTS)
    payload["project"] = project
    payload["run_id"] = run_id
    payload["state"] = state
    payload.update(fields)
    return payload


def emit_json_object(payload: dict[str, Any], *, stream: TextIO | None = None) -> int:
    """Write exactly one JSON object plus one trailing newline."""

    target = stream or sys.stdout
    target.write(json.dumps(payload, sort_keys=True))
    target.write("\n")
    return 0


def emit_lifecycle_json(
    *,
    project: str | None,
    run_id: str | None,
    state: str,
    stream: TextIO | None = None,
    **fields: Any,
) -> int:
    """Shape and emit a lifecycle JSON payload."""

    return emit_json_object(
        shape_lifecycle_payload(
            project=project,
            run_id=run_id,
            state=state,
            **fields,
        ),
        stream=stream,
    )


def astrid_argument_error_to_error(
    error: AstridArgumentError,
    *,
    recovery_command: str = "",
    state_snapshot: object | None = None,
) -> AstridError:
    """Convert a recoverable parser failure into the canonical envelope."""

    snapshot = build_state_snapshot(
        state_snapshot,
        argument_name=error.argument_name,
        invalid_value=error.invalid_value,
        catalog=error.catalog,
    )
    return AstridError(
        error.message,
        valid_options=error.valid_options,
        recovery_command=recovery_command,
        state_snapshot=snapshot,
        source_type=type(error).__name__,
    )


def exit_with_astrid_error(error: AstridError) -> int:
    """Delegate envelope rendering to the shared renderer."""

    return render_astrid_error(error)


def exit_with_argument_error(
    error: AstridArgumentError,
    *,
    recovery_command: str = "",
    state_snapshot: object | None = None,
) -> int:
    """Render a recoverable parser failure via the shared Astrid renderer."""

    return exit_with_astrid_error(
        astrid_argument_error_to_error(
            error,
            recovery_command=recovery_command,
            state_snapshot=state_snapshot,
        )
    )


__all__ = [
    "astrid_argument_error_to_error",
    "emit_json_object",
    "emit_lifecycle_json",
    "exit_with_argument_error",
    "exit_with_astrid_error",
    "shape_lifecycle_payload",
]
