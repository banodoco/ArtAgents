from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from astrid.core.media import ffprobe_metadata_strict
from astrid.core.rendering.contracts import (
    AudioOwnership,
    FinalizeRequest,
    FinalizerManifest,
    FinalizerResolution,
    FrameWindow,
    LayerRef,
    PlannerResolution,
    RenderPlan,
    RenderProfile,
    RendererResolution,
    RenderSegment,
    SCHEMA_VERSION,
    SupportReport,
    VideoArtifact,
)
from astrid.packs.rendering.finalizers.compositor import run as compositor


ROOT = Path(__file__).resolve().parents[3]
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
WIDTH = 64
HEIGHT = 64


def _profile(
    *,
    fps: tuple[int, int] = (10, 1),
    width: int = WIDTH,
    height: int = HEIGHT,
    audio: bool = True,
) -> RenderProfile:
    return RenderProfile(
        width=width,
        height=height,
        fps_rational=fps,
        time_base=(1, 10_000),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48_000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        duration_tolerance=1,
    )


def _support(backend: str) -> SupportReport:
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=True,
        reasons=[],
        features={},
        alternatives=[],
        backend=backend,
        backend_version="1.0.0",
    )


def _renderer(index: int) -> RendererResolution:
    backend = f"fixture.renderer-{index}"
    return RendererResolution(
        id=backend,
        source_pack={"id": "fixture"},
        manifest_digest=SHA_A,
        alias_chain=[],
        override=None,
        support_decision=_support(backend),
        trust_eligibility={"eligible": True},
    )


def _plan(
    profile: RenderProfile,
    *,
    total_frames: int,
    layers: list[tuple[int, int, int, float]],
) -> RenderPlan:
    segments: list[RenderSegment] = []
    for index, (z, start, end, opacity) in enumerate(layers):
        segments.append(
            RenderSegment(
                window=FrameWindow(
                    start_frame=start,
                    end_frame=end,
                    fps_rational=profile.fps_rational,
                ),
                renderer=_renderer(index),
                input_hashes={"timeline": SHA_B},
                layer=LayerRef(z=z, tracks=(f"track-{z}",), opacity=opacity),
            )
        )
    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest=SHA_C,
        requested_policy="hybrid",
        planner=PlannerResolution(
            id="fixture.planner",
            source_pack={"id": "fixture"},
            manifest_digest=SHA_A,
            trust_eligibility={"eligible": True},
        ),
        segments=segments,
        finalizer=FinalizerResolution(
            id=compositor.BACKEND_ID,
            source_pack={"id": "rendering"},
            manifest_digest=SHA_B,
            trust_eligibility={"eligible": True},
            support_decision=_support(compositor.BACKEND_ID),
        ),
        profile=profile,
        total_frames=total_frames,
        reasons={str(index): "fixture" for index in range(len(segments))},
    )


def _dummy_artifact(name: str) -> VideoArtifact:
    return VideoArtifact(
        path=f"segments/{name}",
        profile=_profile(audio=False),
        sha256=SHA_C,
        duration_frames=10,
        audio=AudioOwnership.NONE,
    )


def _support_request(tmp_path: Path, plan: RenderPlan) -> FinalizeRequest:
    return FinalizeRequest(
        schema_version=SCHEMA_VERSION,
        plan=plan,
        artifacts=[
            _dummy_artifact(f"segment-{index}.mp4")
            for index in range(len(plan.segments))
        ],
        output_name="video.mp4",
        backend_config={compositor.BACKEND_ID: {"faststart": True}},
    )


