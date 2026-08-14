"""Focused Layer Stack batch-1 contract tests: ``LayerRef`` + per-z tiling.

These tests pin the new contract surface only; the frozen overlap/gap matrix
for the default layer lives in ``test_contracts.py`` and is asserted here
again with the exact same cases.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from astrid.core.rendering import FrameWindow, RenderPlan, RenderProfile
from astrid.core.rendering.contracts import (
    FinalizerResolution,
    LayerRef,
    PlannerResolution,
    RenderSegment,
    RendererResolution,
    SupportReport,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64

SCHEMA_DIR = (
    Path(__file__).resolve().parents[3]
    / "astrid"
    / "core"
    / "rendering"
    / "schemas"
    / "v1"
)


def _support(backend: str = "acme.example") -> SupportReport:
    return SupportReport(
        schema_version=1,
        supported=True,
        reasons=[],
        features={"media": True, "audio_mode": "rendered"},
        alternatives=[],
        backend=backend,
        backend_version="1.0.0",
    )


def _renderer(backend: str = "acme.example") -> RendererResolution:
    return RendererResolution(
        id=backend,
        source_pack={"id": backend.split(".", 1)[0]},
        manifest_digest=SHA_B,
        alias_chain=[backend],
        override=None,
        support_decision=_support(backend),
        trust_eligibility={"eligible": True, "method": "source-tree"},
    )


def _planner() -> PlannerResolution:
    return PlannerResolution(
        id="rendering.legacy_hybrid",
        source_pack={"id": "rendering"},
        manifest_digest=SHA_C,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
        override=None,
        support_decision=_support("rendering.legacy_hybrid"),
    )


def _finalizer() -> FinalizerResolution:
    return FinalizerResolution(
        id="rendering.ffmpeg-finalizer",
        source_pack={"id": "rendering"},
        manifest_digest=SHA_E,
        alias_chain=["ffmpeg-finalizer", "rendering.ffmpeg-finalizer"],
        override=None,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        support_decision=_support("rendering.ffmpeg-finalizer"),
    )


def _profile() -> RenderProfile:
    return RenderProfile(
        width=1920,
        height=1080,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        container="mp4",
        video_codec="h264",
        video_profile="high",
        video_level="4.1",
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channel_layout="stereo",
        duration_tolerance=1,
    )


def _window(start: int = 0, end: int = 48) -> FrameWindow:
    return FrameWindow(
        start_frame=start,
        end_frame=end,
        fps_rational=(24, 1),
        source_range=(10 + start, 10 + end),
        speed=1.0,
    )


def _layer(
    z: int = 0,
    *,
    tracks: tuple[str, ...] = ("visual-1",),
    blend: str = "normal",
    opacity: float = 1.0,
) -> LayerRef:
    return LayerRef(z=z, tracks=tracks, blend=blend, opacity=opacity)


def _segment(
    start: int = 0,
    end: int = 48,
    *,
    layer: LayerRef | None = None,
) -> RenderSegment:
    return RenderSegment(
        window=_window(start, end),
        renderer=_renderer(),
        input_hashes={"timeline": SHA_A},
        layer=layer,
    )


def _plan(
    *,
    segments: list[RenderSegment] | None = None,
    total_frames: int = 48,
    window: FrameWindow | None = None,
) -> RenderPlan:
    selected = [_segment()] if segments is None else segments
    return RenderPlan(
        schema_version=1,
        request_digest=SHA_D,
        requested_policy="hybrid",
        planner=_planner(),
        segments=selected,
        finalizer=_finalizer(),
        profile=_profile(),
        total_frames=total_frames,
        reasons={str(index): "the request is supported" for index in range(len(selected))},
        window=window,
    )


# --- 1. the frozen default-layer behavior is unchanged ---------------------


@pytest.mark.parametrize(
    ("segments", "total_frames", "match"),
    [
        ([_segment(1, 48)], 48, "gap"),
        ([_segment(0, 47)], 48, "trailing gap"),
        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
    ],
)
def test_default_layer_still_rejects_overlap_gap_and_out_of_order(
    segments: list[RenderSegment],
    total_frames: int,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _plan(segments=segments, total_frames=total_frames)


# --- 2. the new capability: cross-z overlap ---------------------------------


def test_distinct_z_segments_may_overlap_in_time() -> None:
    plan = _plan(
        segments=[
            _segment(0, 48, layer=_layer(z=0)),
            _segment(0, 48, layer=_layer(z=1, tracks=("visual-2",))),
        ]
    )
    assert plan.total_frames == 48
    assert [segment.layer.z for segment in plan.segments] == [0, 1]


def test_distinct_z_layers_may_end_early() -> None:
    """A top layer tiles contiguously but may cover only part of the timeline
    (e.g. a text overlay [0, 24) over a full-length video); the compositor's
    background fill handles the uncovered tail.  Only the default (layer=None)
    layer must reach target_end."""
    plan = _plan(
        segments=[
            _segment(0, 48, layer=_layer(z=0)),
            _segment(0, 24, layer=_layer(z=1, tracks=("visual-2",))),
        ]
    )
    assert [segment.layer.z for segment in plan.segments] == [0, 1]
    assert plan.total_frames == 48


# --- 3/4. per-z tiling: same-z overlap rejected, adjacency parses -----------


def test_same_z_overlapping_segments_rejected() -> None:
    with pytest.raises(ValueError, match="layer z=1.*overlaps or is out of order"):
        _plan(
            segments=[
                _segment(0, 25, layer=_layer(z=1)),
                _segment(24, 48, layer=_layer(z=1)),
            ]
        )


def test_same_z_gap_rejected_with_z_named_in_error() -> None:
    with pytest.raises(ValueError, match=r"segments\[1\] layer z=1 leaves a gap at frame 24"):
        _plan(
            segments=[
                _segment(0, 24, layer=_layer(z=1)),
                _segment(30, 48, layer=_layer(z=1)),
            ]
        )


def test_same_z_adjacent_segments_parse() -> None:
    plan = _plan(
        segments=[
            _segment(0, 24, layer=_layer(z=1)),
            _segment(24, 48, layer=_layer(z=1)),
        ]
    )
    assert [segment.window.start_frame for segment in plan.segments] == [0, 24]


# --- 5. the all-or-none rule -------------------------------------------------


@pytest.mark.parametrize(
    "segments",
    [
        [_segment(0, 24), _segment(24, 48, layer=_layer(z=1))],
        [_segment(0, 24, layer=_layer(z=1)), _segment(24, 48)],
    ],
)
def test_mixed_default_and_explicit_layer_segments_rejected(segments: list[RenderSegment]) -> None:
    with pytest.raises(ValueError, match="all carry an explicit layer"):
        _plan(segments=segments)


# --- 6. blend must be "normal" in v1 ----------------------------------------


def test_blend_other_than_normal_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="only 'normal'"):
        _layer(z=0, blend="multiply")
    with pytest.raises(ValueError, match="only 'normal'"):
        LayerRef.from_dict({"z": 0, "tracks": ["visual-1"], "blend": "screen"})
    with pytest.raises(ValueError, match="only 'normal'"):
        RenderSegment.from_dict(
            {
                "window": _window().to_dict(),
                "renderer": _renderer().to_dict(),
                "input_hashes": {"timeline": SHA_A},
                "layer": {"z": 0, "tracks": ["visual-1"], "blend": "darken"},
            }
        )


# --- 7. serialization round-trip + fast-path key set ------------------------


def test_layer_round_trips_through_to_dict_and_from_dict() -> None:
    layer = _layer(z=2, tracks=("visual-a", "visual-b"), opacity=0.75)
    segment = _segment(0, 48, layer=layer)
    payload = segment.to_dict()
    assert payload["layer"] == {
        "z": 2,
        "tracks": ["visual-a", "visual-b"],
        "blend": "normal",
        "opacity": 0.75,
    }
    assert RenderSegment.from_dict(payload) == segment
    assert LayerRef.from_dict(layer.to_dict()) == layer

    plan = _plan(
        segments=[
            _segment(0, 48, layer=_layer(z=0)),
            _segment(0, 48, layer=_layer(z=1)),
        ]
    )
    assert RenderPlan.from_dict(plan.to_dict()) == plan


def test_layer_none_omits_key_and_fast_path_key_set_is_unchanged() -> None:
    segment = _segment()
    assert set(segment.to_dict()) == {"window", "renderer", "input_hashes"}
    assert RenderSegment.from_dict(segment.to_dict()) == segment


# --- 8. LayerRef field validation -------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"z": -1}, ">= 0"),
        ({"tracks": ()}, "at least one track"),
        ({"tracks": ("",)}, "must not be empty"),
        ({"tracks": "visual-1"}, "array of strings"),
        ({"opacity": 0.0}, "must be > 0"),
        ({"opacity": -0.5}, "must be > 0"),
        ({"opacity": 1.5}, "must be <= 1"),
    ],
)
def test_invalid_layer_refs_rejected(kwargs: dict[str, Any], match: str) -> None:
    with pytest.raises((TypeError, ValueError), match=match):
        _layer(z=kwargs.get("z", 0), tracks=kwargs.get("tracks", ("visual-1",)), opacity=kwargs.get("opacity", 1.0), blend=kwargs.get("blend", "normal"))


def test_layer_from_dict_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError, match="unknown fields"):
        LayerRef.from_dict({"z": 0, "tracks": ["visual-1"], "matte": "luma"})


# --- plan.json wire schema ---------------------------------------------------


def test_plan_schema_accepts_segment_layer() -> None:
    schema = json.loads((SCHEMA_DIR / "plan.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    example = deepcopy(schema["examples"][0])
    example["segments"][0]["layer"] = {
        "z": 0,
        "tracks": ["visual-1"],
        "blend": "normal",
        "opacity": 1.0,
    }
    validator.validate(example)
    # dataclass parse agrees, and the wire payload round-trips identically
    assert RenderPlan.from_dict(example).to_dict() == example


def test_plan_schema_rejects_unknown_layer_keys() -> None:
    schema = json.loads((SCHEMA_DIR / "plan.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    example = deepcopy(schema["examples"][0])
    example["segments"][0]["layer"] = {"z": 0, "tracks": ["visual-1"], "matte": "luma"}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(example)
