from __future__ import annotations

import json
import struct
import wave
from pathlib import Path
from typing import Any, Mapping


def ensure_tone_wav(path: Path, duration_sec: float) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 48000
    n_frames = int(sample_rate * float(duration_sec))
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<h", 0) * n_frames)


def resolve_mapping_path(mapping: str | Path) -> Path:
    p = Path(mapping)
    if p.exists():
        return p
    base = Path(__file__).parent / "mappings"
    cand = base / f"{str(mapping)}.yaml"
    if cand.exists():
        return cand
    cand2 = base / str(mapping)
    if cand2.exists():
        return cand2
    return p


def parse_json_rows(raw: str | Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    parsed: Any = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(parsed, list):
        return [dict(r) if isinstance(r, Mapping) else {"value": r} for r in parsed]
    if isinstance(parsed, dict) and "rows" in parsed and isinstance(parsed["rows"], list):
        return [dict(r) if isinstance(r, Mapping) else {"value": r} for r in parsed["rows"]]
    if isinstance(parsed, dict):
        return [dict(parsed)]
    return [dict(parsed)] if isinstance(parsed, Mapping) else []
