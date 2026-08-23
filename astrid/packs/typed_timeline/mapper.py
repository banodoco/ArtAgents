from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .frames import frame_to_sec, ms_to_frame

MAX_TIMELINE_DURATION_SEC = 600.0
MAX_CANVAS_DIMENSION = 8_192
_HEX_COLOUR_RE = re.compile(r"^#[0-9A-F]{6}$")


def _get_dotted(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _resolve_value(
    row: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    spec: Any,
    *,
    fps: float,
    total_duration_sec: float,
) -> Any:
    if spec is None:
        return None
    if isinstance(spec, dict):
        if "const" in spec:
            return spec["const"]
        if "first" in spec:
            p = spec["first"]
            if rows:
                return _get_dotted(rows[0], str(p))
            return None
        if "path" in spec:
            return _get_dotted(row, str(spec["path"]))
        if "ms_to_frame" in spec:
            v = _get_dotted(row, str(spec["ms_to_frame"]))
            if v is None:
                return None
            try:
                return ms_to_frame(int(v), fps)
            except (TypeError, ValueError, OverflowError):
                return None
        if "$total_duration_sec" in spec:
            return total_duration_sec
        # prefer/fallback composite for frame
        if "prefer" in spec or "fallback" in spec:
            prefer = spec.get("prefer")
            if prefer is not None:
                pv = _get_dotted(row, str(prefer))
                if pv is not None:
                    try:
                        # if it's already a frame number
                        return int(pv)
                    except (TypeError, ValueError, OverflowError):
                        return pv
            fallback = spec.get("fallback")
            if fallback is not None:
                return _resolve_value(row, rows, fallback, fps=fps, total_duration_sec=total_duration_sec)
            return None
        # generic dict recursion not expected
        return spec
    if isinstance(spec, str):
        if spec == "$total_duration_sec":
            return total_duration_sec
        # dotted path shorthand?
        if "." in spec or spec in row:
            got = _get_dotted(row, spec)
            if got is not None:
                return got
        return spec
    return spec


class TypedDataTimelineMapper:
    def __init__(
        self,
        rows: Sequence[Mapping[str, Any]],
        mapping: Mapping[str, Any] | Path | str,
    ) -> None:
        if isinstance(mapping, (str, Path)):
            from .common import resolve_mapping_path

            p = resolve_mapping_path(mapping)
            raw = yaml.safe_load(p.read_text(encoding="utf-8"))
            self.mapping = raw
        else:
            self.mapping = dict(mapping)
        if self.mapping.get("schema_version", 1) != 1:
            raise ValueError("typed timeline mapping schema_version must be 1")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise ValueError("typed timeline rows must be an array")
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"typed timeline rows[{index}] must be an object")
        # normalize rows sorted by ordinal when present
        self.rows = sorted(list(rows), key=lambda r: (int(r.get("ordinal", 0)) if isinstance(r.get("ordinal"), int) else 0, str(r.get("id", ""))))
        # canvas — single canonical path
        canvas = self.mapping.get("canvas", {}) if isinstance(self.mapping.get("canvas"), Mapping) else {}
        self.fps = int(canvas.get("fps", 48))
        if not 1 <= self.fps <= 240:
            raise ValueError(f"mapping fps must be between 1 and 240, got {self.fps}")
        if "total_frames" in canvas:
            self.total_frames = int(canvas["total_frames"])
            self.total_duration_sec = self.total_frames / float(self.fps)
        elif "total_duration_sec" in canvas:
            self.total_duration_sec = float(canvas["total_duration_sec"])
            self.total_frames = int(round(self.total_duration_sec * self.fps))
        elif "total_duration" in canvas:
            self.total_duration_sec = float(canvas["total_duration"])
            self.total_frames = int(round(self.total_duration_sec * self.fps))
        elif "total_frames" in self.mapping:
            self.total_frames = int(self.mapping["total_frames"])
            self.total_duration_sec = self.total_frames / float(self.fps)
        elif "total_duration_sec" in self.mapping:
            self.total_duration_sec = float(self.mapping["total_duration_sec"])  # type: ignore[arg-type]
            self.total_frames = int(round(self.total_duration_sec * self.fps))
        else:
            self.total_frames = 8085
            self.total_duration_sec = self.total_frames / float(self.fps)
        if self.total_frames <= 0 or not 0 < self.total_duration_sec <= MAX_TIMELINE_DURATION_SEC:
            raise ValueError(
                "mapping duration must be positive and no longer than "
                f"{MAX_TIMELINE_DURATION_SEC:g} seconds"
            )
    def _frame_for_row(self, row: Mapping[str, Any]) -> int | None:
        # prefer metadata.frame else ms_to_frame(start_ms)
        meta = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        frame_val = None
        if isinstance(meta, Mapping):
            frame_val = meta.get("frame")
            if frame_val is None:
                frame_val = meta.get("colour_frame") or meta.get("color_frame")
        if frame_val is not None:
            try:
                return int(frame_val)
            except (TypeError, ValueError, OverflowError):
                pass
        # also try top-level metadata.* dotted path "metadata.frame"
        dotted = _get_dotted(row, "metadata.frame")
        if dotted is not None:
            try:
                return int(dotted)
            except (TypeError, ValueError, OverflowError):
                pass
        # fallback ms_to_frame
        start_ms = row.get("start_ms")
        if start_ms is not None:
            try:
                return ms_to_frame(int(start_ms), self.fps)
            except (TypeError, ValueError, OverflowError):
                return None
        return None

    def to_timeline(self) -> dict[str, Any]:
        scope = self.mapping.get("scope", "aggregated")
        # tracks
        tracks = self.mapping.get("tracks")
        if tracks is None:
            # default per mapping type
            if scope == "aggregated":
                tracks = [
                    {"id": "colour", "kind": "visual", "label": "Colour"},
                    {"id": "audio", "kind": "audio", "label": "Audio"},
                ]
            else:
                tracks = [
                    {"id": "v", "kind": "visual", "label": "Visual"},
                    {"id": "overlay", "kind": "visual", "label": "Overlay"},
                ]
        canvas = self.mapping.get("canvas", {})
        width = int(canvas.get("width", 1280))
        height = int(canvas.get("height", 720))
        if not 1 <= width <= MAX_CANVAS_DIMENSION or not 1 <= height <= MAX_CANVAS_DIMENSION:
            raise ValueError(
                f"canvas dimensions must be between 1 and {MAX_CANVAS_DIMENSION}"
            )
        theme_overrides = {"visual": {"canvas": {"width": width, "height": height, "fps": self.fps}}}

        clips: list[dict[str, Any]] = []

        if scope == "aggregated":
            # single effect clip covering whole duration
            clip_cfg = self.mapping.get("clip", {})
            clip_id = clip_cfg.get("id", "colour_map")
            track = clip_cfg.get("track", "colour")
            clip_type = clip_cfg.get("clipType", "audio-reactive-colour")
            if clip_type == "audio-reactive-colour":
                # declarative spec from YAML — honor clip.events if present, else hard-coded fallback
                events_cfg = clip_cfg.get("events") if isinstance(clip_cfg.get("events"), Mapping) else None
                frame_spec = events_cfg.get("frame") if isinstance(events_cfg, Mapping) else None
                color_spec = None
                if isinstance(events_cfg, Mapping):
                    color_spec = events_cfg.get("color") if "color" in events_cfg else events_cfg.get("colour")
                id_spec = events_cfg.get("id") if isinstance(events_cfg, Mapping) else None
                events: list[dict[str, Any]] = []
                for row in self.rows:
                    # frame: YAML spec via _resolve_value, fallback to _frame_for_row
                    if frame_spec is not None:
                        raw_frame = _resolve_value(row, self.rows, frame_spec, fps=float(self.fps), total_duration_sec=self.total_duration_sec)
                        try:
                            frame = int(raw_frame) if raw_frame is not None else None
                        except (TypeError, ValueError, OverflowError):
                            frame = None
                    else:
                        frame = self._frame_for_row(row)
                    if frame is None:
                        raise ValueError("every aggregated row must resolve to a frame")
                    if frame <= 0 or frame >= self.total_frames:
                        raise ValueError(
                            f"event frame {frame} must be positive and below {self.total_frames}"
                        )
                    # color: YAML color.path/spec, fallback to hard-coded multi-path
                    if color_spec is not None:
                        color = _resolve_value(row, self.rows, color_spec, fps=float(self.fps), total_duration_sec=self.total_duration_sec)
                    else:
                        color = _get_dotted(row, "metadata.colour_hex")
                        if color is None:
                            color = _get_dotted(row, "metadata.color_hex")
                        if color is None:
                            color = _get_dotted(row, "metadata.colour")
                        if color is None:
                            color = _get_dotted(row, "color")
                    if not isinstance(color, str):
                        raise ValueError(f"event at frame {frame} has no colour")
                    color = color.upper()
                    if _HEX_COLOUR_RE.fullmatch(color) is None:
                        raise ValueError(
                            f"event at frame {frame} colour must be #RRGGBB"
                        )
                    # id: YAML id.path/spec, fallback to row id/ordinal
                    if id_spec is not None:
                        raw_id = _resolve_value(row, self.rows, id_spec, fps=float(self.fps), total_duration_sec=self.total_duration_sec)
                        fallback_id = row.get("id")
                        if fallback_id in (None, ""):
                            fallback_id = row.get("ordinal")
                        eid = str(raw_id) if raw_id not in (None, "") else str(
                            fallback_id if fallback_id not in (None, "") else f"e{frame}"
                        )
                    else:
                        fallback_id = row.get("id")
                        if fallback_id in (None, ""):
                            fallback_id = row.get("ordinal")
                        eid = str(
                            fallback_id if fallback_id not in (None, "") else f"e{frame}"
                        )
                    if not eid:
                        raise ValueError(f"event at frame {frame} has an empty id")
                    events.append({"id": eid, "frame": int(frame), "color": color})
                events.sort(key=lambda e: e["frame"])
                frames = [event["frame"] for event in events]
                if len(frames) != len(set(frames)):
                    raise ValueError("aggregated event frames must be unique")
                ids = [event["id"] for event in events]
                if len(ids) != len(set(ids)):
                    raise ValueError("aggregated event ids must be unique")
                initial = clip_cfg.get("initialColor") or self.mapping.get("initialColor") or "#16B09B"
                if isinstance(initial, dict) and "const" in initial:
                    initial = initial["const"]
                initial = str(initial).upper()
                hold = self.total_duration_sec
                clips.append(
                    {
                        "id": clip_id,
                        "at": 0,
                        "track": track,
                        "clipType": clip_type,
                        "hold": hold,
                        "params": {
                            "schemaVersion": 1,
                            "initialColor": initial,
                            "events": events,
                        },
                    }
                )
                # audio clip required for fast path
                audio_cfg = self.mapping.get("audio_clip", {})
                clips.append(
                    {
                        "id": audio_cfg.get("id", "source_audio"),
                        "at": 0,
                        "track": audio_cfg.get("track", "audio"),
                        "clipType": "media",
                        "asset": audio_cfg.get("asset", "audio"),
                        "from": 0,
                        "to": self.total_duration_sec,
                    }
                )
            else:
                # generic aggregated text?
                hold = self.total_duration_sec
                clips.append({"id": clip_id, "at": 0, "track": track, "clipType": clip_type, "hold": hold, "params": clip_cfg.get("params", {})})
                clips.append({"id": "source_audio", "at": 0, "track": "audio", "clipType": "media", "asset": "audio", "from": 0, "to": self.total_duration_sec})
        else:
            # per-row: one clip per row
            clip_cfg = self.mapping.get("clip", {})
            track = clip_cfg.get("track", "overlay")
            clip_type = clip_cfg.get("clipType", "text-card")
            params_map = clip_cfg.get("params", {}) or clip_cfg.get("paramMapper", {})
            for idx, row in enumerate(self.rows):
                frame = self._frame_for_row(row)
                at_sec = frame_to_sec(frame, self.fps) if frame is not None else (float(row.get("start_ms", 0)) / 1000.0)
                # hold from duration_ms if available else 1 sec
                hold = 1.0
                if "duration_ms" in row:
                    try:
                        hold = float(int(row["duration_ms"])) / 1000.0
                    except (TypeError, ValueError, OverflowError):
                        pass
                exact_remaining = self.total_duration_sec - float(at_sec)
                if 0 < exact_remaining < hold and hold - exact_remaining <= 0.001:
                    hold = exact_remaining
                # start/duration milliseconds are independently rounded from
                # frame values, so their reconstructed end may differ from
                # the exact frame boundary by at most one millisecond.
                if at_sec < 0 or hold <= 0 or at_sec + hold > self.total_duration_sec + 0.001:
                    raise ValueError(
                        f"row {idx} clip range [{at_sec}, {at_sec + hold}) escapes timeline duration"
                    )
                # resolve params via dotted paths + builtins
                params: dict[str, Any] = {}
                for k, v in params_map.items():
                    if isinstance(v, dict) and ("path" in v or "const" in v or "ms_to_frame" in v or "first" in v or "$total_duration_sec" in v):
                        resolved = _resolve_value(row, self.rows, v, fps=float(self.fps), total_duration_sec=self.total_duration_sec)
                        params[k] = resolved
                    elif isinstance(v, str) and v == "$total_duration_sec":
                        params[k] = self.total_duration_sec
                    elif isinstance(v, str) and ("." in v or v in row):
                        got = _get_dotted(row, v)
                        params[k] = got if got is not None else v
                    else:
                        params[k] = v
                # special: if content not resolved and clip is text-card, pull prompt
                if "content" not in params and clip_type == "text-card":
                    params["content"] = str(row.get("prompt", f"row {idx}"))
                # overlay track first => ensure at is overlay? track already overlay
                identity = row.get("id")
                if identity in (None, ""):
                    identity = row.get("ordinal", idx)
                clip_id = f"row_{idx}_{identity}"
                clips.append(
                    {
                        "id": clip_id,
                        "at": float(at_sec),
                        "track": track,
                        "clipType": clip_type,
                        "hold": float(hold),
                        "params": params,
                    }
                )

        timeline: dict[str, Any] = {
            "theme": self.mapping.get("theme", "banodoco-default"),
            "theme_overrides": theme_overrides,
            "tracks": tracks,
            "clips": clips,
        }
        # include hard_cut transition if requested
        if self.mapping.get("transition") == "hard_cut":
            # no explicit transition needed for audio-reactive path; keep timeline clean for fast path
            pass
        return timeline

    def to_assets(self) -> dict[str, Any]:
        assets_cfg = self.mapping.get("assets", {})
        if assets_cfg:
            return {"assets": assets_cfg}
        # default for aggregated: single audio asset placeholder
        return {"assets": {"audio": {"file": "tone.wav", "type": "audio/wav", "duration": self.total_duration_sec}}}

    def hash(self) -> str:
        canonical = json.dumps(self.to_timeline(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
