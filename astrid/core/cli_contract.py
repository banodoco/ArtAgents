"""Stable non-task home for shared CLI JSON/error rendering helpers.

Release N keeps ``astrid.core.task.cli_contract`` as the implementation and
fallback surface. This module provides the long-lived import path for
non-task consumers while the behavioral core is being retired.
"""

from astrid.core.task.cli_contract import (
    astrid_argument_error_to_error,
    emit_json_object,
    emit_lifecycle_json,
    exit_with_argument_error,
    exit_with_astrid_error,
    shape_lifecycle_payload,
)

__all__ = [
    "astrid_argument_error_to_error",
    "emit_json_object",
    "emit_lifecycle_json",
    "exit_with_argument_error",
    "exit_with_astrid_error",
    "shape_lifecycle_payload",
]
