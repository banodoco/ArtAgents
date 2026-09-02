"""Installed-wheel contract proof for the m8 packaged product."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reshape.installed_artifact import InstalledArtifactHarness, build_once


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def installed_harness(
    tmp_path_factory: pytest.TempPathFactory,
) -> InstalledArtifactHarness:
    workspace = tmp_path_factory.mktemp("m8-installed-contract")
    harness = build_once(REPO_ROOT, workspace=workspace)
    try:
        yield harness
    finally:
        harness.close()


_CONTRACT_PROBE = r'''
import hashlib
import json
import os
import re
import sqlite3
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from importlib import resources


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def resource_text(relative):
    return resources.files("astrid").joinpath(*relative.split("/")).read_text(
        encoding="utf-8"
    )


def yaml_section(text, field):
    match = re.search(rf"(?m)^\s*{re.escape(field)}:\s*$", text)
    if match is None:
        raise AssertionError(f"missing manifest section: {field}")
    remainder = text[match.end():]
    next_field = re.search(r"(?m)^[a-z_]+:\s*", remainder)
    return remainder if next_field is None else remainder[:next_field.start()]


def manifest_catalog(relative):
    text = resource_text(relative)
    mounts = dict(
        re.findall(
            r"(?m)^\s{4}([a-z][a-z0-9_]*):\s*([a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)*)\s*$",
            yaml_section(text, "cli_mounts"),
        )
    )
    tables_section = re.search(
        r"(?ms)^[ ]{2}migrations:\s*\n.*?^[ ]{6}tables:\s*\n((?:^[ ]{8}-\s+[^\n]+\n?)+)",
        text,
    )
    if tables_section is None:
        raise AssertionError(f"missing migration tables in {relative}")
    tables = tuple(
        line.strip()[2:].strip()
        for line in tables_section.group(1).splitlines()
        if line.strip().startswith("-")
    )
    return {"mounts": mounts, "tables": tables, "text": text}


def sql_tables(relative):
    return tuple(
        re.findall(r"(?mi)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)", resource_text(relative))
    )


# The wheel's declared YAML dependency is intentionally not installed by the
# shared harness in this lane. Importing any ``astrid.core`` module first
# executes the package initializer, so install the same inert parser shim
# before touching the installed runtime registration. The probe reads the
# canonical v2 pack resources directly above.
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    yaml = types.ModuleType("yaml")
    yaml.YAMLError = Exception
    yaml.SafeLoader = object
    yaml.safe_load = lambda _text: {}
    yaml.load = lambda _text, Loader=None: {}
    yaml.compose = lambda _text, Loader=None: None
    nodes = types.ModuleType("yaml.nodes")
    nodes.MappingNode = type("MappingNode", (), {})
    nodes.SequenceNode = type("SequenceNode", (), {})
    constructor = types.ModuleType("yaml.constructor")
    constructor.ConstructorError = type("ConstructorError", (Exception,), {})
    yaml.nodes = nodes
    yaml.constructor = constructor
    sys.modules["yaml"] = yaml
    sys.modules["yaml.nodes"] = nodes
    sys.modules["yaml.constructor"] = constructor

try:
    import jsonschema  # noqa: F401
except ModuleNotFoundError:
    jsonschema = types.ModuleType("jsonschema")
    sys.modules["jsonschema"] = jsonschema

# domain_product is the installed runtime registration. Canonical v2 pack
# resources are read separately from the installed tree and must agree with it.
from astrid.core.cli import domain_product

expected_families = (
    "projects", "timelines", "media", "tasks", "runs", "serve", "doctor", "backup"
)
runtime_families = tuple(domain_product.PRODUCT_FAMILIES) + (
    "serve", "doctor", "backup"
)
assert set(runtime_families) == set(expected_families), runtime_families
assert set(domain_product.FAMILY_PARSER_MODULES) == {
    "projects", "timelines", "media", "tasks", "runs", "shots", "references"
}
pack_ids = (
    "blender", "comfy_wrap", "editorial", "fal", "foley", "generation",
    "iteration", "media", "moirae", "references", "reigh", "rendering",
    "runaway", "runpod", "shots", "stream_content", "timeline", "training",
    "understanding", "vibecomfy", "video_editing", "youtube",
)
manifest_files = {pack: f"packs/{pack}/pack.yaml" for pack in pack_ids}
manifest_catalogs = {}
for pack, path in manifest_files.items():
    text = resource_text(path)
    assert re.search(r"(?m)^schema_version:\s*2\s*$", text), path
    assert re.search(rf"(?m)^id:\s*{re.escape(pack)}\s*$", text), path
    assert "  path: skill/SKILL.md" in text, path
    assert resource_text(f"packs/{pack}/skill/SKILL.md").lstrip().startswith("---\n")
    manifest_catalogs[pack] = manifest_catalog(path) if pack in {
        "timeline", "shots", "references"
    } else {"mounts": {}, "tables": ()}

pack_root = resources.files("astrid").joinpath("packs")
assert "core" not in {item.name for item in pack_root.iterdir()}
for pack in pack_ids:
    names = {item.name for item in pack_root.joinpath(pack).iterdir()}
    assert not names.intersection({"pack.yml", "pack.json", "schema-pack.yaml"}), pack
assert pack_root.joinpath("_core", "skill", "SKILL.md").is_file()

manifest_mounts = {
    family: mount
    for catalog in manifest_catalogs.values()
    for family, mount in catalog["mounts"].items()
}
expected_mounts = {
    family: " ".join(path)
    for family, path in domain_product.REQUIRED_MANIFEST_MOUNTS.items()
}
assert manifest_mounts == expected_mounts, (manifest_mounts, expected_mounts)

from astrid.core.migrations.runner import (
    MigrationTooNewError,
    apply_pending_migrations,
    probe_database,
)
from astrid.core.schema_packs.registry import RegisteredMigration


core_sql = "core/migrations/sql/core/0001_initial.sql"
core_tables = set(sql_tables(core_sql))
assert len(core_tables) == 14, sorted(core_tables)
pack_specs = {
    "timeline": "migrations/0001_initial.sql",
    "shots": "migrations/0001_initial.sql",
    "references": "migrations/0001_initial.sql",
}
pack_resource_paths = {
    pack: f"packs/{pack}/{path}"
    for pack, path in pack_specs.items()
}
pack_catalog = {
    pack: {
        "manifest_tables": sorted(manifest_catalogs[pack]["tables"]),
        "sql_tables": sorted(sql_tables(path)),
    }
    for pack, path in pack_resource_paths.items()
}
for pack, catalog in pack_catalog.items():
    assert catalog["manifest_tables"] == catalog["sql_tables"], (pack, catalog)


import astrid

package_root = Path(astrid.__file__).resolve().parent


def database_resource(pack: str, relative: str) -> SimpleNamespace:
    owner_root = package_root if pack == "core" else package_root / f"packs/{pack}"
    resolved = owner_root / relative
    payload = resolved.read_bytes()
    return SimpleNamespace(
        path=relative,
        root=owner_root,
        resolved=resolved,
        kind="database.migration",
        file_kind="file",
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )

class InstalledRegistry:
    def __init__(self):
        self.packs = {
            "core": SimpleNamespace(depends_on=()),
            **{
                pack: SimpleNamespace(
                    depends_on=(SimpleNamespace(pack="core"),)
                )
                for pack in pack_specs
            },
        }
        specs = [("core", "initial", "core/migrations/sql/core/0001_initial.sql")]
        specs.extend(
            (pack, "initial", path) for pack, path in pack_specs.items()
        )
        self.migrations = tuple(
            RegisteredMigration(
                pack=pack,
                version=1,
                name=name,
                path=path,
                tables=tuple(
                    sorted(
                        core_tables
                        if pack == "core"
                        else manifest_catalogs[pack]["tables"]
                    )
                ),
                owner_root=(
                    package_root
                    if pack == "core"
                    else package_root / f"packs/{pack}"
                ),
                resource=database_resource(pack, path),
            )
            for pack, name, path in specs
        )

    def migration(self, pack, version):
        return next(
            (
                migration
                for migration in self.migrations
                if migration.pack == pack and migration.version == version
            ),
            None,
        )


registry = InstalledRegistry()
database = Path(os.environ["ASTRID_PROJECTS_ROOT"]) / "installed-contract.sqlite3"
database.parent.mkdir(parents=True, exist_ok=True)
for existing in (database, database.with_name(database.name + "-wal"), database.with_name(database.name + "-shm")):
    existing.unlink(missing_ok=True)
connection = sqlite3.connect(str(database), isolation_level=None)
try:
    applied = apply_pending_migrations(
        connection, registry, probe_database(database, registry)
    )
finally:
    connection.close()

connection = sqlite3.connect(str(database))
try:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    migration_rows = {
        (row[0], row[1])
        for row in connection.execute(
            "SELECT pack, version FROM schema_migrations ORDER BY pack, version"
        )
    }
finally:
    connection.close()

expected_tables = core_tables | {
    table
    for catalog in pack_catalog.values()
    for table in catalog["manifest_tables"]
}
assert tables == expected_tables, sorted(tables ^ expected_tables)
assert migration_rows == {("core", 1), ("timeline", 1), ("shots", 1), ("references", 1)}
assert {(row.pack, row.version) for row in applied} == migration_rows


def too_new_evidence(pack):
    path = database.parent / f"too-new-{pack}.sqlite3"
    for existing in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        existing.unlink(missing_ok=True)
    connection = sqlite3.connect(str(path), isolation_level=None)
    try:
        connection.execute(
            "CREATE TABLE schema_migrations (pack TEXT, version INTEGER, name TEXT, checksum TEXT, applied_at TEXT)"
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, 99, 'future', 'future', 'future')",
            (pack,),
        )
    finally:
        connection.close()
    before = digest(path)
    try:
        probe_database(path, registry)
    except MigrationTooNewError as error:
        message = str(error)
    else:
        raise AssertionError(f"too-new {pack} schema was accepted")
    after = digest(path)
    assert before == after, (pack, before, after)
    return {"before": before, "after": after, "message": message}


too_new = {pack: too_new_evidence(pack) for pack in ("core", "timeline")}
artifact_digest = os.environ["ASTRID_ARTIFACT_SHA256"]
assert len(artifact_digest) == 64
print(json.dumps({
    "schema": "astrid.m8.installed_contract.v1",
    "artifact_sha256": artifact_digest,
    "families": list(expected_families),
    "manifest_mounts": manifest_mounts,
    "pack_catalog": pack_catalog,
    "kernel_table_count": len(core_tables),
    "database_tables": sorted(tables),
    "migration_rows": sorted([list(row) for row in migration_rows]),
    "too_new": too_new,
}, sort_keys=True))
'''


def test_installed_contract_uses_manifest_runtime_and_migration_evidence(
    installed_harness: InstalledArtifactHarness,
) -> None:
    record = installed_harness.run_lane(
        "installed-contract",
        ["-c", _CONTRACT_PROBE],
        env={"ASTRID_ARTIFACT_SHA256": installed_harness.artifact_digest},
        check=True,
    )
    payload = json.loads(record.stdout)

    assert payload["schema"] == "astrid.m8.installed_contract.v1"
    assert payload["artifact_sha256"] == installed_harness.artifact_digest
    assert payload["families"] == [
        "projects", "timelines", "media", "tasks", "runs", "serve", "doctor", "backup"
    ]
    assert payload["manifest_mounts"] == {
        "timelines": "timelines",
        "shots": "timelines shots",
        "references": "media references",
    }
    assert payload["kernel_table_count"] == 14
    assert {tuple(row) for row in payload["migration_rows"]} == {
        ("core", 1),
        ("timeline", 1),
        ("shots", 1),
        ("references", 1),
    }
    for evidence in payload["too_new"].values():
        assert evidence["before"] == evidence["after"]
        assert "too new" in evidence["message"]

    lane = record.as_dict()
    assert lane["stdout"]
    assert lane["output"] == lane["stdout"] + lane["stderr"]
    assert lane["wheel_sha256"] == installed_harness.artifact_digest
    assert lane["status"] == "passed"


__all__ = ["test_installed_contract_uses_manifest_runtime_and_migration_evidence"]
