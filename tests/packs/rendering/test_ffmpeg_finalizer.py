from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest
import yaml

from astrid.core.media import MediaProbe, MediaProbeError
from astrid.core.rendering.contracts import (
    Attachment,
    AudioOwnership,
    FinalizeRequest,
    FinalizerManifest,
    FinalizerResolution,
    FrameWindow,
    PlannerResolution,
    RenderPlan,
    RenderProfile,
    RendererResolution,
    RenderSegment,
    SCHEMA_VERSION,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.errors import RendererInvalidArtifactError
from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer


ROOT = Path(__file__).resolve().parents[3]
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _profile(
    *,
    fps: tuple[int, int] = (24, 1),
    time_base: tuple[int, int] | None = None,
    width: int = 1280,
    height: int = 720,
    video_codec: str = "h264",
    video_profile: str | None = None,
    video_level: str | None = None,
    pixel_format: str = "yuv420p",
    audio: bool = False,
    audio_codec: str = "aac",
    audio_sample_rate: int = 48_000,
    audio_channel_layout: str = "stereo",
) -> RenderProfile:
    if time_base is None:
        timescale = fps[0]
        while timescale < 10_000:
            timescale *= 2
        time_base = (1, timescale)
    return RenderProfile(
        width=width,
        height=height,
        fps_rational=fps,
        time_base=time_base,
        container="mp4",
        video_codec=video_codec,
        video_profile=video_profile,
        video_level=video_level,
        pixel_format=pixel_format,
        audio_codec=audio_codec if audio else None,
        audio_sample_rate=audio_sample_rate if audio else None,
        audio_channel_layout=audio_channel_layout if audio else None,
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
    segment_frames: list[int],
) -> RenderPlan:
    cursor = 0
    segments: list[RenderSegment] = []
    for index, duration in enumerate(segment_frames):
        segments.append(
            RenderSegment(
                window=FrameWindow(
                    start_frame=cursor,
                    end_frame=cursor + duration,
                    fps_rational=profile.fps_rational,
                ),
                renderer=_renderer(index),
                input_hashes={"timeline": SHA_B},
            )
        )
        cursor += duration
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
            id=ffmpeg_finalizer.BACKEND_ID,
            source_pack={"id": "rendering"},
            manifest_digest=SHA_B,
            trust_eligibility={"eligible": True},
            support_decision=_support(ffmpeg_finalizer.BACKEND_ID),
        ),
        profile=profile,
        total_frames=cursor,
        reasons={str(index): "fixture" for index in range(len(segments))},
    )


def _artifact(
    tmp_path: Path,
    index: int,
    *,
    profile: RenderProfile,
    duration_frames: int,
    audio: AudioOwnership,
    attachments: dict[str, Attachment] | None = None,
) -> VideoArtifact:
    path = tmp_path / "segments" / f"segment-{index}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"segment-{index}".encode())
    return VideoArtifact.from_file(
        path=path,
        workspace_root=tmp_path,
        profile=profile,
        duration_frames=duration_frames,
        audio=audio,
        attachments=attachments,
    )


def _request(
    tmp_path: Path,
    *,
    canonical: RenderProfile,
    artifact_profiles: list[RenderProfile] | None = None,
    artifact_frames: list[int] | None = None,
    segment_frames: list[int] | None = None,
    ownerships: list[AudioOwnership] | None = None,
    attachments: dict[str, Attachment] | None = None,
) -> FinalizeRequest:
    segment_frames = segment_frames or [24]
    artifact_profiles = artifact_profiles or [canonical]
    artifact_frames = artifact_frames or list(segment_frames)
    ownerships = ownerships or [
        AudioOwnership.RENDERED if profile.has_audio else AudioOwnership.NONE
        for profile in artifact_profiles
    ]
    artifacts = [
        _artifact(
            tmp_path,
            index,
            profile=profile,
            duration_frames=artifact_frames[index],
            audio=ownerships[index],
            attachments=attachments if index == 0 else None,
        )
        for index, profile in enumerate(artifact_profiles)
    ]
    return FinalizeRequest(
        schema_version=SCHEMA_VERSION,
        plan=_plan(canonical, segment_frames),
        artifacts=artifacts,
        output_name="video.mp4",
        backend_config={ffmpeg_finalizer.BACKEND_ID: {"faststart": True}},
        metadata={"case": "fixture"},
    )


