"""Identifier validation for project timeline theme metadata.

The project schema may retain a portable theme label for authored timeline
compatibility.  This module deliberately contains no path, directory, or
theme-resolution authority; renderers consume a runtime document instead.
"""

from __future__ import annotations

import re

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def validate_project_identifier(value: object) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            "project identifier must start with a lowercase letter and use lowercase letters, digits or hyphens"
        )
    return value


def validate_theme_identifier(value: object) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            "theme identifier must start with a lowercase letter and use lowercase letters, digits or hyphens"
        )
    return value


__all__ = ["validate_project_identifier", "validate_theme_identifier"]
