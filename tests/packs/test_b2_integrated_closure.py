"""Focused B2 closure checks for the canonical bundled-pack candidate.

These tests build an explicit temporary catalog root from the 22 converted
product directories and inject a tiny kernel migration solely to satisfy the
B1 catalog dependency contract. No production loader or consumer is exercised
here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from astrid.core.model_catalog.taxonomy import GenerationTaxonomyRegistry
from astrid.core.pack._common import find_component_manifest
from astrid.core.pack.canonical import BundledCatalog, validate_canonical_pack

ROOT = Path(__file__).resolve().parents[2]
PACKS_ROOT = ROOT / "astrid" / "packs"
PRODUCT_IDS = (
    "blender",
    "comfy_wrap",
    "editorial",
    "fal",
    "foley",
    "generation",
    "iteration",
    "media",
    "moirae",
    "references",
    "reigh",
    "rendering",
    "runaway",
    "runpod",
    "shots",
    "stream_content",
    "timeline",
    "training",
    "understanding",
    "vibecomfy",
    "video_editing",
    "youtube",
)
DATABASE_TABLES = {
    "timeline": ("timelines",),
    "shots": ("shots", "shot_items"),
    "references": ("project_references", "media_references", "reference_links"),
    "runaway": ("runaway_transitions",),
}
EXPECTED_STANDALONE_RESOURCES = {
    "blender": {
        "render_core.py",
        "mesh_fetch.py",
        "renders/wink_turn.py",
        "server/blender_render_server.py",
        "server/blender-render-api.service",
    }
}


def _component_counts(entry) -> dict[str, int]:
    counts = {"executors": 0, "orchestrators": 0, "elements": 0}
    for kind, plural in (("executor", "executors"), ("orchestrator", "orchestrators")):
        relative = entry.definition.content.get(plural)
        if relative is None:
            continue
        counts[plural] = sum(
            1
            for child in (entry.root / relative).iterdir()
            if child.is_dir() and find_component_manifest(child, kind) is not None
        )

    relative = entry.definition.content.get("elements")
    if relative is not None:
        for kind_root in (entry.root / relative).iterdir():
            if not kind_root.is_dir():
                continue
            counts["elements"] += sum(
                1
                for child in kind_root.iterdir()
                if child.is_dir() and find_component_manifest(child, "element") is not None
            )
    return counts


def _explicit_catalog_root(tmp_path: Path) -> Path:
    root = tmp_path / "packs"
    root.mkdir()
    for pack_id in PRODUCT_IDS:
        shutil.copytree(
            PACKS_ROOT / pack_id,
            root / pack_id,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    # B3 owns projecting the irreducible kernel.  This fixture-only declaration
    # lets B2 exercise the complete explicit-root catalog without changing it.
    core = root / "core"
    migrations = core / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "0001_initial.sql").write_text(
        "CREATE TABLE core_probe (id INTEGER PRIMARY KEY);\n", encoding="utf-8"
    )
    (core / "pack.yaml").write_text(
        """schema_version: 2
id: core
name: Core
version: 1.0.0
database:
  default_enabled: true
  depends_on: []
  migrations:
    - version: 1
      name: initial
      path: migrations/0001_initial.sql
      tables: [core_probe]
  stream_types: []
  event_kinds: []
  command_kinds: []
  repositories: []
  conformance: []
  cli_mounts: {}
  bridge_mounts: []
