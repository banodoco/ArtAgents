#!/usr/bin/env python3
"""Three.js timeline renderer and raw rendering-protocol v1 command adapter.

``rendering.threejs`` is a thin backend that renders complete Astrid
timelines through the ``ThreeTimelineComposition`` in the Remotion project
(three.js canvas, deterministic frame clock, texture text planes).  It has
its OWN identity and provenance (``engine="threejs"``, never claims
``rendering.remotion``) while reusing the Remotion backend's execution
helper and the shared Remotion render lock.

The public ``support``/``_protocol_render`` functions are the protocol-v1
surface used by the generic renderer transport: the command-line entry
point reads one request file and writes exactly one result or structured
error file, mirroring the Remotion and HyperFrames backends.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

# Raw renderer commands are deliberately executable without an installed
# Astrid wheel.  The command transport sanitizes PYTHONPATH, so direct script
# execution must make the owning checkout importable before SDK imports.
if __package__ in {None, ""}:
    _CHECKOUT_ROOT = Path(__file__).resolve().parents[5]
    if str(_CHECKOUT_ROOT) not in sys.path:
        sys.path.insert(0, str(_CHECKOUT_ROOT))

from astrid.core import timeline
from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.errors import (
    RendererException,
    make_renderer_error,
    raise_unsupported_error,
)
from astrid.packs.rendering.backends.remotion import run as remotion_backend

# Reuse seam (T3.3): only the side-effect-free execution/provenance helpers.
# The shared Remotion render lock is acquired inside ``_execute_remotion``;
# this backend never adds a second lock or capture stack.
_execute_remotion = remotion_backend._execute_remotion
_render_provenance_payload = remotion_backend._render_provenance_payload
_serialize_timeline = remotion_backend._serialize_timeline
_load_registry_mapping = remotion_backend._load_registry_mapping
_input_path = remotion_backend._input_path
_duration_frames = remotion_backend._duration_frames
_canonical_profile = remotion_backend._canonical_profile


BACKEND_ID = "rendering.threejs"
BACKEND_VERSION = "1.0.0"
THREE_COMPOSITION_ID = "ThreeTimelineComposition"
THREE_VERSION = "0.185.1"

_DEFAULT_PROJECT_DIR = REPO_ROOT / "remotion"
# Own-namespace config keys honored by support (render v1 takes no config).
_CONFIG_KEYS = frozenset({"project_dir", "theme_path", "min_free_gb"})

# The exact field set the ThreeTimelineComposition maps (composition contract):
# text.content/fontSize/color/align/bold and
# params.anchor/offsetX/offsetY/textShadow/maxWidth/weight.
_TEXT_TEXT_KEYS = frozenset({"content", "fontSize", "color", "align", "bold"})
_TEXT_PARAM_KEYS = frozenset(
    {"anchor", "offsetX", "offsetY", "textShadow", "maxWidth", "weight"}
)
_SUPPORTED_CLIP_TYPES = frozenset({"text"})


@dataclass(frozen=True)
class _ThreeSettings:
    project_dir: Path
    theme_path: Path | None
    min_free_gb: float | None


# ---------------------------------------------------------------------------
# Pure timeline eligibility helpers
# ---------------------------------------------------------------------------


def _canvas(timeline: Mapping[str, Any]) -> tuple[int, int, int] | None:
    overrides = timeline.get("theme_overrides") or {}
    visual = overrides.get("visual") or {}
    canvas = visual.get("canvas") or {}
    width = canvas.get("width")
    height = canvas.get("height")
    fps = canvas.get("fps")
    if not all(isinstance(v, int) and v > 0 for v in (width, height, fps)):
        return None
    return int(width), int(height), int(fps)


def _effective_gain(clip: Mapping[str, Any], tracks: Sequence[Any]) -> float:
    """Exact timeline gain for a text clip, 0..1.

    Text clips declare no audio by default, so a missing volume is silent
    (0.0), unlike media clips.  An explicit clip/track volume or an unmuted
    track with volume declares audible content, which the visual-only
    composition would silently drop.
    """
    track_id = clip.get("track")
    track = next(
        (
            t
            for t in tracks
            if isinstance(t, dict) and t.get("id") == track_id
        ),
        None,
    )
    if isinstance(track, dict) and track.get("muted") is True:
        return 0.0
    track_volume = track.get("volume") if isinstance(track, dict) else None
    track_gain = float(track_volume) if track_volume is not None else 0.0
    clip_volume = clip.get("volume")
    clip_gain = float(clip_volume) if clip_volume is not None else 0.0
    return max(0.0, min(1.0, max(track_gain, clip_gain)))


def _support_reasons(
    timeline_data: Mapping[str, Any],
    registry: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return stable, clip-specific reasons this serialized timeline is
    unsupported by the Three.js composition (text clips only, visual-only,
    exact text field set, background/empty accepted)."""
    reasons: list[str] = []
    tracks = timeline_data.get("tracks") or []
    clips = timeline_data.get("clips") or []
    audio_tracks = [
        track.get("id")
        for track in tracks
        if isinstance(track, dict) and track.get("kind") == "audio"
    ]
    if audio_tracks:
        reasons.append(
            "audio tracks are not supported by the Three.js renderer: "
            + str(audio_tracks)
        )
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            reasons.append(f"clip[{index}] is not an object")
            continue
        clip_type = clip.get("clipType", "media")
        if clip_type not in _SUPPORTED_CLIP_TYPES:
            reasons.append(
                f"clip[{index}] clipType {clip_type!r} is not supported "
                "(text clips only)"
            )
        if clip.get("track") in audio_tracks:
            reasons.append(f"clip[{index}] sits on an audio track")
        if clip.get("effects"):
            reasons.append(f"clip[{index}] effects are not supported in v1")
        if clip.get("transition"):
            reasons.append(f"clip[{index}] transitions are not supported in v1")
        if clip.get("animation"):
            reasons.append(f"clip[{index}] animation is not supported in v1")
        if clip.get("opacity") not in (None, 1):
            reasons.append(f"clip[{index}] opacity != 1 is not supported in v1")
        if _effective_gain(clip, tracks) > 0:
            reasons.append(
                f"clip[{index}] carries audio; the Three.js renderer is "
                "visual-only in v1 (set clip/track volume to 0)"
            )
        text_field = clip.get("text")
        if text_field is not None and not isinstance(text_field, dict):
            reasons.append(f"clip[{index}] text must be an object")
        elif isinstance(text_field, dict):
            unknown_text = sorted(set(text_field) - _TEXT_TEXT_KEYS)
            if unknown_text:
                reasons.append(
                    f"clip[{index}] unsupported text fields: {unknown_text}"
                )
        params = clip.get("params")
        if params is not None and not isinstance(params, dict):
            reasons.append(f"clip[{index}] params must be an object")
        elif isinstance(params, dict):
            unknown_params = sorted(set(params) - _TEXT_PARAM_KEYS)
            if unknown_params:
                reasons.append(
                    f"clip[{index}] unsupported text params: {unknown_params}"
                )
    if _canvas(timeline_data) is None:
        reasons.append("canvas width/height/fps must be positive integers")
    return reasons


