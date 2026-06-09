"""Shared helpers for understanding executors (dry-run, etc.)."""

from __future__ import annotations

import json
from typing import Any


def emit_dry_run_preview(preview: dict[str, Any], kind: str) -> int:
    """Set schema_version/kind on a preview dict, print as JSON, return 0."""
    preview["schema_version"] = 1
    preview["kind"] = kind
    print(json.dumps(preview, indent=2))
    return 0
