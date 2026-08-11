# Python TypedDict mirrors of the canonical timeline.schema.json definitions.
#
# Plan-v5 B2: `timeline.schema.json` is the single source of truth; this file
# is a small committed mirror of its six definitions so Python consumers get
# typing without a runtime codegen dependency. `scripts/gen_python_types.py`
# checks it stays consistent with the artifact — regenerate by hand from the
# artifact and run that check (validation itself always uses jsonschema against
# the artifact via validate.py, never these TypedDicts).

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class TimelineClip(TypedDict, total=False):
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
    text: dict[str, Any]
    entrance: dict[str, Any]
    exit: dict[str, Any]
    continuous: dict[str, Any]
    transition: Any
    effects: Any
    params: dict[str, Any]
    generation: dict[str, Any]
    pool_id: str
    clip_order: int
    source_uuid: str
    label: str
    keyframes: dict[str, Any]
    derived_output: dict[str, Any]
    app: dict[str, Any]


class Theme(TypedDict, total=False):
    id: str
    visual: dict[str, Any]
    generation: dict[str, Any]
    voice: dict[str, Any]
    audio: dict[str, Any]
    pacing: dict[str, Any]


class ThemeOverrides(TypedDict, total=False):
    visual: dict[str, Any]
    generation: dict[str, Any]
    voice: dict[str, Any]
    audio: dict[str, Any]
    pacing: dict[str, Any]


class TimelineOutput(TypedDict, total=False):
    resolution: str
    fps: float
    file: str
    background: NotRequired[str | None]
    background_scale: NotRequired[float | None]


class AssetEntry(TypedDict, total=False):
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
    variantId: str
    thumbnailUrl: str


class TimelineConfig(TypedDict, total=False):
    theme: str
    theme_overrides: ThemeOverrides
    generation_defaults: dict[str, Any]
    clips: list[TimelineClip]
    tracks: list[dict[str, Any]]
    pinnedShotGroups: list[dict[str, Any]]
    output: TimelineOutput
    app: dict[str, Any]
