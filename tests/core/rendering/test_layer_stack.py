"""Batch 5: ``rendering.layer-stack`` planner.

Covers fast-path concat, per-track registry routing, greedy merge, fail-closed
blend/unsupported tracks, profile honesty (no canonical H.264 profile on
stamped-layer support() calls), and exact full-window tiling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.rendering.contracts import (
    RenderPlan,
    RenderRequest,
    SupportReport,
)
from astrid.core.rendering.errors import RendererUnsupportedError
from astrid.core.rendering.registry import RendererRegistry, load_default_registries
from astrid.packs.rendering.planners.layer_stack import run as layer_stack

REPO_ROOT = Path(__file__).resolve().parents[3]


def _timeline(
    *,
    clips: list[dict] | None = None,
    fps: int = 30,
    tracks: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    result: dict = {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": fps}}
        },
        "tracks": tracks
        or [
            {"id": "overlay", "kind": "visual", "label": "Overlay"},
            {"id": "source", "kind": "visual", "label": "Source"},
        ],
        "clips": clips or [],
    }
    if metadata is not None:
        result["metadata"] = metadata
    return result


def _text(
    clip_id: str = "title",
    *,
    at: float = 0,
    hold: float = 2,
    track: str = "overlay",
    **extra: object,
) -> dict:
    return {
        "id": clip_id,
        "at": at,
        "track": track,
        "clipType": "text",
        "text": {
            "content": "Hello",
            "fontSize": 48,
            "color": "#ffffff",
            "align": "center",
            "bold": False,
        },
        "params": {
            "anchor": "center",
            "offsetX": 0,
            "offsetY": 0,
            "textShadow": False,
            "maxWidth": 100,
            "weight": 400,
        },
        "hold": hold,
        **extra,
    }


def _media(
    clip_id: str = "media",
    *,
    at: float = 0,
    duration: float = 2,
    track: str = "source",
    **extra: object,
) -> dict:
    return {
        "id": clip_id,
        "at": at,
        "track": track,
        "clipType": "media",
        "asset": "source",
        "from": 0,
        "to": duration,
        "speed": 1,
        "volume": 0,
        **extra,
    }


def _request(
    tmp_path: Path,
    timeline: dict,
    *,
    assets: dict | None = None,
    profile: object = None,
) -> RenderRequest:
    timeline_path = tmp_path / "timeline.json"
    assets_path = tmp_path / "assets.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    assets_path.write_text(json.dumps(assets or {"assets": {}}), encoding="utf-8")
    return RenderRequest(
        schema_version=1,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="video.mp4",
        profile=profile,
    )


def _registries(*renderer_ids: str):
    renderers, _planners, finalizers = load_default_registries(
        REPO_ROOT, include_installed=False
    )
    if not renderer_ids:
        return renderers, finalizers
    wanted = set(renderer_ids)
    subset = RendererRegistry(
        [
            candidate
            for candidate in renderers.candidates(eligible=True)
            if candidate.id in wanted
        ]
    )
    return subset, finalizers


def _kinds(timeline: object) -> tuple[set[str], int, bool]:
    mapping = timeline if isinstance(timeline, dict) else {}
    clips = [clip for clip in mapping.get("clips", []) if isinstance(clip, dict)]
    tracks = [track for track in mapping.get("tracks", []) if isinstance(track, dict)]
    types = {str(clip.get("clipType", "media")) for clip in clips}
    visual = sum(1 for track in tracks if track.get("kind") == "visual")
    audio = any(track.get("kind") == "audio" for track in tracks)
    return types, visual, audio


def _backend_accepts(renderer_id: str, timeline: object) -> bool:
    types, visual, audio = _kinds(timeline)
    if renderer_id == layer_stack.THREE_ID:
        return bool(types) and types <= {"text"} and not audio
    if renderer_id == layer_stack.FFMPEG_ID:
        return bool(types) and types <= {"media"} and visual == 1
    if renderer_id == layer_stack.REMOTION_ID:
        return True
    return False


def _resolver(allowed: set[str] | None = None):
    accepted = allowed or {
        layer_stack.FFMPEG_ID,
        layer_stack.REMOTION_ID,
        layer_stack.THREE_ID,
    }

    def resolve(
        renderer_id: str, request: RenderRequest, timeline: object
    ) -> SupportReport:
        ok = renderer_id in accepted and _backend_accepts(renderer_id, timeline)
        return SupportReport(
            schema_version=1,
            supported=ok,
            reasons=[] if ok else ["fixture rejection"],
            features={"fixture": True},
            alternatives=[],
            backend=renderer_id,
            backend_version="1.0.0",
        )

    return resolve


class _RecordingResolver:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.requests: list[RenderRequest] = []

    def __call__(
        self, renderer_id: str, request: RenderRequest, timeline: object
    ) -> SupportReport:
        self.requests.append(request)
        return self.inner(renderer_id, request, timeline)


def _plan(
    tmp_path: Path,
    timeline: dict,
    *,
    allowed: set[str] | None = None,
    renderer_ids: tuple[str, ...] | None = None,
    assets: dict | None = None,
    profile: object = None,
) -> tuple[RenderPlan, _RecordingResolver]:
    if renderer_ids is None:
        renderers, finalizers = _registries()
    else:
        renderers, finalizers = _registries(*renderer_ids)
    resolver = _RecordingResolver(_resolver(allowed))
    result = layer_stack.plan(
        _request(tmp_path, timeline, assets=assets, profile=profile),
        workspace=tmp_path,
        support_resolver=resolver,
        registries=(renderers, finalizers),
    )
    return result, resolver


def _mixed_timeline(*, fps: int = 30, duration: float = 2) -> dict:
    return _timeline(
        fps=fps,
        clips=[
            _text(hold=duration, track="overlay"),
            _media(duration=duration, track="source"),
        ],
    )


# ---------------------------------------------------------------------------
# Fast path
# ---------------------------------------------------------------------------


def test_remotion_capable_timeline_is_one_unlayered_concat_segment(
    tmp_path: Path,
) -> None:
    result, _resolver_used = _plan(tmp_path, _mixed_timeline())

    assert result.total_frames == 60
    assert len(result.segments) == 1
    segment = result.segments[0]
    assert segment.layer is None
    assert segment.window.start_frame == 0
    assert segment.window.end_frame == 60
    assert segment.renderer.id == layer_stack.REMOTION_ID
    assert segment.renderer.support_decision.backend == layer_stack.REMOTION_ID
    assert segment.renderer.support_decision.supported is True
    assert result.finalizer.id == layer_stack.CONCAT_FINALIZER_ID
    assert "layer" not in segment.to_dict()


# ---------------------------------------------------------------------------
# Layer path
# ---------------------------------------------------------------------------


def test_text_plus_media_without_remotion_splits_into_two_full_window_layers(
    tmp_path: Path,
) -> None:
    result, recorder = _plan(
        tmp_path,
        _mixed_timeline(),
        renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
    )

    assert result.finalizer.id == layer_stack.COMPOSITOR_FINALIZER_ID
    assert result.total_frames == 60
    assert len(result.segments) == 2
    by_z = {segment.layer.z: segment for segment in result.segments}
    assert set(by_z) == {0, 1}

    bottom = by_z[0]
    top = by_z[1]
    assert bottom.layer is not None
    assert top.layer is not None
    assert bottom.layer.tracks == ("source",)
    assert bottom.renderer.id == layer_stack.FFMPEG_ID
    assert top.layer.tracks == ("overlay",)
    assert top.renderer.id == layer_stack.THREE_ID
    for segment in result.segments:
        assert (segment.window.start_frame, segment.window.end_frame) == (0, 60)
        assert segment.renderer.support_decision.backend == segment.renderer.id
        assert segment.renderer.support_decision.supported is True
        assert segment.layer.blend == "normal"
        assert segment.layer.opacity == 1.0
    assert all(request.profile is None for request in recorder.requests)


def test_layer_path_real_threejs_and_ffmpeg_support(tmp_path: Path) -> None:
    """Preferred split: real backend support() on a threejs+ffmpeg registry."""

    from tests.packs.rendering._helpers import _execution_env, _source_video

    source = _source_video(tmp_path)
    timeline = _timeline(
        fps=24,
        clips=[
            _text(hold=1, track="overlay"),
            _media(duration=1, track="source"),
        ],
    )
    assets = {
        "assets": {
            "source": {
                "file": str(source),
                "type": "video/mp4",
            }
        }
    }
    renderers, finalizers = _registries(layer_stack.THREE_ID, layer_stack.FFMPEG_ID)
    with _execution_env():
        result = layer_stack.plan(
            _request(tmp_path, timeline, assets=assets),
            workspace=tmp_path,
            registries=(renderers, finalizers),
        )

    assert result.finalizer.id == layer_stack.COMPOSITOR_FINALIZER_ID
    assert result.total_frames == 24
    by_renderer = {segment.renderer.id: segment for segment in result.segments}
    assert set(by_renderer) == {layer_stack.THREE_ID, layer_stack.FFMPEG_ID}
    assert by_renderer[layer_stack.FFMPEG_ID].layer is not None
    assert by_renderer[layer_stack.THREE_ID].layer is not None
    assert by_renderer[layer_stack.FFMPEG_ID].layer.tracks == ("source",)
    assert by_renderer[layer_stack.THREE_ID].layer.tracks == ("overlay",)
    assert by_renderer[layer_stack.FFMPEG_ID].layer.z == 0
    assert by_renderer[layer_stack.THREE_ID].layer.z == 1
    for segment in result.segments:
        assert segment.renderer.support_decision.backend == segment.renderer.id
        assert segment.renderer.support_decision.supported is True
        assert (segment.window.start_frame, segment.window.end_frame) == (0, 24)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


def test_adjacent_same_renderer_tracks_merge_into_one_layer(tmp_path: Path) -> None:
    timeline = _timeline(
        tracks=[
            {"id": "brand", "kind": "visual", "label": "Brand"},
            {"id": "captions", "kind": "visual", "label": "Captions"},
            {"id": "source", "kind": "visual", "label": "Source"},
        ],
        clips=[
            _text("brand", hold=2, track="brand"),
            _text("cap", hold=2, track="captions"),
            _media(duration=2, track="source"),
        ],
    )
    result, _recorder = _plan(
        tmp_path,
        timeline,
        renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
    )

    assert result.finalizer.id == layer_stack.COMPOSITOR_FINALIZER_ID
    assert len(result.segments) == 2
    by_z = {segment.layer.z: segment for segment in result.segments}
    assert by_z[0].renderer.id == layer_stack.FFMPEG_ID
    assert by_z[0].layer.tracks == ("source",)
    assert by_z[1].renderer.id == layer_stack.THREE_ID
    assert by_z[1].layer.tracks == ("captions", "brand")
    assert by_z[1].layer.z == 1


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


def test_unsupported_track_fails_closed(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            {
                "id": "weird",
                "at": 0,
                "track": "overlay",
                "clipType": "effect-layer",
                "hold": 2,
            },
            _media(duration=2, track="source"),
        ]
    )
    with pytest.raises(RendererUnsupportedError, match="overlay") as caught:
        _plan(
            tmp_path,
            timeline,
            renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
        )
    assert "overlay" in caught.value.error.message


def test_non_normal_blend_mode_fails_closed(tmp_path: Path) -> None:
    timeline = _timeline(
        tracks=[
            {
                "id": "overlay",
                "kind": "visual",
                "label": "Overlay",
                "blendMode": "multiply",
            },
            {"id": "source", "kind": "visual", "label": "Source"},
        ],
        clips=[
            _text(hold=2, track="overlay"),
            _media(duration=2, track="source"),
        ],
    )
    with pytest.raises(RendererUnsupportedError, match="blendMode") as caught:
        _plan(
            tmp_path,
            timeline,
            renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
        )
    assert "multiply" in caught.value.error.message
    assert "overlay" in caught.value.error.message


def test_non_normal_blend_is_escaped_by_full_stack_fast_path(tmp_path: Path) -> None:
    timeline = _timeline(
        tracks=[
            {
                "id": "overlay",
                "kind": "visual",
                "label": "Overlay",
                "blendMode": "multiply",
            },
            {"id": "source", "kind": "visual", "label": "Source"},
        ],
        clips=[
            _text(hold=2, track="overlay"),
            _media(duration=2, track="source"),
        ],
    )
    result, _recorder = _plan(tmp_path, timeline)
    assert result.segments[0].layer is None
    assert result.finalizer.id == layer_stack.CONCAT_FINALIZER_ID
    assert result.segments[0].renderer.id == layer_stack.REMOTION_ID


def test_empty_timeline_is_unsupported(tmp_path: Path) -> None:
    request = _request(tmp_path, _timeline(clips=[]))
    report = layer_stack.support(request, workspace=tmp_path)
    assert report.supported is False
    assert any("empty timeline" in reason for reason in report.reasons)
    with pytest.raises(RendererUnsupportedError):
        layer_stack.plan(request, workspace=tmp_path, support_resolver=_resolver())


# ---------------------------------------------------------------------------
# Profile honesty + exact tiling
# ---------------------------------------------------------------------------


def test_layer_plan_parses_per_z_and_strips_canonical_profile_from_support(
    tmp_path: Path,
) -> None:
    result, recorder = _plan(
        tmp_path,
        _mixed_timeline(fps=30, duration=2),
        renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
    )

    assert recorder.requests
    assert all(request.profile is None for request in recorder.requests)
    assert result.profile.video_codec == "h264"
    assert result.profile.pixel_format == "yuv420p"
    assert result.profile.container == "mp4"
    assert result.profile.fps_rational == (30, 1)

    parsed = RenderPlan.from_dict(result.to_dict())
    assert [(segment.layer.z, segment.layer.tracks) for segment in parsed.segments] == [
        (segment.layer.z, segment.layer.tracks) for segment in result.segments
    ]
    assert {segment.layer.z for segment in parsed.segments} == {0, 1}
    for segment in parsed.segments:
        assert segment.layer is not None
        assert (segment.window.start_frame, segment.window.end_frame) == (
            0,
            parsed.total_frames,
        )
        # z>0 is the service's alpha-stamp predicate (batch 2); the planner
        # only has to emit a correct LayerRef so that stamp can fire.
        assert segment.layer.z >= 0


def test_each_layer_covers_the_full_plan_window(tmp_path: Path) -> None:
    result, _recorder = _plan(
        tmp_path,
        _mixed_timeline(fps=24, duration=1.5),
        renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
    )

    assert result.total_frames == 36
    assert result.segments
    for segment in result.segments:
        assert segment.window.start_frame == 0
        assert segment.window.end_frame == result.total_frames
        assert segment.window.fps_rational == result.profile.fps_rational
    assert set(result.reasons) == {str(index) for index in range(len(result.segments))}