# ---------------------------------------------------------------------------
# Environment / project preflight
# ---------------------------------------------------------------------------


def _threejs_project_reasons(project_dir: Path) -> list[str]:
    reasons: list[str] = []
    if not project_dir.exists():
        reasons.append(f"Remotion project directory not found: {project_dir}")
        return reasons
    package_json = project_dir / "package.json"
    if not package_json.exists():
        reasons.append(f"Remotion project is missing package.json: {package_json}")
    node_modules = project_dir / "node_modules"
    if not node_modules.is_dir():
        reasons.append(
            f"Remotion project is missing node_modules: {node_modules} "
            "(run `npm install` in remotion/ first)"
        )
        return reasons
    for package in ("three", "@remotion/three", "@react-three/fiber"):
        if not (node_modules / package).is_dir():
            reasons.append(
                f"missing node_modules/{package} (required by the Three.js "
                "composition; run `npm install` in remotion/ first)"
            )
    return reasons


def _binaries_reasons() -> list[str]:
    return [
        f"required binary is unavailable: {binary}"
        for binary in ("node", "npx", "ffprobe")
        if shutil.which(binary) is None
    ]


# ---------------------------------------------------------------------------
# Own-namespace settings (never reads the rendering.remotion namespace)
# ---------------------------------------------------------------------------


