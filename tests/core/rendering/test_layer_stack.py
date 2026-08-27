"""Batch 5+6: ``rendering.layer-stack`` planner and the real stacked render.

Covers fast-path concat, per-track registry routing, greedy merge, fail-closed
blend/unsupported tracks, profile honesty (no canonical H.264 profile on
stamped-layer support() calls), exact full-window tiling, merge-reject /
opacity insurance, and one real two-layer render through the public service.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from astrid.core.rendering.contracts import (
    LayerRef,
    RenderPlan,
    RenderRequest,
    SupportReport,
)
from astrid.core.rendering.errors import RendererUnsupportedError
from astrid.core.rendering.registry import RendererRegistry, load_default_registries
from astrid.core.rendering.service import RenderService
from astrid.core.rendering.transport import CommandTransport
from astrid.packs.rendering.planners.layer_stack import run as layer_stack
from astrid.sdk.rendering import render as sdk_render
from tests.packs.rendering._helpers import _execution_env, _probe

REPO_ROOT = Path(__file__).resolve().parents[3]


def _timeline(
    *,
    clips: list[dict] | None = None,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    tracks: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    result: dict = {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": width, "height": height, "fps": fps}}
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
    content: str = "Hello",
    font_size: int = 48,
    color: str = "#ffffff",
    **extra: object,
) -> dict:
    return {
        "id": clip_id,
        "at": at,
        "track": track,
        "clipType": "text",
        "text": {
            "content": content,
            "fontSize": font_size,
            "color": color,
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
    audio: str | None = None,
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
        audio=audio,
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
    audio: str | None = None,
) -> tuple[RenderPlan, _RecordingResolver]:
    if renderer_ids is None:
        renderers, finalizers = _registries()
    else:
        renderers, finalizers = _registries(*renderer_ids)
    resolver = _RecordingResolver(_resolver(allowed))
    result = layer_stack.plan(
        _request(
            tmp_path, timeline, assets=assets, profile=profile, audio=audio
        ),
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


# ---------------------------------------------------------------------------
# Insurance (Batch 5 deferrals)
# ---------------------------------------------------------------------------


def test_ffmpeg_rejects_merge_of_two_adjacent_media_tracks(tmp_path: Path) -> None:
    """Two adjacent media tracks stay split: ffmpeg cannot claim both."""

    timeline = _timeline(
        tracks=[
            {"id": "a", "kind": "visual", "label": "A"},
            {"id": "b", "kind": "visual", "label": "B"},
        ],
        clips=[
            _media("media-a", duration=2, track="a"),
            _media("media-b", duration=2, track="b"),
        ],
    )
    result, _recorder = _plan(
        tmp_path,
        timeline,
        renderer_ids=(layer_stack.FFMPEG_ID,),
    )

    assert result.finalizer.id == layer_stack.COMPOSITOR_FINALIZER_ID
    assert len(result.segments) == 2
    by_z = {segment.layer.z: segment for segment in result.segments}
    assert by_z[0].layer.tracks == ("b",)
    assert by_z[1].layer.tracks == ("a",)
    assert by_z[0].renderer.id == layer_stack.FFMPEG_ID
    assert by_z[1].renderer.id == layer_stack.FFMPEG_ID
    assert by_z[0].layer.z == 0
    assert by_z[1].layer.z == 1


def test_track_opacity_below_one_is_copied_onto_layer_ref(tmp_path: Path) -> None:
    """A visual track with opacity < 1 lands on LayerRef.opacity."""

    timeline = _timeline(
        tracks=[
            {
                "id": "overlay",
                "kind": "visual",
                "label": "Overlay",
                "opacity": 0.4,
            },
            {"id": "source", "kind": "visual", "label": "Source"},
        ],
        clips=[
            _text(hold=2, track="overlay"),
            _media(duration=2, track="source"),
        ],
    )
    result, _recorder = _plan(
        tmp_path,
        timeline,
        renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
    )

    by_z = {segment.layer.z: segment for segment in result.segments}
    assert by_z[1].layer.tracks == ("overlay",)
    assert by_z[1].layer.opacity == 0.4
    assert by_z[0].layer.opacity == 1.0
    assert by_z[1].layer.blend == "normal"


# ---------------------------------------------------------------------------
# Batch 6 — real stacked render
# ---------------------------------------------------------------------------


def _require_stacked_environment() -> None:
    from tests.packs.rendering.test_threejs_backend import _missing_environment

    missing = _missing_environment()
    if missing:
        pytest.skip(
            "stacked render skipped: missing optional dependencies: "
            + ", ".join(missing)
        )


def _red_source(tmp_path: Path, *, frames: int = 24, audio: bool = True) -> Path:
    source_path = tmp_path / "source.mp4"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:s=320x180:rate=24:d={frames / 24}",
    ]
    if audio:
        command += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
    command += ["-frames:v", str(frames)]
    if audio:
        command += ["-shortest"]
    command += [
        "-c:v",
        "libx264",
        "-profile:v",
        "main",
        "-pix_fmt",
        "yuv420p",
    ]
    if audio:
        command += ["-c:a", "aac"]
    else:
        command.append("-an")
    command += ["-video_track_timescale", "12288", str(source_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return source_path


def _stacked_timeline(*, duration: float = 1.0) -> dict:
    return _timeline(
        fps=24,
        width=320,
        height=180,
        tracks=[
            {"id": "overlay", "kind": "visual", "label": "Overlay"},
            {"id": "source", "kind": "visual", "label": "Source"},
        ],
        clips=[
            _text(
                hold=duration,
                track="overlay",
                content="HI",
                font_size=72,
                color="#00ffff",
            ),
            _media(duration=duration, track="source"),
        ],
    )


def _stacked_assets(source: Path) -> dict:
    return {
        "assets": {
            "source": {
                "file": str(source),
                "type": "video/mp4",
            }
        }
    }


def _frame_rgb(path: Path, frame: int, tmp_path: Path):
    from PIL import Image

    png = tmp_path / f"stacked-frame-{frame}.png"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(path),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-vsync",
            "vfr",
            str(png),
        ],
        check=True,
    )
    return Image.open(png).convert("RGB")


def _is_media_red(rgb: tuple[int, int, int]) -> bool:
    red, green, blue = rgb
    return red >= 180 and green <= 80 and blue <= 80


def _is_not_media(rgb: tuple[int, int, int]) -> bool:
    return not _is_media_red(rgb)


class _InjectPlanTransport:
    """Return a constructed RenderPlan for the planner's plan verb.

    Every other verb (planner support, segment render, finalize) is a real
    CommandTransport call.  This is how a constructed LayerRef plan is
    executed through the public service without remotion claiming the
    full stack on the fast path.
    """

    def __init__(self, plan: RenderPlan) -> None:
        self._plan = plan

    def run(self, verb, command, *, backend, request_path, result_path, cwd, **kwargs):
        if verb == "plan" and backend == layer_stack.BACKEND_ID:
            return self._plan
        return CommandTransport(backend).run(
            verb,
            command,
            backend=backend,
            request_path=request_path,
            result_path=result_path,
            cwd=cwd,
            **kwargs,
        )


def _write_stacked_proof(
    *,
    proof_path: Path,
    output: Path,
    probe: dict,
    sidecar: dict,
    corner: tuple[int, int, int],
    text_pixel: tuple[int, int, int],
    planner: str,
    segments: list[dict],
) -> None:
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    audio = next(
        (stream for stream in probe["streams"] if stream["codec_type"] == "audio"),
        None,
    )
    proof_path.write_text(
        "\n".join(
            [
                "Layer Stack — real stacked render proof",
                "test: tests/core/rendering/test_layer_stack.py::"
                "test_real_stacked_render_constructed_plan_threejs_over_remotion",
                f"video.codec={video.get('codec_name')} pix_fmt={video.get('pix_fmt')} "
                f"frames={video.get('nb_read_frames')} "
                f"size={video.get('width')}x{video.get('height')}",
                f"audio.codec={None if audio is None else audio.get('codec_name')}",
                f"format.duration={probe.get('format', {}).get('duration')}",
                f"planner={planner}",
                "finalizer="
                + str(
                    sidecar.get("routing", {})
                    .get("resolved_policy", {})
                    .get("finalizer")
                ),
                f"segments={json.dumps(segments, sort_keys=True)}",
                f"corner_rgb={corner}  — media red showing through transparent threejs",
                f"text_rgb={text_pixel} — NOT media red (top composited)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _assert_stacked_output(
    output: Path,
    sidecar_path: Path,
    tmp_path: Path,
    *,
    expected_frames: int,
    expected_renderers: set[str],
    proof: bool,
) -> None:
    assert output.is_file() and output.stat().st_size > 0
    probe = _probe(output)
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert "420p" in video["pix_fmt"], video
    assert int(video["nb_read_frames"]) == expected_frames, video
    assert video["width"] == 320 and video["height"] == 180
    assert any(
        stream["codec_type"] == "audio" and stream["codec_name"] == "aac"
        for stream in probe["streams"]
    ), probe
    duration = float(probe["format"]["duration"])
    assert abs(duration - expected_frames / 24.0) < 0.15, probe

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    routing = sidecar["routing"]["resolved_policy"]
    assert routing["finalizer"] == layer_stack.COMPOSITOR_FINALIZER_ID
    segments = sidecar["segments_v2"]
    assert {segment["renderer"]["id"] for segment in segments} == expected_renderers
    by_renderer = {segment["renderer"]["id"]: segment for segment in segments}
    for renderer_id, segment in by_renderer.items():
        layer = segment["layer"]
        assert layer["blend"] == "normal"
        assert (segment["window"]["start_frame"], segment["window"]["end_frame"]) == (
            0,
            expected_frames,
        )
        if renderer_id == layer_stack.THREE_ID:
            assert layer["z"] == 1
            assert layer["tracks"] == ["overlay"]
        else:
            assert layer["z"] == 0
            assert layer["tracks"] == ["source"]

    image = _frame_rgb(output, 0, tmp_path)
    corner = image.getpixel((4, 4))
    center = image.getpixel((160, 90))
    text_hits = [
        image.getpixel((x, y))
        for x in range(80, 240, 4)
        for y in range(40, 140, 4)
        if _is_not_media(image.getpixel((x, y)))
    ]
    assert _is_media_red(corner), corner
    assert text_hits, f"no non-media pixels in the text region; center={center}"
    text_pixel = text_hits[0]
    assert _is_not_media(text_pixel), text_pixel

    if proof:
        proof_path = tmp_path / "stacked-render-proof.txt"
        _write_stacked_proof(
            proof_path=proof_path,
            output=output,
            probe=probe,
            sidecar=sidecar,
            corner=corner,
            text_pixel=text_pixel,
            planner=routing.get("planner", ""),
            segments=[
                {
                    "renderer": segment["renderer"]["id"],
                    "z": segment["layer"]["z"],
                    "tracks": segment["layer"]["tracks"],
                    "alpha_expected": segment["layer"]["z"] > 0,
                }
                for segment in segments
            ],
        )
        assert proof_path.is_file()


@pytest.mark.timeout(900)
def test_real_stacked_render_constructed_plan_threejs_over_remotion(
    tmp_path: Path,
) -> None:
    """Direct RenderPlan: threejs z=1 (alpha text) over remotion z=0 (media).

    Remotion would take the full-stack fast path, so the plan is constructed
    and executed through the public service (planner support is real; the
    plan verb returns the constructed LayerRef plan; segment renders and
    the compositor are real).
    """

    _require_stacked_environment()
    source = _red_source(tmp_path)
    timeline = _stacked_timeline()
    assets = _stacked_assets(source)
    constructed, _recorder = _plan(
        tmp_path,
        timeline,
        renderer_ids=(layer_stack.THREE_ID, layer_stack.FFMPEG_ID),
        assets=assets,
        audio="rendered",
    )
    swapped: list = []
    for segment in constructed.segments:
        if segment.renderer.id != layer_stack.FFMPEG_ID:
            swapped.append(segment)
            continue
        decision = segment.renderer.support_decision
        swapped.append(
            replace(
                segment,
                renderer=replace(
                    segment.renderer,
                    id=layer_stack.REMOTION_ID,
                    support_decision=replace(decision, backend=layer_stack.REMOTION_ID),
                ),
            )
        )
    injected = replace(
        constructed,
        segments=swapped,
        finalizer=replace(
            constructed.finalizer, id=layer_stack.COMPOSITOR_FINALIZER_ID
        ),
    )
    assert {segment.renderer.id for segment in injected.segments} == {
        layer_stack.THREE_ID,
        layer_stack.REMOTION_ID,
    }
    assert all(isinstance(segment.layer, LayerRef) for segment in injected.segments)

    request = _request(tmp_path, timeline, assets=assets, audio="rendered")
    assert injected.profile.has_audio
    renderers, planners, finalizers = load_default_registries(
        REPO_ROOT, include_installed=False
    )
    service = RenderService(
        registries=(renderers, planners, finalizers),
        transport=_InjectPlanTransport(injected),
    )
    output = tmp_path / "stacked-direct.mp4"
    with _execution_env():
        published = sdk_render(
            timeline_path=request.timeline_path,
            assets_registry_path=request.assets_registry_path,
            out_path=output,
            backend=layer_stack.BACKEND_ID,
            audio="rendered",
            service=service,
            backend_config={
                "rendering.threejs": {},
                "rendering.remotion": {},
                "rendering.ffmpeg-compositor": {"faststart": True},
            },
        )

    _assert_stacked_output(
        Path(published),
        Path(f"{published}.provenance.json"),
        tmp_path,
        expected_frames=24,
        expected_renderers={layer_stack.THREE_ID, layer_stack.REMOTION_ID},
        proof=True,
    )
    sidecar = json.loads(Path(f"{published}.provenance.json").read_text(encoding="utf-8"))
    assert sidecar["routing"]["resolved_policy"]["planner"] == layer_stack.BACKEND_ID
