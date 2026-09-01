"""Temporary-copy factoring tests (m3 Step 14 / T15_impl, T17).

Proves the deterministic temporary-copy check in
:mod:`scripts.reshape.check_pack_factoring`: each in-tree domain pack
(``timeline``, ``shots``, ``references``) can be removed one at a time from
a temporary source copy **and** from the explicit registration tuple while
the complete enumerated kernel lane stays green and the remaining
manifest-derived catalog is unchanged -- with the real repository tree never
touched and no runtime discovery or uninstall behavior.

Also proves the software-engineering-agent composition sketch (T17): the
sketch's declared kernel inventory is compared against ``CORE_MIGRATIONS``
and cannot silently add (or omit) a kernel table, while the sketch stays a
read-only source-composition proof rather than generic plugin infrastructure.

The heavy removal proof is parametrized over the three packs; each case runs
the real kernel lane once inside the check. The remaining tests are cheap
and assert the surgery is deterministic, the real tree is untouched, the
enumerated lane is complete, unknown packs are rejected, and the sketch
inventory binding is enforced.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from astrid.core.migrations.catalog import CORE_TABLES
from scripts.reshape import check_pack_factoring
from scripts.reshape.check_pack_factoring import (
    ALL_PACK_TABLES,
    DOMAIN_PACKS,
    KERNEL_LANE,
    PACK_TABLES,
    REPO_ROOT,
    _patch_packs_init,
    build_temp_source_copy,
    check_removal,
)

LANE_TIMEOUT = 90
"""Generous per-lane pytest bound; the measured lane wall time is ~32s."""


# ---------------------------------------------------------------------------
# The proof itself: one removal per in-tree domain pack
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("removed_pack", DOMAIN_PACKS)
def test_removing_each_domain_pack_keeps_kernel_lane_and_catalog_green(
    removed_pack: str,
) -> None:
    """Removing timeline/shots/references one at a time from a temporary
    source composition and the explicit registration tuple leaves the
    complete enumerated kernel lane green and the remaining manifest-derived
    catalog verified."""
    result = check_removal(removed_pack, lane_timeout=LANE_TIMEOUT)
    assert result.ok, (
        f"kernel lane failed after removing {removed_pack} "
        f"(exit {result.lane_returncode})\n"
        f"{result.lane_output}\n{result.lane_error}"
    )
    assert "catalog-ok" in result.catalog_output

    # The remaining registration tuple and catalog are derived, not assumed:
    # kernel tables plus every remaining pack's declared tables.
    remaining = tuple(pack for pack in DOMAIN_PACKS if pack != removed_pack)
    remaining_tables = ALL_PACK_TABLES - set(PACK_TABLES[removed_pack])
    expected_count = len(CORE_TABLES) + len(remaining_tables)
    assert f"tables={expected_count}" in result.catalog_output
    assert f"packs={sorted(remaining)}" in result.catalog_output


# ---------------------------------------------------------------------------
# The check is confined to temporary copies and never mutates the real tree
# ---------------------------------------------------------------------------


def test_real_repository_tree_is_never_mutated() -> None:
    """All three pack directories and the explicit registration tuple are
    untouched by the check (no runtime discovery, no uninstall behavior)."""
    import astrid.packs as packs_module

    for pack in DOMAIN_PACKS:
        assert (REPO_ROOT / "astrid" / "packs" / pack).is_dir(), pack
    assert packs_module.STANDARD_SCHEMA_PACKS == DOMAIN_PACKS
    # The three standard packs remain registered explicitly. Optional schema
    # packs may also ship in-tree without joining that composition.
    discovered = sorted(
        path.parent.name
        for path in (REPO_ROOT / "astrid" / "packs").glob("*/schema-pack.yaml")
    )
    assert discovered == sorted((*DOMAIN_PACKS, "runaway"))


def test_temp_copy_removes_source_and_registration_deterministically(
    tmp_path,
) -> None:
    """A shots removal edits only the temporary copy: the pack directory is
    gone, the registration tuple keeps the remaining packs, and the timeline
    bridge imports (needed only when timeline itself is removed) stay."""
    work = build_temp_source_copy("shots", base_dir=tmp_path)
    try:
        assert not (work / "astrid" / "packs" / "shots").exists()
        assert (work / "astrid" / "packs" / "timeline").is_dir()
        assert (work / "astrid" / "packs" / "references").is_dir()
        init_text = (work / "astrid" / "packs" / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert (
            'STANDARD_SCHEMA_PACKS: tuple[str, ...] = ("timeline", "references")'
            in init_text
        )
        # timeline imports survive a shots-only removal.
        assert "from astrid.packs.timeline.repository import TimelineRepository" in init_text
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_timeline_removal_drops_bridge_imports(tmp_path) -> None:
    """Removing timeline also removes its module-level bridge/repository
    imports from the temporary composition so ``import astrid.packs`` keeps
    working without the pack."""
    work = build_temp_source_copy("timeline", base_dir=tmp_path)
    try:
        init_text = (work / "astrid" / "packs" / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert "astrid.packs.timeline" not in init_text
        assert (
            'STANDARD_SCHEMA_PACKS: tuple[str, ...] = ("shots", "references")'
            in init_text
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_patch_requires_the_registration_literal(tmp_path) -> None:
    """The deterministic surgery fails loudly if the expected tuple literal
    is missing instead of silently producing a broken composition."""
    bogus = tmp_path / "__init__.py"
    bogus.write_text(
        "STANDARD_SCHEMA_PACKS = ('timeline',)\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="STANDARD_SCHEMA_PACKS tuple not found"):
        _patch_packs_init(bogus, "timeline")


def test_unknown_pack_is_rejected_before_any_copy(tmp_path) -> None:
    """The enumeration is explicit: an unknown pack is rejected up front and
    no temporary composition is built."""
    with pytest.raises(ValueError, match="unknown domain pack"):
        check_removal("mystery", base_dir=tmp_path)


# ---------------------------------------------------------------------------
# Lane completeness and explicit enumeration
# ---------------------------------------------------------------------------


def test_kernel_lane_is_explicit_and_complete() -> None:
    """The enumerated lane is a fixed tuple of existing kernel test files
    that import no domain schema pack at module level and hold under any
    subset of the three packs (see the check's module docstring)."""
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