def _fake_runner(commands: list[list[str]], *, fail_concat: bool = False):
    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs == {"check": True}
        commands.append(list(argv))
        output = Path(argv[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"ffmpeg-output")
        if fail_concat and "concat" in argv:
            raise subprocess.CalledProcessError(1, argv)
        return subprocess.CompletedProcess(argv, 0)

    return run


def _fake_preflight_probe(request: FinalizeRequest, tmp_path: Path):
    artifacts = {
        str((tmp_path / artifact.path).resolve()): artifact
        for artifact in request.artifacts
    }

    def probe(path: str | Path) -> MediaProbe:
        artifact = artifacts[str(Path(path).resolve())]
        profile = artifact.profile
        return MediaProbe(
            width=profile.width,
            height=profile.height,
            fps_rational=profile.fps_rational,
            time_base=profile.time_base,
            video_codec=profile.video_codec,
            video_profile=profile.video_profile or "High",
            video_level=profile.video_level or "40",
            pixel_format=profile.pixel_format,
            audio_codec=profile.audio_codec,
            audio_sample_rate=profile.audio_sample_rate,
            audio_channel_layout=profile.audio_channel_layout,
            container=profile.container,
            video_stream_present=True,
            audio_stream_present=profile.has_audio,
            audio_channels=2 if profile.has_audio else None,
        )

    return probe


def _finalize_without_real_media(
    request: FinalizeRequest,
    tmp_path: Path,
    commands: list[list[str]],
    *,
    runner=None,
):
    validate = mock.patch.object(
        ffmpeg_finalizer,
        "validate_render_result",
        side_effect=lambda result, **_kwargs: result,
    )
    normalized_probe = mock.patch.object(
        ffmpeg_finalizer,
        "_probe_normalized_segments",
    )
    strict_probe = mock.patch.object(
        ffmpeg_finalizer,
        "ffprobe_metadata_strict",
        side_effect=_fake_preflight_probe(request, tmp_path),
    )
    with validate, strict_probe, normalized_probe:
        return ffmpeg_finalizer.finalize(
            request,
            workspace=tmp_path,
            runner=runner or _fake_runner(commands),
        )


def test_manifest_registers_static_raw_command_finalizer() -> None:
    manifest_path = (
        ROOT
        / "astrid"
        / "packs"
        / "rendering"
        / "finalizers"
        / "ffmpeg"
        / "finalizer.yaml"
    )
    manifest = FinalizerManifest.from_dict(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )

    assert manifest.id == "rendering.ffmpeg-finalizer"
    assert manifest.protocol_version == 1
    assert manifest.command == ("python3", "run.py")
    assert manifest.operations == ("finalize", "support")
    assert manifest.required_permissions == ("project_files", "subprocess")
    assert manifest.required_binaries == ("ffmpeg", "ffprobe")
    assert manifest.capabilities["preserves_attachments"] is True
    assert manifest.capabilities["containers"] == ["mp4"]
    assert manifest.capabilities["audio_ownership"] == [
        "rendered",
        "passthrough",
        "none",
    ]
    assert (manifest_path.parents[2] / manifest.command[1]).is_file()

    pack = yaml.safe_load(
        (manifest_path.parents[2] / "pack.yaml").read_text(encoding="utf-8")
    )
    assert "finalizers/ffmpeg/finalizer.yaml" in pack["extensions"][
        "rendering"
    ]["finalizers"]


def test_single_compatible_segment_is_stream_copied_without_reencode(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, canonical=_profile(), segment_frames=[24])
    commands: list[list[str]] = []

    result = _finalize_without_real_media(request, tmp_path, commands)

    assert len(commands) == 1
    assert commands[0][commands[0].index("-c") + 1] == "copy"
    assert "libx264" not in commands[0]
    assert result.normalization == []
    assert result.video.duration_frames == 24


def test_mixed_compatible_and_incompatible_segments_normalize_only_mismatch(
    tmp_path: Path,
) -> None:
    canonical = _profile()
    incompatible = replace(canonical, width=640, video_codec="hevc")
    request = _request(
        tmp_path,
        canonical=canonical,
        artifact_profiles=[canonical, incompatible],
        segment_frames=[24, 24],
    )
    commands: list[list[str]] = []

    result = _finalize_without_real_media(request, tmp_path, commands)

    assert len(commands) == 2
    normalize, concat = commands
    assert normalize[normalize.index("-c:v") + 1] == "libx264"
    assert concat[concat.index("-c") + 1] == "copy"
    assert result.backend_fragments[ffmpeg_finalizer.BACKEND_ID][
        "stream_copied_segments"
    ] == [0]
    assert result.backend_fragments[ffmpeg_finalizer.BACKEND_ID][
        "normalized_segments"
    ] == [1]
    assert "segment[1] width: 640 -> 1280" in result.normalization
    assert "segment[1] video_codec: hevc -> h264" in result.normalization


@pytest.mark.parametrize(
    "fps",
    [(24, 1), (25, 1), (30, 1), (30_000, 1001)],
)
def test_normalization_uses_exact_canonical_rational_fps(
    tmp_path: Path,
    fps: tuple[int, int],
) -> None:
    target = _profile(fps=fps)
    source = _profile(fps=(60, 1), time_base=(1, 60_000))
    path = tmp_path / "segment.mp4"
    segment = ffmpeg_finalizer._PreparedSegment(
        index=0,
        path=path,
        profile=source,
        audio=AudioOwnership.NONE,
        duration_frames=60,
    )
    differences = ffmpeg_finalizer._profile_differences(source, target)

    argv = ffmpeg_finalizer.build_normalize_command(
        segment,
        tmp_path / "normalized.mp4",
        target_profile=target,
        differences=differences,
        faststart=True,
    )
    filters = argv[argv.index("-vf") + 1]
    rational = f"{fps[0]}/{fps[1]}"

    assert f"fps={rational}" in filters
    assert argv[argv.index("-r:v") + 1] == rational
    assert f"settb=expr={target.time_base[0]}/{target.time_base[1]}" in filters


def test_duration_error_is_rejected_before_any_assembly_command(
    tmp_path: Path,
) -> None:
    canonical = _profile(fps=(24, 1))
    source = _profile(fps=(25, 1))
    request = _request(
        tmp_path,
        canonical=canonical,
        artifact_profiles=[source],
        artifact_frames=[50],
        segment_frames=[24],
    )
    runner = mock.Mock()

    with mock.patch.object(
        ffmpeg_finalizer,
        "validate_render_result",
        side_effect=lambda result, **_kwargs: result,
    ):
        with pytest.raises(RendererInvalidArtifactError, match="duration"):
            ffmpeg_finalizer.finalize(
                request,
                workspace=tmp_path,
                runner=runner,
            )

    runner.assert_not_called()


def test_missing_video_and_rendered_audio_are_rejected() -> None:
    with pytest.raises(MediaProbeError, match="no video stream"):
        ffmpeg_finalizer._profile_from_probe(
            MediaProbe(
                video_stream_present=False,
                audio_stream_present=False,
            ),
            ownership=AudioOwnership.NONE,
            duration_tolerance=1,
        )

    with pytest.raises(MediaProbeError, match="required audio stream"):
        ffmpeg_finalizer._profile_from_probe(
            MediaProbe(
                width=1280,
                height=720,
                fps_rational=(24, 1),
                time_base=(1, 12_288),
                container="mp4",
                video_codec="h264",
                pixel_format="yuv420p",
                video_stream_present=True,
                audio_stream_present=False,
            ),
            ownership=AudioOwnership.RENDERED,
            duration_tolerance=1,
        )


def test_codec_mismatch_records_normalization_and_reencodes(tmp_path: Path) -> None:
    canonical = _profile(video_codec="h264")
    request = _request(
        tmp_path,
        canonical=canonical,
        artifact_profiles=[replace(canonical, video_codec="hevc")],
    )
    commands: list[list[str]] = []

    result = _finalize_without_real_media(request, tmp_path, commands)

    assert commands[0][commands[0].index("-c:v") + 1] == "libx264"
    assert result.normalization == ["segment[0] video_codec: hevc -> h264"]


def test_unspecified_canonical_profile_normalizes_concrete_stream_mismatch(
    tmp_path: Path,
) -> None:
    canonical = _profile()
    request = _request(
        tmp_path,
        canonical=canonical,
        artifact_profiles=[
            replace(canonical, video_profile="High", video_level="40"),
            replace(canonical, video_profile="Main", video_level="31"),
        ],
        segment_frames=[24, 24],
    )
    commands: list[list[str]] = []

    result = _finalize_without_real_media(request, tmp_path, commands)

    assert result.backend_fragments[ffmpeg_finalizer.BACKEND_ID][
        "stream_copied_segments"
    ] == [0]
    assert "segment[1] video_profile: Main -> High" in result.normalization
    assert "segment[1] video_level: 31 -> 40" in result.normalization


@pytest.mark.parametrize(
    ("canonical_audio", "source_audio", "ownership", "expected"),
    [
        (True, True, AudioOwnership.RENDERED, AudioOwnership.RENDERED),
        (True, False, AudioOwnership.PASSTHROUGH, AudioOwnership.PASSTHROUGH),
        (False, False, AudioOwnership.NONE, AudioOwnership.NONE),
    ],
)
def test_audio_rendered_passthrough_and_none_modes(
    tmp_path: Path,
    canonical_audio: bool,
    source_audio: bool,
    ownership: AudioOwnership,
    expected: AudioOwnership,
) -> None:
    canonical = _profile(audio=canonical_audio)
    source = _profile(audio=source_audio)
    request = _request(
        tmp_path,
        canonical=canonical,
        artifact_profiles=[source],
        ownerships=[ownership],
    )
    commands: list[list[str]] = []

    result = _finalize_without_real_media(request, tmp_path, commands)

    assert result.audio_ownership is expected
    assert result.video.audio is expected
    concat = commands[-1]
    if expected is AudioOwnership.RENDERED:
        assert "0:a:0" in concat
        assert "-an" not in concat
        assert result.video.profile.has_audio is True
    else:
        assert "-an" in concat
        assert not any("anullsrc" in item for item in concat)
        assert result.video.profile.has_audio is False


def test_attachments_are_preserved_without_interpretation(tmp_path: Path) -> None:
    attachment_path = tmp_path / "attachments" / "project.blend"
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_bytes(b"opaque-project-data")
    attachment = Attachment.from_file(
        name="project.blend",
        path=attachment_path,
        kind="project",
        workspace_root=tmp_path,
    )
    request = _request(
        tmp_path,
        canonical=_profile(),
        attachments={attachment.name: attachment},
    )
    commands: list[list[str]] = []

    result = _finalize_without_real_media(request, tmp_path, commands)

    assert result.attachments == {attachment.name: attachment}
    assert attachment_path.read_bytes() == b"opaque-project-data"


def test_failure_cleans_partial_output_and_owned_temp_directories(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, canonical=_profile())
    commands: list[list[str]] = []
    runner = _fake_runner(commands, fail_concat=True)

    with pytest.raises(subprocess.CalledProcessError):
        _finalize_without_real_media(
            request,
            tmp_path,
            commands,
            runner=runner,
        )

    assert not (tmp_path / "outputs" / "video.mp4").exists()
    assert not list((tmp_path / "outputs").glob(".video.mp4.ffmpeg-finalizer-*"))


def test_failure_restores_preexisting_output(tmp_path: Path) -> None:
    request = _request(tmp_path, canonical=_profile())
    output = tmp_path / "outputs" / "video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"previous-output")
    commands: list[list[str]] = []

    with pytest.raises(subprocess.CalledProcessError):
        _finalize_without_real_media(
            request,
            tmp_path,
            commands,
            runner=_fake_runner(commands, fail_concat=True),
        )

    assert output.read_bytes() == b"previous-output"
    assert not list(output.parent.glob(".video.mp4.ffmpeg-finalizer-*"))


def test_raw_adapter_writes_finalize_result(tmp_path: Path) -> None:
    request = _request(tmp_path, canonical=_profile())
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
    commands: list[list[str]] = []

    with (
        mock.patch.object(
            ffmpeg_finalizer,
            "validate_render_result",
            side_effect=lambda result, **_kwargs: result,
        ),
        mock.patch.object(ffmpeg_finalizer, "_probe_normalized_segments"),
        mock.patch.object(
            ffmpeg_finalizer,
            "ffprobe_metadata_strict",
            side_effect=_fake_preflight_probe(request, tmp_path),
        ),
        mock.patch.object(
            ffmpeg_finalizer.subprocess,
            "run",
            side_effect=_fake_runner(commands),
        ),
    ):
        assert ffmpeg_finalizer.main(
            [
                "finalize",
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ]
        ) == 0

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["audio_ownership"] == "none"
    assert payload["backend_fragments"][ffmpeg_finalizer.BACKEND_ID][
        "finalizer_kind"
    ] == "ffmpeg"
