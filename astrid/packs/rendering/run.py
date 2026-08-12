#!/usr/bin/env python3
"""Pack-root launcher for rendering raw-command adapters.

Rendering protocol commands execute with their owning pack as the working
directory.  Built-in manifests intentionally keep the portable
``[python3, run.py]`` command, so this launcher bridges that lifecycle to the
implementation stored beside each manifest.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


_CHECKOUT_ROOT = Path(__file__).resolve().parents[3]
if str(_CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(_CHECKOUT_ROOT))

def _request_path(argv: Sequence[str]) -> Path | None:
    try:
        index = argv.index("--request")
        return Path(argv[index + 1])
    except (ValueError, IndexError):
        return None


def _selects_finalizer(argv: Sequence[str]) -> bool:
    """Route finalize and explicitly-namespaced support operations."""

    if argv and argv[0] == "finalize":
        return True
    if not argv or argv[0] != "support":
        return False
    request_path = _request_path(argv)
    if request_path is None:
        return False
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, Mapping):
        return False
    backend_config = payload.get("backend_config")
    return isinstance(backend_config, Mapping) and (
        "rendering.ffmpeg-finalizer" in backend_config
    )


def _selects_ffmpeg(argv: Sequence[str]) -> bool:
    """Select FFmpeg from its backend-config namespace or legacy media shape.

    V1 transport does not append an implementation id to the command.  The
    namespace is authoritative when present.  Config-free requests retain the
    facade's existing media-only auto-route; all other requests retain
    Remotion as the pre-extraction compatibility default.
    """

    request_path = _request_path(argv)
    if request_path is None:
        return False
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, Mapping):
        return False
    backend_config = payload.get("backend_config")
    if isinstance(backend_config, Mapping):
        if "rendering.ffmpeg" in backend_config:
            return True
        if "rendering.remotion" in backend_config:
            return False

    timeline_path = payload.get("timeline_path")
    assets_path = payload.get("assets_registry_path")
    if not isinstance(timeline_path, str) or not isinstance(assets_path, str):
        return False
    workspace = request_path.resolve().parent
    timeline_candidate = Path(timeline_path).expanduser()
    assets_candidate = Path(assets_path).expanduser()
    if not timeline_candidate.is_absolute():
        timeline_candidate = workspace / timeline_candidate
    if not assets_candidate.is_absolute():
        assets_candidate = workspace / assets_candidate
    from astrid.packs.rendering.backends.ffmpeg.run import (
        can_render_with_ffmpeg_media,
    )

    return can_render_with_ffmpeg_media(timeline_candidate, assets_candidate)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _selects_finalizer(args):
        from astrid.packs.rendering.finalizers.ffmpeg.run import (
            main as backend_main,
        )
    elif _selects_ffmpeg(args):
        from astrid.packs.rendering.backends.ffmpeg.run import main as backend_main
    else:
        from astrid.packs.rendering.backends.remotion.run import main as backend_main

    return backend_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
