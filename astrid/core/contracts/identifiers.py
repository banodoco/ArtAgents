"""Store-free identifiers shared by project and timeline contracts.

This module deliberately contains only validation rules.  Filesystem path
construction and timeline authority remain owned by their respective domain
modules; importing these validators must never import a project, timeline, or
store implementation.
"""

from __future__ import annotations

import re

from astrid.core.foundation.project_paths import ProjectPathError
from astrid.core.ids import is_ulid

_TIMELINE_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class IdentifierValidationError(ProjectPathError):
    """Raised when a shared identifier is not in its canonical form."""


def validate_timeline_slug(slug: object) -> str:
    """Validate and return a canonical timeline slug."""
    if not isinstance(slug, str) or _TIMELINE_SLUG_RE.fullmatch(slug) is None:
        raise IdentifierValidationError(
            "timeline slug must start with a lowercase letter, contain only "
            "lowercase letters, digits or '-', and be 1–32 characters long"
        )
    return slug


def validate_timeline_ulid(ulid: object) -> str:
    """Validate and return a lowercase or historical uppercase timeline ULID."""
    if not is_ulid(ulid):
        raise IdentifierValidationError("timeline ULID must be a 26-character Crockford ULID")
    return str(ulid)


__all__ = [
    "IdentifierValidationError",
    "validate_timeline_slug",
    "validate_timeline_ulid",
]
