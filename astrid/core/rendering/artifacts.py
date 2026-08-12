"""Strict validation for renderer and finalizer artifacts."""

from __future__ import annotations

import math
import re
import stat
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn

from astrid.core.foundation.hash import sha256_file
from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict

from .contracts import (
    Attachment,
    AudioOwnership,
    RenderProfile,
    RenderResult,
    VideoArtifact,
)
from .errors import raise_invalid_artifact_error, raise_protocol_error


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_ECMA_WHITESPACE = (
    " \t\n\r\f\v\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_BACKEND = "astrid.core"
_RECOVERY = (
    "rerun the renderer in a fresh invocation workspace and emit a contained, "
    "non-empty artifact matching the canonical render profile"
)


def _invalid(reason: str, message: str, **details: Any) -> NoReturn:
    raise_invalid_artifact_error(
        backend=_BACKEND,
        message=message,
        recovery_command=_RECOVERY,
        details={"reason": reason, **details},
    )


def _coerce_result(result: RenderResult | Mapping[str, Any]) -> RenderResult:
    if isinstance(result, RenderResult):
        return result
    if isinstance(result, Mapping):
        return RenderResult.from_dict(result)
    raise_protocol_error(
        backend=_BACKEND,
        message="render result must be a RenderResult or result mapping",
        details={"received_type": type(result).__name__},
    )


def _coerce_expected_profile(
    profile: RenderProfile | Mapping[str, Any],
) -> RenderProfile:
    try:
        if isinstance(profile, RenderProfile):
            candidate = profile
        elif isinstance(profile, Mapping):
            candidate = RenderProfile.from_dict(profile)
        else:
            raise_protocol_error(
                backend=_BACKEND,
                message="expected_profile must be a RenderProfile or profile mapping",
                details={"received_type": type(profile).__name__},
            )
        # Reconstruct solely to catch forged/mutated frozen instances.  The
        # caller's object remains authoritative and is returned untouched.
        RenderProfile.from_dict(candidate.to_dict())
    except Exception as exc:
        from .errors import RendererException

        if isinstance(exc, RendererException):
            raise
        raise_protocol_error(
            backend=_BACKEND,
            message=f"expected_profile is malformed: {exc}",
            details={"error_type": type(exc).__name__},
        )
    return candidate


def _validate_declared_profile(profile: Any) -> RenderProfile:
    if not isinstance(profile, RenderProfile):
        _invalid(
            "malformed_profile",
            "renderer video profile is not a RenderProfile",
            received_type=type(profile).__name__,
        )
    try:
        RenderProfile.from_dict(profile.to_dict())
    except Exception as exc:
        _invalid(
            "malformed_profile",
            f"renderer video profile is malformed: {exc}",
            error_type=type(exc).__name__,
        )
    return profile


def _workspace_root(path: str | Path) -> Path:
    try:
        root = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _invalid(
            "invalid_workspace",
            f"cannot resolve invocation workspace: {path}",
            workspace_root=str(path),
            error_type=type(exc).__name__,
        )
    if not root.is_dir():
        _invalid(
            "invalid_workspace",
            f"invocation workspace is not a directory: {root}",
            workspace_root=str(root),
        )
    return root


def _validate_relative_path(raw: Any, *, label: str) -> str:
    if not isinstance(raw, str):
        _invalid(
            "invalid_path",
            f"{label} must be a workspace-relative string path",
            path_type=type(raw).__name__,
        )
    if not raw or "\x00" in raw or "\\" in raw:
        _invalid("invalid_path", f"{label} is not a normalized relative path", path=raw)
    if raw.startswith("/") or raw.startswith("//") or _WINDOWS_DRIVE_RE.match(raw):
        _invalid("escaped_path", f"{label} must not be absolute", path=raw)
    parts = raw.split("/")
    if any(
        part in {"", ".", ".."} or not part.strip(_ECMA_WHITESPACE)
        for part in parts
    ):
        _invalid(
            "escaped_path",
            f"{label} contains traversal or a non-normalized component",
            path=raw,
        )
    return raw


def _contained_regular_file(raw: Any, *, root: Path, label: str) -> Path:
    relative = _validate_relative_path(raw, label=label)
    candidate = root.joinpath(*relative.split("/"))
    if candidate.is_symlink():
        _invalid(
            "escaped_path",
            f"{label} must not be a symbolic link: {relative}",
            path=relative,
        )
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _invalid(
            "missing_artifact",
            f"{label} does not resolve to an existing file: {relative}",
            path=relative,
            error_type=type(exc).__name__,
        )
    try:
        resolved.relative_to(root)
    except ValueError:
        _invalid(
            "escaped_path",
            f"{label} escapes the invocation workspace",
            path=relative,
            resolved_path=str(resolved),
            workspace_root=str(root),
        )
    try:
        mode = resolved.stat().st_mode
    except OSError as exc:
        _invalid(
            "missing_artifact",
            f"cannot inspect {label}: {relative}",
            path=relative,
            error_type=type(exc).__name__,
        )
    if not stat.S_ISREG(mode):
        _invalid(
            "invalid_file_type",
            f"{label} is not a regular file: {relative}",
            path=relative,
        )
    return resolved


def _validate_digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        _invalid(
            "invalid_hash",
            f"{label} must declare a lowercase 64-character SHA-256 digest",
            declared_sha256=value if isinstance(value, str) else None,
        )
    return value


def _verify_hash(path: Path, declared: Any, *, label: str) -> None:
    declared_hash = _validate_digest(declared, label=label)
    try:
        actual_hash = sha256_file(path)
    except OSError as exc:
        _invalid(
            "hash_failed",
            f"cannot hash {label}",
            path=str(path),
            error_type=type(exc).__name__,
        )
    if actual_hash != declared_hash:
        _invalid(
            "hash_mismatch",
            f"{label} SHA-256 does not match the declared digest",
            path=str(path),
            expected=declared_hash,
            actual=actual_hash,
        )


def _rational(value: Any, *, label: str) -> Fraction:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or type(value[0]) is not int
        or type(value[1]) is not int
        or value[0] <= 0
        or value[1] <= 0
    ):
        _invalid(
            "incomplete_probe",
            f"ffprobe did not return a valid {label}",
            actual=value,
        )
    return Fraction(value[0], value[1])


