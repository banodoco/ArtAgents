"""Generation backend adapters — local (vibecomfy) and cloud (fal).

SD-004: Backend dispatch goes through this package.  The executor imports
the adapter classes from here and calls ``.generate()`` without any
backend-specific branching.
"""

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.generation.backends.fal import FalBackend
from astrid.core.generation.backends.vibecomfy import VibeComfyBackend

__all__ = [
    "BackendAdapter",
    "FalBackend",
    "GenerationResult",
    "VibeComfyBackend",
]
