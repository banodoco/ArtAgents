"""FFmpeg implementation of Astrid's rendering finalizer protocol v1."""

from __future__ import annotations

from typing import Any


BACKEND_ID = "rendering.ffmpeg-finalizer"
BACKEND_VERSION = "1.0.0"
FINALIZER_ID = BACKEND_ID


def finalize(*args: Any, **kwargs: Any) -> Any:
    """Lazily enter the finalizer implementation."""

    from .run import finalize as implementation

    return implementation(*args, **kwargs)


def support(*args: Any, **kwargs: Any) -> Any:
    """Lazily enter the finalizer support implementation."""

    from .run import support as implementation

    return implementation(*args, **kwargs)


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "FINALIZER_ID",
    "finalize",
    "support",
]
