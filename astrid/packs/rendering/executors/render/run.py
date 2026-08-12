#!/usr/bin/env python3

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('rendering.render')


import argparse
import ast
import json
import os
import sys
from contextvars import ContextVar
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from astrid.core import timeline
from astrid.core.audit import AuditContext
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.core.rendering.service import RenderService
from astrid.packs.rendering.backends.ffmpeg import command as ffmpeg_command
from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_backend
from astrid.packs.rendering.backends.remotion import run as remotion_backend
from astrid.packs.rendering.executors.render import audio_reactive_colour
from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _complex_clip_windows,
    _hybrid_segments,
)


# Compatibility exports for callers that historically imported these private
# helpers from the facade.  Their implementation now lives with the backend.
_RangeHTTPRequestHandler = remotion_backend._RangeHTTPRequestHandler
_validate_project_dir = remotion_backend._validate_project_dir
_serialize_timeline = remotion_backend._serialize_timeline
_resolve_theme_path = remotion_backend._resolve_theme_path
_theme_for_props = remotion_backend._theme_for_props
_theme_slug_for_render_default = remotion_backend._theme_slug_for_render_default
_resolved_theme_for_render = remotion_backend._resolved_theme_for_render
_timeline_composition_src = remotion_backend._timeline_composition_src
_registry_output_paths = remotion_backend._registry_output_paths
_registry_outputs_exist = remotion_backend._registry_outputs_exist
_active_theme_pointer_current = remotion_backend._active_theme_pointer_current
_effective_registry_state = remotion_backend._effective_registry_state
_read_registry_state = remotion_backend._read_registry_state
_write_registry_state = remotion_backend._write_registry_state
_regenerate_element_registries = remotion_backend._regenerate_element_registries
_render_asset_stage_hash = remotion_backend._render_asset_stage_hash
_effect_registry_for_assets = remotion_backend._effect_registry_for_assets
_effect_id_for_clip = remotion_backend._effect_id_for_clip
_source_pack_id = remotion_backend._source_pack_id
_inject_clip_asset_params = remotion_backend._inject_clip_asset_params
_stage_effect_assets_for_timeline = remotion_backend._stage_effect_assets_for_timeline
_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
_render_provenance_payload = remotion_backend._render_provenance_payload
_write_render_provenance = remotion_backend._write_render_provenance
_timeline_canvas = ffmpeg_command.timeline_canvas
_clip_duration_seconds = ffmpeg_command.clip_duration_seconds


# The Hype pipeline's default output file name.  The executor manifest exposes
# an ``output_name`` input defaulting to this sentinel; non-default names are
# validated (plain file name, ``.mp4`` extension) and flow through the same
# placeholder expansion and declared-output resolution as the default.
DEFAULT_OUTPUT_NAME = "hype.mp4"

_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
    "render_publication_previous_outputs",
    default=(),
)
_HYBRID_FINALIZER_PROFILE: ContextVar[RenderProfile | None] = ContextVar(
    "hybrid_finalizer_profile",
    default=None,
)

_SERVICE: RenderService | None = None


def _default_service() -> RenderService:
    """Build (once) the backend-neutral service the facade delegates to.

    Legacy engine translation, renderer/planner selection, invocation,
    validation, audio completion, finalization, and publication all happen
    inside :class:`RenderService`.  The facade is a thin adapter: it maps the
    legacy argument surface onto the service call and returns the published
    output path.
    """
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RenderService()
    return _SERVICE


def validate_output_name(name: str) -> str:
    """Validate an ``output_name``: a plain ``.mp4`` file name.

    Rejects empty names, path separators (``/`` and ``\\``), directory
    traversal (``.``, ``..``, or any ``..``-prefixed component), absolute
    paths, and anything that does not end in ``.mp4``.  The Hype default
    ``hype.mp4`` validates unchanged.
    """
    text = str(name)
    if text == "":
        raise ValueError("output_name must not be empty")
    if text in {".", ".."} or text.startswith(".."):
        raise ValueError(
            f"output_name must not traverse directories, got {name!r}"
        )
    if "/" in text or "\\" in text or text.startswith(os.sep):
        raise ValueError(
            f"output_name must be a plain file name without path separators, got {name!r}"
        )
    if Path(text).name != text:
        raise ValueError(
            f"output_name must be a plain file name, got {name!r}"
        )
    if not text.endswith(".mp4"):
        raise ValueError(
            f"output_name must end with .mp4, got {name!r}"
        )
    return text


