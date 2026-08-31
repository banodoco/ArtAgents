"""Strict parsing and validation of the 11-field schema-pack manifest.

Schema packs are the database-schema counterpart of capability packs. Their
``schema-pack.yaml`` is deliberately *not* a capability ``pack.yaml``: it has
its own exact 11-field snake_case contract and never reuses capability-pack
semantics such as executor,
orchestrator, element, model, or component blocks.

Parsing reuses only the shared :func:`load_manifest_mapping` YAML loader; every
field is then validated strictly (exact top-level keys, dependency grammar,
migration descriptors with owned tables, namespaced vocabulary, repository
declarations, and CLI/bridge mounts). The result is an immutable
:class:`SchemaPackManifest` consumed by the composed schema-pack registry.

This module never opens a database and never imports the capability-pack
definition or validation machinery (m1 plan step 2; v10 section 2 "Boundary
now, loader later").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, NoReturn

from astrid.core.pack.manifest import ManifestParseError, load_manifest_mapping

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

SCHEMA_PACK_TOP_LEVEL_FIELDS: tuple[str, ...] = (
    "id",
    "version",
    "depends_on",
    "migrations",
    "stream_types",
    "event_kinds",
    "command_kinds",
    "repositories",
    "conformance",
    "cli_mounts",
    "bridge_mounts",
)
"""The exact 11 snake_case top-level fields of a ``schema-pack.yaml`` manifest.

Any manifest missing one of these fields or carrying any other field is
rejected before any registry mutation can occur.
"""

MIGRATION_DESCRIPTOR_FIELDS: tuple[str, ...] = ("version", "name", "path", "tables")
"""The exact keys of one ``migrations[]`` descriptor.

