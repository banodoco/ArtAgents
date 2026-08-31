#!/usr/bin/env python3

# The canonical-entrypoint guard intentionally runs before imports.
# ruff: noqa: E402

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("rendering.render")


import argparse
import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from astrid.core import timeline
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.foundation.project_paths import resolve_projects_root
from astrid.core.rendering.errors import RendererException
from astrid.core.rendering.output_policy import (
    DEFAULT_RENDER_OUTPUT_NAME,
    validate_output_basename,
)
from astrid.core.rendering.service import RenderService

# The Hype pipeline's default output file name.  The executor manifest exposes
# an ``output_name`` input defaulting to this sentinel; non-default names are
# validated as plain file names and flow through the same
# placeholder expansion and declared-output resolution as the default.
DEFAULT_OUTPUT_NAME = DEFAULT_RENDER_OUTPUT_NAME

_SERVICE: RenderService | None = None
_MAX_CLI_ERROR_CHARS = 3_500


def _renderer_cli_error(exc: RendererException) -> str:
    """Keep structured renderer reasons actionable across the CLI boundary."""

    lines = [str(exc)]
    reasons = exc.error.details.get("reasons")
    if isinstance(reasons, list):
        for reason in reasons:
            text = str(reason).strip()
            if text:
                lines.append(f"reason: {text}")
    message = "\n".join(lines)
    if len(message) <= _MAX_CLI_ERROR_CHARS:
        return message
    return message[: _MAX_CLI_ERROR_CHARS - 30] + "\n…renderer detail truncated…"


def _default_service() -> RenderService:
    """Build (once) the backend-neutral service the facade delegates to.

    Renderer selection, invocation, validation, audio completion, finalization,
    and publication all happen inside :class:`RenderService`.
    """
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RenderService()
    return _SERVICE


def validate_output_name(name: str) -> str:
    """Validate only portable-basename safety at the executor boundary.

    The shared RenderService policy owns the media suffix decision because it
    can inspect the timeline's alpha stamp and explicit render profile.
    """

    return validate_output_basename(name)


