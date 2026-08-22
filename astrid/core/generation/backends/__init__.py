"""Generation backend adapters — local, cloud, and Codex.

SD-004: Backend dispatch goes through this package.  The executor imports
the adapter classes from here and calls ``.generate()`` without any
backend-specific branching.
"""

from astrid.core.generation.backends.base import BackendAdapter, GenerationResult
from astrid.core.generation.backends.codex import CodexBackend
from astrid.core.generation.backends.fal import FalBackend
from astrid.core.generation.backends.registry import (
    GenerationBackendDescriptor,
    GenerationBackendRegistry,
    discover_generation_backend_descriptors,
    load_default_generation_backend_registry,
)

# VibeComfyBackend is lazy-imported via module __getattr__ (SD-009) so
# that ``import astrid`` never pulls in the vibecomfy module tree.
# The public name is preserved: ``from astrid.core.generation.backends
# import VibeComfyBackend`` still works and triggers the lazy load.

__all__ = [
    "BackendAdapter",
    "CodexBackend",
    "discover_generation_backend_descriptors",
    "FalBackend",
    "GenerationBackendDescriptor",
    "GenerationBackendRegistry",
    "GenerationResult",
    "load_default_generation_backend_registry",
    "VibeComfyBackend",
    "WavespeedBackend",
]


def __getattr__(name: str):
    if name == "VibeComfyBackend":
        from astrid.core.generation.backends.vibecomfy import VibeComfyBackend

        return VibeComfyBackend
    if name == "WavespeedBackend":
        try:
            from astrid.core.generation.backends.wavespeed import WavespeedBackend

            return WavespeedBackend
        except ModuleNotFoundError as exc:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
