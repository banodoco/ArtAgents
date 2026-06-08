"""Migration-only loose decoders for Sprint 2 timeline container migration.

Runtime projection/import code must stay strict.  Historical compatibility for
wrapped assemblies, old full-state snapshots, old clip payloads, and no-label
``track.added`` events lives in this script-local module.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from astrid.core import timeline


class LegacyDecodeError(ValueError):
    """Raised when a historical timeline/event shape cannot be migrated."""


def _json_safe_copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise LegacyDecodeError(f"legacy payload is not JSON-serializable: {exc}") from exc


def unwrap_legacy_assembly(value: Any) -> dict[str, Any]:
    """Return an assembly dict from a raw or ``{schema_version, assembly}`` value."""
    if not isinstance(value, dict):
        raise LegacyDecodeError("legacy assembly must be a JSON object")
    if "assembly" in value or "schema_version" in value:
        inner = value.get("assembly")
        if not isinstance(inner, dict):
            raise LegacyDecodeError("legacy wrapped assembly must contain an object assembly")
        return _json_safe_copy(inner)
    return _json_safe_copy(value)


def decode_old_imported_snapshot(snapshot: Any) -> dict[str, Any]:
    """Decode historical ``timeline.imported`` snapshot payloads."""
    if not isinstance(snapshot, dict):
        raise LegacyDecodeError("timeline.imported snapshot must be an object")
    raw = snapshot.get("assembly.json", snapshot)
    return unwrap_legacy_assembly(raw)


def decode_old_recovered_snapshot(payload: Any) -> dict[str, Any]:
    """Decode historical ``timeline.recovered.projected_state_summary`` payloads."""
    if not isinstance(payload, dict):
        raise LegacyDecodeError("timeline.recovered payload must be an object")
    summary = payload.get("projected_state_summary")
    if summary is None:
        raise LegacyDecodeError("timeline.recovered payload has no projected_state_summary")
    return unwrap_legacy_assembly(summary)


def backfill_track_added_payload(payload: Any) -> dict[str, Any]:
    """Return a strict ``track.added`` payload, backfilling label from track_id.

    Historical events sometimes omitted ``label``.  Migration keeps a non-empty
    recorded label when present; otherwise it uses the exact non-empty
    ``track_id``.  Missing or empty ``track_id`` is corrupt and must stop the
    migration.
    """
    if not isinstance(payload, dict):
        raise LegacyDecodeError("track.added payload must be an object")
    track_id = payload.get("track_id")
    if not isinstance(track_id, str) or not track_id:
        raise LegacyDecodeError("track.added payload requires a non-empty track_id")
    kind = payload.get("kind")
    if kind not in {"visual", "audio"}:
        raise LegacyDecodeError("track.added payload.kind must be 'visual' or 'audio'")
    label = payload.get("label")
    if not isinstance(label, str) or not label:
        label = track_id
    return {"track_id": track_id, "kind": kind, "label": label}


def convert_old_clip_added_payload(payload: Any) -> dict[str, Any]:
    """Convert old ``clip.added`` payload data to a TimelineConfig clip draft."""
    if not isinstance(payload, dict):
        raise LegacyDecodeError("clip.added payload must be an object")
    clip_id = payload.get("clip_id")
    if not isinstance(clip_id, str) or not clip_id:
        raise LegacyDecodeError("clip.added payload requires a non-empty clip_id")
    kind = payload.get("kind")
    if kind not in {"visual", "audio", "text"}:
        raise LegacyDecodeError("clip.added payload.kind must be visual, audio, or text")
    track = payload.get("track")
    if not isinstance(track, str) or not track:
        track = kind
    clip: dict[str, Any] = {"id": clip_id, "at": 0.0, "track": track}
    if kind == "text":
        clip["clipType"] = "text"
        clip["text"] = {"content": ""}
        clip["hold"] = 0.0
    else:
        clip["clipType"] = "media"
        asset_id = payload.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            clip["asset"] = asset_id
        clip["hold"] = 0.0
    return _json_safe_copy(clip)


def convert_old_projected_clip(clip: Any) -> dict[str, Any]:
    """Convert old projected clip fields into a TimelineConfig clip draft."""
    if not isinstance(clip, dict):
        raise LegacyDecodeError("projected clip must be an object")
    clip_id = clip.get("id")
    if not isinstance(clip_id, str) or not clip_id:
        raise LegacyDecodeError("projected clip requires a non-empty id")
    kind = clip.get("kind")
    if kind not in {"visual", "audio", "text"}:
        raise LegacyDecodeError("projected clip.kind must be visual, audio, or text")
    track = clip.get("track")
    if not isinstance(track, str) or not track:
        track = kind
    start = clip.get("start", clip.get("at", 0.0))
    duration = clip.get("duration", clip.get("hold", 0.0))
    if isinstance(start, bool) or not isinstance(start, (int, float)):
        raise LegacyDecodeError("projected clip.start must be numeric")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise LegacyDecodeError("projected clip.duration must be numeric")
    converted: dict[str, Any] = {
        "id": clip_id,
        "at": float(start),
        "track": track,
        "clipType": "text" if kind == "text" else "media",
        "hold": float(duration),
    }
    asset_id = clip.get("asset_id")
    if isinstance(asset_id, str) and asset_id:
        converted["asset"] = asset_id
    text = clip.get("text")
    if kind == "text" or isinstance(text, str):
        converted["text"] = {"content": text if isinstance(text, str) else ""}
    return _json_safe_copy(converted)


def convert_legacy_arrangement_replaced_payload(payload: Any) -> dict[str, Any]:
    """Convert historical ``arrangement.replaced`` payloads to raw TimelineConfig.

    Some managed writers already stored a renderable TimelineConfig under the
    old ``arrangement`` key.  Those are preserved exactly through the shared
    container validator.  Older arrangement-read-model payloads have no lossless
    renderable container representation, so migration uses the canonical empty
    TimelineConfig and later migration steps can attach read-model history
    separately.
    """
    if not isinstance(payload, dict):
        raise LegacyDecodeError("arrangement.replaced payload must be an object")
    arrangement = payload.get("arrangement")
    if not isinstance(arrangement, dict):
        raise LegacyDecodeError("arrangement.replaced payload.arrangement must be an object")
    candidate = copy.deepcopy(arrangement)
    try:
        return timeline.validate_timeline_config_for_container(candidate)
    except ValueError:
        return timeline.canonical_empty_timeline()
