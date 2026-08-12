#!/usr/bin/env python3

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('rendering.render')


import argparse
import ast
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from astrid.core import timeline
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.service import RenderService

# The Hype pipeline's default output file name.  The executor manifest exposes
# an ``output_name`` input defaulting to this sentinel; non-default names are
# validated (plain file name, ``.mp4`` extension) and flow through the same
# placeholder expansion and declared-output resolution as the default.
DEFAULT_OUTPUT_NAME = "hype.mp4"

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


def _write_empty_asset_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timeline.save_registry({"assets": {}}, path)


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
        if value is None:
            continue
        existing = config.get(str(key))
        if existing is None:
            config[str(key)] = dict(value)
        else:
            # Explicit caller configuration overlays, never replaces, the
            # legacy-derived settings so project/theme/composition values
            # survive a partial --backend-config payload.
            overlaid = dict(existing)
            overlaid.update({k: v for k, v in value.items() if v is not None})
            config[str(key)] = overlaid
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
        if args.backend is not None and args.engine != "remotion":
            raise ValueError(
                f"--engine {args.engine!r} and --backend {args.backend!r} "
                "conflict; supply exactly one selector"
            )
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
