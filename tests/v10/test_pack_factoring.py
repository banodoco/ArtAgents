"""Canonical bundled database projection and factoring checks.

These tests prove that the default-enabled bundled database packs are owned
by the canonical catalog and that the independent kernel-inventory sketch
continues to match ``CORE_MIGRATIONS``. They intentionally do not model
pack removal, an explicit registration tuple, or any deleted legacy authority;
beta composition has no enable/disable lifecycle.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.migrations.catalog import CORE_TABLES
from astrid.packs import compose_standard_pack_database
from scripts.reshape import check_pack_factoring
from scripts.reshape.check_pack_factoring import DOMAIN_PACKS, KERNEL_LANE, REPO_ROOT

def test_canonical_catalog_projects_database_packs() -> None:
    """The bundled catalog owns every database declaration and default."""
    composition = compose_standard_pack_database()
    database_entries = {
        entry.id: entry
        for entry in composition.catalog.entries
        if entry.database is not None
    }
    assert set(database_entries) == {*DOMAIN_PACKS, "runaway"}
    assert {
        entry.id
        for entry in database_entries.values()
        if entry.database.default_enabled
    } == set(DOMAIN_PACKS)
    assert set(composition.registry.packs) == {"core", *DOMAIN_PACKS}


def test_real_repository_tree_is_never_mutated() -> None:
    """The canonical pack directories stay present and manifest-backed."""
    for pack in DOMAIN_PACKS:
        pack_root = REPO_ROOT / "astrid" / "packs" / pack
        assert pack_root.is_dir(), pack
        assert (pack_root / "pack.yaml").is_file(), pack


# ---------------------------------------------------------------------------
def test_kernel_lane_is_explicit_and_complete() -> None:
    """The lane is explicit and independent of bundled pack authorities."""
    assert isinstance(KERNEL_LANE, tuple) and len(KERNEL_LANE) >= 10
    for rel in KERNEL_LANE:
        assert (REPO_ROOT / rel).is_file(), f"lane file missing: {rel}"
    # The lane is fully enumerated in the check module, never discovered:
    # no glob-based pack discovery anywhere in the check.
    lane_source = Path(check_pack_factoring.__file__).read_text(encoding="utf-8")
    assert "glob(" not in lane_source
    for rel in KERNEL_LANE:
        assert rel in lane_source, rel


# ---------------------------------------------------------------------------
# The software-engineering-agent sketch reuses exactly CORE_MIGRATIONS (T17)
# ---------------------------------------------------------------------------


def test_sketch_reuses_exact_core_migrations_kernel_inventory() -> None:
    """The SWE-agent sketch's declared kernel inventory equals exactly the
    audited ``CORE_MIGRATIONS`` tables (14), and the sketch names its own
    in-tree packs (workspace, changeset, review)."""
    summary = check_pack_factoring.verify_sketch_kernel_inventory()
    assert summary.startswith("sketch-ok")
    assert f"kernel_tables={len(CORE_TABLES)}" in summary
    assert check_pack_factoring.CORE_KERNEL_TABLES == CORE_TABLES
    for pack in ("workspace", "changeset", "review"):
        assert pack in summary
    # The sketch's packs stay disjoint from the Astrid standard packs.
    assert set(check_pack_factoring.SKETCH_PACKS).isdisjoint(DOMAIN_PACKS)


def test_sketch_cannot_silently_add_a_kernel_table(tmp_path) -> None:
    """Negative control: a sketch inventory that adds any table fails against
    CORE_MIGRATIONS before any pack-level check, so the sketch cannot
    silently grow the kernel (e.g. with a pack-shaped table)."""
    real = (REPO_ROOT / check_pack_factoring.SKETCH_DOC).read_text(
        encoding="utf-8"
    )
    closing = "media, media_locations, media_relations\n```"
    assert closing in real
    inflated = real.replace(
        closing, "media, media_locations, media_relations, kernel_patches\n```"
    )
    sketch_dir = tmp_path / "docs" / "architecture"
    sketch_dir.mkdir(parents=True)
    (sketch_dir / "software-engineering-pack-sketch.md").write_text(
        inflated, encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="sketch adds kernel table"):
        check_pack_factoring.verify_sketch_kernel_inventory(repo_root=tmp_path)


def test_sketch_cannot_omit_a_core_migrations_kernel_table(tmp_path) -> None:
    """Negative control: dropping a kernel table from the sketch's inventory
    also fails, so the sketch cannot drift from the audited kernel."""
    real = (REPO_ROOT / check_pack_factoring.SKETCH_DOC).read_text(
        encoding="utf-8"
    )
    first_line = (
        "schema_migrations, projects, event_streams, events, "
        "command_receipts,\n"
    )
    assert first_line in real
    deflated = real.replace(
        first_line, "projects, event_streams, events, command_receipts,\n", 1
    )
    sketch_dir = tmp_path / "docs" / "architecture"
    sketch_dir.mkdir(parents=True)
    (sketch_dir / "software-engineering-pack-sketch.md").write_text(
        deflated, encoding="utf-8"
    )
    with pytest.raises(AssertionError, match="sketch omits kernel table"):
        check_pack_factoring.verify_sketch_kernel_inventory(repo_root=tmp_path)


def test_sketch_remains_a_source_composition_not_plugin_infrastructure() -> None:
    """The sketch and its check stay a read-only source-composition proof:
    no loader, no discovery, no install/uninstall, and no new kernel
    primitive implied by the document or the check module."""
    doc = (REPO_ROOT / check_pack_factoring.SKETCH_DOC).read_text(
        encoding="utf-8"
    )
    lowered = doc.lower()
    assert "source composition" in lowered
    assert "no dynamic loader" in lowered
    for forbidden in ("importlib", "pkgutil", "entry_points", "pip install"):
        assert forbidden not in lowered, forbidden
    check_source = Path(check_pack_factoring.__file__).read_text(encoding="utf-8")
    for forbidden in ("importlib", "pkgutil", "glob("):
        assert forbidden not in check_source, forbidden