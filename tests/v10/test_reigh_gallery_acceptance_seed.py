from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "v10" / "seed_reigh_gallery_acceptance.py"
SPEC = importlib.util.spec_from_file_location("seed_reigh_gallery_acceptance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_seed_is_explicit_complete_and_receipt_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_daemon = pytest.importorskip("runtime_protocol.daemon")
    RuntimeDaemon = runtime_daemon.RuntimeDaemon
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


def test_seed_repairs_missing_variant_without_reclaiming_completed_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_daemon = pytest.importorskip("runtime_protocol.daemon")
    RuntimeDaemon = runtime_daemon.RuntimeDaemon
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        from astrid.sdk.remote import RemoteGenerations

        original = RemoteGenerations.create_variant
        calls = 0

        def fail_once(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("injected graph write failure")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(RemoteGenerations, "create_variant", fail_once)
        with pytest.raises(RuntimeError, match="injected graph write failure"):
            MODULE.seed_reigh_gallery_acceptance(tmp_path / "staging", apply=True)
        monkeypatch.setattr(RemoteGenerations, "create_variant", original)

        repaired = MODULE.seed_reigh_gallery_acceptance(tmp_path / "staging", apply=True)
        assert repaired["ok"] is True
        assert repaired["after"]["generations"] == MODULE.GENERATION_COUNT
        assert repaired["after"]["variants"] == MODULE.GENERATION_COUNT * MODULE.VARIANTS_PER_GENERATION
    finally:
        daemon.stop()
