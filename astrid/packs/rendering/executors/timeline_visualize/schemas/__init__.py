"""Versioned machine-artifact schemas for timeline visualization.

The eight entries are independently versioned even though they currently all
start at version 1.  ``_defs.json`` is shared schema infrastructure and is not
itself an emitted artifact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA_ROOT = Path(__file__).resolve().parent


def _reject_nonstandard_constant(token: str) -> None:
    raise ValueError(f"non-standard JSON constant {token} is not allowed")


@dataclass(frozen=True, slots=True)
class Schema:
    """Descriptor for one emitted artifact's JSON Schema contract."""

    name: str
    filename: str
    version: int

    @property
    def path(self) -> Path:
        return _SCHEMA_ROOT / self.filename

    def load(self) -> dict[str, Any]:
        document = json.loads(
            self.path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_constant,
        )
        if not isinstance(document, dict):
            raise ValueError(f"schema {self.filename} must contain a JSON object")
        return document


SCHEMAS: dict[str, Schema] = {
    name: Schema(name=name, filename=f"{name}.json", version=1)
    for name in (
        "manifest",
        "ground-truth",
        "view-map",
        "action-index",
        "asset-index",
        "transcript-index",
        "diagnostics",
        "metric-definitions",
    )
}

DEFS_PATH = _SCHEMA_ROOT / "_defs.json"


__all__ = ["DEFS_PATH", "SCHEMAS", "Schema"]