def _legacy_backend_config(
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> dict[str, dict[str, Any]]:
    """Map the legacy render kwargs onto namespaced backend configuration.

    The facade remains backend-neutral: it only knows the qualified ids that
    correspond to the historical selector spellings and scopes each legacy
    value under the backend that understands it.  The service forwards each
    candidate only its own namespace.
    """
    config: dict[str, dict[str, Any]] = {}
    remotion: dict[str, Any] = {}
    if project_dir is not None:
        remotion["project_dir"] = str(project_dir)
    if composition_id is not None:
        remotion["composition_id"] = composition_id
    if theme_path is not None:
        remotion["theme_path"] = str(theme_path)
    if min_free_gb is not None:
        remotion["min_free_gb"] = min_free_gb
    if remotion:
        config["rendering.remotion"] = remotion
    hybrid: dict[str, Any] = {}
    if theme_path is not None:
        hybrid["theme_path"] = str(theme_path)
    if hybrid:
        config["rendering.legacy_hybrid"] = hybrid
    return config


def _parse_backend_config(value: str | None) -> dict[str, dict[str, Any]]:
    """Parse the ``--backend-config`` CLI payload (JSON or Python literal)."""
    if value is None or value == "":
        return {}
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(
                f"--backend-config must be a JSON object keyed by qualified "
                f"backend id, got {value!r}"
            ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"--backend-config must be a JSON object keyed by qualified backend id"
        )
    return {str(key): dict(item) for key, item in parsed.items() if item is not None}


def _swap_from_dump(clip: dict) -> dict:
    out = dict(clip)
    if "from_" in out:
        out["from"] = out.pop("from_")
    return out


def _write_empty_asset_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timeline.save_registry({"assets": {}}, path)


def _clip_timeline_end_seconds(clip: dict) -> float:
    start = float(clip.get("at", 0) or 0)
    if clip.get("clipType") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)):
        return start + max(0.0, float(hold))
    if isinstance(clip.get("to"), (int, float)):
        return float(clip["to"])
    return start


def _timeline_duration_seconds(timeline_data: dict) -> float:
    metadata = timeline_data.get("metadata", {})
    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
        explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    return max((_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0)


def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
    instant = (
        seconds
        if isinstance(seconds, Fraction)
        else Fraction(seconds).limit_denominator(1_000_000)
    )
    frames = instant * rate
    if mode == "floor":
        frame = frames.numerator // frames.denominator
    elif mode == "ceil":
        frame = -(-frames.numerator // frames.denominator)
    else:
        frame = round(frames)
    return float(Fraction(frame, 1) / rate)


def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
    clip_start = float(clip.get("at", 0) or 0)
    clip_end = _clip_timeline_end_seconds(clip)
    return clip_start < end and clip_end > start


def _window_clip(clip: dict, start: float, end: float) -> dict | None:
    if not _clip_overlaps(clip, start, end):
        return None
    clip_start = float(clip.get("at", 0) or 0)
    visible_start = max(clip_start, start)
    visible_end = min(_clip_timeline_end_seconds(clip), end)
    if visible_end <= visible_start:
        return None

    out = dict(clip)
    out["at"] = visible_start - start
    out["id"] = f"{clip.get('id', 'clip')}_{start:.3f}_{end:.3f}".replace(".", "_")
    if clip.get("clipType") == "media":
        speed = float(clip.get("speed", 1) or 1)
        source_from = float(clip.get("from", 0) or 0) + ((visible_start - clip_start) * speed)
        out["from"] = source_from
        out["to"] = source_from + ((visible_end - visible_start) * speed)
    elif isinstance(clip.get("hold"), (int, float)):
        out["hold"] = visible_end - visible_start
    return out


def _window_timeline_data(timeline_data: dict, start: float, end: float, *, media_only: bool) -> dict:
    clips: list[dict] = []
    for clip in timeline_data.get("clips", []):
        if media_only and clip.get("clipType") != "media":
            continue
        windowed = _window_clip(clip, start, end)
        if windowed is not None:
            clips.append(windowed)
    used_tracks = {clip.get("track") for clip in clips}
    tracks = [track for track in timeline_data.get("tracks", []) if track.get("id") in used_tracks]
    out = dict(timeline_data)
    out["tracks"] = tracks
    out["clips"] = clips
    out["metadata"] = {
        **dict(timeline_data.get("metadata", {})),
        "source_window_start_seconds": start,
        "source_window_end_seconds": end,
        "duration_seconds": end - start,
    }
    return out


_validate_ffmpeg_media_timeline = (
    ffmpeg_command.validate_ffmpeg_media_timeline
)


def _render_ffmpeg_media_to_path(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
) -> Path:
    return ffmpeg_backend._render_ffmpeg_media_to_path(
        timeline_path,
        assets_path,
        out_path,
    )


def _render_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    _previous_outputs: Sequence[Path] | None = None,
) -> Path:
    return ffmpeg_backend.render(
        timeline_path,
        assets_path,
        out_path,
        previous_outputs=(
            _PUBLICATION_PREVIOUS_OUTPUTS.get()
            if _previous_outputs is None
            else _previous_outputs
        ),
        _render_to_path=_render_ffmpeg_media_to_path,
    )


def _can_render_with_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
) -> bool:
    return ffmpeg_backend.can_render_with_ffmpeg_media(
        timeline_path,
        assets_path,
    )