def _settings_from_request(request: RenderRequest, workspace: Path) -> _ThreeSettings:
    config = dict(request.backend_config.get(BACKEND_ID, {}))
    unknown = sorted(set(config) - _CONFIG_KEYS)
    if unknown:
        raise ValueError(f"unknown {BACKEND_ID} configuration: {', '.join(unknown)}")

    project_value = config.get("project_dir", _DEFAULT_PROJECT_DIR)
    if not isinstance(project_value, (str, os.PathLike)):
        raise TypeError("project_dir must be a path string")
    project_dir = _input_path(os.fspath(project_value), workspace)

    theme_value = config.get("theme_path")
    if theme_value is None:
        theme_path = None
    elif isinstance(theme_value, (str, os.PathLike)):
        theme_path = _input_path(os.fspath(theme_value), workspace)
    else:
        raise TypeError("theme_path must be a path string or null")

    min_free_value = config.get("min_free_gb")
    if min_free_value is None:
        min_free_gb = None
    elif isinstance(min_free_value, bool) or not isinstance(min_free_value, (int, float)):
        raise TypeError("min_free_gb must be a number or null")
    else:
        min_free_gb = float(min_free_value)
        if min_free_gb < 0:
            raise ValueError("min_free_gb must not be negative")

    return _ThreeSettings(
        project_dir=project_dir,
        theme_path=theme_path,
        min_free_gb=min_free_gb,
    )


def _default_settings() -> _ThreeSettings:
    return _ThreeSettings(
        project_dir=_DEFAULT_PROJECT_DIR,
        theme_path=None,
        min_free_gb=None,
    )


# ---------------------------------------------------------------------------
# Profile contract (90 kHz timescale + always-muxed AAC, same as Remotion)
# ---------------------------------------------------------------------------


def _profile_mismatches(
    requested: RenderProfile,
    canonical: RenderProfile,
) -> list[str]:
    requested_data = requested.to_dict()
    canonical_data = canonical.to_dict()
    mismatches: list[str] = []
    for field, expected in canonical_data.items():
        if field == "duration_tolerance":
            continue
        actual = requested_data[field]
        if actual != expected:
            mismatches.append(f"{field}={actual!r} (requires {expected!r})")
    return mismatches


def _render_declared_profile(canonical: RenderProfile) -> RenderProfile:
    declared = replace(canonical, time_base=(1, 90000))
    return replace(
        declared,
        audio_codec=declared.audio_codec or "aac",
        audio_sample_rate=declared.audio_sample_rate or 48000,
        audio_channel_layout=declared.audio_channel_layout or "stereo",
    )


# ---------------------------------------------------------------------------
# Protocol surface: support + render
# ---------------------------------------------------------------------------


