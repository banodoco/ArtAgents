from __future__ import annotations

import copy
import json
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .timeline_model import (
    Arrangement,
    AssetRegistry,
    ClipClassifiedKind,
    PipelineMetadata,
    Pool,
    ThemeOverrides,
    TimelineClip,
    TimelineConfig,
    TimelineOutput,
    TrackDefinition,
    _effect_ids,
    validate_arrangement,
    validate_metadata,
    validate_pool,
    validate_registry,
    validate_timeline,
)


def _write_json(path: Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _swap_from_load(clip: dict[str, Any]) -> dict[str, Any]:
    if "from" in clip:
        clip["from_"] = clip.pop("from")
    return clip


def _swap_from_dump(clip: dict[str, Any]) -> dict[str, Any]:
    out = dict(clip)
    if "from_" in out:
        out["from"] = out.pop("from_")
    return out


def _round_at_for_dump(clip: dict[str, Any]) -> dict[str, Any]:
    if "at" in clip and isinstance(clip["at"], (int, float)):
        clip["at"] = round(float(clip["at"]), 3)
    return clip

def _asset_entry_for_clip(
    clip: Mapping[str, Any],
    registry: AssetRegistry | Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    asset_key = clip.get("asset")
    if not isinstance(asset_key, str) or not isinstance(registry, Mapping):
        return None
    assets = registry.get("assets")
    if not isinstance(assets, Mapping):
        return None
    entry = assets.get(asset_key)
    return entry if isinstance(entry, Mapping) else None


def _asset_kind_from_entry(entry: Mapping[str, Any] | None) -> ClipClassifiedKind | None:
    if not isinstance(entry, Mapping):
        return None
    raw_type = entry.get("type")
    if isinstance(raw_type, str):
        normalized = raw_type.lower()
        if normalized in {"video", "image", "audio"}:
            return ClipClassifiedKind(normalized)
        if normalized.startswith("video/"):
            return ClipClassifiedKind.VIDEO
        if normalized.startswith("image/"):
            return ClipClassifiedKind.IMAGE
        if normalized.startswith("audio/"):
            return ClipClassifiedKind.AUDIO
    for key in ("mime", "mimeType", "contentType"):
        mime = entry.get(key)
        if not isinstance(mime, str):
            continue
        normalized = mime.lower()
        if normalized.startswith("video/"):
            return ClipClassifiedKind.VIDEO
        if normalized.startswith("image/"):
            return ClipClassifiedKind.IMAGE
        if normalized.startswith("audio/"):
            return ClipClassifiedKind.AUDIO
    return None


def _classify_clip(
    clip: Mapping[str, Any],
    registry: AssetRegistry | Mapping[str, Any] | None = None,
    *,
    theme: str | None = None,
) -> ClipClassifiedKind:
    clip_type = clip.get("clipType", "media")
    if clip_type == "text":
        return ClipClassifiedKind.TEXT
    if clip_type == "media":
        return _asset_kind_from_entry(_asset_entry_for_clip(clip, registry)) or ClipClassifiedKind.OPAQUE
    if clip_type in {"hold"}:
        return _asset_kind_from_entry(_asset_entry_for_clip(clip, registry)) or ClipClassifiedKind.VIDEO
    if clip_type == "effect-layer":
        return ClipClassifiedKind.EFFECT
    if isinstance(clip_type, str) and clip_type in _effect_ids(theme):
        return ClipClassifiedKind.EFFECT
    return ClipClassifiedKind.OPAQUE


@dataclass(frozen=True)
class TimelineClipView:
    data: Mapping[str, Any]
    registry: AssetRegistry | Mapping[str, Any] | None = None
    theme: str | None = None

    @property
    def classified_kind(self) -> ClipClassifiedKind:
        return _classify_clip(self.data, self.registry, theme=self.theme)


class TimelineRenderView:
    def __init__(self, timeline: "Timeline", *, default_theme: str) -> None:
        self._timeline = timeline
        self._default_theme = default_theme

    @property
    def theme(self) -> str:
        return self._timeline.theme or self._default_theme

    @property
    def clips(self) -> list[TimelineClip]:
        return self._timeline.clips

    @property
    def tracks(self) -> list[TrackDefinition]:
        return self._timeline.tracks

    def to_json_data(self) -> dict[str, Any]:
        payload = self._timeline.to_json_data()
        payload.setdefault("theme", self._default_theme)
        return payload


class Timeline:
    """Persisted timeline JSON with top-level passthrough fields preserved."""

    def __init__(self, config: Mapping[str, Any], *, validate: bool = True) -> None:
        data = copy.deepcopy(dict(config))
        if validate:
            validate_timeline(data)
        self._data = data

    @classmethod
    def from_json_data(cls, payload: Mapping[str, Any], *, validate: bool = True) -> "Timeline":
        data = copy.deepcopy(dict(payload))
        clips = data.get("clips")
        if isinstance(clips, list):
            data["clips"] = [
                _swap_from_load(dict(clip)) if isinstance(clip, dict) else clip
                for clip in clips
            ]
        return cls(data, validate=validate)

    @classmethod
    def load(cls, path: Path, *, validate: bool = True) -> "Timeline":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Timeline must be a JSON object")
        return cls.from_json_data(data, validate=validate)

    @classmethod
    def from_config(cls, config: Mapping[str, Any], *, validate: bool = True) -> "Timeline":
        return cls(config, validate=validate)

    @property
    def theme(self) -> str | None:
        theme = self._data.get("theme")
        return theme if isinstance(theme, str) else None

    @property
    def clips(self) -> list[TimelineClip]:
        # setdefault returns the dict's `Any` value type because TimelineConfig
        # is a `total=False` TypedDict; the cast names the validated shape.
        return cast(list[TimelineClip], self._data.setdefault("clips", []))

    @property
    def tracks(self) -> list[TrackDefinition]:
        return cast(list[TrackDefinition], self._data.setdefault("tracks", []))

    @property
    def theme_overrides(self) -> ThemeOverrides | None:
        value = self._data.get("theme_overrides")
        return cast(ThemeOverrides, value) if isinstance(value, dict) else None

    @property
    def generation_defaults(self) -> dict[str, Any] | None:
        value = self._data.get("generation_defaults")
        return value if isinstance(value, dict) else None

    @property
    def pinnedShotGroups(self) -> list[dict[str, Any]] | None:
        value = self._data.get("pinnedShotGroups")
        return value if isinstance(value, list) else None

    @property
    def output(self) -> TimelineOutput | None:
        value = self._data.get("output")
        return cast(TimelineOutput, value) if isinstance(value, dict) else None

    def classified_clips(
        self,
        registry: AssetRegistry | Mapping[str, Any] | None = None,
    ) -> list[TimelineClipView]:
        return [
            TimelineClipView(clip, registry=registry, theme=self.theme)
            for clip in self.clips
            if isinstance(clip, Mapping)
        ]

    def for_render(self, default_theme: str = "banodoco-default") -> TimelineRenderView:
        if not isinstance(default_theme, str) or not default_theme:
            raise ValueError("default_theme must be a non-empty slug")
        return TimelineRenderView(self, default_theme=default_theme)

    def to_config(self) -> TimelineConfig:
        return cast(TimelineConfig, copy.deepcopy(self._data))

    def to_json_data(self) -> dict[str, Any]:
        payload = copy.deepcopy(self._data)
        clips = payload.get("clips")
        if isinstance(clips, list):
            payload["clips"] = [
                _round_at_for_dump(_swap_from_dump(dict(clip))) if isinstance(clip, dict) else clip
                for clip in clips
            ]
        validate_timeline(payload)
        return payload

    def dump(self, path: Path) -> None:
        _write_json(path, self.to_json_data())

def merge_generation(
    theme_generation: dict[str, Any] | None,
    per_clip: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge per-clip generation atop the resolved theme.generation block.

    Per-clip keys win on conflict. Lists (references, assets) are replaced wholesale,
    not merged. Returns an empty dict if both inputs are empty/None.
    """
    merged: dict[str, Any] = {}
    if isinstance(theme_generation, dict):
        merged.update(theme_generation)
    if isinstance(per_clip, dict):
        merged.update(per_clip)
    return merged


def _deep_merge_theme(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge overlay onto base for theme blocks.

    Top-level theme keys (visual, generation, voice, audio, pacing) are merged at one
    level deep. Nested dicts inside (e.g. visual.canvas) are merged key-by-key. Lists
    such as generation.references and generation.assets are replaced wholesale.
    """
    result: dict[str, Any] = {key: value for key, value in base.items()}
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            merged_block: dict[str, Any] = dict(result[key])
            for sub_key, sub_value in value.items():
                if (
                    sub_key in merged_block
                    and isinstance(merged_block[sub_key], dict)
                    and isinstance(sub_value, dict)
                ):
                    inner = dict(merged_block[sub_key])
                    inner.update(sub_value)
                    merged_block[sub_key] = inner
                else:
                    merged_block[sub_key] = sub_value
            result[key] = merged_block
        else:
            result[key] = value
    return result


def resolve_timeline_theme(timeline: "TimelineConfig", themes_root: Path) -> dict[str, Any]:
    """Return the merged theme view: theme.json + timeline.theme_overrides.

    `timeline['theme']` is a slug resolved against `<themes_root>/<slug>/theme.json`.
    Overrides are deep-merged onto the loaded theme; list-valued fields (references,
    assets) are replaced wholesale by the override.
    """
    slug = timeline.get("theme") if isinstance(timeline, dict) else None
    if not isinstance(slug, str) or not slug:
        raise ValueError("Timeline.theme must be a non-empty slug")
    theme_path = Path(themes_root) / slug / "theme.json"
    if not theme_path.is_file():
        raise FileNotFoundError(f"Theme {slug!r} not found at {theme_path}")
    base = json.loads(theme_path.read_text(encoding="utf-8"))
    if not isinstance(base, dict):
        raise ValueError(f"Theme file {theme_path} must contain a JSON object")
    overrides = timeline.get("theme_overrides") if isinstance(timeline, dict) else None
    if isinstance(overrides, dict) and overrides:
        return _deep_merge_theme(base, overrides)
    return base

def load_timeline(path: Path) -> TimelineConfig:
    return Timeline.load(path).to_config()

def save_timeline(config: TimelineConfig, path: Path) -> None:
    Timeline.from_config(config).dump(path)

def load_registry(path: Path) -> AssetRegistry:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_registry(data)
    return cast(AssetRegistry, data)

def save_registry(registry: AssetRegistry, path: Path) -> None:
    validate_registry(registry)
    _write_json(path, registry)

def load_metadata(path: Path) -> PipelineMetadata:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_metadata(data)
    return cast(PipelineMetadata, data)

def save_metadata(meta: PipelineMetadata, path: Path) -> None:
    validate_metadata(meta)
    _write_json(path, meta)

def load_pool(path: Path) -> Pool:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_pool(data)
    return cast(Pool, data)

def save_pool(pool: Pool, path: Path) -> None:
    validate_pool(pool)
    _write_json(path, pool)

def _assign_missing_arrangement_uuids(arrangement: Any) -> bool:
    if not isinstance(arrangement, dict):
        return False
    clips = arrangement.get("clips")
    if not isinstance(clips, list):
        return False
    used = {
        clip.get("uuid")
        for clip in clips
        if isinstance(clip, dict) and isinstance(clip.get("uuid"), str)
    }
    assigned = False
    for clip in clips:
        if not isinstance(clip, dict) or "uuid" in clip:
            continue
        value = uuid.uuid4().hex[:8]
        while value in used:
            value = uuid.uuid4().hex[:8]
        used.add(value)
        clip["uuid"] = value
        assigned = True
        order = clip.get("order")
        print(f"timeline.load_arrangement: migrated clip order={order} uuid={value}", file=sys.stderr)
    return assigned

def load_arrangement(
    path: Path,
    pool_ids: set[str] | None = None,
    *,
    assign_missing_uuids: bool = False,
) -> Arrangement:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    migrated = False
    if assign_missing_uuids:
        migrated = _assign_missing_arrangement_uuids(data)
    validate_arrangement(data, pool_ids)
    if migrated:
        _write_json(Path(path), data)
    return cast(Arrangement, data)

def save_arrangement(arrangement: Arrangement, path: Path, pool_ids: set[str] | None = None) -> None:
    validate_arrangement(arrangement, pool_ids)
    _write_json(path, arrangement)
