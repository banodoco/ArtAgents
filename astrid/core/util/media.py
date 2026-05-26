"""TODO(m5a): Re-export shim — delete once all callers use astrid._media directly.

The canonical location for ``ffprobe_duration_seconds`` is ``astrid._media``.
This module exists only to keep existing ``astrid.core.util.media`` imports working
while packs migrate.
"""

# ruff: noqa: F401

from astrid._media import ffprobe_duration_seconds  # noqa: F401
