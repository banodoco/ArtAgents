"""Backend-neutral rendering helpers shared by the Remotion and Three.js backends.

Only ``astrid.core`` is imported here: this module is the seam that lets
``rendering.threejs`` reuse the Remotion backend's side-effect-free
serialization/profile/provenance helpers without importing the Remotion
backend module itself.

Deliberately NOT included here (backend-specific, see the C0 plan's LEAVE
table): ``_execute_remotion`` (owns the Remotion render lock and the
``npx remotion render`` invocation), settings parsers, project validation,
and the ffmpeg backend's probe-form ``_duration_frames``.
"""

from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

from astrid.core import timeline
from astrid.core.foundation.paths import REPO_ROOT, WORKSPACE_ROOT
from astrid.core.media import ffprobe_metadata_strict
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.core.rendering.contracts import RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.theme import load_theme


def _input_path(raw_path: str, workspace: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    return (candidate if candidate.is_absolute() else workspace / candidate).resolve()


def _load_registry_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"assets": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
        raise ValueError("assets registry must be an object containing an assets object")
    return data


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


def _active_pack_order_for_provenance(
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "id": discovered.id,
            "source_kind": discovered.source_kind,
            "priority_index": discovered.priority_index,
            "root": str(discovered.pack_dir),
        }
        for discovered in discover_pack_metadata(
            project_root=project_root if project_root is not None else REPO_ROOT
        )
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
    active_pack_order: list[dict[str, Any]] | None = None,
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
        "active_pack_order": (
            active_pack_order
            if active_pack_order is not None
            else _active_pack_order_for_provenance()
        ),
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


def _canonical_profile(
    timeline_path: Path,
    assets_data: Mapping[str, Any],
    theme_path: Path | None,
) -> RenderProfile:
    fallback_theme = theme_path or (
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


def _remotion_mux_profile(profile: RenderProfile) -> RenderProfile:
    return replace(
        profile,
        time_base=(1, 90000),
        audio_codec=profile.audio_codec or "aac",
        audio_sample_rate=profile.audio_sample_rate or 48000,
        audio_channel_layout=profile.audio_channel_layout or "stereo",
    )


def _reject_unknown_config(
    config: Mapping[str, Any],
    allowed: frozenset[str],
    backend_id: str,
) -> None:
    unknown = sorted(set(config) - allowed)
    if unknown:
        raise ValueError(f"unknown {backend_id} configuration: {', '.join(unknown)}")


def _parse_min_free_gb(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("min_free_gb must be a number or null")
    min_free_gb = float(value)
    if min_free_gb < 0:
        raise ValueError("min_free_gb must not be negative")
    return min_free_gb
