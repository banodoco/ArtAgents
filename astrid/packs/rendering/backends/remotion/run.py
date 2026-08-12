#!/usr/bin/env python3
"""Remotion renderer and raw rendering-protocol v1 command adapter.

The public ``render`` function is the compatibility seam used by the legacy
``rendering.render`` executor.  The command-line entry point is the leaf
backend protocol used by the generic renderer transport: it reads one request
file and writes exactly one result or structured error file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass, replace
from fractions import Fraction
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
from astrid.core.audit import AuditContext
from astrid.core.element.registry import load_default_registry
from astrid.core.element.schema import ElementDefinition
from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.paths import REPO_ROOT, WORKSPACE_ROOT
from astrid.core.media import ffprobe_metadata_strict
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.assets import (
    AssetMaterializer,
    InvocationAssetServer,
    RangeHTTPRequestHandler as _RangeHTTPRequestHandler,
)
from astrid.core.rendering.contracts import (
    AudioOwnership,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SCHEMA_VERSION,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.errors import (
    RendererException,
    make_renderer_error,
    raise_unsupported_error,
)
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.core.subprocess_env import build_child_subprocess_env
from astrid.core.theme import load_theme
from astrid.packs.rendering.backends.remotion import lock as remotion_lock
from scripts import gen_effect_registry


BACKEND_ID = "rendering.remotion"
BACKEND_VERSION = "1.0.0"
DEFAULT_COMPOSITION_ID = "TimelineComposition"
_REGISTRY_STATE_PATH = ".astrid-registry-state.json"
_CONFIG_KEYS = frozenset(
    {"project_dir", "composition_id", "composition", "theme_path", "theme", "min_free_gb"}
)


@dataclass(frozen=True)
class _RenderSettings:
    project_dir: Path
    composition_id: str
    theme_path: Path | None
    min_free_gb: float | None


@dataclass(frozen=True)
class _ExecutionDetails:
    active_theme: dict[str, Any]
    registry_state: dict[str, Any]
    stage_summary: dict[str, Any]


def _validate_project_dir(project_dir: Path) -> None:
    if not project_dir.exists():
        raise FileNotFoundError(f"Remotion project directory not found: {project_dir}")
    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise FileNotFoundError(f"Remotion project is missing package.json: {package_json}")
    node_modules = project_dir / "node_modules"
    if not node_modules.exists():
        raise FileNotFoundError(
            "Run `npm install` in tools/remotion/ first; "
            "see docs/reference/render-adapter.md for @banodoco adapter package install instructions"
        )

    banodoco_root = node_modules / "@banodoco"
    required_packages = (
        "timeline-composition",
        "timeline-schema",
        "timeline-theme-2rp",
    )
    missing = [
        f"@banodoco/{package}"
        for package in required_packages
        if not (banodoco_root / package).is_dir()
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing @banodoco render package(s): {', '.join(missing)}. "
            "These packages are adapter-required and not published to a public npm registry. "
            "See docs/reference/render-adapter.md for adapter install instructions."
        )


def _serialize_timeline(
    timeline_path: Path,
    *,
    default_theme: str = "banodoco-default",
) -> dict[str, Any]:
    return timeline.Timeline.load(timeline_path).for_render(default_theme=default_theme).to_json_data()


def _resolve_theme_path(theme_path: Path) -> Path:
    if theme_path.name == "theme.json":
        return theme_path
    if theme_path.exists() and theme_path.is_dir():
        return theme_path / "theme.json"
    if theme_path.exists():
        return theme_path
    return WORKSPACE_ROOT / "themes" / str(theme_path) / "theme.json"


def _theme_for_props(theme_path: Path) -> dict[str, Any]:
    resolved = _resolve_theme_path(theme_path)
    if not resolved.exists():
        return {
            "id": "banodoco-default",
            "visual": {
                "color": {"fg": "#ffffff", "bg": "#000000", "accent": "#ffffff"},
                "type": {
                    "families": {"heading": "Georgia, serif", "body": "Georgia, serif"},
                    "size": {"base": 64, "small": 36, "large": 96},
                    "weight": {"normal": 400, "bold": 700},
                    "lineHeight": 1.1,
                },
                "motion": {"fadeMs": 250},
                "canvas": {"width": 1920, "height": 1080, "fps": 30},
            },
        }
    theme_data = load_theme(resolved)
    return {"id": theme_data["id"], "visual": theme_data["visual"]}


def _theme_slug_for_render_default(theme_path: Path) -> str:
    resolved = _resolve_theme_path(theme_path)
    if resolved.name == "theme.json":
        return resolved.parent.name
    return resolved.stem or "banodoco-default"


def _resolved_theme_for_render(
    timeline_path: Path,
    fallback_theme_path: Path,
) -> dict[str, Any]:
    """Return the timeline theme with its per-run overrides merged."""

    loaded = timeline.Timeline.load(timeline_path)
    render_view = loaded.for_render(
        default_theme=_theme_slug_for_render_default(fallback_theme_path)
    )
    timeline_config = loaded.to_config()
    timeline_config.setdefault("theme", render_view.theme)
    repo_themes_root = REPO_ROOT / "themes"
    themes_root = repo_themes_root if repo_themes_root.exists() else WORKSPACE_ROOT / "themes"
    try:
        merged = timeline.resolve_timeline_theme(timeline_config, themes_root)
    except (FileNotFoundError, ValueError):
        merged = None
    if not isinstance(merged, dict) or "visual" not in merged:
        return _theme_for_props(fallback_theme_path)
    return {
        "id": merged.get("id") or merged.get("visual", {}).get("id") or "theme",
        "visual": merged["visual"],
    }


def _timeline_composition_src(project_dir: Path) -> Path | None:
    composition_src = (
        project_dir
        / "node_modules"
        / "@banodoco"
        / "timeline-composition"
        / "typescript"
        / "src"
    )
    return composition_src if composition_src.is_dir() else None


def _registry_output_paths(project_dir: Path) -> list[Path]:
    composition_src = _timeline_composition_src(project_dir)
    package_src = composition_src or (
        WORKSPACE_ROOT / "packages" / "timeline-composition" / "typescript" / "src"
    )
    paths = [
        package_src / f"{kind}.generated.ts"
        for kind in ("effects", "animations", "transitions")
    ]
    remotion_src = REPO_ROOT / "remotion" / "src"
    for kind in ("effects", "animations", "transitions"):
        base = remotion_src / f"{kind}.generated"
        paths.extend(
            Path(f"{base}{extension}") for extension in gen_effect_registry.SHIM_EXTENSIONS
        )
    return paths


def _registry_outputs_exist(project_dir: Path) -> bool:
    return all(path.exists() for path in _registry_output_paths(project_dir))


def _active_theme_pointer_current(theme_path: Path | None) -> bool:
    link = gen_effect_registry.ACTIVE_THEME_LINK
    pointer = gen_effect_registry.ACTIVE_THEME_POINTER
    if theme_path is None:
        return not link.exists() and not pointer.exists()

    theme_dir = _resolve_theme_path(theme_path).parent.resolve()
    if os.name == "nt":
        try:
            return pointer.read_text(encoding="utf-8").strip() == str(theme_dir)
        except OSError:
            return False
    if not link.is_symlink():
        return False
    try:
        return link.resolve() == theme_dir
    except OSError:
        return False


def _effective_registry_state(theme_path: Path | None) -> dict[str, Any]:
    theme_file = _resolve_theme_path(theme_path) if theme_path is not None else None
    return gen_effect_registry.compute_generated_registry_state(theme_dir=theme_file)


def _read_registry_state(project_dir: Path) -> dict[str, Any] | None:
    state_path = project_dir / _REGISTRY_STATE_PATH
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_registry_state(project_dir: Path, state: dict[str, Any]) -> None:
    state_path = project_dir / _REGISTRY_STATE_PATH
    state_path.write_text(
        json.dumps(state, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _regenerate_element_registries(
    project_dir: Path,
    theme_path: Path | None,
) -> None:
    if remotion_lock.remotion_render_lock_held():
        _regenerate_element_registries_locked(project_dir, theme_path)
        return
    with remotion_lock.remotion_render_lock():
        _regenerate_element_registries_locked(project_dir, theme_path)


def _regenerate_element_registries_locked(
    project_dir: Path,
    theme_path: Path | None,
) -> None:
    """Regenerate shared registries while the caller owns the Remotion lock."""

    state = _effective_registry_state(theme_path)
    cached_state = _read_registry_state(project_dir)
    if (
        cached_state is not None
        and cached_state.get("hash") == state.get("hash")
        and _registry_outputs_exist(project_dir)
        and _active_theme_pointer_current(theme_path)
    ):
        return

    generator = REPO_ROOT / "scripts" / "gen_effect_registry.py"
    cmd = [sys.executable, str(generator)]
    if theme_path is not None:
        cmd.extend(["--theme", str(_resolve_theme_path(theme_path))])
    env: dict[str, str] = {}
    composition_src = _timeline_composition_src(project_dir)
    if composition_src is not None:
        env["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
    env.update(remotion_lock.remotion_render_lock_child_env())
    subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=build_child_subprocess_env(explicit_env=env),
        capture_output=True,
        check=True,
        text=True,
    )
    _write_registry_state(project_dir, state)


def _render_asset_stage_hash(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
) -> str:
    digest = hashlib.sha256()
    for path in (timeline_path, assets_path):
        resolved = path.resolve()
        digest.update(str(resolved).encode("utf-8"))
        digest.update(b"\0")
        if resolved.exists():
            digest.update(resolved.read_bytes())
        digest.update(b"\0")
    digest.update(str(out_path.resolve()).encode("utf-8"))
    return digest.hexdigest()[:16]


def _effect_registry_for_assets(
    theme_path: Path | None,
) -> tuple[dict[str, ElementDefinition], dict[str, str]]:
    active_theme = _resolve_theme_path(theme_path) if theme_path is not None else None
    registry = load_default_registry(active_theme=active_theme, project_root=REPO_ROOT)
    effects = {element.id: element for element in registry.list(kind="effects")}
    aliases: dict[str, str] = {}
    if "text-card" in effects:
        aliases["text"] = "text-card"
    for effect_id, element in effects.items():
        raw_aliases = element.metadata.get("clipTypeAliases")
        if not isinstance(raw_aliases, list):
            continue
        for alias in raw_aliases:
            if isinstance(alias, str) and alias:
                aliases[alias] = effect_id
    return effects, aliases


def _effect_id_for_clip(
    clip: dict[str, Any],
    effects: dict[str, ElementDefinition],
    aliases: dict[str, str],
) -> str | None:
    clip_type = clip.get("clipType")
    if not isinstance(clip_type, str) or clip_type == "effect-layer":
        return None
    if clip_type in effects:
        return clip_type
    return aliases.get(clip_type)


def _source_pack_id(element: ElementDefinition) -> str:
    pack_id = element.metadata.get("pack_id")
    if isinstance(pack_id, str) and pack_id:
        return pack_id
    if element.source.startswith("pack:"):
        return element.source.split(":", 1)[1]
    return element.source


def _inject_clip_asset_params(
    clip: dict[str, Any],
    staged_assets: dict[str, str],
) -> None:
    params = clip.get("params")
    next_params = dict(params) if isinstance(params, dict) else {}
    next_params["__astridAssets"] = staged_assets
    clip["params"] = next_params


def _stage_effect_assets_for_timeline(
    timeline_data: dict[str, Any],
    *,
    project_dir: Path,
    theme_path: Path | None,
    render_hash: str,
) -> dict[str, Any]:
    effects, aliases = _effect_registry_for_assets(theme_path)
    clips = timeline_data.get("clips")
    if not isinstance(clips, list):
        return {"root": None, "effects": []}

    used_effect_ids: set[str] = set()
    clip_effect_ids: dict[int, str] = {}
    clip_ids_by_effect: dict[str, list[str]] = {}
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            continue
        effect_id = _effect_id_for_clip(clip, effects, aliases)
        if effect_id is None:
            continue
        used_effect_ids.add(effect_id)
        clip_effect_ids[index] = effect_id
        clip_id = clip.get("id")
        if isinstance(clip_id, str) and clip_id:
            clip_ids_by_effect.setdefault(effect_id, []).append(clip_id)

    if not used_effect_ids:
        return {"root": None, "effects": []}

    public_root = project_dir / "public" / "astrid-effects" / render_hash
    staged_by_effect: dict[str, dict[str, str]] = {}
    for effect_id in sorted(used_effect_ids):
        element = effects[effect_id]
        staged_assets: dict[str, str] = {}
        for asset in element.assets:
            source = (element.root / asset.path).resolve()
            relative_target = Path(effect_id) / asset.path
            target = public_root / relative_target
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            staged_assets[asset.name] = (
                f"astrid-effects/{render_hash}/{relative_target.as_posix()}"
            )
        staged_by_effect[effect_id] = staged_assets

    for index, effect_id in clip_effect_ids.items():
        clip = clips[index]
        if isinstance(clip, dict) and staged_by_effect[effect_id]:
            _inject_clip_asset_params(clip, staged_by_effect[effect_id])
    return {
        "root": str(public_root),
        "effects": [
            {
                "effect_id": effect_id,
                "source_pack_id": _source_pack_id(effects[effect_id]),
                "source": effects[effect_id].source,
                "element_root": str(effects[effect_id].root),
                "clip_ids": sorted(clip_ids_by_effect.get(effect_id, ())),
                "staged_asset_ids": sorted(staged_by_effect[effect_id]),
                "staged_assets": dict(sorted(staged_by_effect[effect_id].items())),
            }
            for effect_id in sorted(used_effect_ids)
        ],
    }


def _render_provenance_sidecar_path(out_path: Path) -> Path:
    return Path(f"{out_path}.provenance.json")


def _active_pack_order_for_provenance() -> list[dict[str, Any]]:
    return [
        {
            "id": discovered.id,
            "source_kind": discovered.source_kind,
            "priority_index": discovered.priority_index,
            "root": str(discovered.pack_dir),
        }
        for discovered in discover_pack_metadata(project_root=REPO_ROOT)
    ]


def _active_theme_for_provenance(
    theme_path: Path | None,
    active_theme: dict[str, Any] | None,
) -> dict[str, Any] | None:
    theme_id = active_theme.get("id") if isinstance(active_theme, dict) else None
    if theme_path is None:
        return {"id": theme_id or "banodoco-default", "path": None}
    resolved = _resolve_theme_path(theme_path)
    return {"id": theme_id or resolved.parent.name, "path": str(resolved)}


def _render_provenance_payload(
    out_path: Path,
    *,
    engine: str,
    timeline_path: Path,
    assets_path: Path,
    project_dir: Path,
    composition_id: str,
    theme_path: Path | None,
    active_theme: dict[str, Any] | None,
    registry_state: dict[str, Any],
    stage_summary: dict[str, Any],
    segments: list[dict[str, float | str]] | None = None,
    segment_provenance: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    effects = list(stage_summary.get("effects") or [])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "engine": engine,
        "output": str(out_path.resolve()),
        "timeline": str(timeline_path.resolve()),
        "assets_registry": str(assets_path.resolve()),
        "project_dir": str(project_dir.resolve()),
        "composition_id": composition_id,
        "active_pack_order": _active_pack_order_for_provenance(),
        "active_theme": _active_theme_for_provenance(theme_path, active_theme),
        "registry_hash": registry_state.get("hash"),
        "registry_state": registry_state,
        "resolved_effect_ids": [
            str(effect["effect_id"]) for effect in effects if "effect_id" in effect
        ],
        "resolved_effects": effects,
        "source_pack_ids": sorted(
            {
                str(effect["source_pack_id"])
                for effect in effects
                if isinstance(effect, dict) and effect.get("source_pack_id")
            }
        ),
        "element_roots": sorted(
            {
                str(effect["element_root"])
                for effect in effects
                if isinstance(effect, dict) and effect.get("element_root")
            }
        ),
        "staged_asset_ids": sorted(
            {
                str(asset_id)
                for effect in effects
                if isinstance(effect, dict)
                for asset_id in effect.get("staged_asset_ids", ())
            }
        ),
        "staged_asset_root": stage_summary.get("root"),
    }
    if segments is not None:
        payload["segments"] = segments
    if segment_provenance is not None:
        payload["segment_provenance"] = segment_provenance
    return payload


def _write_render_provenance(
    out_path: Path,
    *,
    engine: str,
    timeline_path: Path,
    assets_path: Path,
    project_dir: Path,
    composition_id: str,
    theme_path: Path | None,
    active_theme: dict[str, Any] | None,
    registry_state: dict[str, Any],
    stage_summary: dict[str, Any],
    segments: list[dict[str, float | str]] | None = None,
    segment_provenance: list[dict[str, Any]] | None = None,
) -> Path:
    payload = _render_provenance_payload(
        out_path,
        engine=engine,
        timeline_path=timeline_path,
        assets_path=assets_path,
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        active_theme=active_theme,
        registry_state=registry_state,
        stage_summary=stage_summary,
        segments=segments,
        segment_provenance=segment_provenance,
    )
    sidecar_path = _render_provenance_sidecar_path(out_path)
    write_json_atomic(sidecar_path, payload)
    return sidecar_path


def _stderr_tail(stderr: str) -> str:
    lines = stderr.splitlines()
    tail = lines[-40:] if len(lines) > 40 else lines
    return "\n".join(tail).strip()


def _require_free_space(path: Path, min_free_gb: float | None) -> None:
    if min_free_gb is None or min_free_gb <= 0:
        return
    target = path if path.exists() else path.parent
    usage = shutil.disk_usage(target)
    min_free = int(min_free_gb * 1024 * 1024 * 1024)
    if usage.free < min_free:
        free_gb = usage.free / (1024 * 1024 * 1024)
        raise RuntimeError(
            f"Remotion render needs at least {min_free_gb:.1f} GiB free at {target}; "
            f"only {free_gb:.1f} GiB is available"
        )


def _execute_remotion(
    timeline_path: Path,
    assets_path: Path,
    staged_video: Path,
    *,
    provenance_out_path: Path,
    project_dir: Path,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> _ExecutionDetails:
    """Render one private video and return the data needed for provenance."""

    with remotion_lock.remotion_render_lock():
        return _execute_remotion_locked(
            timeline_path,
            assets_path,
            staged_video,
            provenance_out_path=provenance_out_path,
            project_dir=project_dir,
            composition_id=composition_id,
            theme_path=theme_path,
            min_free_gb=min_free_gb,
        )


def _execute_remotion_locked(
    timeline_path: Path,
    assets_path: Path,
    staged_video: Path,
    *,
    provenance_out_path: Path,
    project_dir: Path,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> _ExecutionDetails:
    """Execute one render while the caller owns the non-recursive outer lock."""

    _validate_project_dir(project_dir)
    _regenerate_element_registries(project_dir, theme_path)
    registry_state = _effective_registry_state(theme_path)
    _require_free_space(provenance_out_path.parent, min_free_gb)
    props_path = (provenance_out_path.parent / ".remotion-props.json").resolve()
    render_hash = _render_asset_stage_hash(
        timeline_path,
        assets_path,
        provenance_out_path,
    )
    staged_public_root = project_dir / "public" / "astrid-effects" / render_hash
    with ExitStack() as asset_lifecycle:
        try:
            materializer = asset_lifecycle.enter_context(AssetMaterializer(assets_path))
            asset_server = None
            if materializer.needs_server:
                try:
                    asset_server = asset_lifecycle.enter_context(
                        InvocationAssetServer(materializer.staging_dir)
                    )
                except OSError as exc:
                    raise RuntimeError(
                        f"Permission denied (1100): local HTTP asset server blocked: {exc}"
                    ) from exc
            resolved_registry = materializer.resolved_registry(asset_server)
            resolved_theme = theme_path or (
                WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
            )
            theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
            merged_props = {
                "timeline": _serialize_timeline(
                    timeline_path,
                    default_theme=str(
                        theme_for_props.get("id") or "banodoco-default"
                    ),
                ),
                "assets": resolved_registry,
                "theme": theme_for_props,
            }
            stage_summary = _stage_effect_assets_for_timeline(
                merged_props["timeline"],
                project_dir=project_dir,
                theme_path=theme_path,
                render_hash=render_hash,
            )
            staged_video.parent.mkdir(parents=True, exist_ok=True)
            props_path.write_text(json.dumps(merged_props), encoding="utf-8")
            remotion_env_additions: dict[str, str] = {}
            composition_src = _timeline_composition_src(project_dir)
            if composition_src is not None:
                remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(
                    composition_src
                )
            completed = subprocess.run(
                [
                    "npx",
                    "remotion",
                    "render",
                    composition_id,
                    "--props",
                    str(props_path),
                    "--output",
                    str(staged_video),
                    "--allow-html-in-canvas",
                ],
                cwd=str(project_dir),
                env=build_child_subprocess_env(explicit_env=remotion_env_additions),
                capture_output=True,
                check=False,
                text=True,
            )
            if completed.returncode != 0:
                stderr_tail = _stderr_tail(completed.stderr)
                message = f"Remotion render failed with exit code {completed.returncode}"
                if stderr_tail:
                    message = f"{message}\n{stderr_tail}"
                raise RuntimeError(message)
            if not staged_video.is_file() or staged_video.stat().st_size <= 0:
                raise RuntimeError("Remotion render did not produce a non-empty video")
            return _ExecutionDetails(
                active_theme=theme_for_props,
                registry_state=registry_state,
                stage_summary=stage_summary,
            )
        finally:
            props_path.unlink(missing_ok=True)
            shutil.rmtree(staged_public_root, ignore_errors=True)


def render(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    project_dir: Path | None = None,
    composition_id: str = DEFAULT_COMPOSITION_ID,
    theme_path: Path | None = None,
    min_free_gb: float | None = None,
    previous_outputs: Sequence[Path] = (),
) -> Path:
    """Render privately, then publish the legacy video/provenance pair."""

    timeline_path = Path(timeline_path)
    assets_path = Path(assets_path)
    out_path = Path(out_path)
    project_dir = Path(project_dir) if project_dir is not None else REPO_ROOT / "remotion"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=f".{out_path.name}.publication-",
        dir=str(out_path.parent),
    ) as publication_tmp:
        staged_video = Path(publication_tmp) / out_path.name
        details = _execute_remotion(
            timeline_path,
            assets_path,
            staged_video,
            provenance_out_path=out_path,
            project_dir=project_dir,
            composition_id=composition_id,
            theme_path=theme_path,
            min_free_gb=min_free_gb,
        )
        provenance = _render_provenance_payload(
            out_path,
            engine="remotion",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=project_dir,
            composition_id=composition_id,
            theme_path=theme_path,
            active_theme=details.active_theme,
            registry_state=details.registry_state,
            stage_summary=details.stage_summary,
        )
        output = publish_render_result(
            staged_video,
            provenance,
            out_path=out_path,
            sidecar_path=_render_provenance_sidecar_path(out_path),
            previous_outputs=previous_outputs,
        )

    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(
            kind="timeline",
            path=timeline_path,
            label="Render timeline",
            stage="render_remotion",
        )
        assets_id = audit.register_asset(
            kind="assets_registry",
            path=assets_path,
            label="Render asset registry",
            stage="render_remotion",
        )
        render_id = audit.register_asset(
            kind="render",
            path=output,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_remotion",
            metadata={"composition": composition_id},
        )
        audit.register_node(
            stage="render_remotion",
            label="Render Remotion timeline",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={
                "composition": composition_id,
                "project_dir": str(project_dir),
            },
        )
    return output


def _input_path(raw_path: str, workspace: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    return (candidate if candidate.is_absolute() else workspace / candidate).resolve()


def _theme_setting_path(raw_path: str, workspace: Path) -> Path:
    """Preserve legacy theme slugs while localizing actual request paths."""

    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    localized = workspace / candidate
    if localized.exists() or len(candidate.parts) > 1 or candidate.suffix:
        return localized.resolve()
    return candidate


def _settings_from_request(request: RenderRequest, workspace: Path) -> _RenderSettings:
    config = dict(request.backend_config.get(BACKEND_ID, {}))
    unknown = sorted(set(config) - _CONFIG_KEYS)
    if unknown:
        raise ValueError(f"unknown {BACKEND_ID} configuration: {', '.join(unknown)}")

    project_value = config.get("project_dir", REPO_ROOT / "remotion")
    if not isinstance(project_value, (str, os.PathLike)):
        raise TypeError("project_dir must be a path string")
    project_dir = _input_path(os.fspath(project_value), workspace)

    composition_value = config.get(
        "composition_id",
        config.get("composition", DEFAULT_COMPOSITION_ID),
    )
    if not isinstance(composition_value, str) or not composition_value.strip():
        raise TypeError("composition_id must be a non-empty string")

    theme_value = config.get("theme_path", config.get("theme"))
    if theme_value is None:
        theme_path = None
    elif isinstance(theme_value, (str, os.PathLike)):
        theme_path = _theme_setting_path(os.fspath(theme_value), workspace)
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

    return _RenderSettings(
        project_dir=project_dir,
        composition_id=composition_value,
        theme_path=theme_path,
        min_free_gb=min_free_gb,
    )


def _load_registry_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"assets": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
        raise ValueError("assets registry must be an object containing an assets object")
    return data


def _canonical_profile(
    timeline_path: Path,
    assets_data: Mapping[str, Any],
    settings: _RenderSettings,
) -> RenderProfile:
    fallback_theme = settings.theme_path or (
        WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
    )
    active_theme = _resolved_theme_for_render(timeline_path, fallback_theme)
    return resolve_render_profile(
        timeline_path,
        assets_data,
        theme=active_theme,
        themes_root=REPO_ROOT / "themes",
    )


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


def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
    """Return request-specific evidence for the timeline Remotion can render."""

    reasons: list[str] = []
    features: dict[str, bool | str] = {
        "timeline_composition": True,
        "full_timeline": True,
        "windows": False,
        "effects": True,
        "asset_serving": "invocation-scoped",
    }
    try:
        settings = _settings_from_request(request, workspace)
    except (TypeError, ValueError) as exc:
        settings = _RenderSettings(
            project_dir=REPO_ROOT / "remotion",
            composition_id=DEFAULT_COMPOSITION_ID,
            theme_path=None,
            min_free_gb=None,
        )
        reasons.append(str(exc))

    if request.window is not None:
        reasons.append(
            "rendering.remotion accepts complete timelines, not native frame windows"
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
    except Exception as exc:
        reasons.append(f"timeline is not renderable: {exc}")
    try:
        assets_data = _load_registry_mapping(assets_path)
    except Exception as exc:
        reasons.append(f"assets registry is not renderable: {exc}")

    if timeline_data is not None and assets_data is not None:
        registered_assets = assets_data.get("assets", {})
        missing_asset_ids = sorted(
            {
                str(clip.get("asset"))
                for clip in timeline_data.get("clips", [])
                if isinstance(clip, dict)
                and isinstance(clip.get("asset"), str)
                and clip.get("asset") not in registered_assets
            }
        )
        if missing_asset_ids:
            reasons.append(
                "timeline references missing asset ids: " + ", ".join(missing_asset_ids)
            )
        dynamic_clip_types = sorted(
            {
                str(clip.get("clipType"))
                for clip in timeline_data.get("clips", [])
                if isinstance(clip, dict)
                and clip.get("clipType", "media") != "media"
            }
        )
        if dynamic_clip_types:
            try:
                effects, aliases = _effect_registry_for_assets(settings.theme_path)
            except Exception as exc:
                reasons.append(f"Remotion element registry cannot be resolved: {exc}")
            else:
                unknown_clip_types = [
                    clip_type
                    for clip_type in dynamic_clip_types
                    if clip_type not in effects and clip_type not in aliases
                ]
                if unknown_clip_types:
                    reasons.append(
                        "timeline uses unregistered Remotion clip types: "
                        + ", ".join(unknown_clip_types)
                    )
        try:
            canonical = _canonical_profile(timeline_path, assets_data, settings)
        except Exception as exc:
            reasons.append(f"canonical Remotion profile cannot be resolved: {exc}")
        else:
            canonical_audio = (
                AudioOwnership.RENDERED
                if canonical.has_audio
                else AudioOwnership.NONE
            )
            features["audio_ownership"] = canonical_audio.value
            if request.audio is not None and request.audio is not canonical_audio:
                reasons.append(
                    f"audio={request.audio.value!r} is incompatible with "
                    f"timeline audio ownership {canonical_audio.value!r}"
                )
            if request.profile is not None:
                mismatches = _profile_mismatches(request.profile, canonical)
                if mismatches:
                    reasons.append(
                        "requested profile is not produced by Remotion: "
                        + "; ".join(mismatches)
                    )

    try:
        _validate_project_dir(settings.project_dir)
    except (FileNotFoundError, OSError) as exc:
        reasons.append(str(exc))
    for binary in ("node", "npx"):
        if shutil.which(binary) is None:
            reasons.append(f"required binary is unavailable: {binary}")

    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=not reasons,
        reasons=reasons,
        features=features,
        alternatives=[],
        backend=BACKEND_ID,
        backend_version=BACKEND_VERSION,
    )


def _duration_frames(video_path: Path, profile: RenderProfile) -> int:
    probe = ffprobe_metadata_strict(video_path)
    if probe.duration_rational is not None:
        duration = Fraction(*probe.duration_rational)
    elif probe.duration_seconds is not None:
        duration = Fraction(str(probe.duration_seconds))
    else:
        raise RuntimeError("ffprobe did not report a video duration")
    frames = duration * Fraction(*profile.fps_rational)
    return max(1, int(frames + Fraction(1, 2)))


def _protocol_render(request: RenderRequest, *, workspace: Path) -> RenderResult:
    report = support(request, workspace=workspace)
    if not report.supported:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="Remotion does not support this render request",
            recovery_command="resolve the reported support reasons and retry",
            details={"reasons": report.reasons, "features": report.features},
        )

    settings = _settings_from_request(request, workspace)
    timeline_path = _input_path(request.timeline_path, workspace)
    requested_assets_path = (
        _input_path(request.assets_registry_path, workspace)
        if request.assets_registry_path is not None
        else None
    )
    outputs_dir = workspace / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / request.output_name

    with ExitStack() as lifecycle:
        if requested_assets_path is None:
            empty_assets_tmp = lifecycle.enter_context(
                TemporaryDirectory(prefix=".remotion-empty-assets-", dir=str(workspace))
            )
            assets_path = Path(empty_assets_tmp) / "assets.json"
            timeline.save_registry({"assets": {}}, assets_path)
        else:
            assets_path = requested_assets_path
        assets_data = _load_registry_mapping(assets_path)
        canonical = _canonical_profile(timeline_path, assets_data, settings)
        declared_profile = request.profile or canonical
        # Remotion always muxes MP4 at the 90 kHz timescale regardless of the
        # input timeline's time base; the declared profile must match what the
        # renderer actually produces or strict validation rejects the output.
        declared_profile = replace(declared_profile, time_base=(1, 90000))
        # Remotion always muxes an audio track into its MP4 (silent when the
        # timeline has none), so ownership is effectively 'rendered' and the
        # declared profile must carry the AAC audio fields it always emits.
        ownership = AudioOwnership.RENDERED
        declared_profile = replace(
            declared_profile,
            audio_codec=declared_profile.audio_codec or "aac",
            audio_sample_rate=declared_profile.audio_sample_rate or 48000,
            audio_channel_layout=declared_profile.audio_channel_layout or "stereo",
        )
        private_tmp = lifecycle.enter_context(
            TemporaryDirectory(
                prefix=f".{request.output_name}.remotion-",
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
            composition_id=settings.composition_id,
            theme_path=settings.theme_path,
            min_free_gb=settings.min_free_gb,
        )
        output_path.unlink(missing_ok=True)
        os.replace(staged_video, output_path)

    try:
        provenance_v1 = _render_provenance_payload(
            output_path,
            engine="remotion",
            timeline_path=timeline_path,
            assets_path=requested_assets_path or assets_path,
            project_dir=settings.project_dir,
            composition_id=settings.composition_id,
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
                    "renderer": "remotion",
                    "renderer_version": BACKEND_VERSION,
                    "composition": settings.composition_id,
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
    "DEFAULT_COMPOSITION_ID",
    "main",
    "render",
    "support",
]
