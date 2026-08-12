from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.media import MediaProbe
from astrid.core.rendering import artifacts
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    Attachment,
    AudioOwnership,
    RenderProfile,
    RenderResult,
    VideoArtifact,
)
from astrid.core.rendering.errors import RendererInvalidArtifactError


def _profile(*, audio: bool = False, tolerance: int = 1) -> RenderProfile:
    return RenderProfile(
        width=1280,
        height=720,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        duration_tolerance=tolerance,
    )


def _probe(*, audio: bool = False, duration: tuple[int, int] = (2, 1)) -> MediaProbe:
    return MediaProbe(
        duration_seconds=float(duration[0] / duration[1]),
        fps=24.0,
        resolution="1280x720",
        width=1280,
        height=720,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        video_codec="h264",
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        container="mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        duration_rational=duration,
        video_stream_present=True,
        audio_stream_present=audio,
    )


def _result(
    root: Path,
    *,
    profile: RenderProfile | None = None,
    ownership: AudioOwnership = AudioOwnership.NONE,
    path: str = "outputs/video.mp4",
    contents: bytes = b"video-bytes",
    write: bool = True,
    attachments: dict[str, Attachment] | None = None,
) -> RenderResult:
    output = root / path
    if write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(contents)
    digest = sha256_file(output) if output.is_file() else "0" * 64
    video = VideoArtifact(
        path=path,
        profile=profile or _profile(audio=ownership is AudioOwnership.RENDERED),
        sha256=digest,
        duration_frames=48,
        audio=ownership,
        attachments=attachments or {},
    )
    return RenderResult(
        schema_version=SCHEMA_VERSION,
        video=video,
        audio_ownership=ownership,
    )


def _assert_invalid(callable_: object, *, reason: str | None = None) -> RendererInvalidArtifactError:
    with pytest.raises(RendererInvalidArtifactError) as caught:
        callable_()  # type: ignore[operator]
    error = caught.value.error
    assert error.kind == "invalid_artifact"
    assert error.backend == "astrid.core"
    assert error.recovery_command
    if reason is not None:
        assert error.details["reason"] == reason
    return caught.value


def test_happy_path_preserves_named_attachment_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attachment_path = tmp_path / "outputs" / "alpha.bin"
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_bytes(b"alpha")
    attachment = Attachment(
        name="alpha",
        path="outputs/alpha.bin",
        kind="alpha",
        sha256=sha256_file(attachment_path),
    )
    result = _result(tmp_path, attachments={attachment.name: attachment})
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    validated = validate_render_result(
        result,
        expected_profile=_profile(),
        workspace_root=tmp_path,
    )

    assert validated is result
    assert validated.attachments["alpha"] is attachment


def test_missing_primary_output_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, write=False)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="missing_artifact",
    )


def test_empty_primary_output_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, contents=b"")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="empty_artifact",
    )


@pytest.mark.parametrize("bad_path", ["../video.mp4", "/tmp/video.mp4", "outputs/../video.mp4"])
def test_traversal_and_absolute_output_paths_are_rejected(
    tmp_path: Path, bad_path: str
) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video, "path", bad_path)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="escaped_path",
    )


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video-bytes")
    (workspace / "escape.mp4").symlink_to(outside)
    result = _result(workspace, path="placeholder.mp4")
    object.__setattr__(result.video, "path", "escape.mp4")
    object.__setattr__(result.video, "sha256", sha256_file(outside))

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=workspace
        ),
        reason="escaped_path",
    )


def test_primary_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video, "sha256", "f" * 64)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="hash_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 1920),
        ("height", 1080),
        ("fps_rational", (25, 1)),
        ("time_base", (1, 12800)),
        ("container", "webm"),
        ("video_codec", "hevc"),
        ("pixel_format", "yuv444p"),
    ],
)
def test_probed_video_profile_mismatches_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: replace(_probe(), **{field: value}),
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="profile_mismatch",
    )


def test_declared_profile_mismatch_is_rejected_before_probe(tmp_path: Path) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video.profile, "width", 1920)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="profile_mismatch",
    )


def test_duration_outside_tolerance_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: _probe(duration=(13, 6)),  # 52 frames, declared 48
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        ),
        reason="duration_mismatch",
    )


def test_duration_at_tolerance_boundary_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: _probe(duration=(49, 24)),  # exactly 49 frames
    )

    assert (
        validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        )
        is result
    )


def test_rendered_ownership_without_audio_stream_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile(audio=True)
    result = _result(
        tmp_path,
        profile=profile,
        ownership=AudioOwnership.RENDERED,
    )
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=profile, workspace_root=tmp_path
        ),
        reason="audio_ownership_mismatch",
    )


def test_none_ownership_with_audio_stream_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts, "ffprobe_metadata_strict", lambda _path: _probe(audio=True)
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="audio_ownership_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("audio_codec", "opus"),
        ("audio_sample_rate", 44100),
        ("audio_channel_layout", "mono"),
    ],
)
def test_rendered_audio_profile_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    profile = _profile(audio=True)
    result = _result(tmp_path, profile=profile, ownership=AudioOwnership.RENDERED)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: replace(_probe(audio=True), **{field: value}),
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=profile, workspace_root=tmp_path
        ),
        reason="audio_profile_mismatch",
    )


def test_passthrough_visual_artifact_may_target_canonical_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path, ownership=AudioOwnership.PASSTHROUGH)
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    assert (
        validate_render_result(
            result,
            expected_profile=_profile(audio=True),
            workspace_root=tmp_path,
        )
        is result
    )


def _attachment_result(tmp_path: Path) -> tuple[RenderResult, Attachment]:
    path = tmp_path / "attachments" / "data.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"attachment")
    attachment = Attachment(
        name="data",
        path="attachments/data.bin",
        kind="project",
        sha256=sha256_file(path),
    )
    return _result(tmp_path, attachments={"data": attachment}), attachment


def test_missing_attachment_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    (tmp_path / attachment.path).unlink()

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="missing_artifact",
    )


def test_invalid_attachment_path_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "path", "../data.bin")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="escaped_path",
    )


def test_invalid_attachment_kind_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "kind", "Bad Kind")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="invalid_attachment_kind",
    )


def test_attachment_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "sha256", "a" * 64)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="hash_mismatch",
    )
