"""Deterministic pack, writer, schema, and authority lint (m1 plan step 22).

This module enforces the architecture the repository-backed bridge depends
on, with **no** legacy false positives and **no** second-authority false
negatives. Every rule is a pure function over source text, migration SQL,
and the declared schema-pack manifests, so the lint is deterministic and
runs anywhere (no git state, no network).

Rules:

``import_boundaries``
    - kernel-to-pack: nothing under ``astrid/core/`` may import
      ``astrid.packs`` except the single documented application-composition
      exemption (``astrid/core/gateway/dispatch.py``, the serve root that
      composes the standard bridge).
    - pack-to-pack: no pack may import another pack's modules. The timeline
      pack's own ``bridge.py`` and repository compose only kernel services.

``writer_authority``
    SQLite construction (``sqlite3.connect``, ``sqlite3.Connection``,
    ``DatabaseWriter(``) is allowed only inside ``astrid/core/store``. Any
    other writer is a second write authority and a lint error.

``legacy_authorities``
    The supported v10 entry paths (bridge DTOs, the timeline adapter, the
    standard composition, the gateway serve root) must never import the
    legacy file/JSONL/FSA/Supabase authorities. The m1-m6 legacy files stay
    in-tree; the rule is scoped to the supported entry paths, and the
    legacy save/asset routes in ``local_bridge_server.py`` are the
    documented teardown bridge (owned by later tasks), not a fallback.

``removed_authorities``
    The eight-family product paths (dispatch routes, SDK modules, the
    application composition, the bridge composition, and the pack modules)
    must never import a removed authority module: the legacy
    ``astrid.core.timeline.eventlog`` / ``astrid.core.threads`` /
    ``astrid.core.session`` authorities, the deleted
    ``astrid.core.cli.{timeline,project,session}`` CLI modules, and the
    removed ``reigh.supabase_client`` / ``reigh.data_provider`` integrations.
    The legacy modules stay in-tree as dead code for non-product consumers;
    only their import from a product path is forbidden (m6 plan step 8).

``schema_ownership``
    Parsed from migration SQL plus manifest-declared table ownership:
    - kernel foreign keys may reference kernel tables only (never a pack
      table): pack tables must never be kernel FKs;
    - pack foreign keys may reference kernel tables only: cross-pack FKs
      are rejected;
    - every created table/index must be declared (kernel tables/indexes in
      the core catalog; pack tables in the owning manifest);
    - every ``event_streams.stream_type`` value is the open column, so
      stream vocabulary must be registry-declared (closed set) — SQL may not
      hard-code a stream type outside the declared vocabulary;
    - forbidden schema vocabulary (``FORBIDDEN_TABLES``) may never appear;
    - projected alias/default values may never be accepted as write
      authority: no pack table may carry slug/ULID/default convenience
      columns (SD1), and no ``DEFAULT`` on a pack-owned identity column.

The composition exemption is exactly one: ``astrid/core/gateway/dispatch.py``
may import the standard pack composition (and ``astrid/packs/__init__.py``
is the standard composition itself). Nothing else is exempt.
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from astrid.core.migrations.catalog import (
    CORE_INDEXES,
    CORE_TABLES,
    FORBIDDEN_TABLES,
)
from astrid.core.schema_packs.manifest import load_schema_pack_manifest
from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSITION_EXEMPTION = "astrid/core/gateway/dispatch.py"
"""The one documented kernel-to-pack composition exemption (serve root)."""

SUPPORTED_ENTRY_PATHS = (
    "astrid/core/integrations/reigh/bridge_service.py",
    "astrid/packs/timeline/bridge.py",
    "astrid/packs/__init__.py",
    COMPOSITION_EXEMPTION,
    # Eight-family dispatch paths (m6): the gateway entrypoint and the
    # product-family dispatch boundary route the five product families plus
    # serve/doctor/backup. They must never import a legacy/removed authority.
    "astrid/core/gateway/__init__.py",
    "astrid/core/cli/domain_product.py",
    "astrid/core/cli/domain_projects.py",
    "astrid/core/cli/domain_media.py",
    "astrid/core/cli/domain_tasks.py",
    "astrid/core/cli/domain_runs.py",
)
"""Supported v10 entry paths the legacy-authority rule scans."""

LEGACY_AUTHORITY_MARKERS = (
    "LocalFsBackend",
    "astrid.core.timeline.eventlog",
    "supabase",
    "data_provider",
    # Removed-authority modules (m6 plan step 8): dead code that the
    # eight-family product paths must never import.
    "astrid.core.threads",
    "astrid.core.session",
    "astrid.core.cli.timeline",
    "astrid.core.cli.project",
    "astrid.core.cli.session",
    "astrid.core.integrations.reigh.supabase_client",
    "astrid.core.integrations.reigh.data_provider",
)
"""Legacy authority markers (capitalized/qualified so the absence
declarations in docstrings — e.g. 'no FSA/Supabase fallback' — never trip
the rule)."""

REMOVED_AUTHORITY_MODULES = (
    "astrid.core.timeline.eventlog",
    "astrid.core.threads",
    "astrid.core.session",
    "astrid.core.cli.timeline",
    "astrid.core.cli.project",
    "astrid.core.cli.session",
    "astrid.core.integrations.reigh.supabase_client",
    "astrid.core.integrations.reigh.data_provider",
)
"""Removed authority modules forbidden from the eight-family product paths.

