"""Shared Reigh integration helpers for Astrid."""

# Explicit binding registration: importing the integration installs its one
# VibeComfy handler; there is no plugin discovery or filesystem scan.
from astrid.core.integrations.reigh.vibecomfy_binding import (  # noqa: F401
    VibeComfyTaskHandler,
)
from astrid.core.integrations.reigh.wgp_binding import (  # noqa: F401
    WgpTaskHandler,
)