def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
    """Return request-specific evidence for what the Three.js renderer can do."""

    reasons: list[str] = []
    features: dict[str, bool | str] = {
        "webgl": True,
        "textured_text_planes": True,
        "background_only": True,
        "deterministic_frame_clock": True,
        "capture_host": "remotion",
        "media_textures": False,
        "effects": False,
        "transitions": False,
        "full_timeline": True,
        "windows": False,
    }

    try:
        settings = _settings_from_request(request, workspace)
    except (TypeError, ValueError) as exc:
        settings = _default_settings()
        reasons.append(str(exc))

    if request.window is not None:
        reasons.append(
            "rendering.threejs accepts complete timelines, not native frame windows"
        )

    timeline_path = _input_path(request.timeline_path, workspace)
    assets_path = (
        _input_path(request.assets_registry_path, workspace)
        if request.assets_registry_path is not None
        else None
    )
    timeline_data: dict[str, Any] | None = None
    assets_data: dict[str, Any] | None = None
    try:
        timeline_data = _serialize_timeline(timeline_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        reasons.append(f"timeline is not renderable: {exc}")
    try:
        assets_data = _load_registry_mapping(assets_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        reasons.append(f"assets registry is not renderable: {exc}")

    if timeline_data is not None:
        reasons.extend(_support_reasons(timeline_data, assets_data))

    if timeline_data is not None and assets_data is not None:
        # The composition ignores audio content; Remotion still muxes an
        # (enforced) AAC track, so ownership is always 'rendered'.
        features["audio_ownership"] = AudioOwnership.RENDERED.value
        if request.audio is not None and request.audio is not AudioOwnership.RENDERED:
            reasons.append(
                f"audio={request.audio.value!r} is incompatible with the "
                "Three.js renderer's always-rendered audio output"
            )
        if request.profile is not None:
            try:
                canonical = _canonical_profile(timeline_path, assets_data, settings)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                reasons.append(f"canonical Three.js profile cannot be resolved: {exc}")
            else:
                mismatches = _profile_mismatches(
                    request.profile, _render_declared_profile(canonical)
                )
                if mismatches:
                    reasons.append(
                        "requested profile is not produced by the Three.js "
                        "renderer: " + "; ".join(mismatches)
                    )

    reasons.extend(_threejs_project_reasons(settings.project_dir))
    reasons.extend(_binaries_reasons())

    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=not reasons,
        reasons=reasons,
        features=features,
        alternatives=[],
        backend=BACKEND_ID,
        backend_version=BACKEND_VERSION,
    )


def _protocol_render(request: RenderRequest, *, workspace: Path) -> RenderResult:
    # Render re-validates everything itself; it never trusts a prior support
    # verdict.
    if request.window is not None:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="Three.js renderer does not support native frame windows",
            recovery_command="render complete timelines only",
            details={"window": request.window.to_dict()},
        )
    # v1 render takes no backend configuration (plan: reject non-empty
    # own-namespace backend_config); unknown keys fail loudly.
    own_config = request.backend_config.get(BACKEND_ID)
    if own_config:
        try:
            _settings_from_request(request, workspace)
        except (TypeError, ValueError) as exc:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message="invalid rendering.threejs configuration",
                recovery_command="remove rendering.threejs backend_config for v1 renders",
                details={"config_error": str(exc)},
            )
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="rendering.threejs v1 renders accept no backend_config",
            recovery_command="remove rendering.threejs backend_config and retry",
            details={"backend_config": dict(own_config)},
        )
    settings = _default_settings()

    timeline_path = _input_path(request.timeline_path, workspace)
    requested_assets_path = (
        _input_path(request.assets_registry_path, workspace)
        if request.assets_registry_path is not None
        else None
    )

    try:
        timeline_data = _serialize_timeline(timeline_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="timeline is not renderable by the Three.js renderer",
            recovery_command="resolve the reported timeline problem and retry",
            details={"error": str(exc)},
        )
    reasons = _support_reasons(timeline_data, None)
    if reasons:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="Three.js renderer does not support this render request",
            recovery_command="resolve the reported support reasons and retry",
            details={"reasons": reasons},
        )
    project_reasons = _threejs_project_reasons(settings.project_dir)
    if project_reasons:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="Three.js render environment is not available",
            recovery_command="install remotion project dependencies and retry",
            details={"reasons": project_reasons},
        )
    binary_reasons = _binaries_reasons()
    if binary_reasons:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="required binary is unavailable",
            recovery_command="install the missing binary and retry",
            details={"reasons": binary_reasons},
        )

    outputs_dir = workspace / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / request.output_name

    with ExitStack() as lifecycle:
        if requested_assets_path is None:
            empty_assets_tmp = lifecycle.enter_context(
                TemporaryDirectory(
                    prefix=".threejs-empty-assets-", dir=str(workspace)
                )
            )
            assets_path = Path(empty_assets_tmp) / "assets.json"
            timeline.save_registry({"assets": {}}, assets_path)
        else:
            assets_path = requested_assets_path
        assets_data = _load_registry_mapping(assets_path)
        canonical = _canonical_profile(timeline_path, assets_data, settings)
        declared_profile = _render_declared_profile(request.profile or canonical)
        ownership = AudioOwnership.RENDERED
        private_tmp = lifecycle.enter_context(
            TemporaryDirectory(
                prefix=f".{request.output_name}.threejs-",
                dir=str(outputs_dir),
            )
        )
        staged_video = Path(private_tmp) / request.output_name
        details = _execute_remotion(
            timeline_path,
            assets_path,
            staged_video,
            provenance_out_path=output_path,
            project_dir=settings.project_dir,
            composition_id=THREE_COMPOSITION_ID,
            theme_path=settings.theme_path,
            min_free_gb=settings.min_free_gb,
        )
        output_path.unlink(missing_ok=True)
        os.replace(staged_video, output_path)

    try:
        provenance_v1 = _render_provenance_payload(
            output_path,
            engine="threejs",
            timeline_path=timeline_path,
            assets_path=requested_assets_path or assets_path,
            project_dir=settings.project_dir,
            composition_id=THREE_COMPOSITION_ID,
            theme_path=settings.theme_path,
            active_theme=details.active_theme,
            registry_state=details.registry_state,
            stage_summary=details.stage_summary,
        )
        video = VideoArtifact.from_file(
            path=output_path,
            workspace_root=workspace,
            profile=declared_profile,
            duration_frames=_duration_frames(output_path, declared_profile),
            audio=ownership,
        )
        result = RenderResult(
            schema_version=SCHEMA_VERSION,
            video=video,
            audio_ownership=ownership,
            backend_fragments={
                BACKEND_ID: {
                    "renderer": "threejs",
                    "renderer_version": BACKEND_VERSION,
                    "three_version": THREE_VERSION,
                    "capture_host": "remotion",
                    "composition": THREE_COMPOSITION_ID,
                    "legacy_v1": provenance_v1,
                }
            },
            normalization=[],
            logs=[],
            metadata=request.metadata,
        )
        validate_render_result(
            result,
            expected_profile=declared_profile,
            workspace_root=workspace,
        )
        return result
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Raw protocol v1 command entrypoint
# ---------------------------------------------------------------------------


