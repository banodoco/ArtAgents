"""Public SDK DTOs, result types, and schema records.

Consolidates the lightweight data-transfer objects that ``import astrid``
exposes without loading execution machinery.
"""

from __future__ import annotations

from astrid.core.contracts.exec_error import ExecError
from astrid.core.contracts.schema import (
    AliasRecord,
    CapabilityHandle,
    Output,
    Port,
    Provenance,
    SafetyDeclaration,
)
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventStreamRecord:
    """One runtime-owned event returned by the generated client."""

    source: str
    line: int
    timestamp: str | None
    kind: str | None
    hash: str | None
    payload: dict[str, Any]

from .results import (
    Capability,
    CapabilityType,
    DiscoveryResult,
    InvocationResult,
    _json_safe,
    _json_safe_mapping,
)

__all__ = [
    "AliasRecord",
    "Capability",
    "CapabilityHandle",
    "CapabilityType",
    "DiscoveryResult",
    "EventStreamRecord",
    "ExecError",
    "InvocationResult",
    "Output",
    "Port",
    "Provenance",
    "SafetyDeclaration",
]