``tables`` declares tables first introduced (and therefore owned) by that
migration so catalog tests and the migration runner derive ownership without
parsing SQL (decision artifact section 4). An ALTER-only migration may use an
empty list; a table must still be declared exactly once by an earlier or
later creating migration in the same pack.
"""

_LOWERCASE_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
"""Lowercase snake identifier used for pack ids, table names, dependency pack
names, conformance dimensions, and CLI/bridge mount tokens."""

_REPOSITORY_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
"""Repository declaration names (e.g. ``ShotRepository``) may be PascalCase."""

_DOTTED_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
"""Namespaced (dotted) vocabulary name: at least ``namespace.name``."""

_DEPENDENCY_RE = re.compile(
    r"^(?P<pack>[a-z][a-z0-9_]*) *>= *(?P<version>[1-9][0-9]*)$"
)
"""The only accepted dependency grammar: ``<pack> >= <positive integer>``."""

_MIGRATION_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_MIGRATION_PATH_RE = re.compile(r"^[a-z0-9_./-]+$")
_CLI_MOUNT_PATH_RE = re.compile(r"^[a-z][a-z0-9_]*(\s+[a-z][a-z0-9_]*)*$")

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SchemaPackManifestError(ValueError):
    """Base error for schema-pack manifest loading and validation."""


class SchemaPackManifestValidationError(SchemaPackManifestError):
    """Raised when a loaded manifest violates the 11-field schema-pack contract."""


def _fail(field: str, detail: str) -> NoReturn:
    raise SchemaPackManifestValidationError(
        f"schema-pack manifest field {field!r}: {detail}"
    )


# ---------------------------------------------------------------------------
# Immutable models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackDependency:
    """One parsed ``depends_on`` entry (``<pack> >= <positive integer>``)."""

    pack: str
    version: int
    raw: str


@dataclass(frozen=True, slots=True)
class MigrationDescriptor:
    """One forward-only migration declared by a schema pack.

    ``tables`` is empty for a migration that only changes a table declared by
    an earlier migration; ownership remains with the creating migration.
    """

    version: int
    name: str
    path: str
    tables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SchemaPackManifest:
    """Immutable, validated content of one ``schema-pack.yaml`` manifest."""

    id: str
    version: int
    depends_on: tuple[PackDependency, ...]
    migrations: tuple[MigrationDescriptor, ...]
    stream_types: tuple[str, ...]
    event_kinds: tuple[str, ...]
    command_kinds: tuple[str, ...]
    repositories: tuple[str, ...]
    conformance: tuple[str, ...]
    cli_mounts: Mapping[str, str]
    bridge_mounts: tuple[str, ...]
    source_path: Path | None = None


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------


def _validate_id(raw: Any) -> str:
    if not isinstance(raw, str) or not raw:
        _fail("id", f"must be a non-empty string, got {type(raw).__name__}")
    if not _LOWERCASE_IDENT_RE.fullmatch(raw):
        _fail(
            "id",
            f"{raw!r} must be a lowercase snake identifier matching "
            r"[a-z][a-z0-9_]* (e.g. 'timeline')",
        )
    return raw


def _validate_positive_int(raw: Any, field: str) -> int:
    # bool is an int subclass in Python; a YAML `true` must never pass as 1.
    if isinstance(raw, bool) or not isinstance(raw, int):
        _fail(field, f"must be a positive integer, got {type(raw).__name__}")
    if raw < 1:
        _fail(field, f"must be a positive integer, got {raw}")
    return raw


def _validate_dependencies(raw: Any) -> tuple[PackDependency, ...]:
    if not isinstance(raw, list):
        _fail("depends_on", f"must be a list of dependency strings, got {type(raw).__name__}")
    seen: set[str] = set()
    dependencies: list[PackDependency] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, str):
            _fail(
                "depends_on",
                f"entry {index} must be a string, got {type(entry).__name__}",
            )
        match = _DEPENDENCY_RE.fullmatch(entry)
        if match is None:
            _fail(
                "depends_on",
                f"entry {index} {entry!r} must match the grammar "
                "'<pack> >= <positive integer>' (e.g. 'core >= 1')",
            )
        if entry in seen:
            _fail("depends_on", f"duplicate dependency {entry!r}")
        seen.add(entry)
        dependencies.append(
            PackDependency(
                pack=match.group("pack"),
                version=int(match.group("version")),
                raw=entry,
            )
        )
    return tuple(dependencies)


def _validate_string_list(raw: Any, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        _fail(field, f"must be a list of strings, got {type(raw).__name__}")
    seen: set[str] = set()
    values: list[str] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, str) or not entry:
            _fail(field, f"entry {index} must be a non-empty string")
        if entry in seen:
            _fail(field, f"duplicate entry {entry!r}")
        seen.add(entry)
        values.append(entry)
    return tuple(values)


def _validate_dotted_names(raw: Any, field: str) -> tuple[str, ...]:
    values = _validate_string_list(raw, field)
    for entry in values:
        if not _DOTTED_NAME_RE.fullmatch(entry):
            _fail(
                field,
                f"{entry!r} must be a namespaced dotted name with at least two "
                "lowercase snake segments (e.g. 'timeline.saved')",
            )
    return values


def _validate_repositories(raw: Any) -> tuple[str, ...]:
    values = _validate_string_list(raw, "repositories")
    for entry in values:
        if not _REPOSITORY_IDENT_RE.fullmatch(entry):
            _fail(
                "repositories",
                f"{entry!r} must be an identifier (e.g. 'ShotRepository')",
            )
    return values


def _validate_conformance(raw: Any) -> tuple[str, ...]:
    values = _validate_string_list(raw, "conformance")
    for entry in values:
        if not _LOWERCASE_IDENT_RE.fullmatch(entry):
            _fail(
                "conformance",
                f"{entry!r} must be a lowercase snake identifier "
                "(e.g. 'same_project')",
            )
    return values


def _validate_cli_mounts(raw: Any) -> Mapping[str, str]:
    if not isinstance(raw, dict):
        _fail("cli_mounts", f"must be a mapping of string to string, got {type(raw).__name__}")
    mounts: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not _LOWERCASE_IDENT_RE.fullmatch(key):
            _fail(
                "cli_mounts",
                f"key {key!r} must be a lowercase snake identifier (e.g. 'timelines')",
            )
        if not isinstance(value, str) or not value:
            _fail("cli_mounts", f"value for {key!r} must be a non-empty string")
        if not _CLI_MOUNT_PATH_RE.fullmatch(value):
            _fail(
                "cli_mounts",
                f"value for {key!r} ({value!r}) must be a space-separated "
                "lowercase CLI mount path (e.g. 'shots' or 'shots list')",
            )
        mounts[key] = value
    return MappingProxyType(mounts)


def _validate_bridge_mounts(raw: Any) -> tuple[str, ...]:
    values = _validate_string_list(raw, "bridge_mounts")
    for entry in values:
        if not _LOWERCASE_IDENT_RE.fullmatch(entry):
            _fail(
                "bridge_mounts",
                f"{entry!r} must be a lowercase snake identifier (e.g. 'timeline')",
            )
    return values


def _validate_migrations(raw: Any) -> tuple[MigrationDescriptor, ...]:
    if not isinstance(raw, list):
        _fail("migrations", f"must be a list of descriptors, got {type(raw).__name__}")
    seen_versions: set[int] = set()
    seen_names: set[str] = set()
    seen_tables: set[str] = set()
    descriptors: list[MigrationDescriptor] = []
    for index, entry in enumerate(raw):
        location = f"migrations entry {index}"
        if not isinstance(entry, dict):
            _fail(location, f"must be a mapping descriptor, got {type(entry).__name__}")
        missing = [key for key in MIGRATION_DESCRIPTOR_FIELDS if key not in entry]
        if missing:
            _fail(
                location,
                f"missing required descriptor field(s): {', '.join(missing)}",
            )
        extra = [key for key in entry if key not in MIGRATION_DESCRIPTOR_FIELDS]
        if extra:
            _fail(
                location,
                f"unsupported descriptor field(s): {', '.join(sorted(extra))}",
            )

        version = _validate_positive_int(entry["version"], f"{location} 'version'")
        if version in seen_versions:
            _fail(location, f"duplicate migration version {version}")
        seen_versions.add(version)

        name = entry["name"]
        if not isinstance(name, str) or not name:
            _fail(location, "'name' must be a non-empty string")
        if not _MIGRATION_NAME_RE.fullmatch(name):
            _fail(
                location,
                f"'name' {name!r} must match [a-z0-9][a-z0-9_-]* (e.g. '0001_initial')",
            )
        if name in seen_names:
            _fail(location, f"duplicate migration name {name!r}")
        seen_names.add(name)

        path = entry["path"]
        if not isinstance(path, str) or not path:
            _fail(location, "'path' must be a non-empty string")
        if (
            path.startswith("/")
            or "\\" in path
            or not _MIGRATION_PATH_RE.fullmatch(path)
            or ".." in path.split("/")
        ):
            _fail(
                location,
                f"'path' {path!r} must be a relative, traversal-free SQL resource path",
            )

        tables_raw = entry["tables"]
        if not isinstance(tables_raw, list):
            _fail(location, f"'tables' must be a list of strings, got {type(tables_raw).__name__}")
        tables: list[str] = []
        for table_index, table in enumerate(tables_raw):
            if not isinstance(table, str) or not table:
                _fail(location, f"'tables' entry {table_index} must be a non-empty string")
            if not _LOWERCASE_IDENT_RE.fullmatch(table):
                _fail(
                    location,
                    f"'tables' entry {table!r} must match [a-z][a-z0-9_]*",
                )
            if table in seen_tables:
                _fail(location, f"table {table!r} is already owned by an earlier migration")
            seen_tables.add(table)
            tables.append(table)

        descriptors.append(
            MigrationDescriptor(
                version=version,
                name=name,
                path=path,
                tables=tuple(tables),
            )
        )
    return tuple(descriptors)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def parse_schema_pack_manifest(
    mapping: Mapping[str, Any], *, source_path: Path | None = None
) -> SchemaPackManifest:
    """Validate a raw manifest mapping into an immutable :class:`SchemaPackManifest`.

    The mapping must contain exactly the 11 top-level fields; every extra,
    missing, or malformed field raises :class:`SchemaPackManifestValidationError`
    before any model is constructed.
    """
    missing = [field for field in SCHEMA_PACK_TOP_LEVEL_FIELDS if field not in mapping]
    if missing:
        _fail(
            "top-level",
            f"missing required field(s): {', '.join(missing)}",
        )
    extra = [key for key in mapping if key not in SCHEMA_PACK_TOP_LEVEL_FIELDS]
    if extra:
        _fail(
            "top-level",
            f"unsupported field(s): {', '.join(sorted(extra))}",
        )

    return SchemaPackManifest(
        id=_validate_id(mapping["id"]),
        version=_validate_positive_int(mapping["version"], "version"),
        depends_on=_validate_dependencies(mapping["depends_on"]),
        migrations=_validate_migrations(mapping["migrations"]),
        stream_types=_validate_dotted_names(mapping["stream_types"], "stream_types"),
        event_kinds=_validate_dotted_names(mapping["event_kinds"], "event_kinds"),
        command_kinds=_validate_dotted_names(mapping["command_kinds"], "command_kinds"),
        repositories=_validate_repositories(mapping["repositories"]),
        conformance=_validate_conformance(mapping["conformance"]),
        cli_mounts=_validate_cli_mounts(mapping["cli_mounts"]),
        bridge_mounts=_validate_bridge_mounts(mapping["bridge_mounts"]),
        source_path=source_path,
    )


def load_schema_pack_manifest(path: str | Path) -> SchemaPackManifest:
    """Load and strictly validate a ``schema-pack.yaml`` file.

    YAML parsing reuses only :func:`load_manifest_mapping`; every field is then
    validated by :func:`parse_schema_pack_manifest`. Capability-pack semantics
    are never consulted.
    """
    manifest_path = Path(path)
    try:
        mapping = load_manifest_mapping(manifest_path, manifest_kind="schema-pack")
    except ManifestParseError as exc:
        raise SchemaPackManifestError(
            f"cannot load schema-pack manifest {manifest_path}: {exc}"
        ) from exc
    return parse_schema_pack_manifest(mapping, source_path=manifest_path)


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
