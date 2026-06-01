"""Generation model registry — model entries, validation, and loading."""

from astrid.core.generation.features import (
    CANONICAL_IMAGE_MODES,
    CANONICAL_VIDEO_MODES,
)
from astrid.core.model_catalog.registry import ModelRegistry
from astrid.core.model_catalog.schema import (
    BackendSpec,
    ModeSpec,
    ModelEntry,
    validate_registry,
)

__all__ = [
    "BackendSpec",
    "CANONICAL_IMAGE_MODES",
    "CANONICAL_VIDEO_MODES",
    "ModeSpec",
    "ModelEntry",
    "ModelRegistry",
    "validate_registry",
]