def test_manifest_registers_compositor_finalizer() -> None:
    manifest_path = (
        ROOT
        / "astrid"
        / "packs"
        / "rendering"
        / "finalizers"
        / "compositor"
        / "finalizer.yaml"
    )
    manifest = FinalizerManifest.from_dict(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )

    assert manifest.id == "rendering.ffmpeg-compositor"
    assert manifest.protocol_version == 1
    assert manifest.command == ("python3", "run.py")
    assert manifest.operations == ("finalize", "support")
    assert manifest.required_permissions == ("project_files", "subprocess")
    assert manifest.required_binaries == ("ffmpeg", "ffprobe")
    assert manifest.capabilities["containers"] == ["mp4"]
    assert manifest.capabilities["audio_ownership"] == ["rendered", "none"]
    assert manifest.capabilities["features"]["layer_compositing"] is True
    assert manifest.capabilities["features"]["straight_alpha"] is True
    assert manifest.capabilities["features"]["short_layer_padding"] is True
    assert (manifest_path.parents[2] / manifest.command[1]).is_file()

    pack = yaml.safe_load(
        (manifest_path.parents[2] / "pack.yaml").read_text(encoding="utf-8")
    )
    assert "finalizers/compositor/finalizer.yaml" in pack["extensions"][
        "rendering"
    ]["finalizers"]


def test_support_accepts_two_layer_plan(tmp_path: Path) -> None:
    profile = _profile()
    plan = _plan(profile, total_frames=10, layers=[(0, 0, 10, 1.0), (1, 0, 10, 1.0)])

    report = compositor.support(_support_request(tmp_path, plan), workspace=tmp_path)

    assert report.supported is True
    assert report.reasons == []
    assert report.backend == "rendering.ffmpeg-compositor"
    assert report.features["short_layer_padding"] is True


def test_support_rejects_layer_none_plan(tmp_path: Path) -> None:
    profile = _profile()
    plan = _plan(profile, total_frames=10, layers=[(0, 0, 10, 1.0), (1, 0, 10, 1.0)])
    # Simulate a producer that emitted an implicit (layer=None) segment.
    object.__setattr__(plan.segments[1], "layer", None)

    report = compositor.support(_support_request(tmp_path, plan), workspace=tmp_path)

    assert report.supported is False
    assert any("layer=None" in reason for reason in report.reasons)


def test_support_rejects_single_layer_plan(tmp_path: Path) -> None:
    profile = _profile()
    plan = _plan(profile, total_frames=10, layers=[(0, 0, 10, 1.0)])

    report = compositor.support(_support_request(tmp_path, plan), workspace=tmp_path)

    assert report.supported is False
    assert any("at least 2 distinct z layers" in reason for reason in report.reasons)


def test_support_rejects_blend_not_normal(tmp_path: Path) -> None:
    profile = _profile()
    plan = _plan(profile, total_frames=10, layers=[(0, 0, 10, 1.0), (1, 0, 10, 1.0)])
    # LayerRef validation rejects blend != "normal" at construction, so inject
    # the bad value the way a buggy producer could.
    object.__setattr__(plan.segments[1].layer, "blend", "screen")

    report = compositor.support(_support_request(tmp_path, plan), workspace=tmp_path)

    assert report.supported is False
    assert any("blend 'normal'" in reason for reason in report.reasons)


def test_support_rejects_duplicate_z_layer(tmp_path: Path) -> None:
    profile = _profile()
    plan = _plan(
        profile,
        total_frames=10,
        layers=[(0, 0, 5, 1.0), (0, 5, 10, 1.0), (1, 0, 10, 1.0)],
    )

    report = compositor.support(_support_request(tmp_path, plan), workspace=tmp_path)

    assert report.supported is False
    assert any("one segment per z" in reason for reason in report.reasons)


