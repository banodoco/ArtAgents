"""Generation model registry — model entries, validation, and loading."""

from astrid.core.model_catalog.registry import LoraRegistry, ModelRegistry
from astrid.core.model_catalog.schema import (
    BackendSpec,
    LoraEntry,
    LoraSource,
    ModelEntry,
    ModeSpec,
    Price,
    validate_lora_registry,
)
from astrid.core.model_catalog.taxonomy import (
    CANONICAL_IMAGE_MODES,
    CANONICAL_VIDEO_MODES,
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
    "Price",
    "validate_lora_registry",
]
