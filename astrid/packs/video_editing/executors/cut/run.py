#!/usr/bin/env python3
"""Assemble selected source-video ranges into hype-cut planning files and optional rendered outputs using transcript, scene, and shot inputs.

.. note::

    This module produces **standalone** ``hype.timeline.json`` artifacts for
    the Remotion renderer.  In managed mode the same validated raw
    ``TimelineConfig`` is emitted to the project timeline as
    ``timeline.config_replaced`` before these run-local artifacts are written."""

from __future__ import annotations

from astrid.core.contracts.result_manifest import write_manifest
from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('video_editing.cut')
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from astrid.core.cli_choices import add_choice_arg
from astrid.core.task.managed_binding import is_managed_mode
from astrid.core.timeline import (
    canonical_timeline_config,
    is_all_generative_arrangement,
    load_arrangement,
    load_metadata,
    load_pool,
    load_registry,
    save_metadata,
    save_registry,
    save_timeline,
    validate_arrangement_duration_window,
)
from astrid.core.util.hash import sha256_file
from astrid.packs.editorial.hype.arrangement_rules import compile_arrangement_plan
from astrid.packs.training.executors.asset_cache import run as asset_cache
from astrid.core.paths import REPO_ROOT, WORKSPACE_ROOT
from astrid.core.theme import load_theme, theme_root

from . import probe
from . import registry as _registry
from . import resume as _resume
from . import timeline_build as _timeline_build

# ── re-exports from focused modules (T78) ────────────────────────────
_FFPROBE_VERBOSE = probe._FFPROBE_VERBOSE  # alias for module-level access
parse_ffprobe_fps = probe.parse_ffprobe_fps
probe_asset = probe.probe_asset
probe_video_duration = probe.probe_video_duration

resolve_asset_paths = _registry.resolve_asset_paths
_url_cache_meta = _registry._url_cache_meta
build_registry = _registry.build_registry
rebase_registry_paths = _registry.rebase_registry_paths

# ── re-exports from timeline_build (T80) ─────────────────────────────
_LEGACY_DEFAULT_CLIP_SEC = _timeline_build._LEGACY_DEFAULT_CLIP_SEC
_THEME_DEFAULT_CLIP_SEC = _timeline_build._theme_default_clip_sec
_BRANDED_EFFECT_IDS = _timeline_build._BRANDED_EFFECT_IDS
_TEXT_STYLE_FONT = _timeline_build._TEXT_STYLE_FONT
_clip_bounds_for_duration = _timeline_build._clip_bounds_for_duration
_text_style_preset_to_attrs = _timeline_build._text_style_preset_to_attrs
_drop_brand_animation_overrides = _timeline_build._drop_brand_animation_overrides
_merged_theme_for_output = _timeline_build._merged_theme_for_output
_joined_segment_text = _timeline_build._joined_segment_text
_pool_entry_caption_kind = _timeline_build._pool_entry_caption_kind
_tool_fingerprints = _timeline_build._tool_fingerprints
_ref_path_for_metadata = _timeline_build._ref_path_for_metadata
build_multitrack_timeline = _timeline_build.build_multitrack_timeline
build_metadata_from_arrangement = _timeline_build.build_metadata_from_arrangement
arrangement_edl_rows = _timeline_build.arrangement_edl_rows
write_edl = _timeline_build.write_edl
_register_cut_outputs = _timeline_build._register_cut_outputs
_emit_cut_managed_events = _timeline_build._emit_cut_managed_events

