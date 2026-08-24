"""Gate ③ — per-platform dependency resolution (Batch B7).

The dependency plan is a declarative table; resolution is mechanical.
Real ``uv sync --extra cuda124`` is a CUDA/network leg and runs only
opt-in on a GPU runner — recorded as an explicit skip with reason in the
gate report, never silently dropped.
"""

from __future__ import annotations

import pytest

from astrid.core.integrations.reigh.wgp_gates import (
    PLATFORM_DEPENDENCIES,
    gate3_platform_resolution,
    resolve_platform_plan,
)


def test_darwin_arm64_decord_rides_the_stub_story() -> None:
    plan = resolve_platform_plan("darwin-arm64")
    assert "decord" not in plan["required_imports"]
    assert "decord" in plan["stubs"]
    assert "smplfitter" in plan["required_imports"]


def test_linux_x86_64_locks_the_cuda124_extra() -> None:
    plan = resolve_platform_plan("linux-x86_64")
    assert "--extra" in plan["sync"] and "cuda124" in plan["sync"]
    assert {"decord", "smplfitter"} <= set(plan["required_imports"])
    assert plan["stubs"] == {}


def test_unsupported_platform_refuses() -> None:
    with pytest.raises(KeyError, match="unsupported platform"):
        resolve_platform_plan("plan9-mips")


def test_gate3_report_green_with_documented_cuda_skip() -> None:
    report = gate3_platform_resolution()
    assert report.ok
    skips = report.skipped
    assert len(skips) == 1
    leg = skips[0]
    assert leg.name == "real_uv_sync"
    assert "CUDA" in (leg.reason or "")


def test_platform_table_is_exhaustively_declared() -> None:
    assert set(PLATFORM_DEPENDENCIES) == {"linux-x86_64", "darwin-arm64"}
