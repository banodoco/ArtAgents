"""Capability-registry kernel.

Public exports
--------------
- :class:`CapabilityRegistry` — generic base for executor, orchestrator,
  and element registries.
- :class:`RegistryError` — base exception for registry inconsistencies.
- :class:`RegistryConflict` — one conflict record (winner + shadowed).
"""

from astrid.core.registry.base import CapabilityRegistry, RegistryConflict, RegistryError

__all__ = ["CapabilityRegistry", "RegistryConflict", "RegistryError"]
