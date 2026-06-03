"""Generation model registry — model entries, validation, and loading."""

from astrid.core.generation.features import (
    CANONICAL_IMAGE_MODES,
    CANONICAL_VIDEO_MODES,
)
from astrid.core.model_catalog.registry import LoraRegistry, ModelRegistry
from astrid.core.model_catalog.schema import (
    BackendSpec,
    LoraEntry,
    LoraSource,
    ModelEntry,
    ModeSpec,
    validate_lora_registry,
    validate_registry,
)

__all__ = [
    "BackendSpec",
    "CANONICAL_IMAGE_MODES",
    "CANONICAL_VIDEO_MODES",
    "LoraEntry",
    "LoraRegistry",
    "LoraSource",
    "ModeSpec",
    "ModelEntry",
    "ModelRegistry",
    "validate_lora_registry",
    "validate_registry",
]
