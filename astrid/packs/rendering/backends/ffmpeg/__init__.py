"""FFmpeg implementation of Astrid's rendering protocol v1."""

from __future__ import annotations

from typing import Any

from .command import build_render_command


BACKEND_ID = "rendering.ffmpeg"
BACKEND_VERSION = "1.0.0"


def can_render_with_ffmpeg_media(*args: Any, **kwargs: Any) -> bool:
    """Lazily enter the executable backend from the package surface."""

    from .run import can_render_with_ffmpeg_media as implementation

    return implementation(*args, **kwargs)


def render(*args: Any, **kwargs: Any) -> Any:
    """Lazily enter the executable backend from the package surface."""

    from .run import render as implementation

    return implementation(*args, **kwargs)


def support(*args: Any, **kwargs: Any) -> Any:
    """Lazily enter the executable backend from the package surface."""

    from .run import support as implementation

    return implementation(*args, **kwargs)

__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "build_render_command",
    "can_render_with_ffmpeg_media",
    "render",
    "support",
]