# --- synthetic media helpers (real ffmpeg) ---


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_bottom(
    path: Path,
    *,
    frames: int,
    fps: int = 10,
    color: str = "red",
    audio: bool = False,
) -> None:
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={WIDTH}x{HEIGHT}:r={fps}:d={frames / fps}",
    ]
    if audio:
        argv.extend(["-f", "lavfi", "-i", "sine=frequency=440:duration=1"])
    argv.extend(["-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if audio:
        argv.extend(["-c:a", "aac", "-b:a", "64k", "-shortest"])
    else:
        argv.append("-an")
    argv.append(str(path))
    subprocess.run(argv, check=True)


def _make_top(
    path: Path,
    *,
    frames: int,
    fps: int = 10,
    alpha_zero: bool = False,
) -> None:
    if alpha_zero:
        geq = "r=0:g=255:b=0:a=0"
    else:
        geq = (
            "r=0:g='if(lt(X,20)*lt(Y,20),255,0)':b=0:"
            "a='if(lt(X,20)*lt(Y,20),255,0)'"
        )
    argv = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={WIDTH}x{HEIGHT}:r={fps}:d={frames / fps}",
        "-vf",
        f"format=rgba,geq={geq}",
        "-frames:v",
        str(frames),
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-an",
        str(path),
    ]
    subprocess.run(argv, check=True)


def _artifact_from_file(
    tmp_path: Path,
    name: str,
    *,
    ownership: AudioOwnership,
) -> VideoArtifact:
    path = tmp_path / "segments" / name
    probe = ffprobe_metadata_strict(path)
    layout = probe.audio_channel_layout
    if layout is None and probe.audio_channels is not None:
        layout = {1: "mono", 2: "stereo"}.get(probe.audio_channels)
    profile = RenderProfile(
        width=probe.width or WIDTH,
        height=probe.height or HEIGHT,
        fps_rational=probe.fps_rational or (10, 1),
        time_base=probe.time_base or (1, 10_000),
        container=probe.container or "mp4",
        video_codec=probe.video_codec or "h264",
        video_profile=probe.video_profile,
        video_level=probe.video_level,
        pixel_format=probe.pixel_format or "yuv420p",
        audio_codec=probe.audio_codec if ownership is AudioOwnership.RENDERED else None,
        audio_sample_rate=(
            probe.audio_sample_rate if ownership is AudioOwnership.RENDERED else None
        ),
        audio_channel_layout=(
            layout if ownership is AudioOwnership.RENDERED else None
        ),
        duration_tolerance=1,
    )
    return VideoArtifact.from_file(
        path=path,
        workspace_root=tmp_path,
        profile=profile,
        duration_frames=compositor._duration_frames_from_probe(probe, profile),
        audio=ownership,
    )


def _synthetic_request(
    tmp_path: Path,
    *,
    bottom_frames: int,
    top_frames: int,
    top_alpha_zero: bool = False,
    bottom_audio: bool = False,
) -> FinalizeRequest:
    bottom = tmp_path / "segments" / "bottom.mp4"
    top = tmp_path / "segments" / "top.webm"
    bottom.parent.mkdir(parents=True, exist_ok=True)
    _make_bottom(bottom, frames=bottom_frames, audio=bottom_audio)
    _make_top(top, frames=top_frames, alpha_zero=top_alpha_zero)
    total_frames = bottom_frames
    profile = _profile(audio=True)
    plan = _plan(
        profile,
        total_frames=total_frames,
        layers=[
            (0, 0, bottom_frames, 1.0),
            (1, 0, top_frames, 1.0),
        ],
    )
    return FinalizeRequest(
        schema_version=SCHEMA_VERSION,
        plan=plan,
        artifacts=[
            _artifact_from_file(
                tmp_path,
                "bottom.mp4",
                ownership=(
                    AudioOwnership.RENDERED if bottom_audio else AudioOwnership.NONE
                ),
            ),
            _artifact_from_file(tmp_path, "top.webm", ownership=AudioOwnership.NONE),
        ],
        output_name="composite.mp4",
        backend_config={compositor.BACKEND_ID: {"faststart": True}},
    )


def _frame_pixel(path: Path, frame: int, tmp_path: Path, x: int, y: int) -> tuple[int, int, int]:
    from PIL import Image

    png = tmp_path / f"frame-{frame}.png"
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
    return Image.open(png).convert("RGB").getpixel((x, y))


def test_synthetic_composite_pixel_proof(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("real FFmpeg compositor smoke requires ffmpeg and ffprobe")

    request = _synthetic_request(tmp_path, bottom_frames=10, top_frames=10)

    result = compositor.finalize(request, workspace=tmp_path)

    output = tmp_path / result.video.path
    probe = ffprobe_metadata_strict(output)
    assert probe.video_codec == "h264"
    assert probe.pixel_format == "yuv420p"
    assert probe.audio_codec == "aac"
    # Frame-count authority: both layers cover the full window, so the naive
    # sum of per-layer windows is 20, but the output must be the plan total.
    assert sum(
        segment.window.duration_frames for segment in request.plan.segments
    ) == 20
    assert request.plan.total_frames == 10
    assert probe.frames == 10
    assert result.video.duration_frames == 10
    assert result.audio_ownership is AudioOwnership.RENDERED
    fragments = result.backend_fragments[compositor.BACKEND_ID]
    assert fragments["layer_count"] == 2
    assert [layer["z"] for layer in fragments["layers"]] == [0, 1]

    # Pixel proof: the green box region shows the top layer; a region outside
    # the box shows the opaque bottom layer through.
    assert _frame_pixel(output, 0, tmp_path, 5, 5) == (0, 254, 0)
    assert _frame_pixel(output, 0, tmp_path, 50, 50) == (252, 0, 0)


def test_short_top_layer_pads_to_plan_length(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("real FFmpeg compositor smoke requires ffmpeg and ffprobe")

    request = _synthetic_request(tmp_path, bottom_frames=10, top_frames=5)

    result = compositor.finalize(request, workspace=tmp_path)

    output = tmp_path / result.video.path
    probe = ffprobe_metadata_strict(output)
    assert probe.frames == 10
    assert result.video.duration_frames == 10
    # Oracle note: the compositor pads short layers; the top covers only the
    # first half, so the second half shows the bottom layer through.
    assert _frame_pixel(output, 0, tmp_path, 5, 5) == (0, 254, 0)
    assert _frame_pixel(output, 8, tmp_path, 5, 5) == (252, 0, 0)
    assert _frame_pixel(output, 8, tmp_path, 50, 50) == (252, 0, 0)


def test_zero_alpha_top_layer_leaves_bottom_visible(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("real FFmpeg compositor smoke requires ffmpeg and ffprobe")

    request = _synthetic_request(
        tmp_path,
        bottom_frames=10,
        top_frames=10,
        top_alpha_zero=True,
    )

    result = compositor.finalize(request, workspace=tmp_path)

    output = tmp_path / result.video.path
    probe = ffprobe_metadata_strict(output)
    assert probe.frames == 10
    # A fully transparent top layer paints nothing: the bottom shows through
    # everywhere, including the region where the transparent box would be.
    assert _frame_pixel(output, 0, tmp_path, 5, 5) == (252, 0, 0)
    assert _frame_pixel(output, 0, tmp_path, 50, 50) == (252, 0, 0)


def test_synthetic_composite_audio_from_lowest_z_segment(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("real FFmpeg compositor smoke requires ffmpeg and ffprobe")

    request = _synthetic_request(
        tmp_path,
        bottom_frames=10,
        top_frames=10,
        bottom_audio=True,
    )

    result = compositor.finalize(request, workspace=tmp_path)

    output = tmp_path / result.video.path
    probe = ffprobe_metadata_strict(output)
    assert probe.audio_codec == "aac"
    assert probe.audio_sample_rate == 48_000
    assert probe.audio_channel_layout == "stereo"
    assert result.audio_ownership is AudioOwnership.RENDERED
    assert result.backend_fragments[compositor.BACKEND_ID]["audio_source_z"] == 0


def test_recovery_cleans_staging_and_restores_previous_output(tmp_path: Path) -> None:
    if not _ffmpeg_available():
        pytest.skip("real FFmpeg compositor smoke requires ffmpeg and ffprobe")

    request = _synthetic_request(tmp_path, bottom_frames=10, top_frames=5)
    output_path = tmp_path / "outputs" / "composite.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"previous-output")
    with pytest.raises(subprocess.CalledProcessError):
        compositor.finalize(
            request,
            workspace=tmp_path,
            runner=lambda argv, **kwargs: (_ for _ in ()).throw(
                subprocess.CalledProcessError(1, argv)
            ),
        )
    # The previous output is restored and no staging directories remain.
    assert output_path.read_bytes() == b"previous-output"
    assert not list(output_path.parent.glob(".composite.mp4.ffmpeg-compositor-*"))