def _load_request(path: Path) -> RenderRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("render request must contain a JSON object")
    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)


def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
    if isinstance(exc, RendererException):
        error_kind = exc.error.kind
        message = exc.error.message
        recovery = exc.error.recovery_command
        details = exc.error.details
    else:
        error_kind = kind
        message = str(exc) or type(exc).__name__
        recovery = None
        details = {"error_type": type(exc).__name__}
    error = make_renderer_error(
        error_kind,
        backend=BACKEND_ID,
        message=message,
        recovery_command=recovery,
        details=details,
    )
    write_json_atomic(result_path, error.to_dict())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=("render", "support"))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        request_path = args.request.resolve(strict=True)
        result_path = args.result.resolve()
        if request_path == result_path:
            raise ValueError("--request and --result must be different paths")
        request = _load_request(request_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, RendererException) as exc:
        _write_failure(args.result.resolve(), exc, kind="protocol")
        return 0

    try:
        workspace = request_path.parent
        response: RenderResult | SupportReport
        if args.verb == "support":
            response = support(request, workspace=workspace)
        else:
            response = _protocol_render(request, workspace=workspace)
        write_json_atomic(result_path, response.to_dict())
    except RendererException as exc:
        _write_failure(result_path, exc, kind=exc.error.kind)
    except FileNotFoundError as exc:
        _write_failure(result_path, exc, kind="binary_missing")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        _write_failure(result_path, exc, kind="protocol")
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _write_failure(result_path, exc, kind="internal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "THREE_COMPOSITION_ID",
    "THREE_VERSION",
    "main",
    "support",
]
