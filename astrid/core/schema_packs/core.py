"""Code-declared kernel schema-pack vocabulary.

This lower-level module owns the core manifest and composition helper so the
schema-pack layer never has to import the event validation layer.  The event
registry re-exports these names for compatibility with its historical API.
"""

from __future__ import annotations

from astrid.core.schema_packs.manifest import (
    SchemaPackManifest,
    parse_schema_pack_manifest,
)
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
    SchemaPackRegistry,
)

CORE_PACK_ID = "core"
CORE_MANIFEST_VERSION = 1
CORE_STREAM_TYPES: tuple[str, ...] = (
    "core.project",
    "core.task",
    "core.run",
    "core.media",
)
CORE_REPOSITORIES: tuple[str, ...] = (
    "ProjectRepository",
    "TaskRepository",
    "MediaRepository",
    "RunRepository",
)
CORE_CONFORMANCE_DIMENSIONS: tuple[str, ...] = (
    "replay",
    "mismatch_before_mutation",
    "same_project",
    "vocabulary",
    "writer_ownership",
    "crash_atomicity",
    "hash_chain",
)
CORE_EVENT_KINDS: tuple[str, ...] = (
    "core.project.created",
    "core.project.updated",
    "core.task.created",
    "core.task.claimed",
    "core.task.started",
    "core.task.expired",
    "core.task.cancelled",
    "core.task.failed",
    "core.task.retried",
    "core.task.completed",
    "core.run.created",
    "core.run.cancelled",
    "core.run.retried",
    "core.run.closed",
    "core.run.continued",
    "core.evidence.recorded",
    "core.media.imported",
    "core.media.location_replaced",
    "core.media.related",
    "core.media.verified",
)
CORE_COMMAND_KINDS: tuple[str, ...] = (
    "core.project.create",
    "core.project.update",
    "core.task.create",
    "core.task.claim",
    "core.task.start",
    "core.task.expire",
    "core.task.cancel",
    "core.task.fail",
    "core.task.retry",
    "core.task.complete",
    "core.run.create",
    "core.run.cancel",
    "core.run.retry",
    "core.run.close",
    "core.run.continue",
    "core.evidence.record",
    "core.media.import",
    "core.media.replace_location",
    "core.media.relate",
    "core.media.verify",
)

# Keep the code-declared manifest aligned with the audited core migration
# descriptor without importing the migration runner/catalog back into the
# schema-pack layer.  The descriptor is intentionally immutable data here;
# catalog tests compare the two declarations and catch drift.
CORE_MIGRATION_VERSION = 1
CORE_MIGRATION_NAME = "initial"
CORE_MIGRATION_PATH = "sql/core/0001_initial.sql"
CORE_MIGRATION_TABLES: tuple[str, ...] = (
    "command_receipts",
    "event_streams",
    "events",
    "evidence_items",
    "execution_attempts",
    "media",
    "media_locations",
    "media_relations",
    "projects",
    "runs",
    "schema_migrations",
    "task_dependencies",
    "task_outputs",
    "tasks",
)


def core_schema_pack_manifest() -> SchemaPackManifest:
    """Build the strict, validated kernel manifest without YAML."""

    return parse_schema_pack_manifest(
        {
            "id": CORE_PACK_ID,
            "version": CORE_MANIFEST_VERSION,
            "depends_on": [],
            "migrations": [
                {
                    "version": CORE_MIGRATION_VERSION,
                    "name": CORE_MIGRATION_NAME,
                    "path": CORE_MIGRATION_PATH,
                    "tables": list(CORE_MIGRATION_TABLES),
                }
            ],
            "stream_types": list(CORE_STREAM_TYPES),
            "event_kinds": list(CORE_EVENT_KINDS),
            "command_kinds": list(CORE_COMMAND_KINDS),
            "repositories": list(CORE_REPOSITORIES),
            "conformance": list(CORE_CONFORMANCE_DIMENSIONS),
            "cli_mounts": {},
            "bridge_mounts": [],
        },
        source_path=None,
    )


def register_core_vocabulary(registry: SchemaPackRegistry) -> SchemaPackRegistry:
    """Register the kernel vocabulary into ``registry`` independently."""

    return registry.register_pack(core_schema_pack_manifest())


def core_only_registry() -> FrozenSchemaPackRegistry:
    """Compose the frozen kernel-only registry (no Astrid packs)."""

    return register_core_vocabulary(SchemaPackRegistry()).freeze()


__all__ = [
    "CORE_COMMAND_KINDS",
    "CORE_CONFORMANCE_DIMENSIONS",
    "CORE_EVENT_KINDS",
    "CORE_MANIFEST_VERSION",
    "CORE_PACK_ID",
    "CORE_REPOSITORIES",
    "CORE_STREAM_TYPES",
    "core_only_registry",
    "core_schema_pack_manifest",
    "register_core_vocabulary",
]