""",
        encoding="utf-8",
    )
    return root


def test_all_retained_manifests_and_skills_are_strict_v2(tmp_path: Path) -> None:
    assert not (PACKS_ROOT / "builtin").exists()
    retained_dirs = tuple(
        sorted(
            child.name
            for child in PACKS_ROOT.iterdir()
            if child.is_dir()
            and not child.name.startswith(".")
            and child.name not in {"_core", "__pycache__"}
        )
    )
    assert retained_dirs == PRODUCT_IDS
    manifest_paths = sorted(PACKS_ROOT.glob("*/pack.yaml"))
    assert tuple(path.parent.name for path in manifest_paths) == PRODUCT_IDS

    for manifest_path in manifest_paths:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2
        assert data["id"] == manifest_path.parent.name
        assert data.get("aliases", []) == []
        assert data["documentation"] == {"kind": "skill", "path": "skill/SKILL.md"}
        assert (manifest_path.parent / "skill/SKILL.md").is_file()

        isolated = tmp_path / manifest_path.parent.name
        shutil.copytree(
            manifest_path.parent,
            isolated,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        entry = validate_canonical_pack(isolated)
        assert entry.id == manifest_path.parent.name
        assert entry.documentation is not None
        assert entry.documentation.path == "skill/SKILL.md"


def test_all_pack_skills_and_core_census_are_structured_and_routed() -> None:
    routed: list[str] = []
    census = (PACKS_ROOT / "_core" / "skill" / "SKILL.md").read_text(encoding="utf-8")
    in_census = False
    for line in census.splitlines():
        if line.startswith("<!-- BEGIN PACK CENSUS"):
            in_census = True
            continue
        if line.startswith("<!-- END PACK CENSUS"):
            break
        if in_census and line.startswith("| `"):
            pack_id = line.split("`", 2)[1]
            routed.append(pack_id)
            assert f"../../{pack_id}/skill/SKILL.md" in line
    assert tuple(routed) == PRODUCT_IDS
    assert not (PACKS_ROOT / "_core" / "pack.yaml").exists()

    for pack_id in PRODUCT_IDS:
        text = (PACKS_ROOT / pack_id / "skill" / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n")
        _, frontmatter, body = text.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter)
        assert metadata["name"] == pack_id
        assert isinstance(metadata["description"], str) and metadata["description"].strip()
        assert body.lstrip().startswith("# ")


def test_explicit_catalog_preserves_typed_counts_extensions_and_resources(tmp_path: Path) -> None:
    catalog = BundledCatalog.from_root(_explicit_catalog_root(tmp_path))
    entries = {entry.id: entry for entry in catalog.entries}
    assert set(entries) == {"core", *PRODUCT_IDS}
    assert len([entry for entry in catalog.entries if entry.id in PRODUCT_IDS]) == 22

    totals = {"executors": 0, "orchestrators": 0, "elements": 0}
    for pack_id in PRODUCT_IDS:
        for key, count in _component_counts(entries[pack_id]).items():
            totals[key] += count
    assert totals == {"executors": 64, "orchestrators": 12, "elements": 10}

    rendering = entries["rendering"]
    rendering_paths = {
        handle.path
        for handle in rendering.resource_handles
        if handle.kind.startswith("extensions.rendering:")
    }
    assert len(rendering_paths) == 8
    assert all(
        handle.resolved.is_relative_to(handle.root) and handle.resolved.is_file()
        for handle in rendering.resource_handles
        if handle.kind.startswith("extensions.rendering:")
    )

    taxonomy = GenerationTaxonomyRegistry()
    assert len(taxonomy.feature_ids()) == 29
    assert len(taxonomy.mode_descriptors()) == 14
    assert len(taxonomy.backend_descriptors()) == 4

    standalone = {
        pack_id: {resource.path for resource in entries[pack_id].definition.resources}
        for pack_id in PRODUCT_IDS
        if entries[pack_id].definition.resources
    }
    assert standalone == EXPECTED_STANDALONE_RESOURCES

    for pack_id in PRODUCT_IDS:
        handles = entries[pack_id].resource_handles
        assert all(handle.resolved.is_relative_to(entries[pack_id].root) for handle in handles)
        by_kind: dict[str, set[str]] = {}
        for handle in handles:
            if handle.kind.startswith("content:"):
                group = "content"
            elif handle.kind.startswith("extensions.rendering:"):
                group = "extension"
            elif handle.kind == "database.migration":
                group = "migration"
            else:
                continue
            by_kind.setdefault(group, set()).add(handle.path)
        groups = tuple(by_kind.values())
        assert all(left.isdisjoint(right) for index, left in enumerate(groups) for right in groups[index + 1 :])


def test_database_declarations_and_defaults_are_preserved(tmp_path: Path) -> None:
    catalog = BundledCatalog.from_root(_explicit_catalog_root(tmp_path))
    entries = {entry.id: entry for entry in catalog.entries}
    assert {projection.pack_id for projection in catalog.databases} == {"core", *DATABASE_TABLES}

    expected_defaults = {"timeline": True, "shots": True, "references": True, "runaway": False}
    for pack_id, tables in DATABASE_TABLES.items():
        database = entries[pack_id].database
        assert database is not None
        assert database.default_enabled is expected_defaults[pack_id]
        assert database.depends_on[0].pack == "core"
        assert database.depends_on[0].min_migration == 1
        assert database.migration_head == 1
        assert tuple(database.migrations[0].tables) == tuple(sorted(tables))
        assert database.migrations[0].path == "migrations/0001_initial.sql"
        assert database.migrations[0].name == "initial"

    assert dict(entries["timeline"].database.cli_mounts) == {"timelines": "timelines"}
    assert dict(entries["shots"].database.cli_mounts) == {"shots": "timelines shots"}
    assert dict(entries["references"].database.cli_mounts) == {"references": "media references"}
    assert entries["runaway"].database.cli_mounts == {}
    assert entries["timeline"].database.bridge_mounts == ("timelines",)
    assert entries["references"].database.repositories == ("ReferenceRepository",)
    assert entries["runaway"].database.command_kinds == ("runaway.create",)

def test_v2_database_projection_matches_canonical_manifests(tmp_path: Path) -> None:
    """The database projection is a direct view of canonical ``pack.yaml``."""
    catalog = BundledCatalog.from_root(_explicit_catalog_root(tmp_path))
    entries = {entry.id: entry for entry in catalog.entries}
    tuple_fields = (
        "stream_types",
        "event_kinds",
        "command_kinds",
        "repositories",
        "conformance",
        "bridge_mounts",
    )
    for pack_id in DATABASE_TABLES:
        database = entries[pack_id].database
        assert database is not None
        manifest = yaml.safe_load(
            (PACKS_ROOT / pack_id / "pack.yaml").read_text(encoding="utf-8")
        )
        declared = manifest["database"]
        for field in tuple_fields:
            assert tuple(sorted(getattr(database, field))) == tuple(
                sorted(declared[field])
            )
        assert dict(database.cli_mounts) == declared["cli_mounts"]
        migration = database.migrations[0]
        declared_migration = declared["migrations"][0]
        assert tuple(sorted(migration.tables)) == tuple(
            sorted(declared_migration["tables"])
        )
        assert migration.version == declared_migration["version"]
        assert migration.name == declared_migration["name"]
        assert migration.path == declared_migration["path"]
        assert database.depends_on[0].pack == declared["depends_on"][0]["pack"]
        assert (
            database.depends_on[0].min_migration
            == declared["depends_on"][0]["min_migration"]
        )
