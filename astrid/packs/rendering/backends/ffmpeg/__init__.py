"""FFmpeg implementation of Astrid's rendering protocol v1."""

from __future__ import annotations

from .command import build_render_command

BACKEND_ID = "rendering.ffmpeg"
BACKEND_VERSION = "1.0.0"


def support(*args, **kwargs):
    """Lazily enter the executable backend from the package surface."""

    from .run import support as implementation

    return implementation(*args, **kwargs)


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "build_render_command",
    "support",
]
