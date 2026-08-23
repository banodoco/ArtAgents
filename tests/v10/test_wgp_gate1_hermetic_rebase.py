"""Gate ① — hermetic rebase + patch applicability (Batch B7).

Named evidence:

- The vendored Wan2GP tree is exactly at the pinned SHA with a clean
  working tree (submodule bump reproducible).
- Every declared patch anchor matches the pinned bytes exactly once —
  patch drift rejects mechanically, never report-only.
- Patch application is lock-scoped and restores the module surface
  exactly (including previously-absent attributes).
- ``wgp_config.json`` key schema reconstructs from the pinned bytes by
  AST with zero drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.integrations.reigh.wgp_bridge import (
    verify_config_schema_against_pin,
)
from astrid.core.integrations.reigh.wgp_patches import (
    PATCHES,
    PINNED_WAN2GP_SHA,
    anchor_report,
    patchset_hash,
)
from astrid.core.integrations.reigh.wgp_patches import (
    applied as patches_applied,
)

VENDORED_CHECKOUT = (
    Path(__file__).resolve().parents[2].parent / "vendor" / "Wan2GP"
)


def _checkout_or_skip() -> Path:
    if not (VENDORED_CHECKOUT / "wgp.py").is_file():  # pragma: no cover
        pytest.skip(
            f"vendored Wan2GP tree not present at {VENDORED_CHECKOUT}; "
            "run T7.1 vendoring first"
        )
    return VENDORED_CHECKOUT


def test_gate1_pipeline_green_on_vendored_pin() -> None:
    from astrid.core.integrations.reigh.wgp_gates import gate1_hermetic_rebase

    report = gate1_hermetic_rebase(_checkout_or_skip())
    assert report.ok, [
        (leg.name, leg.status, leg.detail)
        for leg in report.legs
        if leg.status != "ok"
    ]
    names = {leg.name for leg in report.legs}
    assert "submodule_bump_pinned" in names
    assert "working_tree_clean" in names


def test_every_patch_anchor_matches_exactly_once() -> None:
    report = anchor_report(_checkout_or_skip())
    assert set(report) == {patch.name for patch in PATCHES}
    assert all(status == "ok" for status in report.values()), report


def test_patch_application_is_scoped_and_restores_exactly() -> None:
    class _Wgp:
        sliding_window_size = 0

    module = _Wgp()
    with patches_applied(module, {"sliding_window_size": 33}):
        assert module.sliding_window_size == 33
        assert module.svi_pro is False  # absent before, patched in
    assert module.sliding_window_size == 0
    assert not hasattr(module, "svi_pro")  # absent again, not None


def test_patch_restore_survives_body_exception() -> None:
    class _Wgp:
        pass

    module = _Wgp()
    with pytest.raises(RuntimeError), patches_applied(module, {}):
        raise RuntimeError("generation blew up")
    assert not hasattr(module, "model_switch_phase")


def test_patchset_hash_is_stable() -> None:
    assert patchset_hash() == patchset_hash()
    assert len(patchset_hash()) == 64


def test_pinned_sha_constant_matches_vendored_head() -> None:
    checkout = _checkout_or_skip()
    import subprocess

    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == PINNED_WAN2GP_SHA


def test_config_schema_reconstructs_from_pinned_bytes_with_zero_drift() -> None:
    drift = verify_config_schema_against_pin(_checkout_or_skip())
    assert drift == [], (
        "recorded wgp_config.json schema disagrees with pinned bytes; "
        "reconstruct DEFAULT_SERVER_CONFIG against the pin"
    )
