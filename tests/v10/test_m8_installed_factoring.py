"""Packaged-wheel factorability checks for the m8 GA gate.

Each case starts from one wheel, makes a throwaway artifact root, removes one
standard schema pack, patches the explicit standard composition, and runs the
complete fixed kernel lane against that root.  The checks also exercise the
reduced registry, fresh database, foreign-key ownership, and shared-writer
boundaries before the lane runs.
"""

from __future__ import annotations

import json
import os
import subprocess
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
    _artifact_environment,
    check_artifact_factoring,
    extract_sketch_kernel_inventory,
    unpack_wheel,
    verify_sketch_kernel_inventory,
)
from scripts.reshape.installed_artifact import (
    PROOF_LOCK,
    InstalledArtifactHarness,
    build_once,
)

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
        dependency_lock=PROOF_LOCK,
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
        # dependency-bearing interpreter built for this artifact so PyYAML,
        # jsonschema, and pytest come from the declared proof lock, not the
        # host process.
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


def test_packaged_factoring_uses_only_locked_dependencies_and_explicit_roots(
    packaged_harness: InstalledArtifactHarness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contaminated host/user path cannot satisfy the packaged lane.

    The factoring helper must leave dependency resolution to the selected
    interpreter's lock-provisioned venv.  In particular, a host
    ``PYTHONPATH`` containing fake ``yaml``/``jsonschema`` modules must not
    appear in the child environment or win imports over the locked packages.
    """
    host_site = tmp_path / "host-site"
    host_site.mkdir()
    (host_site / "yaml.py").write_text("raise AssertionError('host yaml used')\n", encoding="utf-8")
    (host_site / "jsonschema.py").write_text(
        "raise AssertionError('host jsonschema used')\n", encoding="utf-8"
    )
    user_base = tmp_path / "user-base"
    user_site = (
        user_base
        / "lib"
        / f"python{os.sys.version_info.major}.{os.sys.version_info.minor}"
        / "site-packages"
    )
    user_site.mkdir(parents=True)
    (user_site / "yaml.py").write_text("raise AssertionError('user yaml used')\n", encoding="utf-8")
    (user_site / "jsonschema.py").write_text(
        "raise AssertionError('user jsonschema used')\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(host_site))
    monkeypatch.setenv("PYTHONUSERBASE", str(user_base))
    hostile_pythonhome = tmp_path / "hostile-pythonhome"
    # A real PYTHONHOME attack does not need a valid Python installation: an
    # incomplete fake root is enough to make CPython select the wrong prefix
    # and fail while bootstrapping its standard library.
    (hostile_pythonhome / "lib").mkdir(parents=True)
    monkeypatch.setenv("PYTHONHOME", str(hostile_pythonhome))

    artifact_root = tmp_path / "artifact"
    artifact_root.mkdir()
    env = _artifact_environment(artifact_root)
    assert env["PYTHONPATH"] == str(artifact_root.resolve())
    assert "PYTHONHOME" not in env
    assert str(host_site) not in env["PYTHONPATH"]
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PYTHONSAFEPATH"] == "1"

    probe = subprocess.run(
        [
            str(packaged_harness.python_executable),
            "-c",
            (
                "import json, jsonschema, yaml; "
                "import os, sys, sysconfig; "
                "print(json.dumps({'yaml': yaml.__file__, 'jsonschema': jsonschema.__file__, "
                "'prefix': sys.prefix, 'stdlib': sysconfig.get_path('stdlib'), "
                "'os': os.__file__}))"
            ),
        ],
        cwd=artifact_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    origins = json.loads(probe.stdout)
    venv_root = packaged_harness.venv_dir.resolve()
    assert Path(origins["prefix"]).resolve() == venv_root
    assert not Path(origins["stdlib"]).resolve().is_relative_to(hostile_pythonhome)
    assert not Path(origins["os"]).resolve().is_relative_to(hostile_pythonhome)
    for name in ("yaml", "jsonschema"):
        origin = origins[name]
        resolved = Path(origin).resolve()
        assert resolved.is_relative_to(venv_root), resolved
        assert not resolved.is_relative_to(host_site)
        assert not resolved.is_relative_to(user_site)


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
    assert (
        extract_sketch_kernel_inventory(
            (REPO_ROOT / "docs/architecture/software-engineering-pack-sketch.md").read_text(
                encoding="utf-8"
            )
        )
        == CORE_KERNEL_TABLES
    )
    summary = verify_sketch_kernel_inventory()
    assert summary.startswith("sketch-ok kernel_tables=14")
    assert "workspace" in summary
    assert "changeset" in summary
    assert "review" in summary
