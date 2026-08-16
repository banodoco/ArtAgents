"""Strict schema-pack manifest models and loading.

Public exports for the schema-pack contract (m1 plan step 2). The composed
schema-pack registry consumes the immutable :class:`SchemaPackManifest` models
from this package; nothing here imports or reuses capability-pack semantics
beyond the shared YAML loader used by :func:`load_schema_pack_manifest`.
"""

from astrid.core.schema_packs.manifest import (
    MIGRATION_DESCRIPTOR_FIELDS,
    MigrationDescriptor,
    PackDependency,
    SCHEMA_PACK_TOP_LEVEL_FIELDS,
    SchemaPackManifest,
    SchemaPackManifestError,
    SchemaPackManifestValidationError,
    load_schema_pack_manifest,
    parse_schema_pack_manifest,
)

__all__ = [
    "MIGRATION_DESCRIPTOR_FIELDS",
    "MigrationDescriptor",
    "PackDependency",
    "SCHEMA_PACK_TOP_LEVEL_FIELDS",
    "SchemaPackManifest",
    "SchemaPackManifestError",
    "SchemaPackManifestValidationError",
    "load_schema_pack_manifest",
    "parse_schema_pack_manifest",
]
