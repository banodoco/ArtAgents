"""Checkout pack registry and manifest composition.

Pack discovery is intentionally a pure checkout concern. Runtime projects,
writers, SDK services, and bridge composition live behind the generated
workspace client or the runtime daemon; importing this package never opens a
database or constructs a local application.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.events.registry import register_core_vocabulary
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
    SchemaPackRegistry,
)

STANDARD_SCHEMA_PACKS: tuple[str, ...] = ("timeline", "shots", "references", "runaway")
"""Exactly the in-tree schema packs shipped with Astrid."""

_PACKS_ROOT = Path(__file__).parent


def register_standard_schema_packs(registry: SchemaPackRegistry) -> SchemaPackRegistry:
    """Register shipped schema-pack manifests into ``registry``."""
    for pack_id in STANDARD_SCHEMA_PACKS:
        manifest = load_schema_pack_manifest(
            _PACKS_ROOT / pack_id / "schema-pack.yaml"
        )
        registry.register_pack(manifest)
    return registry


def build_standard_registry() -> FrozenSchemaPackRegistry:
    """Build the frozen checkout registry (core vocabulary plus pack manifests)."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


__all__ = [
    "FrozenSchemaPackRegistry",
    "STANDARD_SCHEMA_PACKS",
    "SchemaPackRegistry",
    "build_standard_registry",
    "register_standard_schema_packs",
]