# ── re-exports from resume (T80) ─────────────────────────────────────
ensure_resume_mode_args = _resume.ensure_resume_mode_args
build_resume_metadata = _resume.build_resume_metadata
run_resume_mode = _resume.run_resume_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or render a hype cut from scene, shot, and transcript inputs.")
    parser.add_argument("--scenes", type=Path, help="Path to scenes.json.")
    parser.add_argument("--timeline", type=Path, help="Existing hype.timeline.json to resume from.")
    parser.add_argument("--assets", type=Path, help="Asset registry to use with --timeline (defaults to <timeline_dir>/hype.assets.json).")
    parser.add_argument("--video", type=str, help="Source video file.")
    parser.add_argument("--audio", type=str, help="Optional rant audio file for audio-backed pure-generative mode.")
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help=(
            "Output directory. Writes hype.edl.csv, hype.timeline.json, "
            "hype.assets.json, and hype.metadata.json."
        ),
    )
    parser.add_argument("--transcript", type=Path, help="Transcript JSON used for arrangement metadata.")
    parser.add_argument("--shots", type=Path, help="Optional shots.json for future enrichment.")
    parser.add_argument("--arrangement", type=Path, help="Arrangement JSON for pool-based multitrack assembly.")
    parser.add_argument("--pool", type=Path, help="Pool JSON used with --arrangement.")
    parser.add_argument("--brief", type=Path, help="brief.txt used with --arrangement.")
    parser.add_argument("--theme", help="Theme id, theme directory, or path to theme.json.")
    parser.add_argument("--asset", action="append", default=[], help="Additional source asset mapping in KEY=PATH form.")
    parser.add_argument("--verbose", action="store_true", help="Print ffprobe cache activity.")
    parser.add_argument(
        "--primary-asset",
        help=(
            "Asset key that the --scenes / --transcript / --shots CLI inputs describe. "
            "Defaults to main when that key exists (single-source and plain-text picks). "
            "For multi-source JSON picks without a main key, this flag is required."
        ),
    )
    add_choice_arg(
        parser,
        "--renderer",
        values=("remotion",),
        default="remotion",
        help="Render backend. remotion (default) uses tools/remotion/.",
    )
    parser.add_argument("--render", action="store_true", help="Render clips and concat them into hype.mp4.")
    # Managed binding seam (m3.5): when both --project and --timeline-slug are
    # present, the pack writes canonical timeline events through the event gateway.
    # Without these flags, the pack runs in unmanaged artifact mode (writes
    # run-local compatibility outputs only).  --timeline-id is intentionally NOT
    # added here -- it is reserved for executor UUID mode.
    parser.add_argument("--project", help="Project slug for managed canonical writes. When combined with --timeline-slug, timeline mutations emit events through the gateway.")
    parser.add_argument("--timeline-slug", help="Timeline slug within the project for managed canonical writes.")
    parser.add_argument(
        "--actor-via",
        type=json.loads,
        default=None,
        help="Optional JSON TimelineActor for upstream provenance chaining (actor.via).",
    )
    return parser


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_theme_path(theme_value: str | None) -> Path | None:
    if theme_value is None:
        return None
    candidate = Path(theme_value)
    if candidate.name == "theme.json":
        return candidate
    if candidate.exists() and candidate.is_dir():
        return candidate / "theme.json"
    if candidate.exists():
        return candidate
    return WORKSPACE_ROOT / "themes" / theme_value / "theme.json"


def _theme_slug_from_path(theme_path: Path | None) -> str | None:
    """Derive the theme slug (directory name) from a theme.json or theme dir path."""
    if theme_path is None:
        return None
    path = Path(theme_path)
    if path.name == "theme.json":
        return path.parent.name
    if path.is_dir():
        return path.name
    return path.parent.name


