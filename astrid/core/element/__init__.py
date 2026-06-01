"""Canonical element framework APIs."""

from .install import (
    ElementInstallError,
    ElementInstallPlan,
    ElementInstallResult,
    build_element_install_plan,
    install_element,
)
from ..pack import (
    ELEMENT_KIND_REGISTRY,
    ElementKind,
    ElementKindDescriptor,
    ElementKindRegistry,
)
from .registry import (
    ElementConflict,
    ElementRegistry,
    ElementRegistryError,
    ElementSource,
    load_default_registry,
    load_pack_elements,
    load_source_elements,
)
from .schema import (
    ELEMENT_KINDS,
    REQUIRED_ELEMENT_FILES,
    ElementDefinition,
    ElementDependencies,
    ElementValidationError,
    load_element_definition,
    to_capability_handle,
    validate_element_definition,
)

__all__ = [
    "ELEMENT_KINDS",
    "ELEMENT_KIND_REGISTRY",
    "REQUIRED_ELEMENT_FILES",
    "ElementConflict",
    "ElementDefinition",
    "ElementDependencies",
    "ElementInstallError",
    "ElementInstallPlan",
    "ElementInstallResult",
    "ElementKind",
    "ElementKindDescriptor",
    "ElementKindRegistry",
    "ElementRegistry",
    "ElementRegistryError",
    "ElementSource",
    "ElementValidationError",
    "build_element_install_plan",
    "install_element",
    "load_default_registry",
    "load_pack_elements",
    "load_source_elements",
    "load_element_definition",
    "to_capability_handle",
    "validate_element_definition",
]
