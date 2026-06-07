"Minimal schema constants for lineage variant sidecars."

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