The m6 cutover removes these authorities from the product surface: the
legacy file/JSONL/FSA authorities (``eventlog``), the legacy thread/session
kernels, the deleted timeline/project/session CLI modules, and the removed
Reigh Supabase/data-provider integrations. The modules stay in-tree as dead
code for non-product consumers; only their import from a product path is a
lint error.
"""

# Product paths scanned by ``lint_removed_authorities``: the eight-family
# dispatch routes, the SDK, the application composition, the bridge
# composition, and the pack modules — not the entire ``astrid/`` tree. The
# pack product paths are the standard schema packs only (those shipping a
# ``schema-pack.yaml``): the m1-m6 legacy capability packs stay in-tree as
# non-product dead code and keep their own import graph.
_PRODUCT_PATH_DIRS = (
    "astrid/core/gateway",  # eight-family dispatch routes
    "astrid/sdk",           # SDK modules
)

_PRODUCT_PATH_FILES = (
    "astrid/application.py",                            # application composition
    "astrid/core/integrations/reigh/bridge_service.py",  # bridge composition
)

# The m1-m6 legacy rendering/builtin capability packs remain in-tree
# (plan step 22.3): kernel CLI/gateway modules legitimately import them.
# The m1 schema-pack boundary is about the new repository architecture —
# the kernel must never import the schema packs (timeline/shots/references)
# or any other pack module.
_LEGACY_PACK_PREFIXES = ("astrid.packs.rendering.", "astrid.packs.builtin.")

# The kernel conformance kit constructs scratch DatabaseWriters on its own
# temp databases to prove crash atomicity of the kernel store; that is
# conformance testing of the store, never a second write authority.
_CONFORMANCE_KIT_REL = "astrid/core/conformance/kit.py"

FORBIDDEN_CONVENIENCE_COLUMNS = frozenset(
    {"slug", "timeline_ulid", "is_default", "event_hash", "previous_event_hash"}
)
"""Projected alias/default columns that must never become write columns."""

_STREAM_TYPE_RE = re.compile(
    r"INSERT\s+INTO\s+event_streams\s*\([^)]*stream_type[^)]*\)\s*"
    r"VALUES\s*\([^)]*'([^']+)'",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LintReport:
    """The deterministic lint result for one repository root."""

    errors: tuple[str, ...]
    mode: str = "source"
    root: str | None = None
    scanned_files: tuple[str, ...] = ()
    observation_counts: Mapping[str, int] | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        """Return a stable, JSON-safe evidence record for the lint."""
        payload: dict[str, Any] = {
            "ok": self.ok,
            "errors": list(self.errors),
            "mode": self.mode,
        }
        if self.root is not None:
            payload["root"] = self.root
        if self.scanned_files:
            payload["scanned_files"] = list(self.scanned_files)
        if self.observation_counts is not None:
            payload["observation_counts"] = dict(self.observation_counts)
        return payload


def _iter_python(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts and not path.name.startswith(".")
        )
    )


def _child_dirs(root: Path) -> tuple[Path, ...]:
    """Sorted immediate subdirectories, empty when *root* is absent."""
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.iterdir() if path.is_dir()))


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
                modules.update(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
    return modules


def _is_legacy_pack_module(module: str) -> bool:
    """Whether *module* lives in a pre-existing m1-m6 capability pack.

    The legacy rendering/builtin capability packs remain in-tree (plan step
    22.3); kernel CLI/gateway modules legitimately import them, and the
    legacy packs form their own pre-existing import graph. The m1 boundary
    is about the new schema packs (timeline/shots/references) and any other
    pack module — never the documented legacy prefixes.
    """
    return any(
        module == prefix.rstrip(".") or module.startswith(prefix)
        for prefix in _LEGACY_PACK_PREFIXES
    )


def _pack_cli_mount_families(root: Path, pack_id: str) -> frozenset[str]:
    """The host families into which *pack_id*'s manifest declares CLI mounts.

    ``cli_mounts`` values are ``"<family> <verb>"`` tokens (e.g. the shots
    manifest's ``shots: timelines shots``), so the family is the first token.
    """
    manifest_path = root / "astrid" / "packs" / pack_id / "schema-pack.yaml"
    if not manifest_path.is_file():
        return frozenset()
    try:
        manifest = load_schema_pack_manifest(manifest_path)
    except Exception:  # noqa: BLE001 - a broken manifest is a different rule
        return frozenset()
    families: set[str] = set()
    for value in manifest.cli_mounts.values():
        tokens = value.split()
        if tokens:
            families.add(tokens[0])
    return frozenset(families)


def _kernel_cli_family(rel: str) -> str | None:
    """The product family of an ``astrid/core/cli/domain_<family>.py`` module."""
    prefix = "astrid/core/cli/domain_"
    if rel.startswith(prefix) and rel.endswith(".py"):
        return rel[len(prefix) : -3]
    return None


def _is_declared_cli_mount_import(
    root: Path, rel: str, module: str, *, pack_dir_name: str | None = None
) -> bool:
    """Whether *module* is a manifest-declared nested CLI mount import.

    A kernel family module or a host pack's ``cli`` module may embed another
    schema pack's ``cli`` module only when the target pack's manifest
    declares a ``cli_mounts`` entry whose host family matches the importing
    family (e.g. ``references: media references`` allows
    ``astrid/core/cli/domain_media.py`` to embed the references parser, and
    ``shots: timelines shots`` allows ``astrid/packs/timeline/cli.py`` to
    embed the shots parser). This is declared composition, never a hidden
    second authority: repository/conformance/service imports stay forbidden.
    """
    if not (module == "astrid.packs" or module.startswith("astrid.packs.")):
        return False
    parts = module.split(".")
    if len(parts) < 3:
        return False
    target_pack = parts[2]
    if len(parts) > 3 and parts[3] != "cli":
        return False
    mount_families = _pack_cli_mount_families(root, target_pack)
    if not mount_families:
        return False
    if pack_dir_name is not None:
        # Pack-to-pack: the importing pack is a declared host of the
        # target's mount when one of its own cli_mount families matches.
        importing_families = _pack_cli_mount_families(root, pack_dir_name)
        return bool(mount_families & importing_families)
    family = _kernel_cli_family(rel)
    return family is not None and family in mount_families


def lint_import_boundaries(root: Path) -> list[str]:
    """Kernel-to-pack and pack-to-pack import violations.

    Kernel-to-pack: nothing under ``astrid/core/`` may import a pack module
    except the one composition exemption (``dispatch.py``) and the
    documented legacy rendering/builtin prefixes. Pack-to-pack: the m1
    schema packs (those shipping a ``schema-pack.yaml``) may not import any
    other pack; the pre-existing legacy packs keep their own graph.
    """
    errors: list[str] = []
    core_root = root / "astrid" / "core"
    packs_root = root / "astrid" / "packs"
    for path in _iter_python(core_root):
        rel = _rel(path, root)
        if rel == COMPOSITION_EXEMPTION:
            continue
        try:
            modules = _imported_modules(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            errors.append(f"{rel}: unreadable source: {exc}")
            continue
        for module in sorted(modules):
            if not (module == "astrid.packs" or module.startswith("astrid.packs.")):
                continue
            if _is_legacy_pack_module(module):
                continue
            if _is_declared_cli_mount_import(root, rel, module):
                continue
            errors.append(
                f"{rel}: kernel-to-pack import {module!r} "
                "(only the serve composition root is exempt)"
            )
    schema_pack_dirs = [
        path
        for path in _child_dirs(packs_root)
        if (path / "__init__.py").exists()
        and (path / "schema-pack.yaml").is_file()
    ]
    for pack_dir in schema_pack_dirs:
        for path in _iter_python(pack_dir):
            rel = _rel(path, root)
            try:
                modules = _imported_modules(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            for module in sorted(modules):
                if not module.startswith("astrid.packs."):
                    continue
                other_pack = module.split(".")[2]
                if other_pack == pack_dir.name:
                    continue
                if _is_declared_cli_mount_import(
                    root, rel, module, pack_dir_name=pack_dir.name
                ):
                    continue
                errors.append(
                    f"{rel}: pack-to-pack import {module!r} from "
                    f"pack {pack_dir.name!r}"
                )
    return errors


def lint_writer_authority(root: Path) -> list[str]:
    """SQLite writer construction outside the kernel store.

    ``astrid/core/store`` owns every writable connection. Two documented
    exemptions exist: the conformance kit (``astrid/core/conformance/kit.py``)
    constructs scratch ``DatabaseWriter``\ s on its own temp databases to
    prove crash atomicity of the kernel store — that is conformance testing
    of the store, never a second write authority; and
    ``astrid/packs/__init__.py`` is the standard composition root itself,
    the single place that constructs the standard database/writer at the
    gateway serve composition root. Read-only URI probes (``mode=ro``) and the
    canonical ``read_only_uri`` helper are not writers and are never flagged.
    """
    errors: list[str] = []
    store_root = root / "astrid" / "core" / "store"
    for path in _iter_python(root / "astrid"):
        rel = _rel(path, root)
        if rel.startswith("astrid/core/store/"):
            continue
        if rel == _CONFORMANCE_KIT_REL:
            continue
        if rel == "astrid/packs/__init__.py":
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "DatabaseWriter(" in source:
            errors.append(
                f"{rel}: SQLite writer construction outside the kernel store"
            )
            continue
        if (
            "sqlite3.connect(" in source
            and "mode=ro" not in source
            and "read_only_uri(" not in source
        ):
            errors.append(
                f"{rel}: SQLite writer construction outside the kernel store"
            )
    return errors


def lint_legacy_authorities(root: Path) -> list[str]:
    """Legacy authorities inside the supported v10 entry paths."""
    errors: list[str] = []
    for rel in SUPPORTED_ENTRY_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for marker in LEGACY_AUTHORITY_MARKERS:
            if marker in source:
                errors.append(
                    f"{rel}: legacy authority marker {marker!r} in a "
                    "supported v10 entry path"
                )
    return errors


def _is_removed_authority(module: str) -> bool:
    """Whether *module* is a removed authority module (or a submodule)."""
    return any(
        module == removed or module.startswith(removed + ".")
        for removed in REMOVED_AUTHORITY_MODULES
    )


def _schema_pack_ids(root: Path) -> frozenset[str]:
    """The standard schema-pack ids under ``astrid/packs`` (manifest present).

    Mirrors :func:`lint_import_boundaries`: a pack directory is a product
    schema pack only when it ships a ``schema-pack.yaml``. The m1-m6 legacy
    capability packs (rendering, builtin, generation, iteration,
    video_editing, ...) are non-product dead code and are never product
    paths for the removed-authority rule.
    """
    packs_root = root / "astrid" / "packs"
    return frozenset(
        path.name
        for path in _child_dirs(packs_root)
        if (path / "schema-pack.yaml").is_file()
    )


def _is_removed_authority_product_path(root: Path, rel: str) -> bool:
    """Whether *rel* is one of the eight-family product paths.

    The product surface is exactly: the eight-family dispatch routes
    (``astrid/core/gateway/``), the SDK modules (``astrid/sdk/``), the
    application composition (``astrid/application.py``), the bridge
    composition (``astrid/core/integrations/reigh/bridge_service.py``), and
    the standard schema-pack modules (``astrid/packs/<schema-pack>``).
    Everything else in the tree is non-product (legacy dead code that may
    stay in-tree), including the m1-m6 legacy capability packs.
    """
    if rel in _PRODUCT_PATH_FILES:
        return True
    if rel == "astrid/packs" or rel.startswith("astrid/packs/"):
        pack_id = rel.split("/")[2]
        return pack_id in _schema_pack_ids(root)
    return any(rel == d or rel.startswith(d + "/") for d in _PRODUCT_PATH_DIRS)


def lint_removed_authorities(root: Path) -> list[str]:
    """Removed-authority imports from the eight-family product paths.

    The m6 cutover removes the legacy file/JSONL/FSA/Supabase authorities and
    the legacy timeline/project/session CLI modules from the product surface.
    Any product path (dispatch route, SDK module, application composition,
    bridge composition, or pack module) that imports one of the removed
    authority modules is a second authority and a lint error. The legacy
    modules stay in-tree as dead code for non-product consumers; only their
    import from a product path is forbidden.
    """
    errors: list[str] = []
    for path in _iter_python(root / "astrid"):
        rel = _rel(path, root)
        if not _is_removed_authority_product_path(root, rel):
            continue
        try:
            modules = _imported_modules(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for module in sorted(modules):
            if _is_removed_authority(module):
                errors.append(
                    f"{rel}: removed-authority import {module!r} from a "
                    "product path"
                )
    return errors


def _parse_sql_create_tables(sql: str) -> dict[str, dict[str, Any]]:
    """Parse CREATE TABLE statements into {name: columns/fks}."""
    tables: dict[str, dict[str, Any]] = {}
    for match in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)\s*;",
        sql,
        re.IGNORECASE | re.DOTALL,
    ):
        name = match.group(1).lower()
        body = match.group(2)
        columns: list[str] = []
        fks: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            if stripped.upper().startswith("FOREIGN KEY") or "REFERENCES" in stripped.upper():
                fks.append(stripped)
                continue
            col_match = re.match(r"([`\"]?)(\w+)\1\s", stripped)
            if col_match:
                columns.append(col_match.group(2).lower())
        tables[name] = {"columns": columns, "fks": fks}
    return tables


def _declared_tables(root: Path) -> dict[str, str]:
    """Map every declared table to its owning pack (core or pack id)."""
    declared: dict[str, str] = {table: "core" for table in CORE_TABLES}
    packs_root = root / "astrid" / "packs"
    for pack_dir in _child_dirs(packs_root):
        manifest_path = pack_dir / "schema-pack.yaml"
        if not manifest_path.is_file():
            continue
        manifest = load_schema_pack_manifest(manifest_path)
        for migration in manifest.migrations:
            for table in migration.tables:
                declared[table] = manifest.id
    return declared


def _migration_sql_files(root: Path) -> list[tuple[str, str]]:
    """Return (rel, sql) for every migration SQL file under the repo."""
    files: list[tuple[str, str]] = []
    for sql in root.rglob("*.sql"):
        rel = _rel(sql, root)
        if "build/" in rel:
            continue
        try:
            files.append((rel, sql.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return files


def lint_schema_ownership(root: Path) -> list[str]:
    """FK, declaration, vocabulary, forbidden-table, and alias rules."""
    errors: list[str] = []
    declared = _declared_tables(root)
    index_owners: dict[str, str] = {}
    for table, owner in declared.items():
        for index in CORE_INDEXES if owner == "core" else ():
            index_owners[index] = "core"
    for rel, sql in _migration_sql_files(root):
        tables = _parse_sql_create_tables(sql)
        # Undeclared tables.
        for table in tables:
            if table not in declared:
                errors.append(
                    f"{rel}: undeclared table {table!r} "
                    "(missing from the core catalog or a manifest)"
                )
            if table in FORBIDDEN_TABLES:
                errors.append(
                    f"{rel}: forbidden table {table!r} violates the "
                    "no-dormant-platform invariant"
                )
            # Projected alias/default convenience columns (SD1): the rule
            # applies to pack-owned tables only. Kernel tables legitimately
            # carry real write columns (projects.slug is a kernel column);
            # the packs may never project slug/ULID/default/hash state as
            # write authority.
            if declared.get(table) != "core":
                for column in tables[table]["columns"]:
                    if column in FORBIDDEN_CONVENIENCE_COLUMNS:
                        errors.append(
                            f"{rel}: convenience column {table}.{column} "
                            "projects alias/default state as write authority"
                        )
        # FK ownership: kernel FKs to pack tables and cross-pack FKs.
        for table, info in tables.items():
            owner = declared.get(table)
            for fk in info["fks"]:
                ref_match = re.search(r"REFERENCES\s+(\w+)", fk, re.IGNORECASE)
                if ref_match is None:
                    continue
                target = ref_match.group(1).lower()
                target_owner = declared.get(target)
                if target_owner is None:
                    continue
                if owner == "core" and target_owner != "core":
                    errors.append(
                        f"{rel}: kernel FK from {table} to pack table "
                        f"{target!r}"
                    )
                if owner != "core" and target_owner != "core" and target_owner != owner:
                    errors.append(
                        f"{rel}: cross-pack FK from {table} to "
                        f"{target!r} (pack {target_owner!r})"
                    )
        # Closed stream vocabulary: a hard-coded stream type in SQL must be
        # declared by the composed registry vocabulary.
        for match in _STREAM_TYPE_RE.finditer(sql):
            stream_type = match.group(1)
            if not _is_declared_stream_type(root, stream_type):
                errors.append(
                    f"{rel}: stream type {stream_type!r} is not declared "
                    "by the composed registry"
                )
        # Undeclared named indexes (parse CREATE [UNIQUE] INDEX ... ON).
        for match in re.finditer(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"(\w+)\s+ON\s+(\w+)",
            sql,
            re.IGNORECASE,
        ):
            index = match.group(1).lower()
            table = match.group(2).lower()
            owner = declared.get(table, "?")
            if owner == "core" and index not in CORE_INDEXES:
                errors.append(f"{rel}: undeclared kernel index {index!r}")
    return errors


def _is_declared_stream_type(root: Path, stream_type: str) -> bool:
    """Whether *stream_type* is declared by the standard composed registry."""
    registry = _standard_registry(root)
    try:
        from astrid.core.events.registry import validate_stream_type

        validate_stream_type(registry, stream_type)
        return True
    except Exception:
        return False


def _standard_registry(root: Path) -> FrozenSchemaPackRegistry:
    from astrid.core.events.registry import register_core_vocabulary
    from astrid.core.schema_packs.registry import SchemaPackRegistry

    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    packs_root = root / "astrid" / "packs"
    for pack_dir in _child_dirs(packs_root):
        manifest_path = pack_dir / "schema-pack.yaml"
        if manifest_path.is_file():
            manifest = load_schema_pack_manifest(manifest_path)
            registry.register_pack(manifest)
    return registry.freeze()


# ---------------------------------------------------------------------------
# Installed-artifact authority checks (m8 plan step 7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _InstalledLayout:
    """The package layout proved by ``--installed-root``."""

    root: Path
    package_root: Path


_INSTALLED_REQUIRED_FILES = (
    "astrid/__init__.py",
    "astrid/core/__init__.py",
    "astrid/packs/__init__.py",
    "astrid/core/migrations/sql/core/0001_initial.sql",
)

_INSTALLED_SEMANTIC_SUFFIXES = (".json", ".jsonl", ".fsa", ".fsa.json")
_INSTALLED_SEMANTIC_NAMES = frozenset(
    {
        "assembly.head.json",
        "assembly.identity.json",
        "assembly.jsonl",
        "current_run.json",
        "events.jsonl",
        "lease.json",
        "plan.json",
        "project.json",
        "session.json",
        "state.json",
        "thread.json",
        "timeline.json",
    }
)
_INSTALLED_FORBIDDEN_IDENTIFIERS = frozenset(
    {
        "filesystemaccess",
        "indexeddb",
        "localstorage",
        "showopenfilepicker",
        "showsavefilepicker",
        "supabase",
    }
)
_INSTALLED_FALLBACK_MARKERS = frozenset(
    {
        "backend",
        "catalog",
        "connection",
        "database",
        "eventlog",
        "fsa",
        "json",
        "lease",
        "legacy",
        "localfs",
        "registry",
        "session",
        "sidecar",
        "sqlite",
        "supabase",
        "thread",
        "writer",
    }
)
_INSTALLED_DIAGNOSTIC_DIRS = frozenset(
    {"diagnostic", "diagnostics", "evidence", "log", "logs", "out", "output"}
)
_INSTALLED_BACKUP_DIRS = frozenset(
    {"backup", "backups", "backup-output", "restore", "restores"}
)


def _resolve_installed_layout(value: str | Path) -> tuple[_InstalledLayout | None, list[str]]:
    """Resolve an installed root without ever falling back to the checkout.

    Both forms used by the release harness are accepted: a wheel extraction or
    ``site-packages`` directory containing ``astrid/``, and the ``astrid/``
    package directory itself.  A source checkout is deliberately rejected even
    when it happens to contain a valid package, because accepting it would make
    an empty/wrong installed-root check vacuous.
    """
    candidate = Path(value).expanduser().resolve()
    errors: list[str] = []
    if not candidate.exists():
        return None, [f"installed root does not exist: {candidate}"]
    if not candidate.is_dir():
        return None, [f"installed root is not a directory: {candidate}"]

    if candidate.name == "astrid" and (candidate / "__init__.py").is_file():
        root = candidate.parent
        package_root = candidate
    elif (candidate / "astrid" / "__init__.py").is_file():
        root = candidate
        package_root = candidate / "astrid"
    else:
        return None, [
            f"installed root is missing the astrid package: {candidate}"
        ]

    # A checkout root is not an installed root.  The explicit mode must never
    # silently certify source files just because their package layout matches.
    if (root / "pyproject.toml").is_file() or (root / ".git").exists():
        errors.append(
            f"installed root points at a source checkout rather than an unpacked/site-packages root: {root}"
        )

    for relative in _INSTALLED_REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"installed root is missing required artifact file: {relative}")
    python_files = tuple(_iter_python(package_root))
    if not python_files:
        errors.append(f"installed root contains no Python sources: {package_root}")
    if not any(
        path.name.startswith("astrid-") and path.name.endswith(".dist-info")
        for path in root.iterdir()
        if path.is_dir()
    ):
        # A package directory copied out of a wheel is still a useful installed
        # root, so this is a warning-shaped validation only when the package
        # itself is otherwise complete.  Do not require dist-info here.
        pass
    if errors:
        return None, errors
    return _InstalledLayout(root=root, package_root=package_root), []


def _installed_rel(path: Path, root: Path) -> str:
    return _rel(path, root)


def _installed_product_path(root: Path, rel: str) -> bool:
    """Whether an installed Python path is part of the supported product.

    Legacy capability modules remain packageable for compatibility, but they
    are not an authority in the eight-family product.  The installed scan
    therefore applies authority-sensitive source rules to the same product
    boundary as the removed-authority lint, plus every standard schema pack.
    Pack-owned writer/transaction checks below still scan the complete schema
    pack directory rather than only its entry modules.
    """
    return _is_removed_authority_product_path(root, rel)


def _installed_product_python(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in _iter_python(root / "astrid")
        if _installed_product_path(root, _installed_rel(path, root))
    )


def _ast_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _ast_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _ast_string_literals(node: ast.AST) -> tuple[str, ...]:
    return tuple(
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    )


def _ast_path_hint(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else "{value}"
            for value in node.values
        )
    if isinstance(node, ast.Call):
        name = _ast_name(node.func).lower()
        if name in {"path", "pathlib.path", "purepath", "pureposixpath"}:
            return "/".join(filter(None, (_ast_path_hint(arg) for arg in node.args)))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left = _ast_path_hint(node.left)
        right = _ast_path_hint(node.right)
        return f"{left}{right}"
    return ""


def _is_diagnostic_hint(hint: str) -> bool:
    lower = hint.replace("\\", "/").lower()
    parts = [part for part in lower.split("/") if part]
    return bool(
        set(parts) & _INSTALLED_DIAGNOSTIC_DIRS
        or any(token in lower for token in ("stdout", "stderr", "diagnostic", "evidence"))
        or lower.endswith((".log", ".txt", ".ndjson"))
    )


def _is_semantic_path_hint(hint: str) -> bool:
    lower = hint.replace("\\", "/").lower()
    name = lower.rsplit("/", 1)[-1]
    return (
        "sidecar" in lower
        or name in _INSTALLED_SEMANTIC_NAMES
        or lower.endswith(_INSTALLED_SEMANTIC_SUFFIXES)
    ) and not _is_diagnostic_hint(hint)


def _call_writes_file(node: ast.Call) -> bool:
    name = _ast_name(node.func).lower().rsplit(".", 1)[-1]
    if name in {"write_text", "write_bytes", "write_json", "write_json_atomic", "write_json_sidecar", "write_text_sidecar"}:
        return True
    if name in {"open", "fdopen"}:
        mode: str | None = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = str(node.args[1].value)
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                mode = str(keyword.value.value)
        return mode is None or any(flag in mode for flag in ("w", "a", "x", "+"))
    if name == "dump":
        return _ast_name(node.func).lower().endswith("json.dump")
    if name == "openat":
        return True
    return False


def _lint_installed_source_patterns(root: Path) -> list[str]:
    """Find authority patterns in supported installed Python source.

    This is intentionally AST-based for identifiers and calls: documentation
    such as ``no Supabase fallback`` must not become a false positive, while a
    real import, URL, browser storage call, semantic filename, or fallback
    branch remains visible.  The existing deterministic rules handle imports,
    FKs, and SQLite writer construction; this rule covers the artifact-only
    surfaces that cannot be inferred from those rules.
    """
    errors: list[str] = []
    for path in _installed_product_python(root):
        rel = _installed_rel(path, root)
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel)
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            errors.append(f"{rel}: installed source cannot be parsed: {exc}")
            continue

        def add(node: ast.AST, detail: str) -> None:
            line = getattr(node, "lineno", 0)
            suffix = f":{line}" if line else ""
            errors.append(f"{rel}{suffix}: {detail}")

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = []
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif node.module:
                    modules.append(node.module)
                for module in modules:
                    lower = module.lower()
                    if "supabase" in lower:
                        add(node, f"Supabase authority import {module!r}")
                    if any(marker in lower for marker in ("jsonlines", "file_system_access")):
                        add(node, f"semantic file-authority import {module!r}")

            if isinstance(node, (ast.Name, ast.Attribute)):
                identifier = _ast_name(node).lower().replace("_", "")
                if any(marker in identifier for marker in _INSTALLED_FORBIDDEN_IDENTIFIERS):
                    add(node, f"forbidden installed authority identifier {_ast_name(node)!r}")
                if "fallback" in identifier and any(
                    marker in identifier for marker in _INSTALLED_FALLBACK_MARKERS
                ):
                    add(node, f"silent authority fallback identifier {_ast_name(node)!r}")

            if isinstance(node, ast.Call):
                name = _ast_name(node.func).lower()
                if any(
                    marker in name
                    for marker in (
                        "showopenfilepicker",
                        "showsavefilepicker",
                        "filesystemaccess",
                        "localstorage",
                        "indexeddb",
                    )
                ):
                    add(node, f"forbidden FSA/browser-storage writer {name!r}")
                if "supabase" in name:
                    add(node, f"Supabase authority call {name!r}")
                if _call_writes_file(node):
                    call_leaf = name.rsplit(".", 1)[-1]
                    if call_leaf in {"write_text", "write_bytes", "write_json", "write_json_atomic", "write_json_sidecar", "write_text_sidecar"} and isinstance(node.func, ast.Attribute):
                        path_arg = node.func.value
                    else:
                        path_arg = node.args[0] if node.args else None
                    if name.endswith("json.dump") and len(node.args) > 1:
                        path_arg = node.args[1]
                    hint = _ast_path_hint(path_arg)
                    if name.endswith("json.dump") and not _is_diagnostic_hint(hint) and hint not in {
                        "sys.stdout",
                        "sys.stderr",
                        "stdout",
                        "stderr",
                    }:
                        add(node, "semantic JSON writer is not a diagnostic output")
                    elif _is_semantic_path_hint(hint):
                        add(node, f"semantic JSON/JSONL/FSA writer targets {hint!r}")
                call_strings = _ast_string_literals(node)
                if any("supabase" in value.lower() for value in call_strings):
                    add(node, "Supabase authority value in installed product code")
                if any(
                    any(marker in value.lower().replace("_", "") for marker in _INSTALLED_FORBIDDEN_IDENTIFIERS)
                    for value in call_strings
                ):
                    add(node, "forbidden FSA/removed-authority value in installed product code")

            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    handler_names = " ".join(
                        _ast_name(child).lower()
                        for child in ast.walk(handler)
                        if isinstance(child, (ast.Name, ast.Attribute, ast.Call))
                    )
                    handler_strings = " ".join(_ast_string_literals(handler)).lower()
                    combined = f"{handler_names} {handler_strings}"
                    diagnostic_sidecar = "returncode_sidecar" in combined
                    if "fallback" in combined or any(
                        marker in combined
                        for marker in (
                            "legacy",
                            "localfs",
                            "supabase",
                            "sidecar",
                            "jsonl",
                            "file system",
                        )
                    ) and not diagnostic_sidecar:
                        add(handler, "silent fallback or legacy authority in exception path")

    return errors


def lint_pack_dependency_directions(root: str | Path) -> list[str]:
    """Reject schema-pack dependencies that point sideways or outward."""
    repo_root = Path(root)
    errors: list[str] = []
    pack_dirs = [
        path
        for path in _child_dirs(repo_root / "astrid" / "packs")
        if (path / "schema-pack.yaml").is_file()
    ]
    pack_ids = {path.name for path in pack_dirs}
    for pack_dir in pack_dirs:
        rel = _rel(pack_dir / "schema-pack.yaml", repo_root)
        try:
            manifest = load_schema_pack_manifest(pack_dir / "schema-pack.yaml")
        except Exception as exc:  # noqa: BLE001 - fail closed for artifacts
            errors.append(f"{rel}: invalid installed schema-pack manifest: {exc}")
            continue
        if manifest.id != pack_dir.name:
            errors.append(
                f"{rel}: manifest id {manifest.id!r} does not match pack directory {pack_dir.name!r}"
            )
        for dependency in manifest.depends_on:
            if dependency.pack != "core":
                target = "present" if dependency.pack in pack_ids else "missing"
                errors.append(
                    f"{rel}: forbidden pack dependency {manifest.id!r} -> "
                    f"{dependency.pack!r} ({target} pack); packs may depend on core only"
                )
    return errors


def _as_observation_items(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, (str, Path)):
        return (value,)
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def _observation_field(
    observations: Mapping[str, object] | None,
    explicit: object,
    *names: str,
) -> tuple[object, ...]:
    values = list(_as_observation_items(explicit))
    if observations is not None:
        for name in names:
            if name in observations:
                values.extend(_as_observation_items(observations[name]))
    return tuple(values)


def _mapping_path(item: object) -> tuple[str, dict[str, object]]:
    if isinstance(item, Mapping):
        path_value = next(
            (
                item[key]
                for key in (
                    "path",
                    "file",
                    "filename",
                    "database",
                    "database_path",
                    "sqlite",
                    "locator",
                )
                if key in item
            ),
            None,
        )
        return str(path_value) if path_value is not None else "", {
            str(key): value for key, value in item.items()
        }
    return str(item), {}


def _truthy_observation(value: object) -> bool:
    if value is None or value is False or value == 0:
        return False
    if isinstance(value, str) and value.strip().lower() in {
        "",
        "0",
        "false",
        "no",
        "none",
        "null",
        "absent",
        "not observed",
        "not_claimed",
    }:
        return False
    return bool(value)


def _relative_path(path: Path, root: Path | None) -> Path | None:
    if root is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return None


def _path_has_component(path: Path, values: frozenset[str]) -> bool:
    return bool(set(part.lower() for part in path.parts) & values)


def _is_catalog_observation(path: Path, catalog_paths: tuple[Path, ...]) -> bool:
    if any(_relative_path(path, candidate) is not None for candidate in catalog_paths):
        return True
    name = path.name.lower()
    return (
        path.parent.name == ".astrid"
        and name in {"astrid.sqlite3", "astrid.sqlite3-wal", "astrid.sqlite3-shm", "astrid.sqlite3-journal"}
    )


def _is_managed_media_observation(path: Path, media_roots: tuple[Path, ...]) -> bool:
    if any(_relative_path(path, candidate) is not None for candidate in media_roots):
        return True
    parts = tuple(part.lower() for part in path.parts)
    return any(
        parts[index : index + 2] == (".astrid", "media")
        for index in range(max(0, len(parts) - 1))
    )


def _is_backup_observation(path: Path, backup_roots: tuple[Path, ...]) -> bool:
    return any(_relative_path(path, candidate) is not None for candidate in backup_roots) or _path_has_component(
        path, _INSTALLED_BACKUP_DIRS
    )


def _is_diagnostic_observation(path: Path, diagnostic_roots: tuple[Path, ...]) -> bool:
    return any(
        _relative_path(path, candidate) is not None for candidate in diagnostic_roots
    ) or _path_has_component(path, _INSTALLED_DIAGNOSTIC_DIRS)


def _semantic_observation_path(path: Path) -> bool:
    name = path.name.lower()
    return (
        name in _INSTALLED_SEMANTIC_NAMES
        or name.endswith(_INSTALLED_SEMANTIC_SUFFIXES)
        or "sidecar" in name.lower()
        or any(part.lower() in {"sessions", "threads", "leases"} for part in path.parts)
    )


def lint_runtime_authority_observations(
    *,
    journey_logs: object = (),
    sqlite_connections: object = (),
    created_files: object = (),
    observations: Mapping[str, object] | None = None,
    project_root: str | Path | None = None,
    catalog_paths: Iterable[str | Path] = (),
    managed_media_roots: Iterable[str | Path] = (),
    backup_roots: Iterable[str | Path] = (),
    diagnostic_roots: Iterable[str | Path] = (),
) -> list[str]:
    """Check retained installed-journey observations for second authorities.

    The accepted observation shape is deliberately plain JSON: paths may be
    strings or mappings with a ``path``/``database`` field.  A mapping may add
    ``owner``, ``write``/``writable``, ``transaction``, ``semantic``, or
    ``kind``.  This lets the journey retain evidence without importing this
    checkout-side linter into the installed process.
    """
    errors: list[str] = []
    project = Path(project_root).expanduser().resolve() if project_root else None
    catalog = tuple(Path(path).expanduser().resolve() for path in catalog_paths)
    media = tuple(Path(path).expanduser().resolve() for path in managed_media_roots)
    backups = tuple(Path(path).expanduser().resolve() for path in backup_roots)
    diagnostics = tuple(Path(path).expanduser().resolve() for path in diagnostic_roots)

    log_items = _observation_field(observations, journey_logs, "journey_logs", "logs")

    def expand_log_items(items: Iterable[object]) -> Iterable[object]:
        for item in items:
            if isinstance(item, Mapping):
                nested = [
                    item[key]
                    for key in ("stdout", "stderr", "path", "file")
                    if key in item
                ]
                if not nested:
                    errors.append("journey log observation has no readable path")
                else:
                    yield from expand_log_items(nested)
            else:
                yield item

    for item in expand_log_items(log_items):
        text: str
        origin: str
        candidate = Path(str(item)).expanduser()
        if candidate.is_dir():
            files = tuple(sorted(path for path in candidate.rglob("*") if path.is_file()))
            if not files:
                errors.append(f"journey log directory is empty: {candidate}")
            for path in files:
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    errors.append(f"journey log is unreadable {path}: {exc}")
                    continue
                errors.extend(_lint_runtime_log_text(text, str(path)))
            continue
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"journey log is unreadable {candidate}: {exc}")
                continue
            origin = str(candidate)
        else:
            text = str(item)
            origin = "<inline journey log>"
            if "\n" not in text and ("/" in text or "\\" in text or text.endswith((".log", ".txt", ".json", ".jsonl"))):
                errors.append(f"journey log does not exist: {candidate}")
                continue
        errors.extend(_lint_runtime_log_text(text, origin))

    sqlite_items = _observation_field(
        observations,
        sqlite_connections,
        "sqlite_connections",
        "sqlite",
        "connections",
    )
    for item in sqlite_items:
        path_text, metadata = _mapping_path(item)
        if not path_text:
            errors.append("SQLite connection observation has no database path")
            continue
        path = Path(path_text).expanduser()
        if not _is_catalog_observation(path, catalog) and not _is_backup_observation(path, backups):
            errors.append(
                f"SQLite connection outside the catalog/backup authority: {path}"
            )
        owner = str(
            metadata.get("owner", metadata.get("writer_owner", metadata.get("source", "")))
        ).lower()
        if owner and any(pack in owner for pack in _schema_pack_ids_from_paths(project)):
            if any(
                _truthy_observation(metadata.get(key))
                for key in ("write", "writable", "transaction", "owns_transaction")
            ) or "begin" in str(metadata.get("sql", "")).lower():
                errors.append(f"pack-owned SQLite writer/transaction observed: {path} ({owner})")
        if any(
            _truthy_observation(metadata.get(key))
            for key in ("semantic", "sidecar", "fallback")
        ):
            errors.append(f"forbidden semantic SQLite authority observation: {path}")

    file_items = _observation_field(
        observations,
        created_files,
        "created_files",
        "files",
        "write_locations",
    )
    for item in file_items:
        path_text, metadata = _mapping_path(item)
        if not path_text:
            errors.append("created-file observation has no path")
            continue
        path = Path(path_text).expanduser()
        kind = str(metadata.get("kind", "")).lower()
        if kind in {"input", "source", "fixture", "external_input"}:
            continue
        if _truthy_observation(metadata.get("semantic")) and not _is_catalog_observation(path, catalog):
            errors.append(f"semantic created-file authority observed: {path}")
            continue
        allowed = (
            _is_catalog_observation(path, catalog)
            or _is_managed_media_observation(path, media)
            or _is_backup_observation(path, backups)
            or _is_diagnostic_observation(path, diagnostics)
        )
        if not allowed:
            errors.append(
                f"created file is outside catalog, managed media, backup, or diagnostics: {path}"
            )
            continue
        if _semantic_observation_path(path) and not (
            _is_catalog_observation(path, catalog)
            or _is_backup_observation(path, backups)
            or _is_diagnostic_observation(path, diagnostics)
        ):
            errors.append(f"semantic JSON/JSONL/FSA created outside an allowed output: {path}")
        owner = str(metadata.get("owner", "")).lower()
        if owner and any(pack in owner for pack in _schema_pack_ids_from_paths(project)):
            errors.append(f"pack-owned file writer observed: {path} ({owner})")

    return errors


def _schema_pack_ids_from_paths(project_root: Path | None) -> frozenset[str]:
    """Return standard pack ids for observation owner classification."""
    if project_root is None:
        return frozenset({"timeline", "shots", "references"})
    return frozenset({"timeline", "shots", "references"})


def _lint_runtime_log_text(text: str, origin: str) -> list[str]:
    errors: list[str] = []
    lower = text.lower()
    structured: list[object] = []
    try:
        structured.append(json.loads(text))
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        try:
            structured.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    def inspect(value: object, key: str = "") -> None:
        key_lower = key.lower().replace("-", "_")
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                inspect(child_value, str(child_key))
            return
        if isinstance(value, list):
            for child in value:
                inspect(child, key)
            return
        if "fallback" in key_lower or "sidecar" in key_lower or "second_writer" in key_lower:
            if _truthy_observation(value):
                errors.append(f"{origin}: forbidden runtime authority flag {key!r}={value!r}")
        if key_lower in {"semantic_writer", "writer_owner"} and str(value).lower() not in {
            "sqlite-catalog",
            "kernel",
            "one-shared-writer",
            "",
        }:
            errors.append(f"{origin}: forbidden runtime semantic writer {value!r}")

    for value in structured:
        inspect(value)

    if "supabase" in lower and not re.search(
        r"supabase[^\n]{0,40}(?:false|null|absent|none|not present)", lower
    ):
        errors.append(f"{origin}: Supabase authority marker in journey logs")
    for marker, label in (
        ("showopenfilepicker", "FSA"),
        ("showsavefilepicker", "FSA"),
        ("filesystem access", "FSA"),
        ("localstorage", "browser storage"),
        ("indexeddb", "browser storage"),
        ("legacy authority", "removed authority"),
        ("localfs", "removed authority"),
        ("eventlog", "removed authority"),
        ("sidecar", "semantic sidecar"),
        ("second writer", "second writer"),
        ("pack-owned writer", "pack-owned writer"),
    ):
        marker_pattern = re.escape(marker).replace(r"\ ", r"[_\s-]+")
        negative_flag = re.search(
            rf"{marker_pattern}[^\n]{{0,50}}(?:false|null|absent|none|not present)",
            lower,
        )
        if re.search(marker_pattern, lower) and negative_flag is None:
            errors.append(f"{origin}: forbidden runtime {label} marker {marker!r}")
    fallback_negative = re.search(
        r"fallback[^\n]{0,60}(?:false|null|absent|none|not observed)", lower
    )
    if (
        re.search(
            r"fallback[^\n]{0,60}(?:used|using|selected|enabled|true|backend|authority|legacy|jsonl|fsa)",
            lower,
        )
        and fallback_negative is None
    ):
        errors.append(f"{origin}: silent fallback observed in journey logs")
    allowed_catalog_writer = re.search(
        r"(?:semantic_writer|writer_owner)\s*[\":=]+\s*[\"]?(?:sqlite-catalog|kernel|one-shared-writer)",
        lower,
    )
    if (
        re.search(r"(?:semantic|jsonl|fsa)[^\n]{0,50}(?:writer|authority|write)", lower)
        and allowed_catalog_writer is None
    ):
        errors.append(f"{origin}: semantic file writer observed in journey logs")
    return errors


def _safe_installed_rule(
    label: str,
    rule: Any,
    root: Path,
) -> list[str]:
    """Run one installed rule fail-closed when artifact metadata is damaged."""
    try:
        result = rule(root)
    except Exception as exc:  # noqa: BLE001 - a malformed artifact is a lint error
        return [f"installed authority rule {label} failed closed: {type(exc).__name__}: {exc}"]
    return [str(error) for error in result]


def run_installed_authority_lint(
    installed_root: str | Path,
    *,
    journey_logs: object = (),
    sqlite_connections: object = (),
    created_files: object = (),
    observations: Mapping[str, object] | None = None,
    project_root: str | Path | None = None,
    catalog_paths: Iterable[str | Path] = (),
    managed_media_roots: Iterable[str | Path] = (),
    backup_roots: Iterable[str | Path] = (),
    diagnostic_roots: Iterable[str | Path] = (),
) -> LintReport:
    """Run authority checks against one unpacked wheel/site-packages root.

    ``installed_root`` is intentionally separate from the source-mode
    ``root`` argument.  It must contain a real package/resource layout and is
    never replaced with :data:`REPO_ROOT` when the path is empty or wrong.
    Runtime observations are optional for static-only callers and are checked
    when supplied by the installed journey.
    """
    layout, shape_errors = _resolve_installed_layout(installed_root)
    if layout is None:
        return LintReport(
            errors=tuple(sorted(set(shape_errors))),
            mode="installed",
            root=str(Path(installed_root).expanduser().resolve()),
        )

    root = layout.root
    errors: list[str] = []
    errors.extend(_safe_installed_rule("import boundaries", lint_import_boundaries, root))
    errors.extend(_safe_installed_rule("writer authority", lint_writer_authority, root))
    errors.extend(_safe_installed_rule("legacy authorities", lint_legacy_authorities, root))
    errors.extend(_safe_installed_rule("removed authorities", lint_removed_authorities, root))
    errors.extend(_safe_installed_rule("schema ownership", lint_schema_ownership, root))
    errors.extend(
        _safe_installed_rule(
            "pack dependency directions", lint_pack_dependency_directions, root
        )
    )
    errors.extend(_safe_installed_rule("installed source patterns", _lint_installed_source_patterns, root))
    errors.extend(
        lint_runtime_authority_observations(
            journey_logs=journey_logs,
            sqlite_connections=sqlite_connections,
            created_files=created_files,
            observations=observations,
            project_root=project_root,
            catalog_paths=catalog_paths,
            managed_media_roots=managed_media_roots,
            backup_roots=backup_roots,
            diagnostic_roots=diagnostic_roots,
        )
    )
    scanned = tuple(
        sorted(_installed_rel(path, root) for path in _iter_python(layout.package_root))
    )
    counts = {
        "journey_logs": len(
            _observation_field(observations, journey_logs, "journey_logs", "logs")
        ),
        "sqlite_connections": len(
            _observation_field(
                observations,
                sqlite_connections,
                "sqlite_connections",
                "sqlite",
                "connections",
            )
        ),
        "created_files": len(
            _observation_field(
                observations,
                created_files,
                "created_files",
                "files",
                "write_locations",
            )
        ),
    }
    return LintReport(
        errors=tuple(sorted(set(errors))),
        mode="installed",
        root=str(root),
        scanned_files=scanned,
        observation_counts=counts,
    )


def lint_installed_authorities(
    installed_root: str | Path,
    **kwargs: object,
) -> list[str]:
    """Compatibility-friendly list API for the installed authority scan."""
    return list(run_installed_authority_lint(installed_root, **kwargs).errors)


def run_authority_lint(
    root: str | Path = REPO_ROOT,
    *,
    installed_root: str | Path | None = None,
    installed: bool = False,
    **installed_kwargs: object,
) -> LintReport:
    """Run source-mode lint, or explicit installed-root mode when requested."""
    if installed_root is not None or installed:
        target = installed_root if installed_root is not None else root
        return run_installed_authority_lint(target, **installed_kwargs)
    repo_root = Path(root)
    errors: list[str] = []
    errors.extend(lint_import_boundaries(repo_root))
    errors.extend(lint_writer_authority(repo_root))
    errors.extend(lint_legacy_authorities(repo_root))
    errors.extend(lint_removed_authorities(repo_root))
    errors.extend(lint_schema_ownership(repo_root))
    return LintReport(errors=tuple(sorted(errors)), mode="source", root=str(repo_root))


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m scripts.reshape.authority_lint [--json]``."""
    import argparse

    parser = argparse.ArgumentParser(prog="authority_lint")
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument(
        "--installed-root",
        help="scan one unpacked wheel/site-packages root (fail closed; no source fallback)",
    )
    parser.add_argument("--journey-log", action="append", default=[])
    parser.add_argument("--sqlite-connection", action="append", default=[])
    parser.add_argument("--created-file", action="append", default=[])
    parser.add_argument("--project-root")
    parser.add_argument("--catalog-path", action="append", default=[])
    parser.add_argument("--managed-media-root", action="append", default=[])
    parser.add_argument("--backup-root", action="append", default=[])
    parser.add_argument("--diagnostic-root", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.installed_root:
        report = run_installed_authority_lint(
            args.installed_root,
            journey_logs=args.journey_log,
            sqlite_connections=args.sqlite_connection,
            created_files=args.created_file,
            project_root=args.project_root,
            catalog_paths=args.catalog_path,
            managed_media_roots=args.managed_media_root,
            backup_roots=args.backup_root,
            diagnostic_roots=args.diagnostic_root,
        )
    else:
        report = run_authority_lint(args.root)
    if args.json:
        print(json.dumps(report.as_dict(), sort_keys=True))
    else:
        for error in report.errors:
            print(error)
        if report.ok:
            print("AUTHORITY LINT OK")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
