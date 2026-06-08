"""Resume-mode helpers for the hype cut executor.

Extracted from ``run.py`` during M4 batch 79 (T80). Handles the
``--timeline`` resume path where an existing hype.timeline.json is
re-processed for re-render or asset rebasing.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

from astrid.core.contracts.result_manifest import write_manifest
from astrid.core.timeline import (
    METADATA_VERSION,
    PipelineMetadata,
    TimelineConfig,
    canonical_timeline_config,
    load_metadata,
    load_registry,
    load_timeline,
    materialize_output,
    save_metadata,
    save_registry,
    save_timeline,
)
from astrid.core.util.time import utc_now_seconds
from astrid.core.paths import REPO_ROOT, WORKSPACE_ROOT

from .registry import rebase_registry_paths
from .timeline_build import _register_cut_outputs


def ensure_resume_mode_args(args: argparse.Namespace) -> None:
    conflicts: list[tuple[str, Any]] = [
        ("--scenes", args.scenes),
        ("--video", args.video),
        ("--shots", args.shots),
        ("--transcript", args.transcript),
        ("--primary-asset", args.primary_asset),
        ("--asset", args.asset),
    ]
    for flag, value in conflicts:
        if value not in (None, []):
            raise SystemExit(f"--timeline cannot be combined with {flag}")


def build_resume_metadata(
    config: TimelineConfig,
    prior_meta: PipelineMetadata | None,
    *,
    render: bool,
    renderer: str,
) -> PipelineMetadata:
    clip_ids = [clip["id"] for clip in config["clips"]]
    prior_clips = prior_meta.get("clips", {}) if isinstance(prior_meta, dict) else {}
    clips: dict[str, dict[str, Any]] = {}
    if isinstance(prior_clips, dict):
        for clip_id in clip_ids:
            clip_meta = prior_clips.get(clip_id)
            if isinstance(clip_meta, dict):
                clips[clip_id] = dict(clip_meta)
    prior_sources = prior_meta.get("sources", {}) if isinstance(prior_meta, dict) else {}
    sources = {key: dict(value) for key, value in prior_sources.items()} if isinstance(prior_sources, dict) else {}
    return {
        "version": METADATA_VERSION,
        "generated_at": utc_now_seconds(),
        "pipeline": {
            "steps_run": ["cut"],
            "tool_versions": {"cut.py": "sprint3"},
            "config_snapshot": {
                "mode": "timeline_resume",
                "render": render,
                "renderer": renderer,
            },
        },
        "clips": clips,
        "sources": sources,
    }


def run_resume_mode(args: argparse.Namespace) -> int:
    ensure_resume_mode_args(args)

    timeline_path = args.timeline.resolve()
    if not timeline_path.is_file():
        raise SystemExit(f"Timeline file not found: {timeline_path}")
    source_dir = timeline_path.parent
    assets_path_in = args.assets.resolve() if args.assets is not None else source_dir / "hype.assets.json"
    if not assets_path_in.is_file():
        raise SystemExit(f"Assets file not found: {assets_path_in}")

    config = load_timeline(timeline_path)
    registry = load_registry(assets_path_in)

    # SD-009: backfill the canonical `output` block if the resumed timeline
    # was authored before materialize_output() was wired in. Resolves the
    # timeline's theme slug + theme_overrides via the workspace themes root.
    if "output" not in config:
        themes_root = WORKSPACE_ROOT / "themes"
        try:
            from astrid.core.timeline import resolve_timeline_theme
            merged_theme = resolve_timeline_theme(config, themes_root)
            config["output"] = materialize_output(config, merged_theme)
        except (FileNotFoundError, ValueError):
            config["output"] = materialize_output(
                config,
                {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
            )

    missing_assets = sorted(
        {
            asset
            for clip in config["clips"]
            for asset in [clip.get("asset")]
            if asset is not None and asset not in registry["assets"]
        }
    )
    if missing_assets:
        quoted = ", ".join(repr(asset) for asset in missing_assets)
        raise SystemExit(f"Timeline references assets missing from registry: {quoted}")

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    timeline_path_out = out_dir / "hype.timeline.json"
    assets_path_out = out_dir / "hype.assets.json"
    metadata_path_out = out_dir / "hype.metadata.json"
    canonical_timeline_config(config)
    save_timeline(config, timeline_path_out)
    if out_dir == assets_path_in.parent.resolve():
        save_registry(registry, assets_path_out)
    else:
        save_registry(rebase_registry_paths(registry, assets_path_in.parent), assets_path_out)

    prior_meta_path = source_dir / "hype.metadata.json"
    prior_meta = load_metadata(prior_meta_path) if prior_meta_path.exists() else None
    save_metadata(
        build_resume_metadata(config, prior_meta, render=bool(args.render), renderer=args.renderer),
        metadata_path_out,
    )

    summary = f"timeline={timeline_path_out} assets={assets_path_out} metadata={metadata_path_out}"
    if args.render:
        from ..render.run import render as render_remotion

        hype_path = render_remotion(
            timeline_path_out,
            assets_path_out,
            out_dir / "hype.mp4",
            project_dir=REPO_ROOT / "remotion",
        )
        summary = f"{summary} hype={hype_path}"
    _register_cut_outputs(
        out_dir=out_dir,
        stage="cut.resume",
        metadata={"mode": "timeline_resume", "render": bool(args.render), "renderer": args.renderer},
        rendered_path=out_dir / "hype.mp4" if args.render else None,
    )
    # --- universal result manifest (output-contract M2) -------------------
    manifest_outputs = [
        {"path": "hype.timeline.json", "type": "file"},
        {"path": "hype.assets.json", "type": "file"},
        {"path": "hype.metadata.json", "type": "file"},
    ]
    if args.render:
        manifest_outputs.append({"path": "hype.mp4", "type": "file"})
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "cut",
        "inputs": {
            "timeline": str(timeline_path),
        },
        "outputs": manifest_outputs,
        "created": datetime.now(timezone.utc).isoformat(),
        "warnings": [],
    }
    write_manifest(out_dir / "manifest.json", manifest)
    # ---------------------------------------------------------------------
    print(f"wrote {summary}")
    return 0