def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
    profile = _HYBRID_FINALIZER_PROFILE.get()
    audio = None
    if profile is not None:
        audio = (
            AudioOwnership.RENDERED
            if profile.has_audio
            else AudioOwnership.NONE
        )
    ffmpeg_finalizer.concat_segment_files(
        segment_paths,
        out_path,
        profile=profile,
        audio=audio,
    )


def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    canonical_profile = resolve_render_profile(
        timeline_data,
        timeline.load_registry(assets_path),
        theme=remotion_kwargs.get("theme_path"),
        themes_root=REPO_ROOT / "themes",
    )
    segments = _hybrid_segments(
        timeline_data,
        fps=Fraction(*canonical_profile.fps_rational),
    )
    if (
        canonical_profile.fps_rational[1] == 1
        and len(segments) == 1
        and segments[0]["engine"] == "ffmpeg"
    ):
        return _render_ffmpeg_media(timeline_path, assets_path, out_path)

    publication_out = out_path  # unresolved: publication symlink-guards it
    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
        tmp_dir = Path(tmp)
        segment_paths: list[Path] = []
        segment_provenance: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            engine = str(segment["engine"])
            start = float(segment["from"])
            end = float(segment["to"])
            segment_dir = tmp_dir / f"{index:04d}-{engine}"
            segment_dir.mkdir(parents=True, exist_ok=True)
            segment_timeline_path = segment_dir / "timeline.json"
            segment_out_path = segment_dir / "segment.mp4"
            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
            if canonical_profile.fps_rational[1] != 1:
                # Both extracted legacy renderers accept an integer canvas
                # rate.  Render the window at the nearest rate, then let the
                # finalizer normalize to the exact canonical rational rate.
                render_rate = max(
                    1,
                    round(Fraction(*canonical_profile.fps_rational)),
                )
                overrides = dict(segment_timeline.get("theme_overrides", {}))
                visual = dict(overrides.get("visual", {}))
                canvas = dict(visual.get("canvas", {}))
                canvas["fps"] = render_rate
                visual["canvas"] = canvas
                overrides["visual"] = visual
                segment_timeline["theme_overrides"] = overrides
            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
            if engine == "ffmpeg":
                _render_ffmpeg_media(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    _previous_outputs=(),
                )
            else:
                render(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    engine="remotion",
                    **remotion_kwargs,
                )
                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
                if sidecar_path.exists():
                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
            segment_paths.append(segment_out_path)
        staged_video = tmp_dir / "final" / out_path.name
        staged_video.parent.mkdir(parents=True, exist_ok=True)
        profile_token = _HYBRID_FINALIZER_PROFILE.set(canonical_profile)
        try:
            _concat_segments(segment_paths, staged_video)
        finally:
            _HYBRID_FINALIZER_PROFILE.reset(profile_token)
        provenance = _render_provenance_payload(
            out_path,
            engine="hybrid",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=Path(remotion_kwargs.get("project_dir") or (REPO_ROOT / "remotion")),
            composition_id=str(remotion_kwargs.get("composition_id") or "TimelineComposition"),
            theme_path=remotion_kwargs.get("theme_path"),
            active_theme=None,
            registry_state=_effective_registry_state(remotion_kwargs.get("theme_path")),
            stage_summary={"root": None, "effects": []},
            segments=segments,
            segment_provenance=segment_provenance,
        )
        output = publish_render_result(
            staged_video,
            provenance,
            out_path=out_path,
            sidecar_path=_render_provenance_sidecar_path(out_path),
            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        )

    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid")
        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_hybrid")
        render_id = audit.register_asset(
            kind="render",
            path=out_path,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_hybrid",
            metadata={"engine": "hybrid", "segments": segments},
        )
        audit.register_node(
            stage="render_hybrid",
            label="Render hybrid timeline",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={"engine": "hybrid", "segments": segments},
        )
    return output


