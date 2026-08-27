"""Compatibility alias for the FFmpeg backend specialization module."""

from __future__ import annotations

import sys

from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour as _impl

# Keep the historical module path and the backend path as the same module
# object.  Existing callers monkeypatch this path, and the backend must observe
# those patches while the migration remains behavior-preserving.
sys.modules[__name__] = _impl
