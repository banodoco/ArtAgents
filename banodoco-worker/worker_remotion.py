"""Remotion render wrapper for the banodoco-worker (Sprint 8).

Mirrors `tools/render_remotion.py:307-324`'s subprocess invocation. We
keep the subprocess form (rather than calling `@remotion/renderer`
programmatically) for two reasons:

  1. The Sprint 7 image already pre-bakes Node 20 + Chromium + the
     workspace `node_modules` at /app, so `npx remotion render` inside
     `packages/timeline-composition/` "just works" with no extra wiring.
  2. The Remotion CLI prints structured progress + clean error tails to
     stderr; we want those in the worker's logs verbatim.

Render contract (props passed match `tools/render_remotion.py`):

    {
      "timeline": <serialized timeline config>,
      "assets":   <resolved asset registry, all `file` URLs reachable>,
      "theme":    {"id": <theme_id>, "visual": {...}},
    }

We do NOT spin up a local HTTP asset server here (unlike the local CLI);
the worker pre-resolves storage assets to file:// URIs or HTTP URLs
before invoking Remotion, which is sufficient for the render's input
props as long as Remotion's renderer can resolve `file://` (it can —
that's how it loads bundle assets).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from worker_assets import sha256_of_file

logger = logging.getLogger(__name__)


@dataclass
class RemotionRenderResult:
    output_path: Path
    sha256: str


class RemotionRenderError(Exception):
    """Raised when the Remotion subprocess exits non-zero."""


def _stderr_tail(stderr: str, limit: int = 40) -> str:
    lines = stderr.splitlines()
    tail = lines[-limit:] if len(lines) > limit else lines
    return "\n".join(tail).strip()


def _resolve_project_dir() -> Path:
    explicit = os.getenv("BANODOCO_REMOTION_PROJECT_DIR")
    if explicit:
        return Path(explicit)
    # Image layout: /app/packages/timeline-composition/typescript bundles
    # the Remotion entry. Fall back to the legacy tools/remotion path for
    # local dev where the worker is run from the repo.
    candidates = [
        Path("/app/packages/timeline-composition/typescript"),
        Path("/app/packages/timeline-composition"),
        Path("/app/tools/remotion"),
    ]
    for candidate in candidates:
        if (candidate / "package.json").exists():
            return candidate
    # Last-resort fallback for local dev environments.
    return Path("/app/tools/remotion")


def render_timeline_to_mp4(
    *,
    timeline: Dict[str, Any],
    assets: Dict[str, Any],
    theme_id: str,
    output_path: Path,
    composition_id: str = "TimelineComposition",
    project_dir: Optional[Path] = None,
    runner: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> RemotionRenderResult:
    """Invoke `npx remotion render` and return (output_path, sha256).

    Args:
        timeline: serialized TimelineConfig (already passed through the
            same `from`/`to` swap that `_swap_from_dump` does locally).
        assets: resolved asset registry (every entry has a `file` URL
            reachable from the worker's filesystem / network).
        theme_id: theme slug; the wrapper bundles it into the props as
            `{"id": <theme_id>, "visual": {}}`. The composition pulls the
            actual visual from the resolved registry; this stub matches
            `_resolved_theme_for_render`'s shape so props don't break.
        output_path: file path the MP4 will be written to. Parent dirs
            are created if needed.
        composition_id: the Remotion <Composition id="..."> to render.
        project_dir: override for tests / non-default image layouts.
        runner: subprocess.run-compatible callable; tests substitute a
            stub so they don't shell out.

    Raises:
        RemotionRenderError on non-zero exit, with stderr tail.
    """
    project_dir = project_dir or _resolve_project_dir()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    props_path = output_path.parent / ".remotion-props.json"
    merged_props = {
        "timeline": timeline,
        "assets": assets,
        # Mirror tools/render_remotion.py's {id, visual} shape; the
        # composition resolves theme_overrides on the timeline itself,
        # so the worker only needs to supply the slug + an empty visual
        # placeholder for non-themed runs. The Sprint 5 codegen registry
        # handles the actual theme components per clipType.
        "theme": {"id": theme_id, "visual": {}},
    }
    props_path.write_text(json.dumps(merged_props), encoding="utf-8")

    cmd = [
        "npx",
        "remotion",
        "render",
        composition_id,
        "--props",
        str(props_path),
        "--output",
        str(output_path),
    ]
    logger.info(
        "[REMOTION] Invoking %s in %s -> %s",
        " ".join(cmd), project_dir, output_path,
    )

    run = runner or subprocess.run
    try:
        result = run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            check=False,
            text=True,
            timeout=int(os.getenv("BANODOCO_REMOTION_TIMEOUT_SEC", "1800")),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RemotionRenderError(f"Remotion subprocess failed to start: {exc}") from exc
    finally:
        # Always remove the temp props file even on failure — it can
        # contain the user_jwt-bearing context if a future iteration
        # changes the props shape.
        try:
            props_path.unlink(missing_ok=True)
        except OSError:
            pass

    if result.returncode != 0:
        tail = _stderr_tail(result.stderr or "")
        raise RemotionRenderError(
            f"Remotion exited with code {result.returncode}\n{tail}"
        )

    if not output_path.exists():
        raise RemotionRenderError(
            f"Remotion reported success but {output_path} does not exist"
        )

    return RemotionRenderResult(
        output_path=output_path,
        sha256=sha256_of_file(output_path),
    )


__all__ = [
    "RemotionRenderError",
    "RemotionRenderResult",
    "render_timeline_to_mp4",
]
