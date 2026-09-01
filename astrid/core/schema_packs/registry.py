"""Immutable typed database projection registry.

Canonical pack database declarations enter through
``register_database_projection``. This module retains only the reusable
collision, dependency, ordering, resource, and freeze mechanics; it has no
manifest parser or alternate identity authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from astrid.core.pack.canonical import ResourceHandle

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
@dataclass(frozen=True, slots=True)
class RegisteredMigration:
    """One forward-only migration of a registered pack.

    ``path`` remains the public relative identity used by the legacy
    schema-pack contract.  Canonical projections additionally carry the
    owning root and the already-confined resource handle, so execution never
    needs to rediscover a resource from a pack id.
    """

    pack: str
    version: int
    name: str
    path: str
    tables: tuple[str, ...]
    owner_root: Path | None = None
    resource: ResourceHandle | None = None

    @property
    def relative_path(self) -> str:
        """Canonical spelling for the retained relative migration identity."""
        return self.path


@dataclass(frozen=True, slots=True)
class DatabasePackProjection:
    """Immutable database-only projection consumed by collision/freeze logic.

    Canonical packs have one source of truth and enter the runtime registry
    directly; this projection is never converted into another manifest form.
    """

    id: str
    version: str | int
    depends_on: tuple[Any, ...]
    migrations: tuple[Any, ...]
    stream_types: tuple[str, ...]
    event_kinds: tuple[str, ...]
    command_kinds: tuple[str, ...]
    repositories: tuple[str, ...]
    conformance: tuple[str, ...]
    cli_mounts: Mapping[str, str]
    bridge_mounts: tuple[str, ...]
    name: str = ""
    default_enabled: bool = True
    source_path: Path | None = None


@dataclass(frozen=True, slots=True)
class FrozenSchemaPackRegistry:
    """Immutable, deterministically ordered view of the composed registry.

    All mappings are sorted by key at freeze time and exposed through
    ``MappingProxyType``, so iteration order is stable across processes and
    never depends on registration order. This object is the only registry form
    that repositories and the migration runner may consume.
    """

    packs: Mapping[str, Any]
    """Registered legacy manifests or canonical database projections."""

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

    canonical_projection: bool = False

    def pack(self, pack_id: str) -> Any:
        """Return the projected pack for ``pack_id`` or raise ``KeyError``."""
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
        self._packs: dict[str, Any] = {}
        self._tables: dict[str, str] = {}
        self._migration_versions: set[tuple[str, int]] = set()
        self._migration_names: set[tuple[str, str]] = set()
        self._migration_resources: dict[tuple[str, int], ResourceHandle] = {}
        self._stream_types: dict[str, str] = {}
        self._event_kinds: dict[str, str] = {}
        self._command_kinds: dict[str, str] = {}
        self._repositories: dict[str, str] = {}
        self._cli_mounts: dict[str, tuple[str, str]] = {}
        self._bridge_mounts: dict[str, str] = {}
        self._canonical_projection: bool = False
        self._frozen: bool = False

    # -- public API --------------------------------------------------------

    def register_pack(self, manifest: Any) -> SchemaPackRegistry:
        """Register a typed database projection for collision testing.

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

    def register_database_projection(
        self,
        pack_or_id: Any,
        database: Any | None = None,
        *,
        owner_root: Path | None = None,
        resources: Iterable[ResourceHandle] = (),
        default_enabled: bool | None = None,
        name: str | None = None,
        version: str | int | None = None,
    ) -> SchemaPackRegistry:
        """Register one immutable canonical database projection.

        ``pack_or_id`` may be a canonical pack entry or an id string used by
        the explicit kernel projection. No alternate manifest object is built.
        """
        if self._frozen:
            pack_id = getattr(pack_or_id, "id", pack_or_id)
            raise SchemaPackRegistryFrozenError(
                f"cannot register pack {pack_id!r}: the schema-pack registry is already frozen"
            )
        entry = pack_or_id if not isinstance(pack_or_id, str) else None
        source_path: Path | None = None
        if entry is not None:
            pack_id = str(getattr(entry, "id"))
            if database is None:
                database = getattr(entry, "database", None)
            if owner_root is None:
                owner_root = Path(getattr(entry, "root"))
            resources = tuple(resources)
            if not resources:
                resources = tuple(getattr(entry, "resources", ()))
            if name is None:
                definition = getattr(entry, "definition", None)
                name = getattr(definition, "name", None)
            if version is None:
                definition = getattr(entry, "definition", None)
                version = getattr(definition, "version", None)
            manifest = getattr(entry, "manifest", None)
            if manifest is not None:
                source_path = Path(manifest.resolved)
        else:
            pack_id = str(pack_or_id)
        if database is None:
            raise SchemaPackRegistryError(
                f"database projection for pack {pack_id!r} is missing"
            )
        migrations = tuple(getattr(database, "migrations", ()))
        if not migrations:
            raise SchemaPackRegistryError(
                f"database projection for pack {pack_id!r} declares no migrations"
            )
        if owner_root is None:
            raise SchemaPackRegistryError(
                f"database projection for pack {pack_id!r} is missing owner root"
            )
        root = Path(owner_root).resolve()
        resource_by_path: dict[str, ResourceHandle] = {}
        for handle in resources:
            try:
                handle_root = Path(handle.root).resolve()
                resolved = Path(handle.resolved).resolve()
                relative = str(handle.path)
                file_kind = handle.file_kind
                relative_path = Path(relative)
            except (AttributeError, TypeError, ValueError) as exc:
                raise SchemaPackRegistryError(
                    f"database projection {pack_id!r} contains an invalid migration resource"
                ) from exc
            if (
                handle_root != root
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.as_posix() != relative
                or resolved != (root / relative_path).resolve()
                or not resolved.is_relative_to(root)
            ):
                raise SchemaPackRegistryError(
                    f"database migration resource {relative!r} for pack {pack_id!r} "
                    "is outside its owner root"
                )
            if file_kind != "file":
                raise SchemaPackRegistryError(
                    f"database migration resource {relative!r} for pack {pack_id!r} "
                    "is not a regular file"
                )
            if relative in resource_by_path:
                raise SchemaPackRegistryError(
                    f"database projection {pack_id!r} contains duplicate resource {relative!r}"
                )
            resource_by_path[relative] = handle
        for descriptor in migrations:
            path = str(getattr(descriptor, "path"))
            if path not in resource_by_path:
                raise SchemaPackRegistryError(
                    f"database migration {pack_id!r}/{descriptor.version} has no confined resource"
                )
        if default_enabled is None:
            default_enabled = bool(getattr(database, "default_enabled", True))
        projected = DatabasePackProjection(
            id=pack_id,
            name=name or pack_id,
            version=version if version is not None else 1,
            depends_on=tuple(getattr(database, "depends_on", ())),
            migrations=migrations,
            stream_types=tuple(getattr(database, "stream_types", ())),
            event_kinds=tuple(getattr(database, "event_kinds", ())),
            command_kinds=tuple(getattr(database, "command_kinds", ())),
            repositories=tuple(getattr(database, "repositories", ())),
            conformance=tuple(getattr(database, "conformance", ())),
            cli_mounts=MappingProxyType(dict(getattr(database, "cli_mounts", {}))),
            bridge_mounts=tuple(getattr(database, "bridge_mounts", ())),
            default_enabled=default_enabled,
            source_path=source_path,
        )
        collisions = self._collect_collisions(projected)
        if collisions:
            raise SchemaPackDuplicateError(
                f"schema-pack registry rejects pack {pack_id!r} with duplicate declaration(s):\n"
                + "\n".join(f"  - {message}" for message in collisions)
            )
        self._canonical_projection = True
        self._record(projected)
        for descriptor in migrations:
            self._migration_resources[(pack_id, descriptor.version)] = resource_by_path[
                str(descriptor.path)
            ]
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
            canonical_projection=self._canonical_projection,
        )

    # -- internals ---------------------------------------------------------
    def _iter_registered_migrations(self) -> list[RegisteredMigration]:
        migrations: list[RegisteredMigration] = []
        for pack_id, manifest in self._packs.items():
            for descriptor in manifest.migrations:
                key = (pack_id, descriptor.version)
                resource = self._migration_resources.get(key)
                if resource is None:
                    raise SchemaPackRegistryError(
                        f"database migration {pack_id!r}/{descriptor.version} "
                        "has no confined resource"
                    )
                migrations.append(
                    RegisteredMigration(
                        pack=pack_id,
                        version=descriptor.version,
                        name=descriptor.name,
                        path=descriptor.path,
                        tables=descriptor.tables,
                        owner_root=Path(resource.root),
                        resource=resource,
                    )
                )
        return migrations


    def _collect_collisions(self, manifest: Any) -> list[str]:
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

    def _record(self, manifest: Any) -> None:
        """Record a collision-free manifest or projection."""
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
    "DatabasePackProjection",
    "FrozenSchemaPackRegistry",
    "RegisteredMigration",
    "SchemaPackDuplicateError",
    "SchemaPackRegistry",
    "SchemaPackRegistryError",
    "SchemaPackRegistryFrozenError",
]
