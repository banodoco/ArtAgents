"""Pure project identifiers and wire-schema validators.

Project metadata is persisted by the workspace runtime.  This package does
not create, read, or mutate a project tree.
"""

from astrid.core.foundation.project_paths import (
    validate_project_slug,
    validate_run_id,
    validate_source_id,
)

from .schema import (
    build_project,
    build_source,
    validate_project,
    validate_source,
    validate_source_kind,
)

__all__ = [
    "build_project",
    "build_source",
    "validate_project_slug",
    "validate_run_id",
    "validate_source_id",
    "validate_source",
    "validate_source_kind",
    "validate_project",
]
