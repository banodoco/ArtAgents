"""Shared Astrid schema contracts used across executors and orchestrators."""

from .errors import (
    AstridError,
    AstridErrorEnvelope,
    build_state_snapshot,
    coerce_astrid_error,
    error_from_result,
    normalize_valid_options,
    render_astrid_error,
    wrap_degraded_error,
)
from .schema import (
    CACHE_MODES,
    ISOLATION_MODES,
    OUTPUT_MODES,
    PORT_REQUIRED_TYPES,
    AliasRecord,
    CachePolicy,
    CapabilityHandle,
    CommandSpec,
    IsolationMetadata,
    Output,
    Port,
    Provenance,
    SafetyDeclaration,
)
from .result_manifest import complete_output_metadata, write_manifest

__all__ = [
    "CACHE_MODES",
    "ISOLATION_MODES",
    "OUTPUT_MODES",
    "PORT_REQUIRED_TYPES",
    "AstridError",
    "AstridErrorEnvelope",
    "AliasRecord",
    "build_state_snapshot",
    "CachePolicy",
    "CapabilityHandle",
    "CommandSpec",
    "coerce_astrid_error",
    "error_from_result",
    "IsolationMetadata",
    "normalize_valid_options",
    "Output",
    "Port",
    "Provenance",
    "complete_output_metadata",
    "render_astrid_error",
    "SafetyDeclaration",
    "write_manifest",
    "wrap_degraded_error",
]