def _text(value: Any) -> str | None:
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _level(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    if normalized.isdigit() and len(normalized) >= 2:
        return f"{int(normalized[:-1])}.{normalized[-1]}"
    return normalized


def _container_matches(probe: MediaProbe, expected: str) -> bool:
    target = expected.lower().lstrip(".")
    probed_container = _text(probe.container)
    if probed_container is not None:
        return probed_container == target
    format_names = {
        item.strip().lower()
        for item in (probe.format_name or "").split(",")
        if item.strip()
    }
    return target in format_names


def _profile_value(profile: RenderProfile, field: str) -> Any:
    return getattr(profile, field)


def _same_profile_value(field: str, actual: Any, expected: Any) -> bool:
    if field in {"fps_rational", "time_base"}:
        try:
            return Fraction(*actual) == Fraction(*expected)
        except (TypeError, ValueError, ZeroDivisionError):
            return False
    if field == "video_level":
        return _level(actual) == _level(expected)
    if field in {
        "container",
        "video_codec",
        "video_profile",
        "pixel_format",
        "audio_codec",
        "audio_channel_layout",
    }:
        return _text(actual) == _text(expected)
    return actual == expected


def _compare_declared_to_expected(
    declared: RenderProfile,
    expected: RenderProfile,
    ownership: AudioOwnership,
) -> None:
    fields = (
        "width",
        "height",
        "fps_rational",
        "time_base",
        "container",
        "video_codec",
        "pixel_format",
    )
    for field in fields:
        actual_value = _profile_value(declared, field)
        expected_value = _profile_value(expected, field)
        if not _same_profile_value(field, actual_value, expected_value):
            _invalid(
                "profile_mismatch",
                f"renderer video profile has incompatible {field}",
                field=field,
                expected=expected_value,
                actual=actual_value,
            )
    for field in ("video_profile", "video_level"):
        expected_value = _profile_value(expected, field)
        if expected_value is not None and not _same_profile_value(
            field, _profile_value(declared, field), expected_value
        ):
            _invalid(
                "profile_mismatch",
                f"renderer video profile has incompatible {field}",
                field=field,
                expected=expected_value,
                actual=_profile_value(declared, field),
            )

    if ownership is AudioOwnership.RENDERED:
        if not expected.has_audio:
            _invalid(
                "audio_profile_mismatch",
                "renderer declared rendered audio for a visual-only canonical profile",
                expected_audio=False,
                actual_audio=True,
            )
        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
            if not _same_profile_value(
                field, _profile_value(declared, field), _profile_value(expected, field)
            ):
                _invalid(
                    "audio_profile_mismatch",
                    f"renderer audio profile has incompatible {field}",
                    field=field,
                    expected=_profile_value(expected, field),
                    actual=_profile_value(declared, field),
                )
    elif ownership is AudioOwnership.NONE and expected.has_audio:
        _invalid(
            "audio_profile_mismatch",
            "renderer declared no audio for a canonical profile that requires audio",
            expected_audio=True,
            actual_audio=False,
        )


def _probe_required_video(probe: MediaProbe) -> None:
    if not isinstance(probe, MediaProbe):
        _invalid(
            "incomplete_probe",
            "strict ffprobe returned an invalid probe object",
            received_type=type(probe).__name__,
        )
    if not probe.has_video_stream:
        _invalid("missing_video_stream", "primary video has no video stream")
    missing = [
        field
        for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
        if getattr(probe, field) is None
    ]
    if probe.container is None and probe.format_name is None:
        missing.append("container")
    if probe.duration_rational is None and probe.duration_seconds is None:
        missing.append("duration")
    if missing:
        _invalid(
            "incomplete_probe",
            "ffprobe returned incomplete primary-video metadata",
            missing=missing,
        )
    if type(probe.width) is not int or probe.width <= 0:
        _invalid("incomplete_probe", "ffprobe returned invalid video width", actual=probe.width)
    if type(probe.height) is not int or probe.height <= 0:
        _invalid("incomplete_probe", "ffprobe returned invalid video height", actual=probe.height)
    _rational(probe.fps_rational, label="video FPS")
    _rational(probe.time_base, label="video time base")


def _compare_probe_to_profile(
    probe: MediaProbe,
    profile: RenderProfile,
    *,
    label: str,
    compare_audio: bool,
) -> None:
    actual_values: dict[str, Any] = {
        "width": probe.width,
        "height": probe.height,
        "fps_rational": probe.fps_rational,
        "time_base": probe.time_base,
        "video_codec": probe.video_codec,
        "pixel_format": probe.pixel_format,
    }
    for field, actual in actual_values.items():
        expected = _profile_value(profile, field)
        if not _same_profile_value(field, actual, expected):
            _invalid(
                "profile_mismatch",
                f"probed video {field} does not match {label}",
                field=field,
                expected=expected,
                actual=actual,
            )
    if not _container_matches(probe, profile.container):
        _invalid(
            "profile_mismatch",
            f"probed video container does not match {label}",
            field="container",
            expected=profile.container,
            actual=probe.container or probe.format_name,
        )
    for field, actual in (
        ("video_profile", probe.video_profile),
        ("video_level", probe.video_level),
    ):
        expected = _profile_value(profile, field)
        if expected is not None and not _same_profile_value(field, actual, expected):
            _invalid(
                "profile_mismatch",
                f"probed video {field} does not match {label}",
                field=field,
                expected=expected,
                actual=actual,
            )

    if compare_audio:
        for field, actual in (
            ("audio_codec", probe.audio_codec),
            ("audio_sample_rate", probe.audio_sample_rate),
            ("audio_channel_layout", probe.audio_channel_layout),
        ):
            expected = _profile_value(profile, field)
            if field == "audio_channel_layout" and actual is None:
                # Some containers (QuickTime sowt) expose channel COUNT but
                # not a named layout. Compare channel count against the
                # declared layout's canonical count instead of failing.
                expected_channels = _layout_channel_count(expected)
                if expected_channels is None or probe.audio_channels != expected_channels:
                    _invalid(
                        "audio_profile_mismatch",
                        f"probed audio channel layout/count does not match {label}",
                        field=field,
                        expected=expected,
                        actual=actual,
                        probed_channels=probe.audio_channels,
                    )
                continue
            if not _same_profile_value(field, actual, expected):
                _invalid(
                    "audio_profile_mismatch",
                    f"probed audio {field} does not match {label}",
                    field=field,
                    expected=expected,
                    actual=actual,
                )


def _layout_channel_count(layout: str | None) -> int | None:
    return {
        "mono": 1,
        "stereo": 2,
        "5.1": 6,
        "5.1(side)": 6,
        "7.1": 8,
        "7.1(wide)": 8,
    }.get(layout or "")


def _validate_audio(
    probe: MediaProbe,
    *,
    ownership: AudioOwnership,
    declared: RenderProfile,
    expected: RenderProfile,
) -> None:
    has_audio = probe.has_audio_stream
    if has_audio:
        missing = [
            field
            for field in ("audio_codec", "audio_sample_rate")
            if getattr(probe, field) is None
        ]
        if probe.audio_channel_layout is None and probe.audio_channels is None:
            missing.append("audio_channel_layout/audio_channels")
        if missing:
            _invalid(
                "incomplete_probe",
                "ffprobe returned an audio stream with incomplete metadata",
                missing=missing,
            )

    if ownership is AudioOwnership.RENDERED and not has_audio:
        _invalid(
            "audio_ownership_mismatch",
            "renderer declared audio_ownership='rendered' but the video has no audio stream",
            declared_ownership=ownership.value,
            actual_audio_stream=False,
        )
    if ownership in {AudioOwnership.NONE, AudioOwnership.PASSTHROUGH} and has_audio:
        _invalid(
            "audio_ownership_mismatch",
            f"renderer declared audio_ownership={ownership.value!r} but the video has an audio stream",
            declared_ownership=ownership.value,
            actual_audio_stream=True,
        )
    if declared.has_audio != has_audio:
        _invalid(
            "audio_profile_mismatch",
            "declared artifact audio profile does not match probed stream presence",
            declared_audio=declared.has_audio,
            actual_audio_stream=has_audio,
        )
    if has_audio:
        _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=True)
        _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=True)


