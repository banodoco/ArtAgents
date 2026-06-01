"""Generation backend adapters — local (vibecomfy) and cloud (fal).

SD-004: Backend dispatch goes through this package.  The executor imports
the adapter classes from here and calls ``.generate()`` without any
backend-specific branching.
"""

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.generation.backends.fal import FalBackend

# VibeComfyBackend is lazy-imported via module __getattr__ (SD-009) so
# that ``import astrid`` never pulls in the vibecomfy module tree.
# The public name is preserved: ``from astrid.core.generation.backends
# import VibeComfyBackend`` still works and triggers the lazy load.

__all__ = [
    "BackendAdapter",
    "FalBackend",
    "GenerationResult",
    "VibeComfyBackend",
]


def __getattr__(name: str):
    if name == "VibeComfyBackend":
        from astrid.core.generation.backends.vibecomfy import VibeComfyBackend

        return VibeComfyBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
