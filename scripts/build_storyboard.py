#!/usr/bin/env python3
"""Storyboard v1 -> timeline compiler (plan v8 batch B2, executor brief E2).

Compiles a validated storyboard JSON into the render-ready sidecar pair
``timeline.json`` + ``assets.json`` plus a ``resolution_report`` dict dumped
to stdout. The emitted structure is frozen against the astrid-intro golden
build (76 clips / 50 assets / 177.53 s):

- four tracks — ``brand``, ``captions``, ``broll`` (visual) and ``a1`` (audio);
- one brand wordmark text clip at the head (``ASTRID``, top-right, hold =
  the compiled total duration);
- per vo-carrying section EXACTLY three clips, emitted in this order:
  ``vo_{slug}``  — a1 media clip, ``from`` 0 -> ``to`` duration, at start;
  ``cap_{slug}`` — captions text clip, VERBATIM ``vo.text``, fades 0.2/0.2;
  ``broll_{slug}`` — broll media clip on asset ``img_{slug}``,
  hold = duration + GAP;
- sections without ``vo`` compile to their broll plate alone, held for
  ``meta.timing.default_hold`` (no caption, no audio clip, no GAP).

Timing (independent-of-length editing): with ``--vo-align plan.json`` every
section start snaps to its matching plan segment start and the section
duration IS the plan segment duration; without a plan, durations are probed
from the VO wav via ffprobe and section starts accumulate the previous holds.
All emitted times are rounded to millisecond precision. A plan that misses a
section slug fails closed listing every missing slug.

Managed media (ONE store): every referenced PNG/WAV is imported through the
kernel SDK (``MediaService.import_file``, managed_local CAS realm, projects
root from ``ASTRID_PROJECTS_ROOT``) — there is deliberately NO fallback to a
raw file reference when import fails. Registry entries carry the returned CAS
locator, the returned ``content_sha256``, a media ``type``, and a
contract-valid ``origin`` enum (``refreshable-from-generation`` for
regenerable gen-variant images and VO audio, ``immutable-public`` for baked
asset-variant images). The brief's per-asset provenance ``{prompt,
generator}`` cannot live inside the registry — the frozen registry contract
allows only the three-value ``origin`` enum — so it is carried verbatim in the
resolution_report (per slug, image + vo) and, for generative image variants,
on the broll clip's ``generation`` block.

The resolution_report maps slug -> resolved image variant + VO import facts
and is persisted ONLY to stdout/build artifacts; the storyboard JSON file is
never written back.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

# Run from any checkout/worktree: bind astrid imports to THIS tree, not an
# editable install pointing elsewhere (same pattern as gen_effect_registry).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from astrid.core.foundation.atomic_io import write_json_atomic  # noqa: E402
from astrid.core.media import ffprobe_duration_seconds  # noqa: E402
from astrid.core.storyboard import (  # noqa: E402
    StoryboardError,
    load_storyboard,
    validate_storyboard,
)
from astrid.core.timeline.banodoco_schema import canonical_timeline_config  # noqa: E402
from astrid.core.timeline.validators.registry import validate_registry  # noqa: E402

__all__ = [
    "AssetImport",
    "GAP",
    "compile_storyboard",
    "main",
    "make_client_importer",
    "probe_wav_duration",
    "sdk_import_asset",
]

GAP = 0.35
"""Inter-section breathing room added to every VO-carrying broll/caption hold."""

DEFAULT_OUTPUT_NAME = "storyboard.mp4"
DEFAULT_PROJECT = "astrid-intro"
"""Default kernel project for managed imports (the D3/D4 intro target)."""

_THEME = "banodoco-default"
_BACKGROUND_COLOR = "#0b0b0d"

_TRACKS: tuple[dict[str, str], ...] = (
    {"id": "brand", "kind": "visual", "label": "Brand"},
    {"id": "captions", "kind": "visual", "label": "Captions"},
    {"id": "broll", "kind": "visual", "label": "B-Roll"},
    {"id": "a1", "kind": "audio", "label": "VO"},
)

# Caption styling frozen against the astrid-intro golden build.
_CAPTION_TEXT_STYLE = {"fontSize": 30, "color": "#ffffff", "align": "center", "bold": False}
_CAPTION_PARAMS = {
    "anchor": "bottom-center",
    "offsetY": 56,
    "weight": 500,
    "maxWidth": 1500,
    "textShadow": "0 1px 4px rgba(0,0,0,0.95)",
}
_CAPTION_FADES = {"fade_in": 0.2, "fade_out": 0.2}

# Brand wordmark styling frozen against the astrid-intro golden build.
_BRAND_TEXT = {"content": "ASTRID", "fontSize": 30, "color": "#ffffff", "align": "right", "bold": True}
_BRAND_PARAMS = {
    "anchor": "top-right",
    "offsetX": 48,
    "offsetY": 40,
    "textShadow": "0 2px 10px rgba(0,0,0,0.75)",
}

_DEFAULT_TTS_GENERATOR = "tts"
"""Honest default for VO provenance when ``vo.audio.generator`` is not authored."""


@dataclass(frozen=True)
class AssetImport:
    """One managed import receipt: CAS locator, byte digest, kernel media id."""

    file: str
    content_sha256: str
    media_id: str | None = None


# ---------------------------------------------------------------------------
# Managed import seam (kernel SDK by default; monkeypatchable in tests)
# ---------------------------------------------------------------------------

_SHARED_CLIENT: Any = None
"""Lazily opened client behind :func:`sdk_import_asset` (see close_shared_client)."""


def sdk_import_asset(path: Path, *, project: str = DEFAULT_PROJECT) -> AssetImport:
    """Import *path* through the kernel SDK against ``ASTRID_PROJECTS_ROOT``.

    One shared client is opened lazily and reused across a whole compile; the
    exclusive-owner lock means a second owner of the same root fails closed
    with the kernel's typed ``unavailable`` error rather than silently
    degrading. Close it with :func:`close_shared_client` (``main`` does).
    """
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None:
        from astrid.sdk.client import AstridClient

        _SHARED_CLIENT = AstridClient.open(None)
    return _client_import(_SHARED_CLIENT, project, path)


def close_shared_client() -> None:
    """Close the lazily opened shared client (idempotent)."""
    global _SHARED_CLIENT
    if _SHARED_CLIENT is not None:
        _SHARED_CLIENT.close()
        _SHARED_CLIENT = None


def make_client_importer(client: Any, *, project: str) -> Callable[[Path], AssetImport]:
    """Return an importer closure bound to a caller-owned open client."""

    def import_asset(path: Path) -> AssetImport:
        return _client_import(client, project, path)

    return import_asset


def _client_import(client: Any, project: str, path: Path) -> AssetImport:
    result = client.media.import_file(project=project, path=str(path))
    if not result.ok:
        error = result.error
        raise StoryboardError(
            [f"managed import failed for {path}: {error.code}: {error.message}"]
        )
    data = result.data or {}
    locator = next(
        (
            location.get("locator")
            for location in data.get("locations", [])
            if location.get("realm") == "managed_local"
        ),
        None,
    )
    digest = data.get("content_hash")
    if not isinstance(locator, str) or not locator:
        raise StoryboardError(
            [f"managed import for {path} returned no managed_local CAS locator"]
        )
    if not isinstance(digest, str) or not digest:
        raise StoryboardError([f"managed import for {path} returned no content hash"])
    media_id = data.get("id")
    return AssetImport(
        file=locator,
        content_sha256=digest,
        media_id=media_id if isinstance(media_id, str) else None,
    )


def probe_wav_duration(path: Path) -> float:
    """Probe one VO wav's duration in seconds (strict ffprobe)."""
    return float(ffprobe_duration_seconds(path))


