"""Generation facade helpers kept separate from the main SDK facade.

This module stays lightweight so ``import astrid.sdk`` exposes ``generate``
without loading model catalogs or generation backend registries until a facade
method is actually invoked.
"""

from __future__ import annotations

from astrid.sdk_generation import GenerationFacade, generate
from astrid.sdk_generation import _EXPLICIT_ONLY_IMAGE_MODES
from astrid.sdk_generation import _infer_image_mode, _infer_video_mode
from astrid.sdk_generation import _load_model_registry, _resolve_execution

__all__ = [
    "GenerationFacade",
    "_EXPLICIT_ONLY_IMAGE_MODES",
    "_infer_image_mode",
    "_infer_video_mode",
    "_load_model_registry",
    "_resolve_execution",
    "generate",
]
