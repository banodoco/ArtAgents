"""Immutable composed schema-pack registry with deterministic collision rejection.

(m1 plan step 2; decision artifact section 4.) Startup composes exactly the
shipped in-tree packs through one explicit :meth:`SchemaPackRegistry.register_pack`
call per pack, then :meth:`SchemaPackRegistry.freeze` produces the immutable
:class:`FrozenSchemaPackRegistry` that migrations, repositories, and lint consume.

The registry is a startup correctness boundary: every collision class (pack id,
owned table, migration version and name, stream type, event kind, command kind,
repository, CLI mount key, and bridge mount) is rejected deterministically
*before* any database is opened. This module is pure in-memory configuration:

- it never opens a database and never imports store/writer/sqlite modules;
- it never imports the capability-pack loader or definition machinery;
- it consumes only validated :class:`SchemaPackManifest` models produced by
  :func:`astrid.core.schema_packs.manifest.parse_schema_pack_manifest`.

Registration is atomic per pack: all collisions for one manifest are collected
and reported together (sorted, so identical input always produces the identical
error), and no partial state is recorded when any collision exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from astrid.core.schema_packs.manifest import SchemaPackManifest

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SchemaPackRegistryError(ValueError):
    """Base error for schema-pack registry composition."""


class SchemaPackDuplicateError(SchemaPackRegistryError):
    """Raised when a registration collides with an already registered entry."""


class SchemaPackRegistryFrozenError(SchemaPackRegistryError):
    """Raised when ``register_pack()`` is called after ``freeze()``."""


# ---------------------------------------------------------------------------
# Immutable models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisteredMigration:
    """One forward-only migration of a registered pack.

    Flattens the manifest's :class:`MigrationDescriptor` with the owning pack id
    so the migration runner and catalog tests never need to re-derive ownership.
    """

    pack: str
    version: int
    name: str
    path: str
    tables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FrozenSchemaPackRegistry:
    """Immutable, deterministically ordered view of the composed registry.

    All mappings are sorted by key at freeze time and exposed through
    ``MappingProxyType``, so iteration order is stable across processes and
    never depends on registration order. This object is the only registry form
    that repositories and the migration runner may consume.
    """

    packs: Mapping[str, SchemaPackManifest]
    """Registered pack id -> validated immutable manifest (sorted by id)."""

    tables: Mapping[str, str]
    """Owned table name -> owning pack id (sorted by table name)."""

    migrations: tuple[RegisteredMigration, ...]
    """Every registered migration, sorted by ``(pack, version)``."""

    stream_types: Mapping[str, str]
    """Namespaced stream type -> declaring pack id (sorted by name)."""

    event_kinds: Mapping[str, str]
    """Namespaced event kind -> declaring pack id (sorted by name)."""

    command_kinds: Mapping[str, str]
    """Namespaced command kind -> declaring pack id (sorted by name)."""

    repositories: Mapping[str, str]
    """Repository declaration name -> declaring pack id (sorted by name)."""

    cli_mounts: Mapping[str, tuple[str, str]]
    """CLI mount key -> ``(declaring pack id, mount path)`` (sorted by key)."""

    bridge_mounts: Mapping[str, str]
    """Bridge mount token -> declaring pack id (sorted by token)."""

    def pack(self, pack_id: str) -> SchemaPackManifest:
        """Return the manifest for ``pack_id`` or raise :class:`KeyError`."""
        return self.packs[pack_id]

    def migration(self, pack: str, version: int) -> RegisteredMigration | None:
        """Return the registered migration for ``(pack, version)`` if present."""
        for registered in self.migrations:
            if registered.pack == pack and registered.version == version:
                return registered
        return None

    def has_pack(self, pack_id: str) -> bool:
        """Return whether ``pack_id`` is part of this composed registry."""
        return pack_id in self.packs

    def __contains__(self, pack_id: object) -> bool:
        return pack_id in self.packs


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class SchemaPackRegistry:
    """Mutable accumulator of validated schema-pack manifests.

    Usage::

        registry = (
            SchemaPackRegistry()
            .register_pack(timeline_manifest)
            .register_pack(shots_manifest)
            .register_pack(references_manifest)
            .freeze()
        )

    ``register_pack()`` never opens a database and never consults the
    capability-pack loader; it validates composition-level uniqueness only.
    After :meth:`freeze` the builder rejects further registrations.
    """

    def __init__(self) -> None:
        self._packs: dict[str, SchemaPackManifest] = {}
        self._tables: dict[str, str] = {}
        self._migration_versions: set[tuple[str, int]] = set()
        self._migration_names: set[tuple[str, str]] = set()
        self._stream_types: dict[str, str] = {}
        self._event_kinds: dict[str, str] = {}
        self._command_kinds: dict[str, str] = {}
        self._repositories: dict[str, str] = {}
        self._cli_mounts: dict[str, tuple[str, str]] = {}
        self._bridge_mounts: dict[str, str] = {}
        self._frozen: bool = False

    # -- public API --------------------------------------------------------

    def register_pack(self, manifest: SchemaPackManifest) -> SchemaPackRegistry:
        """Register one validated manifest, rejecting every collision class.

        The check is atomic: collisions are collected across all classes and
        reported sorted before any registry state changes.
        """
        if self._frozen:
            raise SchemaPackRegistryFrozenError(
                "cannot register pack "
                f"{manifest.id!r}: the schema-pack registry is already frozen"
            )
        collisions = self._collect_collisions(manifest)
        if collisions:
            raise SchemaPackDuplicateError(
                "schema-pack registry rejects pack "
                f"{manifest.id!r} with duplicate declaration(s):\n"
                + "\n".join(f"  - {message}" for message in collisions)
            )
        self._record(manifest)
        return self

    def freeze(self) -> FrozenSchemaPackRegistry:
        """Freeze the registry into an immutable, sorted view.

        After this call the builder rejects further ``register_pack()`` calls.
        Freezing is idempotent: repeated calls return equivalent frozen views.
        """
        self._frozen = True
        return FrozenSchemaPackRegistry(
            packs=MappingProxyType(dict(sorted(self._packs.items()))),
            tables=MappingProxyType(dict(sorted(self._tables.items()))),
            migrations=tuple(
                sorted(self._iter_registered_migrations(), key=lambda m: (m.pack, m.version))
            ),
            stream_types=MappingProxyType(dict(sorted(self._stream_types.items()))),
            event_kinds=MappingProxyType(dict(sorted(self._event_kinds.items()))),
            command_kinds=MappingProxyType(dict(sorted(self._command_kinds.items()))),
            repositories=MappingProxyType(dict(sorted(self._repositories.items()))),
            cli_mounts=MappingProxyType(dict(sorted(self._cli_mounts.items()))),
            bridge_mounts=MappingProxyType(dict(sorted(self._bridge_mounts.items()))),
        )

    # -- internals ---------------------------------------------------------

    def _iter_registered_migrations(self) -> list[RegisteredMigration]:
        migrations: list[RegisteredMigration] = []
        for pack_id, manifest in self._packs.items():
            for descriptor in manifest.migrations:
                migrations.append(
                    RegisteredMigration(
                        pack=pack_id,
                        version=descriptor.version,
                        name=descriptor.name,
                        path=descriptor.path,
                        tables=descriptor.tables,
                    )
                )
        return migrations

    def _collect_collisions(self, manifest: SchemaPackManifest) -> list[str]:
        """Return every deterministic collision between ``manifest`` and the registry."""
        collisions: list[str] = []
        pack_id = manifest.id

        if pack_id in self._packs:
            collisions.append(
                f"pack id {pack_id!r} is already registered "
                f"(by {pack_id!r})"
            )

        for table in sorted({t for d in manifest.migrations for t in d.tables}):
            if table in self._tables:
                collisions.append(
                    f"table {table!r} is already owned by pack "
                    f"{self._tables[table]!r}"
                )

        for descriptor in manifest.migrations:
            if (pack_id, descriptor.version) in self._migration_versions:
                collisions.append(
                    f"migration version {descriptor.version} of pack "
                    f"{pack_id!r} is already registered"
                )
            if (pack_id, descriptor.name) in self._migration_names:
                collisions.append(
                    f"migration name {descriptor.name!r} of pack "
                    f"{pack_id!r} is already registered"
                )

        for stream_type in sorted(manifest.stream_types):
            if stream_type in self._stream_types:
                collisions.append(
                    f"stream type {stream_type!r} is already declared by pack "
                    f"{self._stream_types[stream_type]!r}"
                )

        for event_kind in sorted(manifest.event_kinds):
            if event_kind in self._event_kinds:
                collisions.append(
                    f"event kind {event_kind!r} is already declared by pack "
                    f"{self._event_kinds[event_kind]!r}"
                )

        for command_kind in sorted(manifest.command_kinds):
            if command_kind in self._command_kinds:
                collisions.append(
                    f"command kind {command_kind!r} is already declared by pack "
                    f"{self._command_kinds[command_kind]!r}"
                )

        for repository in sorted(manifest.repositories):
            if repository in self._repositories:
                collisions.append(
                    f"repository {repository!r} is already declared by pack "
                    f"{self._repositories[repository]!r}"
                )

        for mount_key in sorted(manifest.cli_mounts):
            if mount_key in self._cli_mounts:
                existing_pack, _ = self._cli_mounts[mount_key]
                collisions.append(
                    f"CLI mount key {mount_key!r} is already declared by pack "
                    f"{existing_pack!r}"
                )

        for mount_token in sorted(manifest.bridge_mounts):
            if mount_token in self._bridge_mounts:
                collisions.append(
                    f"bridge mount {mount_token!r} is already declared by pack "
                    f"{self._bridge_mounts[mount_token]!r}"
                )

        return collisions

    def _record(self, manifest: SchemaPackManifest) -> None:
        """Record a collision-free manifest into the registry state."""
        pack_id = manifest.id
        self._packs[pack_id] = manifest
        for descriptor in manifest.migrations:
            self._migration_versions.add((pack_id, descriptor.version))
            self._migration_names.add((pack_id, descriptor.name))
            for table in descriptor.tables:
                self._tables[table] = pack_id
        for stream_type in manifest.stream_types:
            self._stream_types[stream_type] = pack_id
        for event_kind in manifest.event_kinds:
            self._event_kinds[event_kind] = pack_id
        for command_kind in manifest.command_kinds:
            self._command_kinds[command_kind] = pack_id
        for repository in manifest.repositories:
            self._repositories[repository] = pack_id
        for mount_key, mount_path in manifest.cli_mounts.items():
            self._cli_mounts[mount_key] = (pack_id, mount_path)
        for mount_token in manifest.bridge_mounts:
            self._bridge_mounts[mount_token] = pack_id


__all__ = [
    "FrozenSchemaPackRegistry",
    "RegisteredMigration",
    "SchemaPackDuplicateError",
    "SchemaPackRegistry",
    "SchemaPackRegistryError",
    "SchemaPackRegistryFrozenError",
]