def _backend_config(
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> dict[str, dict[str, Any]]:
    """Build explicit configuration for the canonical Remotion backend."""
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
        raise ValueError("--backend-config must be a JSON object keyed by qualified backend id")
    return {str(key): dict(item) for key, item in parsed.items() if item is not None}


def _parse_profile(value: str | Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """Parse the public render-profile input before request admission."""
    if value is None or value == "":
        return None
    if isinstance(value, Mapping):
        return dict(value)
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise ValueError("--profile must be a JSON object describing a render profile") from exc
    if not isinstance(parsed, Mapping):
        raise ValueError("--profile must be a JSON object describing a render profile")
    return dict(parsed)


def _rewrite_provenance_output_path(
    output: Path,
    *,
    timeline_authority: Mapping[str, Any] | None = None,
) -> None:
    """Stamp canonical authority without rewriting output locators.

    Output bytes are published by the neutral runtime. The render pack keeps
    its attempt-local path only as ephemeral execution evidence; it never
    derives or replaces it with a local CAS/project locator.
    """
    if os.environ.get("ASTRID_INTERNAL_INVOCATION") != "1":
        return
    sidecar = Path(f"{output}.provenance.json")
    if not output.is_file() or not sidecar.is_file():
        if timeline_authority is not None:
            raise RuntimeError(
                "canonical timeline render did not produce the provenance sidecar "
                "required to stamp its pinned kernel authority"
            )
        return
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("render provenance must be a JSON object")
        if timeline_authority is not None:
            payload["canonical_timeline"] = dict(timeline_authority)
        sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if timeline_authority is not None:
            raise RuntimeError(
                "canonical timeline render could not stamp its pinned kernel authority "
                "into provenance"
            ) from exc
        # The sidecar remains governed by the renderer's own validation; this
        # additive locator rewrite must never hide a successful render or
        # turn an otherwise useful artifact into a kernel failure.
        return


def _write_empty_asset_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timeline.save_registry({"assets": {}}, path)


def _previous_render_outputs_for_timeline(
    out_path: Path,
    timeline_path: Path,
) -> tuple[Path, ...]:
    """Discover prior sibling outputs; publication validates before deleting.

    Filtering happens under each candidate's publication lock using the
    committed sidecar.
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
    selector: str = "rendering.remotion",
    project_dir: Path | None = None,
    composition_id: str = "TimelineComposition",
    theme_path: Path | None = None,
    min_free_gb: float | None = None,
    keep_previous_renders: bool = False,
    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
    profile: Mapping[str, Any] | None = None,
    timeline_authority: Mapping[str, Any] | None = None,
) -> Path:
    """Render through :class:`RenderService` and publish one locked pair.

    Dispatch, support, invocation, validation, audio completion, finalization,
    and publication happen in the service; this facade only adapts files and
    output naming.
    """
    out_path = Path(out_path)
    validate_output_name(out_path.name)
    previous_outputs = (
        ()
        if keep_previous_renders
        else _previous_render_outputs_for_timeline(out_path, timeline_path)
    )
    config = _backend_config(
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
            # Explicit caller configuration overlays the default Remotion
            # namespace so project/theme/composition values remain intact.
            overlaid = dict(existing)
            overlaid.update({k: v for k, v in value.items() if v is not None})
            config[str(key)] = overlaid
    output = _default_service().render(
        timeline_path,
        assets_path,
        out_path,
        selector=selector,
        backend_config=config,
        profile=profile,
        previous_outputs=previous_outputs,
    )
    _rewrite_provenance_output_path(
        Path(output),
        timeline_authority=timeline_authority,
    )
    return output


_DEFAULT_THEME_PATH = REPO_ROOT / "themes" / "banodoco-default" / "theme.json"
"""Optional default theme for canonical Remotion rendering."""


def _resolve_default_theme(explicit: Path | None) -> Path | None:
    """Return *explicit*, or the historical default theme when it exists.

    A ``None`` result is valid: ffmpeg direct renders and timelines that
    carry their own theme need no ``--theme`` at all.
    """
    if explicit is not None:
        return explicit
    return _DEFAULT_THEME_PATH if _DEFAULT_THEME_PATH.exists() else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--selector",
        default=None,
        help="Qualified renderer id (rendering.remotion, rendering.ffmpeg, or rendering.threejs).",
    )
    parser.add_argument(
        "--backend-config",
        default=None,
        help="JSON object keyed by qualified backend id with per-backend configuration.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="JSON object describing the requested render profile.",
    )
    parser.add_argument(
        "--timeline-authority",
        default=None,
        help="Kernel-resolved canonical timeline authority JSON (managed ref mode only).",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help=(
            "Plain output filename (default hype.mp4). An alpha-stamped timeline may "
            "request .mov for truthful ProRes 4444 output."
        ),
    )
    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
    parser.add_argument("--composition", default="TimelineComposition")
    parser.add_argument(
        "--min-free-gb",
        type=float,
        default=None,
        help="Abort before rendering unless this much free disk is available near --out.",
    )
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
        default=None,
        help=(
            "Theme path or themes/<slug> directory (optional; defaults to "
            "themes/banodoco-default/theme.json when present, otherwise the "
            "timeline's own theme or the built-in canvas is used)."
        ),
    )
    args = parser.parse_args(argv)
    args.theme = _resolve_default_theme(args.theme)
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
        selector = args.selector or "rendering.remotion"
        config = _parse_backend_config(args.backend_config)
        profile = _parse_profile(args.profile)
        timeline_authority = _parse_profile(args.timeline_authority)
        if args.assets is None:
            with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
                assets_path = Path(tmp_text) / "hype.assets.json"
                _write_empty_asset_registry(assets_path)
                output = render(
                    args.timeline,
                    assets_path,
                    args.out,
                    selector=selector,
                    project_dir=args.project_dir,
                    composition_id=args.composition,
                    theme_path=args.theme,
                    min_free_gb=args.min_free_gb,
                    keep_previous_renders=args.keep_previous_renders,
                    backend_config=config,
                    profile=profile,
                    timeline_authority=timeline_authority,
                )
        else:
            output = render(
                args.timeline,
                args.assets,
                args.out,
                selector=selector,
                project_dir=args.project_dir,
                composition_id=args.composition,
                theme_path=args.theme,
                min_free_gb=args.min_free_gb,
                keep_previous_renders=args.keep_previous_renders,
                backend_config=config,
                profile=profile,
                timeline_authority=timeline_authority,
            )
    except RendererException as exc:  # pragma: no cover - CLI path
        print(_renderer_cli_error(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - CLI path
        print(str(exc), file=sys.stderr)
        # The kernel's in-process capability path needs the structured
        # exception to reach its handler boundary; otherwise a support
        # rejection is flattened into a bare return code and the SDK can only
        # report "executor failed".  Preserve the traditional CLI exit code
        # for external callers while retaining actionable typed failure text
        # for project-scoped SDK invocations.
        if os.environ.get("ASTRID_INTERNAL_INVOCATION") == "1":
            structured = getattr(exc, "error", None)
            details = getattr(structured, "details", None)
            reasons = details.get("reasons") if isinstance(details, Mapping) else None
            if isinstance(reasons, (list, tuple)) and reasons:
                raise RuntimeError(
                    f"{exc}: " + "; ".join(str(reason) for reason in reasons)
                ) from exc
            raise
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