def _duration_fraction(probe: MediaProbe) -> Fraction:
    if probe.duration_rational is not None:
        try:
            duration = Fraction(*probe.duration_rational)
        except (TypeError, ValueError, ZeroDivisionError):
            _invalid(
                "incomplete_probe",
                "ffprobe returned an invalid rational duration",
                actual=probe.duration_rational,
            )
    else:
        seconds = probe.duration_seconds
        if seconds is None or not math.isfinite(seconds):
            _invalid(
                "incomplete_probe",
                "ffprobe returned an invalid duration",
                actual=seconds,
            )
        duration = Fraction(str(seconds))
    if duration < 0:
        _invalid(
            "incomplete_probe",
            "ffprobe returned a negative duration",
            actual=float(duration),
        )
    return duration


def _validate_duration(
    probe: MediaProbe,
    *,
    duration_frames: Any,
    expected: RenderProfile,
) -> None:
    if type(duration_frames) is not int or duration_frames <= 0:
        _invalid(
            "invalid_duration",
            "video artifact duration_frames must be a positive integer",
            declared_duration_frames=duration_frames,
        )
    fps = Fraction(*expected.fps_rational)
    actual_frames = _duration_fraction(probe) * fps
    delta = abs(actual_frames - duration_frames)
    if delta > expected.duration_tolerance:
        _invalid(
            "duration_mismatch",
            "probed video duration is outside the canonical frame tolerance",
            declared_duration_frames=duration_frames,
            actual_duration_frames=float(actual_frames),
            actual_duration_frames_rational=[actual_frames.numerator, actual_frames.denominator],
            tolerance_frames=expected.duration_tolerance,
        )