def _previous_render_outputs_for_timeline(
    out_path: Path,
    timeline_path: Path,
) -> tuple[Path, ...]:
    """Discover legacy sibling outputs; publication validates before deleting.

    The timeline argument remains part of the helper boundary for compatibility
    with the legacy cleanup call site.  Filtering now happens under each
    candidate's publication lock using the committed sidecar.
    """

    out_path = out_path.resolve()
    if out_path.name != "hype.mp4":
        return ()
    run_dir = out_path.parent
    runs_dir = run_dir.parent
    if runs_dir.name != "runs" or not runs_dir.is_dir():
        return ()
    candidates: list[Path] = []
    for candidate_run_dir in runs_dir.iterdir():
        if not candidate_run_dir.is_dir() or candidate_run_dir == run_dir:
            continue
        candidates.append(candidate_run_dir / out_path.name)
    return tuple(candidates)


def _parse_bool_arg(value: str | bool | None) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean value, got {value!r}")


def _audio_reactive_ffmpeg_element(
    theme_path: Path | None,
) -> Any | None:
    return ffmpeg_backend._audio_reactive_ffmpeg_element(theme_path)


def _render_audio_reactive_colour_if_supported(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
) -> Path | None:
    return ffmpeg_backend.render_audio_reactive_colour_if_supported(
        timeline_path,
        assets_path,
        out_path,
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        element_resolver=_audio_reactive_ffmpeg_element,
    )


def render(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    engine: str = "remotion",
    project_dir: Path | None = None,
    composition_id: str = "TimelineComposition",
    theme_path: Path | None = None,
    min_free_gb: float | None = None,
    keep_previous_renders: bool = False,
    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path:
    """Render through :class:`RenderService` and publish one locked pair.

    The facade keeps the historical public signature and capability id.  All
    dispatch (legacy engine translation, renderer/planner selection, support,
    invocation, validation, audio completion, finalization, publication)
    happens in the service; the facade only adapts the legacy argument surface
    and the caller-selected output name.
    """
    out_path = Path(out_path)
    validate_output_name(out_path.name)
    previous_outputs = (
        ()
        if keep_previous_renders
        else _previous_render_outputs_for_timeline(out_path, timeline_path)
    )
    config = _legacy_backend_config(
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        min_free_gb=min_free_gb,
    )
    for key, value in (backend_config or {}).items():
        if value is not None:
            config[str(key)] = dict(value)
    return _default_service().render(
        timeline_path,
        assets_path,
        out_path,
        selector=engine,
        backend_config=config,
        previous_outputs=previous_outputs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--engine",
        default="remotion",
        help="Legacy selector (remotion, ffmpeg, hybrid) or a qualified renderer id.",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="Neutral alias for --engine: legacy selector or qualified backend id.",
    )
    parser.add_argument(
        "--backend-config",
        default=None,
        help="JSON object keyed by qualified backend id with per-backend configuration.",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help="Output file name (default hype.mp4); plain .mp4 file name only.",
    )
    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
    parser.add_argument("--composition", default="TimelineComposition")
    parser.add_argument("--min-free-gb", type=float, default=None, help="Abort before rendering unless this much free disk is available near --out.")
    parser.add_argument(
        "--keep-previous-renders",
        nargs="?",
        const=True,
        default=False,
        type=_parse_bool_arg,
        help="Preserve previous sibling hype.mp4 outputs for the same timeline.",
    )
    parser.add_argument(
        "--theme",
        type=Path,
        default=REPO_ROOT / "themes" / "banodoco-default" / "theme.json",
    )
    args = parser.parse_args(argv)
    try:
        if args.output_name is not None:
            validate_output_name(args.output_name)
            if Path(args.out).name != args.output_name:
                raise ValueError(
                    f"--out basename {Path(args.out).name!r} does not match "
                    f"--output-name {args.output_name!r}"
                )
        else:
            validate_output_name(Path(args.out).name)
        selector = args.backend if args.backend is not None else args.engine
        config = _parse_backend_config(args.backend_config)
        if args.assets is None:
            with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
                assets_path = Path(tmp_text) / "hype.assets.json"
                _write_empty_asset_registry(assets_path)
                output = render(
                    args.timeline,
                    assets_path,
                    args.out,
                    engine=selector,
                    project_dir=args.project_dir,
                    composition_id=args.composition,
                    theme_path=args.theme,
                    min_free_gb=args.min_free_gb,
                    keep_previous_renders=args.keep_previous_renders,
                    backend_config=config,
                )
        else:
            output = render(
                args.timeline,
                args.assets,
                args.out,
                engine=selector,
                project_dir=args.project_dir,
                composition_id=args.composition,
                theme_path=args.theme,
                min_free_gb=args.min_free_gb,
                keep_previous_renders=args.keep_previous_renders,
                backend_config=config,
            )
    except Exception as exc:  # pragma: no cover - CLI path
        print(str(exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
