"""Kernel-side standard schema-pack composition (core + in-tree packs).

The standard-Astrid registry is the composed expectation used by schema
validation (``doctor`` schema_versions, backup restore validation). Kernel
modules (``astrid/core/**``) must be able to build it **without importing
``astrid.packs``** — the single documented kernel-to-pack composition
exemption is the gateway serve root
(``astrid/core/gateway/dispatch.py``) — so this kernel composition registers
the core vocabulary and loads the in-tree schema-pack manifests from
the installed package tree. ``astrid.packs.build_standard_registry`` keeps
its own pack-layer implementation (the ``STANDARD_SCHEMA_PACKS`` literal
there is required by the deterministic pack-factoring surgery); this module
is the kernel-side counterpart with the same explicit pack enumeration.
"""

from __future__ import annotations

from pathlib import Path

from astrid.core.schema_packs.core import register_core_vocabulary
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
    SchemaPackRegistry,
)

STANDARD_SCHEMA_PACKS: tuple[str, ...] = ("timeline", "shots", "references")
"""The in-tree schema packs the standard composition registers."""


def build_standard_registry() -> FrozenSchemaPackRegistry:
    """Compose and freeze the standard-Astrid registry (core + packs).

    Registers the core vocabulary, then loads each in-tree schema-pack
    manifest from the installed package tree (``astrid/packs/<id>/``). The
    pack manifests are package data, not imports: this kernel module never
    imports ``astrid.packs``.
    """
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    packs_root = Path(__file__).resolve().parents[2] / "packs"
    for pack_id in STANDARD_SCHEMA_PACKS:
        manifest = load_schema_pack_manifest(packs_root / pack_id / "schema-pack.yaml")
        registry.register_pack(manifest)
    return registry.freeze()


__all__ = ["STANDARD_SCHEMA_PACKS", "build_standard_registry"]