def _validate_attachment(
    key: Any,
    attachment: Any,
    *,
    root: Path,
) -> None:
    if not isinstance(key, str) or not _OUTPUT_NAME_RE.fullmatch(key):
        _invalid(
            "invalid_attachment",
            "attachment map key must be a portable name",
            attachment_name=key if isinstance(key, str) else None,
        )
    if not isinstance(attachment, Attachment):
        _invalid(
            "invalid_attachment",
            f"attachment {key!r} is not an Attachment",
            attachment_name=key,
            received_type=type(attachment).__name__,
        )
    if attachment.name != key or not _OUTPUT_NAME_RE.fullmatch(attachment.name):
        _invalid(
            "invalid_attachment",
            f"attachment {key!r} has an invalid or mismatched name",
            attachment_name=attachment.name,
            map_key=key,
        )
    if not isinstance(attachment.kind, str) or not _KIND_RE.fullmatch(attachment.kind):
        _invalid(
            "invalid_attachment_kind",
            f"attachment {key!r} has an invalid kind",
            attachment_name=key,
            kind=attachment.kind if isinstance(attachment.kind, str) else None,
        )
    path = _contained_regular_file(
        attachment.path,
        root=root,
        label=f"attachment {key!r} path",
    )
    _verify_hash(path, attachment.sha256, label=f"attachment {key!r}")


