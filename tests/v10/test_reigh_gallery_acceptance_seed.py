from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "v10" / "seed_reigh_gallery_acceptance.py"
SPEC = importlib.util.spec_from_file_location("seed_reigh_gallery_acceptance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_seed_is_explicit_complete_and_receipt_idempotent(tmp_path: Path) -> None:
    dry_run = MODULE.seed_reigh_gallery_acceptance(tmp_path)
    assert dry_run["ok"] is True
    assert dry_run["mode"] == "dry-run"
    assert dry_run["after"]["project_present"] is False

    first = MODULE.seed_reigh_gallery_acceptance(tmp_path, apply=True)
    assert first["ok"] is True
    assert first["after"] == {
        "project_present": True,
        "generations": 12,
        "variants": 24,
        "timelines": 1,
        "pinned_shot_groups": 4,
    }

    second = MODULE.seed_reigh_gallery_acceptance(tmp_path, apply=True)
    assert second["ok"] is True
    assert second["after"] == first["after"]


def test_fixture_pngs_are_byte_distinct_and_valid() -> None:
    first = MODULE._solid_png(16, 9, MODULE._palette(0, 0))
    second = MODULE._solid_png(16, 9, MODULE._palette(0, 1))
    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    assert second.startswith(b"\x89PNG\r\n\x1a\n")
    assert first != second
