#!/usr/bin/env python3
"""Timeline schema mirroring reigh-app's TimelineConfig.

TimelineConfig / TimelineClip / ThemeOverrides / TimelineOutput / AssetEntry /
Theme are re-exported from `banodoco_timeline_schema` (see
`packages/timeline-schema/`); the JSON-Schema validator there is the canonical
shape check. Everything else in this file (pool/arrangement/metadata/registry
types, transition validation, effect-id registry checks) is Banodoco-only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from enum import Enum
from typing import Any, List, Literal, TypedDict, Union, cast

from astrid.core.timeline.kinds import normalize_track_kind

try:
    from banodoco_timeline_schema import (
        AssetEntry as SharedAssetEntry,
    )
    from banodoco_timeline_schema import (
        Theme as SharedTheme,
    )
    from banodoco_timeline_schema import (
        ThemeOverrides as SharedThemeOverrides,
    )
    from banodoco_timeline_schema import (
        TimelineClip as SharedTimelineClip,
    )
    from banodoco_timeline_schema import (
        TimelineConfig as SharedTimelineConfig,
    )
    from banodoco_timeline_schema import (
        TimelineOutput as SharedTimelineOutput,
    )
    from banodoco_timeline_schema import (
        materialize_output as _materialize_output,
    )
    from banodoco_timeline_schema import validate_timeline as _shared_validate_timeline
except ImportError:
    class SharedTimelineOutput(TypedDict, total=False):
        resolution: str
        fps: float
        file: str
        background: str
        background_scale: float

    class SharedTimelineClip(TypedDict, total=False):
        id: str
        at: float
        track: str
        clipType: str
        asset: str
        from_: float
        to: float
        speed: float
        hold: float
        volume: float
        x: float
        y: float
        width: float
        height: float
        cropTop: float
        cropBottom: float
        cropLeft: float
        cropRight: float
        opacity: float
        params: dict[str, Any]
        text: "TextClipData"
        entrance: "AnimationReferenceList"
        exit: "AnimationReferenceList"
        continuous: "AnimationReferenceList"
        transition: "ClipTransitionReference"
        effects: list["TimelineEffect"]
        source_uuid: str
        generation: dict[str, Any]
        pool_id: str
        clip_order: int

    class SharedThemeOverrides(TypedDict, total=False):
        visual: dict[str, Any]
        generation: dict[str, Any]
        voice: dict[str, Any]
        audio: dict[str, Any]
        pacing: dict[str, Any]

    class SharedTheme(TypedDict, total=False):
        visual: dict[str, Any]
        generation: dict[str, Any]
        voice: dict[str, Any]
        audio: dict[str, Any]
        pacing: dict[str, Any]

    class SharedTimelineConfig(TypedDict, total=False):
        theme: str
        theme_overrides: SharedThemeOverrides
        generation_defaults: dict[str, Any]
        clips: list[SharedTimelineClip]
        tracks: list[dict[str, Any]]
        pinnedShotGroups: list[dict[str, Any]]
        output: SharedTimelineOutput

    class SharedAssetEntry(TypedDict, total=False):
        file: str
        url: str
        etag: str
        content_sha256: str
        url_expires_at: str
        type: str
        duration: float
        resolution: str
        fps: float
        generationId: str

    def _materialize_output(config: SharedTimelineConfig, theme: dict[str, Any]) -> SharedTimelineOutput:
        canvas = theme.get("visual", {}).get("canvas", {}) if isinstance(theme, dict) else {}
        width = int(canvas.get("width", 1920)) if isinstance(canvas, dict) else 1920
        height = int(canvas.get("height", 1080)) if isinstance(canvas, dict) else 1080
        fps = float(canvas.get("fps", 30)) if isinstance(canvas, dict) else 30.0
        return {"resolution": f"{width}x{height}", "fps": fps, "file": "output.mp4"}

    def _shared_validate_timeline(config: Any, *, strict: bool = True) -> None:
        if not isinstance(config, dict):
            raise ValueError("Timeline must be a JSON object")
        if not isinstance(config.get("clips"), list):
            raise ValueError("Timeline.clips must be a list")

TimelineClip = SharedTimelineClip
TimelineConfig = SharedTimelineConfig
ThemeOverrides = SharedThemeOverrides
TimelineOutput = SharedTimelineOutput
AssetEntry = SharedAssetEntry
Theme = SharedTheme

materialize_output = _materialize_output

ParameterType = Literal["number", "select", "boolean", "color", "audio-binding"]
# Model-level TrackKind; mirrors ``astrid.core.timeline.events.schema.types.TrackKind``
# and the built-in track catalog (catalog="track") in ``astrid.core.pack``.
# This definition is intentionally duplicated rather than imported from the
# event-schema module: keeping event-payload schemas decoupled from the
# Banodoco-schema implementation avoids import-time coupling between the two
# layers. Do not consolidate into a shared kinds module.
TrackKind = Literal["visual", "audio"]
TrackFit = Literal["cover", "contain", "manual"]
TrackBlendMode = Literal[
    "normal", "multiply", "screen", "overlay",
    "darken", "lighten", "soft-light", "hard-light",
]
BUILTIN_CLIP_TYPES = ("media", "hold", "text", "effect-layer")
ClipType = Literal["media", "hold", "text", "effect-layer"]
TextAlignment = Literal["left", "center", "right"]
AudioBindingSource = Literal["bass", "mid", "treble", "amplitude"]

class TimelineEffect(TypedDict, total=False):
    fade_in: float
    fade_out: float

class AnimationReferenceObject(TypedDict, total=False):
    id: str
    durationFrames: float
    easing: str
    params: dict[str, Any]

AnimationReference = Union[str, AnimationReferenceObject]
AnimationReferenceList = Union[AnimationReference, List[AnimationReference]]

class AudioBindingValue(TypedDict):
    source: AudioBindingSource
    min: float
    max: float

class ParameterOption(TypedDict):
    label: str
    value: str

class _ParameterDefinitionRequired(TypedDict):
    name: str
    label: str
    description: str
    type: ParameterType

class ParameterDefinition(_ParameterDefinitionRequired, total=False):
    default: Any
    min: float
    max: float
    step: float
    options: list[ParameterOption]

class _TrackDefinitionRequired(TypedDict):
    id: str
    kind: TrackKind
    label: str

class TrackDefinition(_TrackDefinitionRequired, total=False):
    scale: float
    fit: TrackFit
    opacity: float
    volume: float
    muted: bool
    blendMode: TrackBlendMode

class ClipEntrance(TypedDict, total=False):
    type: str
    duration: float
    intensity: float
    params: dict[str, Any]

class ClipExit(TypedDict, total=False):
    type: str
    duration: float
    intensity: float
    params: dict[str, Any]

class ClipContinuous(TypedDict, total=False):
    type: str
    intensity: float
    params: dict[str, Any]

class ClipTransition(TypedDict):
    type: str
    duration: float

class ClipTransitionReference(TypedDict, total=False):
    id: str
    type: str
    duration: float
    durationFrames: float
    params: dict[str, Any]

class TextClipData(TypedDict, total=False):
    content: str
    fontFamily: str
    fontSize: float
    color: str
    align: TextAlignment
    bold: bool
    italic: bool

# TimelineClip / TimelineConfig / ThemeOverrides / TimelineOutput / AssetEntry
# come from banodoco_timeline_schema (re-exported above). PinnedShotGroup and
# AssetRegistry are Banodoco-only wrappers retained here.

AssetRegistryEntry = AssetEntry

class AssetRegistry(TypedDict):
    assets: dict[str, AssetRegistryEntry]

class ClipClassifiedKind(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"
    EFFECT = "effect"
    OPAQUE = "opaque"

PoolKind = Literal["source", "generative"]
PoolCategory = Literal["dialogue", "visual", "reaction", "applause", "music"]
PipelinePoolKind = Literal["dialogue", "visual", "reaction", "applause", "music", "text"]

class SourceIds(TypedDict, total=False):
    segment_ids: list[int]
    scene_id: str

class PoolScores(TypedDict, total=False):
    triage: float
    deep: float
    quotability: float

class _PoolEntryRequired(TypedDict):
    id: str
    kind: PoolKind
    category: PoolCategory
    duration: float
    scores: PoolScores
    excluded: bool

class PoolEntry(_PoolEntryRequired, total=False):
    asset: str
    src_start: float
    src_end: float
    source_ids: SourceIds
    effect_id: str
    param_schema: dict[str, Any]
    defaults: dict[str, Any]
    meta: dict[str, Any]
    excluded_reason: str | None
    text: str
    speaker: str | None
    quote_kind: str
    motion_tags: list[str]
    mood_tags: list[str]
    subject: str
    camera: str
    intensity: float
    event_label: str
    bed_kind: str
    energy: float

class Pool(TypedDict, total=False):
    version: int
    generated_at: str
    source_slug: str
    entries: list[PoolEntry]

class ArrangementTextOverlay(TypedDict, total=False):
    content: str
    style_preset: str

ArrangementVisualRole = Literal["primary", "overlay", "stinger"]

class ArrangementAudioSource(TypedDict):
    pool_id: str
    trim_sub_range: list[float]

class _ArrangementVisualSourceRequired(TypedDict):
    pool_id: str
    role: ArrangementVisualRole

class ArrangementVisualSource(_ArrangementVisualSourceRequired, total=False):
    params: dict[str, Any]

class _ArrangementClipRequired(TypedDict):
    uuid: str
    order: int
    audio_source: ArrangementAudioSource | None
    visual_source: ArrangementVisualSource
    rationale: str

class ArrangementClip(_ArrangementClipRequired, total=False):
    text_overlay: ArrangementTextOverlay | None

class Arrangement(TypedDict, total=False):
    version: int
    generated_at: str
    brief_text: str
    target_duration_sec: float
    source_slug: str
    brief_slug: str
    pool_sha256: str
    brief_sha256: str
    clips: list[ArrangementClip]

class PipelineMetadataClipEntry(TypedDict, total=False):
    source_uuid: str
    caption_kind: Literal["dialogue", "visual"]
    picked_by: str
    pick_rationale: str
    pool_id: str | None
    pool_kind: PipelinePoolKind
    source_ids: SourceIds
    source_scene_id: str
    source_transcript_text: str | None
    arrangement_notes: str | None
    text_overlay_content: str
    score: float

class PipelineMetadata(TypedDict):
    version: int
    generated_at: str
    pipeline: dict[str, Any]
    clips: dict[str, PipelineMetadataClipEntry]
    sources: dict[str, dict[str, Any]]

# `from` is a Python keyword, so TimelineClip stores it as `from_` in memory and
# swaps to/from `"from"` at the JSON boundary. Every other field is 1:1 with TS.
_FROM_ALIAS = ("from_", "from")
_TIMELINE_TOP_ALLOWED = frozenset({"theme", "theme_overrides", "generation_defaults", "clips", "tracks", "pinnedShotGroups", "output"})
_TIMELINE_CONTAINER_REQUIRED = frozenset({"clips", "tracks"})
_LEGACY_CONTAINER_KEYS = frozenset({"schema_version", "assembly", "pool", "arrangement"})
_THEME_OVERRIDES_ALLOWED = frozenset({"visual", "generation", "voice", "audio", "pacing"})
_CLIP_ALLOWED = frozenset(
    {
        "id", "at", "track", "clipType", "asset", "from", "to", "speed", "hold",
        "volume", "x", "y", "width", "height", "cropTop", "cropBottom",
        "cropLeft", "cropRight", "opacity", "params", "text", "entrance", "exit",
        "continuous", "transition", "effects", "source_uuid", "generation",
        "pool_id", "clip_order",
    }
)
_TRACK_ALLOWED = frozenset({"id", "kind", "label", "scale", "fit", "opacity", "volume", "muted", "blendMode"})
_ASSET_ENTRY_ALLOWED = frozenset(
    {
        "file",
        "url",
        "etag",
        "content_sha256",
        "url_expires_at",
        "type",
        "duration",
        "resolution",
        "fps",
        "generationId",
        "variantId",
        "thumbnailUrl",
    }
)
METADATA_VERSION = 1
POOL_VERSION = 1
ARRANGEMENT_VERSION = 1
# Fields here survive ffprobe cache hits. Run-specific fields (*_ref) must NOT be listed.
CARRY_FORWARD_SOURCE_FIELDS: frozenset[str] = frozenset({"codec"})
_POOL_ENTRY_ALLOWED = frozenset(
    {
        "id",
        "kind",
        "category",
        "asset",
        "src_start",
        "src_end",
        "duration",
        "source_ids",
        "scores",
        "excluded",
        "excluded_reason",
        "effect_id",
        "param_schema",
        "defaults",
        "meta",
        "text",
        "speaker",
        "quote_kind",
        "motion_tags",
        "mood_tags",
        "subject",
        "camera",
        "intensity",
        "event_label",
        "bed_kind",
        "energy",
    }
)
_POOL_ALLOWED = frozenset({"version", "generated_at", "source_slug", "entries"})
_SOURCE_IDS_ALLOWED = frozenset({"segment_ids", "scene_id"})
_POOL_SCORES_ALLOWED = frozenset({"triage", "deep", "quotability"})
_ARRANGEMENT_ALLOWED = frozenset(
    {
        "version",
        "generated_at",
        "brief_text",
        "target_duration_sec",
        "source_slug",
        "brief_slug",
        "pool_sha256",
        "brief_sha256",
        "clips",
    }
)
_ARRANGEMENT_CLIP_ALLOWED = frozenset({"uuid", "order", "audio_source", "visual_source", "text_overlay", "rationale"})
_ARRANGEMENT_AUDIO_SOURCE_ALLOWED = frozenset({"pool_id", "trim_sub_range"})
_ARRANGEMENT_VISUAL_SOURCE_ALLOWED = frozenset({"pool_id", "role", "params"})
_ARRANGEMENT_TEXT_OVERLAY_ALLOWED = frozenset({"content", "style_preset"})
_FORBIDDEN_ARRANGEMENT_TIME_KEYS = frozenset({"src_start", "src_end", "duration", "from", "to", "at", "start", "end", "time"})

def _raise_unknown_keys(path: str, payload: dict[str, Any], allowed: frozenset[str]) -> None:
    for key in payload:
        if key not in allowed:
            raise ValueError(f"{path} has unknown key {key!r}")

def _normalize_clip_for_validation(clip: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(clip)
    if "from_" in normalized and "from" not in normalized:
        normalized["from"] = normalized.pop("from_")
    return normalized

def _known_timeline_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key in _TIMELINE_TOP_ALLOWED}

def _json_safe_copy(value: Any) -> Any:
    """Return a deep JSON-compatible copy using the persisted serialization contract."""
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))

def canonical_empty_timeline() -> TimelineConfig:
    """Return the canonical empty raw TimelineConfig runtime container."""
    config = {"tracks": [], "clips": []}
    return validate_timeline_config_for_container(config)

def validate_timeline_config_for_container(config: Any) -> TimelineConfig:
    """Validate and return a JSON-safe copy of a raw TimelineConfig container.

    Runtime timeline containers are the raw renderable TimelineConfig shape.  This
    stricter surface rejects legacy wrapper/read-model keys that the looser render
    validator intentionally ignores for compatibility with old artifacts.
    """
    if not isinstance(config, Mapping):
        raise ValueError("TimelineConfig container must be a JSON object")
    data = copy.deepcopy(dict(config))
    legacy_keys = sorted(key for key in data if key in _LEGACY_CONTAINER_KEYS)
    if legacy_keys:
        raise ValueError(
            "TimelineConfig container must be raw; legacy wrapper/read-model keys "
            f"are not allowed: {legacy_keys}"
        )
    _raise_unknown_keys("TimelineConfig container", data, _TIMELINE_TOP_ALLOWED)
    missing = sorted(key for key in _TIMELINE_CONTAINER_REQUIRED if key not in data)
    if missing:
        raise ValueError(f"TimelineConfig container missing required key(s): {missing}")
    validate_timeline(data)
    return cast(TimelineConfig, _json_safe_copy(data))

def canonical_timeline_config(config: Any) -> TimelineConfig:
    """Return validated TimelineConfig data in a stable JSON-object order."""
    data = validate_timeline_config_for_container(config)
    return cast(TimelineConfig, _json_safe_copy(data))

def timeline_config_digest(config: Any) -> str:
    """Return a stable sha256 digest for a validated TimelineConfig container."""
    data = canonical_timeline_config(config)
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def timeline_configs_equal(left: Any, right: Any) -> bool:
    """Compare two TimelineConfig containers after validation and canonicalization."""
    return canonical_timeline_config(left) == canonical_timeline_config(right)

# =========================================================================
# Re-exports — validators extracted to astrid.core.timeline.validators.*
# All public names remain importable from this module unchanged.
# =========================================================================
from astrid.core.timeline.validators.arrangement import (
    ArrangementDurationError,
    _reject_forbidden_arrangement_time_keys,
    is_all_generative_arrangement,
    validate_arrangement,
    validate_arrangement_duration_window,
)
from astrid.core.timeline.validators.metadata import (
    _validate_generated_at,
    validate_metadata,
)
from astrid.core.timeline.validators.pool import (
    _validate_pool_scores,
    _validate_source_ids,
    validate_pool,
)
from astrid.core.timeline.validators.registry import (
    _animation_ids,
    _animation_meta,
    _effect_ids,
    _transition_ids,
    validate_registry,
)
from astrid.core.timeline.validators.timeline import (
    _clip_duration_seconds,
    _schema_params_for_animation_refs,
    _timeline_fps,
    _transition_reference,
    _validate_animation_reference,
    _validate_animation_reference_list,
    _validate_clip_transitions,
    _validate_effect_params,
    validate_timeline,
)