def _validate_result_shape(result: RenderResult) -> tuple[VideoArtifact, AudioOwnership]:
    video = result.video
    if not isinstance(video, VideoArtifact):
        _invalid(
            "malformed_artifact",
            "render result video is not a VideoArtifact",
            received_type=type(video).__name__,
        )
    ownership = result.audio_ownership
    if not isinstance(ownership, AudioOwnership):
        try:
            ownership = AudioOwnership(ownership)
        except (TypeError, ValueError):
            _invalid(
                "audio_ownership_mismatch",
                "render result has an invalid audio_ownership value",
                actual=str(result.audio_ownership),
            )
    if video.audio is not ownership:
        _invalid(
            "audio_ownership_mismatch",
            "video.audio does not match result audio_ownership",
            result_audio=ownership.value,
            video_audio=video.audio.value if isinstance(video.audio, AudioOwnership) else None,
        )
    return video, ownership


def validate_render_result(
    result: RenderResult | Mapping[str, Any],
    *,
    expected_profile: RenderProfile | Mapping[str, Any],
    workspace_root: str | Path,
) -> RenderResult:
    """Validate one renderer result before finalization or publication.

    Every artifact path is resolved inside the invocation workspace, every
    digest is recomputed, and the primary media is strictly probed.  On
    success the same :class:`RenderResult` object is returned, preserving its
    named attachments exactly as supplied.
    """

    render_result = _coerce_result(result)
    expected = _coerce_expected_profile(expected_profile)
    root = _workspace_root(workspace_root)
    video, ownership = _validate_result_shape(render_result)
    declared = _validate_declared_profile(video.profile)
    _compare_declared_to_expected(declared, expected, ownership)

    video_path = _contained_regular_file(video.path, root=root, label="primary video path")
    try:
        output_size = video_path.stat().st_size
    except OSError as exc:
        _invalid(
            "missing_artifact",
            "cannot inspect primary video size",
            path=video.path,
            error_type=type(exc).__name__,
        )
    if output_size <= 0:
        _invalid(
            "empty_artifact",
            "renderer primary video is empty",
            path=video.path,
            size=output_size,
        )
    _verify_hash(video_path, video.sha256, label="primary video")

    attachments = video.attachments
    if not isinstance(attachments, Mapping):
        _invalid(
            "invalid_attachment",
            "video attachments must be a named mapping",
            received_type=type(attachments).__name__,
        )
    for name, attachment in attachments.items():
        _validate_attachment(name, attachment, root=root)

    try:
        probe = ffprobe_metadata_strict(video_path)
    except (MediaProbeError, OSError, RuntimeError, ValueError) as exc:
        _invalid(
            "probe_failed",
            f"strict media probe failed for renderer output: {exc}",
            path=video.path,
            error_type=type(exc).__name__,
        )
    _probe_required_video(probe)
    _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=False)
    _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=False)
    _validate_audio(
        probe,
        ownership=ownership,
        declared=declared,
        expected=expected,
    )
    _validate_duration(probe, duration_frames=video.duration_frames, expected=expected)
    return render_result


__all__ = ["validate_render_result"]
