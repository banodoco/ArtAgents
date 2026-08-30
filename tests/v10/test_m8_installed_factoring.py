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
from scripts.reshape.installed_artifact import InstalledArtifactHarness, build_once

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def packaged_harness(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[InstalledArtifactHarness]:
    """Build exactly one wheel for every reduced-composition check."""
    workspace = tmp_path_factory.mktemp("m8-packaged-factoring")
    # The factoring lane executes the complete packaged kernel suite, which
    # imports the declared runtime manifest parsers (PyYAML/jsonschema).  A
    # bare ``--no-deps`` artifact is useful for the identity-only contract,
    # but cannot prove this lane: install the hashed runtime lock into the
    # same isolated venv so a host/user-site package can never satisfy it.
    harness = build_once(
        REPO_ROOT,
        workspace=workspace,
        install_dependencies=True,
    )
    try:
        yield harness
    finally:
        harness.close()


@pytest.fixture(scope="module")
def packaged_wheel(packaged_harness: InstalledArtifactHarness) -> Path:
    return packaged_harness.artifact.path


@pytest.mark.timeout(600)
def test_each_pack_can_be_removed_from_one_wheel_without_kernel_drift(
    packaged_wheel: Path,
    packaged_harness: InstalledArtifactHarness,
    tmp_path: Path,
) -> None:
    """Prove all reduced packaged compositions and their complete kernel lane."""
    result = check_artifact_factoring(
        wheel=packaged_wheel,
        # Factoring launches Python outside the source checkout.  Reuse the
        # dependency-bearing interpreter built for this artifact so PyYAML and
        # jsonschema come from the declared lock, not from the host process.
        python=str(packaged_harness.python_executable),
        base_dir=tmp_path,
        kernel_timeout=180,
        catalog_timeout=30,
    )

    failures = [
        f"{item.removed_pack}: rc={item.kernel_returncode}\n"
        f"{item.kernel_output}\n{item.kernel_error}"
        for item in result.removals
        if not item.ok
    ]
    assert result.ok, "\n\n".join(failures)
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
    assert PACK_VOCABULARY["runaway"]["stream_types"] == ("runaway.transition_set",)
    assert PACK_VOCABULARY["runaway"]["event_kinds"] == ("runaway.created",)
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
