from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNTIME = Path(__file__).parents[3] / "banodoco-workspace-runtime-stage1-convergence"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "packages" / "python"))

import pytest
from runtime_protocol.daemon import RuntimeDaemon

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "v10" / "seed_reigh_gallery_acceptance.py"
SPEC = importlib.util.spec_from_file_location("seed_reigh_gallery_acceptance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_seed_is_explicit_complete_and_receipt_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dry_run = MODULE.seed_reigh_gallery_acceptance(tmp_path)
    assert dry_run["ok"] is True
    assert dry_run["mode"] == "dry-run"
    assert dry_run["after"]["project_present"] is False

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        first = MODULE.seed_reigh_gallery_acceptance(tmp_path / "staging", apply=True)
        assert first["ok"] is True
        assert first["after"] == {
            "project_present": True,
            "generations": 12,
            "variants": 24,
            "timelines": 1,
            "pinned_shot_groups": 4,
        }

        second = MODULE.seed_reigh_gallery_acceptance(tmp_path / "staging", apply=True)
        assert second["ok"] is True
        assert second["after"] == first["after"]
    finally:
        daemon.stop()


def test_fixture_pngs_are_byte_distinct_and_valid() -> None:
    first = MODULE._solid_png(16, 9, MODULE._palette(0, 0))
    second = MODULE._solid_png(16, 9, MODULE._palette(0, 1))
    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    assert second.startswith(b"\x89PNG\r\n\x1a\n")
    assert first != second
