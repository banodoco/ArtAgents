from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

MAX_ROWS_ARTIFACT_BYTES = 8 * 1024 * 1024


def load_json_rows(path: Path | str) -> list[dict[str, Any]]:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise ValueError(f"rows artifact does not exist: {p}")
    if p.stat().st_size > MAX_ROWS_ARTIFACT_BYTES:
        raise ValueError(f"rows artifact exceeds {MAX_ROWS_ARTIFACT_BYTES} bytes: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # support {rows: []} or {transitions: []} or {resolved_events: []}
        for key in ("rows", "transitions", "items", "resolved_events"):
            if key in data and isinstance(data[key], list):
                return [dict(r) if isinstance(r, Mapping) else {"value": r} for r in data[key]]
        # single object -> one row
        return [dict(data)]
    if isinstance(data, list):
        return [dict(r) if isinstance(r, Mapping) else {"value": r} for r in data]
    raise ValueError(f"unsupported JSON shape at {p}")


__all__ = ["MAX_ROWS_ARTIFACT_BYTES", "load_json_rows"]
