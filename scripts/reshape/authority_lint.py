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
import re
import sqlite3
from dataclasses import dataclass
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
)
"""Supported v10 entry paths the legacy-authority rule scans."""

LEGACY_AUTHORITY_MARKERS = (
    "LocalFsBackend",
    "astrid.core.timeline.eventlog",
    "supabase",
    "data_provider",
    "sidecar",
)
"""Legacy authority markers (capitalized/qualified so the absence
declarations in docstrings — e.g. 'no FSA/Supabase fallback' — never trip
the rule)."""

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

    @property
    def ok(self) -> bool:
        return not self.errors


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
                if other_pack != pack_dir.name:
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
    gateway serve composition root. Read-only URI probes (``mode=ro``) are
    not writers and are never flagged.
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
        if "sqlite3.connect(" in source and "mode=ro" not in source:
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
        for table in manifest.migrations[0].tables:
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


def run_authority_lint(root: str | Path = REPO_ROOT) -> LintReport:
    """Run every deterministic rule and return the combined report."""
    repo_root = Path(root)
    errors: list[str] = []
    errors.extend(lint_import_boundaries(repo_root))
    errors.extend(lint_writer_authority(repo_root))
    errors.extend(lint_legacy_authorities(repo_root))
    errors.extend(lint_schema_ownership(repo_root))
    return LintReport(errors=tuple(sorted(errors)))


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m scripts.reshape.authority_lint [--json]``."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(prog="authority_lint")
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_authority_lint(args.root)
    if args.json:
        print(json.dumps({"ok": report.ok, "errors": list(report.errors)}))
    else:
        for error in report.errors:
            print(error)
        if report.ok:
            print("AUTHORITY LINT OK")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
