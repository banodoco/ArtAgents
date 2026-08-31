"""Shared hash helpers for Astrid core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of *path* using 1 MB chunked reads."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_digest(obj: Any) -> str:
    """Return the stable digest used by protocol identity contracts."""

    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def executor_definition_digest(executor_def: Any) -> str:
    """Digest an executor definition without consulting storage."""

    return canonical_json_digest(executor_def.to_dict())


__all__ = ["canonical_json_digest", "executor_definition_digest", "sha256_file"]