def arrangement_uses_generative_visuals(arrangement: dict[str, Any], pool: dict[str, Any]) -> bool:
    generative_ids = {
        entry["id"]
        for entry in pool.get("entries", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry.get("kind") == "generative"
    }
    for clip in arrangement.get("clips", []):
        visual_source = clip.get("visual_source") if isinstance(clip, dict) else None
        if isinstance(visual_source, dict) and visual_source.get("pool_id") in generative_ids:
            return True
    return False


def load_scenes(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise SystemExit(f"Expected a JSON list in {path}")
    return data


def load_transcript_segments(path: Path | None) -> list[dict[str, Any]] | None:
    if path is None:
        return None
    data = load_json(path)
    segments = data.get("segments") if isinstance(data, dict) else data
    if not isinstance(segments, list):
        raise SystemExit(f"Expected transcript segments in {path}")
    return segments


def _quality_zones_ref_from_args(args: argparse.Namespace) -> Path | None:
    for ref in (getattr(args, "scenes", None), getattr(args, "transcript", None)):
        if ref is None:
            continue
        candidate = ref.resolve().parent / "quality_zones.json"
        if candidate.is_file():
            return candidate
    return None


def main(argv: Sequence[str] | None = None) -> int:

    parser = build_parser()
    args = parser.parse_args(argv)
    # m3.5 managed binding seam: detect managed vs unmanaged mode.
    managed = is_managed_mode(args)
    if managed:
        # Managed mode: canonical mutations will route through the event gateway
        # (T10).  For now, validate that both flags are present.
        print(f"cut: managed mode --project={args.project} --timeline-slug={args.timeline_slug}")
    else:
        # Unmanaged mode: writes run-local compatibility outputs only.
        if bool(getattr(args, "project", None)) != bool(getattr(args, "timeline_slug", None)):
            raise SystemExit("--project and --timeline-slug must be supplied together for managed mode, or both omitted for unmanaged artifact mode")
    if args.timeline is not None:
        return run_resume_mode(args)
    theme_path = _resolve_theme_path(args.theme)
    theme = load_theme(theme_path) if theme_path is not None else None
    theme_dir = theme_root(theme_path).resolve() if theme_path is not None else None
    theme_slug = _theme_slug_from_path(theme_path)
    pure_generative = args.video is None and args.audio is not None
    no_audio = args.video is None and args.audio is None
    if args.scenes is None and not (pure_generative or no_audio):
        raise SystemExit("--scenes is required unless --timeline is provided")
    if args.arrangement is None:
        raise SystemExit("--arrangement is required unless --timeline is provided")
    if args.pool is None:
        raise SystemExit("--pool is required unless --timeline is provided")
    if args.brief is None:
        raise SystemExit("--brief is required unless --timeline is provided")
    if args.transcript is None and not no_audio:
        raise SystemExit("--transcript is required unless --timeline is provided")
    probe._FFPROBE_VERBOSE = bool(args.verbose)

    scenes_path = args.scenes.resolve() if args.scenes is not None else None
    out_dir = args.out.resolve()
    if scenes_path is not None and not scenes_path.is_file():
        raise SystemExit(f"Scenes file not found: {scenes_path}")
    if args.video is not None and not asset_cache.is_url(args.video) and not Path(args.video).resolve().is_file():
        raise SystemExit(f"Video file not found: {Path(args.video).resolve()}")
    if args.transcript is not None and not args.transcript.resolve().is_file():
        raise SystemExit(f"Transcript file not found: {args.transcript.resolve()}")
    if args.shots is not None and not args.shots.resolve().is_file():
        raise SystemExit(f"Shots file not found: {args.shots.resolve()}")
    if not args.arrangement.resolve().is_file():
        raise SystemExit(f"Arrangement file not found: {args.arrangement.resolve()}")
    if not args.pool.resolve().is_file():
        raise SystemExit(f"Pool file not found: {args.pool.resolve()}")
    if not args.brief.resolve().is_file():
        raise SystemExit(f"Brief file not found: {args.brief.resolve()}")
    if scenes_path is not None:
        load_scenes(scenes_path)
    transcript = None if no_audio else load_transcript_segments(args.transcript.resolve())
    if args.shots is not None:
        load_json(args.shots.resolve())

    asset_paths, asset_urls = resolve_asset_paths(args)
    for key, path in asset_paths.items():
        if not path.is_file():
            raise SystemExit(f"Asset file not found for {key!r}: {path}")
    asset_keys = set(asset_paths) | set(asset_urls)

    assets_path = out_dir / "hype.assets.json"
    if assets_path.exists():
        existing_registry = load_registry(assets_path)
    else:
        existing_registry = {"assets": {}}

    if args.primary_asset is None:
        if "main" in asset_keys:
            primary_asset = "main"
        elif pure_generative and "rant" in asset_keys:
            primary_asset = None
        elif no_audio:
            primary_asset = None
        else:
            raise SystemExit(
                "--primary-asset is required when --video is not provided as the main asset. "
                f"Available keys: {sorted(asset_keys)}"
            )
    else:
        if args.primary_asset not in asset_keys:
            raise SystemExit(
                f"--primary-asset={args.primary_asset!r} is not one of the configured asset keys: "
                f"{sorted(asset_keys)}"
            )
        primary_asset = args.primary_asset

    metadata_path = out_dir / "hype.metadata.json"
    prior_meta = load_metadata(metadata_path) if metadata_path.exists() else None
    registry, sources_meta = build_registry(asset_paths, asset_urls, existing_registry, prior_meta)

    arrangement_path = args.arrangement.resolve()
    pool_path = args.pool.resolve()
    brief_path = args.brief.resolve()
    pool_sha256 = sha256_file(pool_path)
    arrangement_sha256 = sha256_file(arrangement_path)
    brief_sha256 = sha256_file(brief_path)
    pool = load_pool(pool_path)
    pool_ids = {entry["id"] for entry in pool["entries"]}
    arrangement = load_arrangement(arrangement_path, pool_ids, assign_missing_uuids=True)
    # Mixed-mode (Phase 3): cut accepts arrangements with both source-extracted
    # video clips and generative visual entries. Pre-Phase-3 this was rejected
    # via `args.video is not None and arrangement_uses_generative_visuals(...)`;
    # the rejection is gone. The duration-window check stays gated on whether
    # there is any source-derived material at all.
    if not is_all_generative_arrangement(arrangement, pool):
        validate_arrangement_duration_window(arrangement)
    compiled_plan = compile_arrangement_plan(arrangement, pool)
    edl_rows = arrangement_edl_rows(arrangement, pool, transcript, compiled_plan=compiled_plan)
    if theme_slug is None:
        # Timelines now reference a theme by slug at top level. Default to the
        # banodoco-default theme when --theme isn't supplied so the timeline still
        # validates; callers needing a specific brand pass --theme.
        theme_slug = "banodoco-default"
    timeline = build_multitrack_timeline(
        arrangement,
        pool,
        registry,
        primary_asset,
        compiled_plan=compiled_plan,
        theme=theme,
        theme_dir=theme_dir,
        theme_slug=theme_slug,
    )
    meta = build_metadata_from_arrangement(
        arrangement,
        pool,
        registry,
        sources_meta,
        args,
        primary_asset,
        transcript,
        quality_zones_ref=_quality_zones_ref_from_args(args),
        pool_sha256=pool_sha256,
        arrangement_sha256=arrangement_sha256,
        brief_sha256=brief_sha256,
        compiled_plan=compiled_plan,
    )
    edl_path = write_edl(edl_rows, out_dir, asset_paths, asset_urls)
    timeline_path = out_dir / "hype.timeline.json"
    canonical_timeline_config(timeline)
    # m3.5 managed mode: emit events through the gateway before writing
    # compatibility outputs.
    if managed:
        from astrid.core.timeline.events.schema import TimelineActor as _TimelineActor

        actor_via_raw = getattr(args, "actor_via", None)
        actor_via = _TimelineActor(**actor_via_raw) if isinstance(actor_via_raw, dict) else None
        _emit_cut_managed_events(args, timeline, actor_via=actor_via)
    save_timeline(timeline, timeline_path)
    save_registry(registry, assets_path)
    save_metadata(meta, metadata_path)
    rendered_path = None
    if args.render:
        from ..render.run import render as render_remotion

        hype_path = render_remotion(
            timeline_path,
            assets_path,
            out_dir / "hype.mp4",
            project_dir=REPO_ROOT / "remotion",
        )
        rendered_path = hype_path
        print(
            f"wrote_edl={edl_path} timeline={timeline_path} assets={assets_path} metadata={metadata_path} "
            f"hype={hype_path}"
        )
    else:
        print(f"wrote_edl={edl_path} timeline={timeline_path} assets={assets_path} metadata={metadata_path}")
    _register_cut_outputs(
        out_dir=out_dir,
        stage="cut",
        metadata={"clips": len(timeline.get("clips", [])), "render": bool(args.render), "renderer": args.renderer},
        rendered_path=rendered_path,
    )
    # --- universal result manifest (output-contract M2) -------------------
    manifest_outputs = [
        {"path": "hype.edl.csv", "type": "file"},
        {"path": "hype.timeline.json", "type": "file"},
        {"path": "hype.assets.json", "type": "file"},
        {"path": "hype.metadata.json", "type": "file"},
    ]
    if rendered_path is not None:
        manifest_outputs.append({"path": rendered_path.name, "type": "file"})
    manifest_inputs: dict[str, Any] = {
        "arrangement": str(arrangement_path),
        "pool": str(pool_path),
        "brief": str(brief_path),
    }
    if args.video is not None:
        manifest_inputs["video"] = str(args.video)
    if args.audio is not None:
        manifest_inputs["audio"] = str(args.audio)
    if args.theme is not None:
        manifest_inputs["theme"] = str(args.theme)
    if args.transcript is not None:
        manifest_inputs["transcript"] = str(args.transcript.resolve())
    if args.scenes is not None:
        manifest_inputs["scenes"] = str(scenes_path)
    if args.shots is not None:
        manifest_inputs["shots"] = str(args.shots.resolve())
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "cut",
        "inputs": manifest_inputs,
        "outputs": manifest_outputs,
        "created": datetime.now(timezone.utc).isoformat(),
        "warnings": [],
    }
    write_manifest(out_dir / "manifest.json", manifest)
    # ---------------------------------------------------------------------
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
