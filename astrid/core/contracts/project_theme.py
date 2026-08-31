"""Neutral project/theme binding contracts.

The project cache may persist a theme identifier, while a runtime may inject
the resolved style directory.  These values are transport contracts only:
they do not load a theme, inspect a project, or access a store.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROJECT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_THEME_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


def validate_project_identifier(value: object) -> str:
    if not isinstance(value, str) or _PROJECT_ID_RE.fullmatch(value) is None:
        raise ValueError("project identifier must be lowercase letters/digits joined by hyphens")
    return value


def validate_theme_identifier(value: object) -> str:
    if not isinstance(value, str) or _THEME_ID_RE.fullmatch(value) is None:
        raise ValueError(
            "theme identifier must start with a lowercase letter and use lowercase letters, digits or hyphens"
        )
    return value


@dataclass(frozen=True, slots=True)
class ProjectThemeBinding:
    """The project-to-theme identifier binding supplied by a runtime."""

    project_slug: str
    theme_id: str | None = None

    def __post_init__(self) -> None:
        validate_project_identifier(self.project_slug)
        if self.theme_id is not None and (not isinstance(self.theme_id, str) or not self.theme_id):
            raise ValueError("theme_id must be a non-empty string or None")
        if self.theme_id is not None:
            validate_theme_identifier(self.theme_id)


@dataclass(frozen=True, slots=True)
class ProjectStyleSnapshot:
    """Resolved project style data injected into a scope request.

    ``theme_id`` is the portable identifier.  ``theme_dir`` is optional
    runtime-provided resolution and is never derived by this contract.
    """

    project_slug: str
    theme_id: str | None = None
    theme_dir: Path | str | None = None

    def __post_init__(self) -> None:
        validate_project_identifier(self.project_slug)
        if self.theme_id is not None and (not isinstance(self.theme_id, str) or not self.theme_id):
            raise ValueError("theme_id must be a non-empty string or None")
        if self.theme_id is not None:
            validate_theme_identifier(self.theme_id)
        if self.theme_dir is not None and not isinstance(self.theme_dir, (str, Path)):
            raise ValueError("theme_dir must be a path-like string or None")

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any], *, project_slug: str | None = None
    ) -> "ProjectStyleSnapshot":
        """Decode runtime JSON-style project style data."""
        if not isinstance(value, Mapping):
            raise ValueError("project style snapshot must be an object")
        return cls(
            project_slug=value.get("project_slug", project_slug or ""),
            theme_id=value.get("theme_id"),
            theme_dir=value.get("theme_dir"),
        )


__all__ = [
    "ProjectStyleSnapshot",
    "ProjectThemeBinding",
    "validate_project_identifier",
    "validate_theme_identifier",
]
