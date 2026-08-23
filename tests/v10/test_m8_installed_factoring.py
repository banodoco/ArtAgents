"""Packaged-wheel factorability checks for the m8 GA gate.

Each case starts from one wheel, makes a throwaway artifact root, removes one
standard schema pack, patches the explicit standard composition, and runs the
complete fixed kernel lane against that root.  The checks also exercise the
reduced registry, fresh database, foreign-key ownership, and shared-writer
boundaries before the lane runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from scripts.reshape.check_pack_factoring import (
    ALL_PACK_TABLES,
    CORE_KERNEL_TABLES,
    DOMAIN_PACKS,
    KERNEL_LANE,
    PACK_TABLES,
    PACK_VOCABULARY,
    check_artifact_factoring,
    extract_sketch_kernel_inventory,
    unpack_wheel,
    verify_sketch_kernel_inventory,
)
from scripts.reshape.installed_artifact import build_once

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def packaged_wheel(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    """Build exactly one wheel for every reduced-composition check."""
    workspace = tmp_path_factory.mktemp("m8-packaged-factoring")
    harness = build_once(REPO_ROOT, workspace=workspace)
    try:
        yield harness.artifact.path
    finally:
        harness.close()


def test_each_pack_can_be_removed_from_one_wheel_without_kernel_drift(
    packaged_wheel: Path,
    tmp_path: Path,
) -> None:
    """Prove all reduced packaged compositions and their complete kernel lane."""
    result = check_artifact_factoring(
        wheel=packaged_wheel,
        base_dir=tmp_path,
        kernel_timeout=90,
        catalog_timeout=30,
    )

    assert result.ok
    assert result.sketch_summary == (
        "sketch-ok kernel_tables=14 packs=['changeset', 'review', 'workspace']"
    )
    assert tuple(item.removed_pack for item in result.removals) == DOMAIN_PACKS
    for item in result.removals:
        assert item.kernel_returncode == 0, (
            f"kernel lane failed after removing {item.removed_pack}\n"
            f"{item.kernel_output}\n{item.kernel_error}"
        )
        assert '"removed_pack": "' + item.removed_pack + '"' in item.catalog_output
        assert '"writer": "one-shared-writer"' in item.catalog_output
        assert '"foreign_keys":' in item.catalog_output


def test_packaged_factoring_inputs_are_explicit_and_disjoint() -> None:
    """Lock the four removal inputs and the full, non-discovered kernel lane."""
    assert DOMAIN_PACKS == ("timeline", "shots", "references", "runaway")
    assert set(PACK_TABLES) == set(DOMAIN_PACKS)
    assert set(PACK_VOCABULARY) == set(DOMAIN_PACKS)
    assert len(KERNEL_LANE) == 15
    assert set(PACK_TABLES["timeline"]).isdisjoint(CORE_KERNEL_TABLES)
    assert ALL_PACK_TABLES.isdisjoint(CORE_KERNEL_TABLES)
    assert not set(KERNEL_LANE) & {
        "tests/v10/test_registry.py",
        "tests/v10/test_catalog_migrations.py",
    }


def test_wheel_unpacking_is_confined_to_the_artifact_root(
    packaged_wheel: Path,
    tmp_path: Path,
) -> None:
    """A wheel member cannot escape the temporary artifact root."""
    root = unpack_wheel(packaged_wheel, tmp_path / "unpacked")
    assert root == (tmp_path / "unpacked").resolve()
    assert (root / "astrid" / "__init__.py").is_file()
    assert not (root.parent / "astrid").exists()


def test_sketch_inventory_is_the_unchanged_kernel() -> None:
    """The normative sketch remains exactly the 14-table core composition."""
    assert extract_sketch_kernel_inventory(
        (REPO_ROOT / "docs/architecture/software-engineering-pack-sketch.md").read_text(
            encoding="utf-8"
        )
    ) == CORE_KERNEL_TABLES
    summary = verify_sketch_kernel_inventory()
    assert summary.startswith("sketch-ok kernel_tables=14")
    assert "workspace" in summary
    assert "changeset" in summary
    assert "review" in summary