# ---------------------------------------------------------------------------
# Compiler core
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Segment:
    slug: str
    start: float
    duration: float


def compile_storyboard(
    story: dict[str, Any],
    *,
    base_dir: str | Path,
    plan: Mapping[str, Any] | None = None,
    import_asset: Callable[[Path], AssetImport] | None = None,
    probe_duration: Callable[[Path], float] | None = None,
    project: str = DEFAULT_PROJECT,
    output_name: str = DEFAULT_OUTPUT_NAME,
    projects_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Compile *story* into ``(timeline_config, assets_registry, resolution_report)``.

    Pure with respect to the kernel: every side effect flows through the
    import seam (default: :func:`sdk_import_asset`, i.e. managed SDK imports)
    and the duration probe (default: ffprobe). ``plan`` is a parsed
    ``plan.json`` mapping (``{"segments": [{slug, start, duration}], ...}``);
    when given, section starts snap to plan segment starts and durations come
    from the plan. Raises :class:`StoryboardError` listing every problem at
    once; the storyboard input is never mutated or written back.
    """
    base = Path(base_dir)
    problems = validate_storyboard(story, base_dir=base)
    if problems:
        raise StoryboardError(problems)
    if probe_duration is None:
        probe_duration = probe_wav_duration

    segments = _plan_segments(plan)
    if segments is not None:
        missing = [s["id"] for s in story["sections"] if s["id"] not in segments]
        if missing:
            raise StoryboardError(
                [
                    f"--vo-align plan has no segment for section {slug!r}"
                    for slug in missing
                ]
            )

    width, height, fps = _parse_canvas(story["meta"]["canvas"])
    default_hold = float(story["meta"]["timing"]["default_hold"])

    assets: dict[str, Any] = {}
    section_clips: list[dict[str, Any]] = []
    report_sections: dict[str, Any] = {}
    cursor = 0.0
    total = 0.0

    for section in story["sections"]:
        slug = section["id"]
        segment = segments.get(slug) if segments is not None else None

        # Image path XOR active variant
        img_key = f"img_{slug}"
        image_cfg = section["image"]
        direct_path = image_cfg.get("path")
        variants = image_cfg.get("variants") or []
        if direct_path is not None and not variants:
            img_path = _resolve_path(direct_path, base)
            img_origin = image_cfg.get("provenance") or {}
        else:
            active_index = image_cfg.get("active_index", 0)
            if not isinstance(active_index, int) or not (0 <= active_index < len(variants)):
                raise StoryboardError(
                    [f"sections[{slug}].image: active_index {active_index} out of bounds for {len(variants)} variants"]
                )
            active_variant = variants[active_index]
            img_path, img_origin = _variant_import_path(active_variant, base, f"sections[{slug}].image")
        if import_asset is not None:
            img_import = import_asset(img_path)
        else:
            img_import = sdk_import_asset(img_path, project=project)
        assets[img_key] = {
            "file": img_import.file,
            "type": "image",
            "content_sha256": img_import.content_sha256,
            "origin": "refreshable-from-generation" if img_origin else "immutable-public",
        }

        vo = section.get("vo")
        vo_report: dict[str, Any] | None = None
        duration: float | None = None
        start = cursor
        if vo is not None:
            audio = vo.get("audio") or {}
            wav_path = _resolve_path(audio["asset"], base)
            where = f"sections[{slug}].vo"
            duration = (
                segment.duration
                if segment is not None
                else _positive_duration(probe_duration(wav_path), f"{where}.audio.asset")
            )
            start = segment.start if segment is not None else cursor
            vo_key = f"vo_{slug}"
            if import_asset is not None:
                vo_import = import_asset(wav_path)
            else:
                vo_import = sdk_import_asset(wav_path, project=project)
            generator = audio.get("generator")
            if not isinstance(generator, str) or not generator:
                generator = _DEFAULT_TTS_GENERATOR
            assets[vo_key] = {
                "file": vo_import.file,
                "type": "audio",
                "duration": round(duration, 3),
                "content_sha256": vo_import.content_sha256,
                "origin": "refreshable-from-generation",
            }
            vo_report = {
                "asset_key": vo_key,
                "source_path": str(audio["asset"]),
                "file": vo_import.file,
                "content_sha256": vo_import.content_sha256,
                "media_id": vo_import.media_id,
                "duration": round(duration, 3),
                "origin": {"prompt": vo.get("text") or "", "generator": generator},
            }

        start_r = round(start, 3)
        if vo is not None and duration is not None:
            hold_r = round(duration + GAP, 3)
            section_clips.append(
                {
                    "id": f"vo_{slug}",
                    "at": start_r,
                    "track": "a1",
                    "clipType": "media",
                    "asset": f"vo_{slug}",
                    "from": 0.0,
                    "to": round(duration, 3),
                }
            )
            if vo.get("text"):
                section_clips.append(
                    {
                        "id": f"cap_{slug}",
                        "at": start_r,
                        "track": "captions",
                        "clipType": "text",
                        "hold": hold_r,
                        "text": {"content": vo["text"], **_CAPTION_TEXT_STYLE},
                        "params": dict(_CAPTION_PARAMS),
                        "effects": dict(_CAPTION_FADES),
                    }
                )
            broll: dict[str, Any] = {
                "id": f"broll_{slug}",
                "at": start_r,
                "track": "broll",
                "clipType": "media",
                "asset": img_key,
                "hold": hold_r,
            }
            if img_origin:
                broll["generation"] = img_origin
            section_clips.append(broll)
        else:
            # No VO: the broll plate stands alone for the authored default hold.
            hold_r = round(default_hold, 3)
            broll = {
                "id": f"broll_{slug}",
                "at": start_r,
                "track": "broll",
                "clipType": "media",
                "asset": img_key,
                "hold": hold_r,
            }
            if img_origin:
                broll["generation"] = {"prompt": img_origin} if img_origin else {}
            section_clips.append(broll)

        cursor = max(cursor, start_r + hold_r)
        total = max(total, start_r + hold_r)
        report_sections[slug] = {
            "image": {
                "path": str(img_path),
                "asset_key": img_key,
                "file": img_import.file,
                "content_sha256": img_import.content_sha256,
                "media_id": img_import.media_id,
            },
            "vo": vo_report,
        }

    total_r = round(total, 3)
    clips = [
        {
            "id": "brand_wordmark",
            "at": 0.0,
            "track": "brand",
            "clipType": "text",
            "hold": total_r,
            "text": dict(_BRAND_TEXT),
            "params": dict(_BRAND_PARAMS),
        },
        *section_clips,
    ]
    config: dict[str, Any] = {
        "theme": _THEME,
        "theme_overrides": {
            "visual": {
                "canvas": {"width": width, "height": height, "fps": fps},
                "backgroundColor": _BACKGROUND_COLOR,
            }
        },
        "tracks": [dict(track) for track in _TRACKS],
        "clips": clips,
        "output": {"resolution": f"{width}x{height}", "fps": fps, "file": output_name},
    }
    registry = {"assets": assets}
    # Fail close on the frozen contracts before anything reaches a writer.
    canonical_timeline_config(config)
    validate_registry(registry)
    report = {
        "total_duration": total_r,
        "clips": len(clips),
        "assets": len(assets),
        "sections": report_sections,
    }
    return config, registry, report



def _build_shot_subtimeline(
    story: dict[str, Any],
    section: dict[str, Any],
    image_key: str,
    vo_key: str | None,
    duration: float,
) -> dict[str, Any]:
    """Create a SHOT sub-timeline document for one section (vo a1 / cap captions / broll broll).
    
    The sub-timeline is a self-contained temporal document with LOCAL ``at=0`` for all clips
    and ``hold``/``to`` matching the flat per-section durations. It serves as the timeline
    document reference for the parent shot graph.
    """
    # Use the section's authored timing as the sub-timeline duration
    hold_r = round(duration + GAP, 3)
    
    width, height, fps = _parse_canvas(story["meta"]["canvas"])
    
    clips = []
    # VO on audio track a1
    if vo_key is not None:
        vo_start = 0.0
        vo_end = round(duration, 3)
        clips.append(
            {
                "id": f"vo_{section['id']}",
                "at": vo_start,
                "track": "a1",
                "clipType": "media",
                "asset": vo_key,
                "from": 0.0,
                "to": vo_end,
            }
        )
        
        # Captions over VO
        vo_text = section.get("vo", {}).get("text", "")
        if vo_text:
            clips.append(
                {
                    "id": f"cap_{section['id']}",
                    "at": vo_start,
                    "track": "captions",
                    "clipType": "text",
                    "hold": hold_r,
                    "text": {"content": vo_text, **_CAPTION_TEXT_STYLE},
                    "params": dict(_CAPTION_PARAMS),
                    "effects": dict(_CAPTION_FADES),
                }
            )
    
    # B-roll on visual track broll
    broll_start = 0.0
    broll_end = hold_r
    broll_clip = {
        "id": f"broll_{section['id']}",
        "at": broll_start,
        "track": "broll",
        "clipType": "media",
        "asset": image_key,
        "hold": broll_end,
    }
    
    # B-roll may have generative provenance (variant.source == 'gen')
    img_origin = None
    variants = section.get("image", {}).get("variants", [])
    active_index = section.get("image", {}).get("active_index", 0)
    if 0 <= active_index < len(variants):
        active_variant = variants[active_index]
        if active_variant.get("source") == "gen":
            img_origin = active_variant.get("prompt", "")
    if img_origin:
        broll_clip["generation"] = {"prompt": img_origin}
    
    clips.append(broll_clip)
    
    config: dict[str, Any] = {
        "theme": _THEME,
        "theme_overrides": {
            "visual": {
                "canvas": {"width": width, "height": height, "fps": fps},
                "backgroundColor": _BACKGROUND_COLOR,
            }
        },
        "tracks": [dict(track) for track in _TRACKS],
        "clips": clips,
        "output": {"resolution": f"{width}x{height}", "fps": fps, "file": f"shot-{section['id']}.mp4"},
    }
    return config


def _plan_segments(plan: Any) -> dict[str, _Segment] | None:
    """Validate a parsed plan.json and return slug -> segment (or None)."""
    if plan is None:
        return None
    if not isinstance(plan, Mapping):
        raise StoryboardError(["--vo-align plan must be a JSON object"])
    segments = plan.get("segments")
    if not isinstance(segments, list) or not segments:
        raise StoryboardError(["plan.segments must be a non-empty list"])
    problems: list[str] = []
    mapping: dict[str, _Segment] = {}
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            problems.append(f"plan.segments[{index}] must be an object")
            continue
        slug = segment.get("slug")
        if not isinstance(slug, str) or not slug:
            problems.append(f"plan.segments[{index}].slug must be a non-empty string")
            continue
        start = segment.get("start")
        if not _is_number(start) or start < 0:
            problems.append(f"plan.segments[{index}].start must be a number >= 0")
            continue
        duration = segment.get("duration")
        if not _is_number(duration) or duration <= 0:
            problems.append(f"plan.segments[{index}].duration must be a number > 0")
            continue
        if slug in mapping:
            problems.append(f"plan.segments[{index}]: duplicate slug {slug!r}")
            continue
        mapping[slug] = _Segment(slug=slug, start=float(start), duration=float(duration))
    if problems:
        raise StoryboardError(problems)
    return mapping


def _variant_import_path(
    variant: Mapping[str, Any], base: Path, where: str
) -> tuple[Path, dict[str, Any]]:
    """Return ``(import path, generative provenance)`` for one image variant."""
    source = variant.get("source")
    if source == "asset":
        return _resolve_path(variant["path"], base), {}
    if source == "gen":
        alt = variant.get("alt_render_path")
        if not isinstance(alt, str) or not alt:
            raise StoryboardError(
                [
                    f"{where}: gen variant has no alt_render_path to import — "
                    "capture a rendered artifact first"
                ]
            )
        origin = {
            "prompt": variant.get("prompt") or "",
            "generator": variant.get("model") or "gen",
        }
        return _resolve_path(alt, base), origin
    raise StoryboardError([f"{where}: variant.source must be 'asset' or 'gen'"])


def _resolve_path(raw: str, base: Path) -> Path:
    """Resolve an authored path: expanduser, then absolute or base-relative."""
    path = Path(os.path.expanduser(raw))
    return path if path.is_absolute() else base / path


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_canvas(canvas: str) -> tuple[int, int, int]:
    """Parse a validated ``meta.canvas`` ``WIDTHxHEIGHT@FPS`` string."""
    size, _, fps = canvas.partition("@")
    width, _, height = size.partition("x")
    return int(width), int(height), int(fps)


def _positive_duration(value: float, where: str) -> float:
    if not _is_number(value) or value <= 0:
        raise StoryboardError([f"{where}: probed duration must be a positive number"])
    return float(value)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_storyboard",
        description="Compile a storyboard v1 JSON into render-ready timeline sidecars.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_cmd = subparsers.add_parser(
        "validate", help="Validate a storyboard JSON without compiling."
    )
    validate_cmd.add_argument(
        "--story", required=True, help="Storyboard JSON path (may be relative)."
    )
    validate_cmd.set_defaults(handler=_cmd_validate)
    compile_cmd = subparsers.add_parser(
        "compile", help="Compile a storyboard into timeline.json + assets.json."
    )
    compile_cmd.add_argument(
        "--story", required=True, help="Storyboard JSON path (may be relative)."
    )
    compile_cmd.add_argument(
        "--vo-align",
        default=None,
        metavar="PLAN_JSON",
        help="Optional VO alignment plan.json ({segments: [{slug, start, duration}, …]}); "
        "snaps section starts to VO segment times.",
    )
    compile_cmd.add_argument(
        "--shots",
        action="store_true",
        default=False,
        help="Enable shot projection: compile with kernel writes (parent timeline + shots sub-timelines). Flat emitter stays default.",
    )
    compile_cmd.add_argument(
        "--out",
        default=None,
        metavar="DIR",
        help="Output directory (default: <story dir>/../timeline).",
    )
    compile_cmd.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help="Kernel project slug for managed imports (default: %(default)s).",
    )
    compile_cmd.add_argument(
        "--projects-root",
        default=None,
        help="Projects root override (default: ASTRID_PROJECTS_ROOT env or the "
        "standard default).",
    )
    compile_cmd.add_argument(
        "--output-name",
        default=DEFAULT_OUTPUT_NAME,
        help="Output file name recorded in timeline.output.file and used by a bare "
        "--render (default: %(default)s).",
    )
    compile_cmd.add_argument(
        "--render",
        nargs="?",
        const="",
        default=None,
        metavar="NAME",
        help="After compiling, render through the SDK 'rendering.render' capability "
        "(optional value: output name; default: --output-name). The compiled "
        "timeline must live under the owning project's tree.",
    )
    compile_cmd.set_defaults(handler=_cmd_compile)
    return parser


def _cmd_validate(args: argparse.Namespace) -> int:
    story_path = Path(args.story).expanduser().resolve()
    try:
        story = load_storyboard(story_path)
    except StoryboardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for problem in getattr(exc, "problems", []) or []:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    problems = validate_storyboard(story)
    if problems:
        print("error: storyboard validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"OK {story_path} ({len(story.get('sections', []))} sections)")
    return 0





def _compile_with_shots(
    story: dict[str, Any],
    *,
    base_dir: str | Path,
    plan: Mapping[str, Any] | None = None,
    import_asset: Callable[[Path], AssetImport] | None = None,
    probe_duration: Callable[[Path], float] | None = None,
    project: str = DEFAULT_PROJECT,
    output_name: str = DEFAULT_OUTPUT_NAME,
    client: Any | None = None,
) -> dict[str, Any]:
    """Compile a storyboard with shot projection (task T11).
    
    Creates per-section sub-timelines via TimelinesService, shots via ShotsService,
    and a parent shot graph. All kernel writes go through the SDK services.
    """
    from astrid.sdk.client import AstridClient

    base = Path(base_dir)
    if probe_duration is None:
        probe_duration = probe_wav_duration
    
    segments = _plan_segments(plan)
    width, height, fps = _parse_canvas(story["meta"]["canvas"])
    
    # Import all media first
    assets: dict[str, Any] = {}
    vo_durations: dict[str, float] = {}
    
    for section in story["sections"]:
        slug = section["id"]
        image_cfg = section["image"]
        direct_path = image_cfg.get("path")
        variants = image_cfg.get("variants") or []
        if direct_path is not None and not variants:
            img_path = _resolve_path(direct_path, base)
            img_origin = image_cfg.get("provenance") or {}
        else:
            active_index = image_cfg.get("active_index", 0)
            active_variant = variants[active_index]
            img_path, img_origin = _variant_import_path(active_variant, base, f"sections[{slug}].image")
        
        if import_asset is not None:
            img_import = import_asset(img_path)
        else:
            img_import = sdk_import_asset(img_path, project=project)
        
        img_key = f"img_{slug}"
        assets[img_key] = {
            "file": img_import.file,
            "type": "image",
            "content_sha256": img_import.content_sha256,
            "media_id": img_import.media_id,
        }
        
        # VO
        vo = section.get("vo")
        if vo is not None:
            audio = vo.get("audio") or {}
            wav_path = _resolve_path(audio["asset"], base)
            where = f"sections[{slug}].vo"
            duration = probe_duration(wav_path)
            vo_durations[slug] = duration
            
            vo_key = f"vo_{slug}"
            if import_asset is not None:
                vo_import = import_asset(wav_path)
            else:
                vo_import = sdk_import_asset(wav_path, project=project)
            assets[vo_key] = {
                "file": vo_import.file,
                "type": "audio",
                "duration": round(duration, 3),
                "content_sha256": vo_import.content_sha256,
                "media_id": vo_import.media_id,
            }
    
    # Create shots and sub-timelines against the caller's projects root.
    if client is None:
        raise StoryboardError(
            ["_compile_with_shots requires the caller's open AstridClient"]
        )
    shots_service = client.shots
    timelines_service = client.timelines
        
    shot_data: dict[str, dict[str, Any]] = {}  # slug -> {shot_id, timeline_document_id, nav, prompt}
    
    for section in story["sections"]:
        slug = section["id"]
        segment = segments.get(slug) if segments is not None else None
        
        # Calculate duration for this section
        duration = None
        if segment is not None:
            duration = segment.duration
        elif slug in vo_durations:
            duration = vo_durations[slug]
        
        if duration is None:
            raise StoryboardError([f"section {slug} has no duration"])
        
        # Create sub-timeline
        vo_key = f"vo_{slug}"
        sub_timeline_config = _build_shot_subtimeline(story, section, f"img_{slug}", vo_key if vo_key in assets else None, duration)
        slug_tl = slug.replace("_", "-")
        timeline_result = timelines_service.create(
            project=project,
            slug=f"shot-{slug_tl}",
            name=f"shot-{slug_tl}",
            config=sub_timeline_config,
            registry={"assets": _canonical_assets({k: v for k, v in assets.items() if k in (f"img_{slug}", f"vo_{slug}")})},
            idempotency_key=f"{project}:shot-timeline:{slug}",
        )
        assert timeline_result.ok, getattr(timeline_result, "error", None)
        timeline_document_id = timeline_result.data["timeline_id"]
        
        # Create shot
        nav = section.get("nav", {})
        prompt = section.get("provenance", {}).get("prompt", "")
        shot_result = shots_service.create(
            project=project,
            name=f"shot-{slug}",
            idempotency_key=f"{project}:shot:{slug}",
            metadata={"slug": slug, "nav": nav, "prompt": prompt, "timeline_document_id": timeline_document_id},
        )
        assert shot_result.ok
        shot_id = shot_result.data["id"]
        
        shot_data[slug] = {
            "shot_id": shot_id,
            "timeline_document_id": timeline_document_id,
            "nav": nav,
            "prompt": prompt,
        }
        
        # Add image item
        img_key = f"img_{slug}"
        item_result = shots_service.add_item(
            project=project,
            shot_id=shot_id,
            media_id=assets[img_key]["media_id"],
            position=0,
            idempotency_key=f"{project}:shot-item:{slug}:image",
        )
        assert item_result.ok
        
        # Add VO item if exists
        vo_key = f"vo_{slug}"
        if vo_key in assets:
            item_result = shots_service.add_item(
                project=project,
                shot_id=shot_id,
                media_id=assets[vo_key]["media_id"],
                position=1,
                idempotency_key=f"{project}:shot-item:{slug}:vo",
            )
            assert item_result.ok

    # Create parent shot graph
    total = 0.0
    for section in story["sections"]:
        if "vo" in section:
            duration = vo_durations.get(section["id"], 0.0)
            total = max(total, duration + GAP)
    
    total_r = round(total, 3)
    
    brand_clip = {
        "id": "brand_wordmark",
        "at": 0.0,
        "track": "brand",
        "clipType": "text",
        "hold": total_r,
        "text": dict(_BRAND_TEXT),
        "params": dict(_BRAND_PARAMS),
    }
    
    shot_clips = []
    for slug, data in shot_data.items():
        shot_clip = {
            "id": f"shot_{slug}",
            "at": 0.0,
            "track": "broll",
            "clipType": "shot",
            "hold": total_r,
            "params": {"shot_id": data["shot_id"], "timeline_document_id": data["timeline_document_id"]},
        }
        shot_clips.append(shot_clip)
    
    parent_config = {
        "theme": _THEME,
        "theme_overrides": {
            "visual": {
                "canvas": {"width": width, "height": height, "fps": fps},
                "backgroundColor": _BACKGROUND_COLOR,
            }
        },
        "tracks": [dict(track) for track in _TRACKS],
        "clips": [brand_clip] + shot_clips,
        "output": {"resolution": f"{width}x{height}", "fps": fps, "file": f"parent-shot-graph.mp4"},
    }

    return {
        "timeline": parent_config,
        "assets": _canonical_assets(assets),
        "shots": shot_data,
    }


def _cmd_compile(args: argparse.Namespace) -> int:
    story_path = Path(args.story).expanduser()
    story = load_storyboard(story_path)
    plan = None
    if args.vo_align:
        plan = json.loads(
            Path(args.vo_align).expanduser().read_text(encoding="utf-8")
        )
    out_dir = (
        Path(args.out).expanduser()
        if args.out
        else story_path.resolve().parent.parent / "timeline"
    )
    timeline_path = out_dir / "timeline.json"
    assets_path = out_dir / "assets.json"

    if args.render is not None:
        render_name = args.output_name if args.render == "" else args.render
        from astrid.sdk.client import AstridClient

        with AstridClient.open(args.projects_root) as client:
            importer = make_client_importer(client, project=args.project)
            config, registry, report = compile_storyboard(
                story,
                base_dir=story_path.resolve().parent,
                plan=plan,
                import_asset=importer,
                output_name=args.output_name,
            )
            _write_outputs(timeline_path, assets_path, config, registry)
            _print_report(report)
            return _invoke_render(
                client,
                project=args.project,
                timeline_path=timeline_path,
                assets_path=assets_path,
                output_name=render_name,
            )

    # Shot projection path (--shots)
    if args.shots:
        from astrid.sdk.client import AstridClient

        with AstridClient.open(args.projects_root) as client:
            import_asset = make_client_importer(client, project=args.project)
            shots_result = _compile_with_shots(
                story,
                base_dir=story_path.resolve().parent,
                plan=plan,
                import_asset=import_asset,
                project=args.project,
                output_name=args.output_name,
                client=client,
            )
        # Write parent timeline and assets
        _write_outputs(timeline_path, assets_path, shots_result["timeline"], {"assets": shots_result["assets"]})
        # Print report summary
        print_report_shots(shots_result)
        return 0

    config, registry, report = compile_storyboard(
        story,
        base_dir=story_path.resolve().parent,
        plan=plan,
        project=args.project,
        output_name=args.output_name,
    )
    _write_outputs(timeline_path, assets_path, config, registry)
    _print_report(report)
    return 0

def print_report_shots(result: dict[str, Any]) -> None:
    """Print a brief report for shot projection compile."""
    assets = result["assets"]
    shots = result["shots"]
    print(json.dumps({
        "mode": "shots",
        "clips": len(result["timeline"]["clips"]),
        "assets": len(assets),
        "shots_created": len(shots),
        "timeline_file": result["timeline"]["output"]["file"],
    }, indent=2, sort_keys=True))



def _canonical_assets(assets: dict[str, Any]) -> dict[str, Any]:
    """Registry entries for kernel storage (no private media_id key)."""
    out: dict[str, Any] = {}
    for key, entry in assets.items():
        out[key] = {k: v for k, v in entry.items() if k != "media_id"}
    return out


def _write_outputs(
    timeline_path: Path, assets_path: Path, config: dict[str, Any], registry: dict[str, Any]
) -> None:
    write_json_atomic(timeline_path, config)
    write_json_atomic(assets_path, registry)


def _print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, indent=2, sort_keys=True))


def _invoke_render(
    client: Any,
    *,
    project: str,
    timeline_path: Path,
    assets_path: Path,
    output_name: str,
) -> int:
    """Thin passthrough to the SDK ``rendering.render`` capability (raw-file mode)."""
    result = client.invoke_result(
        "rendering.render",
        kind="executor",
        project=project,
        inputs={
            "timeline": str(timeline_path),
            "assets_registry": str(assets_path),
            "output_name": output_name,
        },
    )
    envelope = {
        "ok": result.ok,
        "run_id": result.run_id,
        "kernel_run_id": result.kernel_run_id,
        "outputs": result.outputs,
    }
    if not result.ok and result.error is not None:
        envelope["error"] = result.error
    print(json.dumps(envelope, indent=2, sort_keys=True, default=str))
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (
        StoryboardError,
        OSError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        close_shared_client()


if __name__ == "__main__":
    raise SystemExit(main())
