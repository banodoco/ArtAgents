"""Rollout + rollback drill (Batch B7, [XHARD] evidence).

Named drill: **N+1 accepted ⇒ roll back to N** — the highest-blast-radius
exceptional path gets full mechanical evidence. Silent swaps are
structurally impossible: swap requires five-gate evidence AND a drained
WGP queue; rollback is explicit, never automatic fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.integrations.reigh.wgp_build import (
    BuildManifest,
    BuildManifestError,
    BuildManifestStore,
    initial_manifest,
    rollout_swap,
)

FULL_GATES = {1: True, 2: True, 3: True, 4: True, 5: True}


def _manifest(sha_suffix: str) -> BuildManifest:
    base = initial_manifest()
    return BuildManifest(
        wan2gp_sha="a" * 32 + sha_suffix,  # 40-hex shape, distinct builds
        upstream_base=base.upstream_base,
        patchset_hash=base.patchset_hash,
        worker_contract_version=base.worker_contract_version,
    )


def test_rollback_drill_n_plus_one_accepted_then_back_to_n(tmp_path: Path) -> None:
    """THE named drill: accept build N+1, then explicitly restore N."""
    store = BuildManifestStore(tmp_path)
    build_n = _manifest("0" * 8)
    store.install(build_n)
    assert store.require_current().digest() == build_n.digest()

    # --- upgrade: gates pass, queue drained → N+1 accepted -------------
    drained = rollout_swap(
        store,
        _manifest("1" * 8),
        drain=lambda: [],
        gates_evidence=FULL_GATES,
    )
    assert drained is not None and drained.digest() == build_n.digest()
    current = store.require_current()
    assert current.wan2gp_sha == "a" * 32 + "1" * 8
    assert store.prior().digest() == build_n.digest()

    # --- the drill: explicit rollback to N ------------------------------
    restored = store.rollback_to_prior()
    assert restored.digest() == build_n.digest()
    assert store.require_current().digest() == build_n.digest()

    # Retention survives the drill both ways: N+1 is now the prior.
    assert store.prior().wan2gp_sha == "a" * 32 + "1" * 8
    restored_again = store.rollback_to_prior()
    assert restored_again.wan2gp_sha == "a" * 32 + "1" * 8
    assert store.require_current().wan2gp_sha == "a" * 32 + "1" * 8


def test_swap_refuses_while_wgp_work_is_in_flight(tmp_path: Path) -> None:
    store = BuildManifestStore(tmp_path)
    store.install(_manifest("0" * 8))
    with pytest.raises(BuildManifestError, match="work is in flight"):
        rollout_swap(
            store,
            _manifest("1" * 8),
            drain=lambda: ["task-abc"],
            gates_evidence=FULL_GATES,
        )
    assert store.require_current().wan2gp_sha == "a" * 32 + "0" * 8


def test_swap_refuses_without_complete_gate_evidence(tmp_path: Path) -> None:
    store = BuildManifestStore(tmp_path)
    store.install(_manifest("0" * 8))
    with pytest.raises(BuildManifestError, match="gate evidence"):
        rollout_swap(
            store,
            _manifest("1" * 8),
            drain=lambda: [],
            gates_evidence={1: True, 2: True, 3: True, 4: True},  # gate 5 missing
        )


def test_identical_manifest_swap_refuses(tmp_path: Path) -> None:
    """A no-op 'upgrade' IS the silent-swap shape; it refuses typed."""
    store = BuildManifestStore(tmp_path)
    manifest = _manifest("0" * 8)
    store.install(manifest)
    with pytest.raises(BuildManifestError, match="identical build manifest"):
        store.install(manifest)


def test_rollback_without_retained_prior_refuses_typed(tmp_path: Path) -> None:
    store = BuildManifestStore(tmp_path)
    with pytest.raises(BuildManifestError, match="no prior build retained"):
        store.rollback_to_prior()


def test_current_and_prior_files_are_canonical_json_on_disk(
    tmp_path: Path,
) -> None:
    """The manifest authority is inspectable: canonical bytes at rest."""
    store = BuildManifestStore(tmp_path)
    store.install(initial_manifest())
    raw = (tmp_path / "build_manifest.json").read_text(encoding="utf-8")
    assert raw == json.dumps(json.loads(raw), indent=2, sort_keys=True) + "\n"
    assert store.current() is not None
    assert store.current_path.name == "build_manifest.json"


def test_malformed_manifest_refuses_typed(tmp_path: Path) -> None:
    bad = tmp_path / "build_manifest.json"
    bad.write_text(json.dumps({"wan2gp_sha": "short"}), encoding="utf-8")
    store = BuildManifestStore(tmp_path)
    with pytest.raises(BuildManifestError, match="malformed build manifest"):
        store.current()


def test_atomic_swap_leaves_no_temp_litter(tmp_path: Path) -> None:
    store = BuildManifestStore(tmp_path)
    store.install(_manifest("0" * 8))
    store.install(_manifest("1" * 8))
    leftovers = [
        p.name for p in tmp_path.iterdir() if p.name.startswith(".swap-")
    ]
    assert leftovers == []
