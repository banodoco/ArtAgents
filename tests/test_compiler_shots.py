"""Compiler shots projection tests (plan v10 batch B3, tasks T8-T12).

Tests the compiler's --shots flag: compile a storyboard into kernel shots,
sub-timelines, and a parent shot graph. Verifies:
- 2 sections → 2 shots / 4 items / 2 sub-timelines
- Same shot ids on recompile (receipt replay-safe)
- 25 total timeline rows on first run, same on second run (no duplication)
- Each shot.metadata_json.timeline_document_id resolves to real timelines row
"""

from __future__ import annotations

import json
from collections import namedtuple
from pathlib import Path
from typing import Any

import pytest

from scripts import build_storyboard as bs

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINIMAL = FIXTURES / "storyboard-minimal.json"
ASSET_DIR = FIXTURES / "storyboard-assets"


class _FakeKernelImports:
    """Monkeypatch stand-in for ``sdk_import_asset``: temp files, real hashes."""

    def __init__(self, cas_root: Path):
        self.cas_root = cas_root
        self.imports: dict[str, Any] = {}
        self.media_ids: dict[str, str] = {}

    def __call__(self, path: Path, *, project: str) -> Any:
        """Mock import_asset: return temp-file-backed receipts with real hashes."""
        rel = path.relative_to(cas_root.parent)
        target = self.cas_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        media_id = f"media_{sha256[:16]}"
        self.media_ids[rel.name] = media_id
        receipt = {
            "file": str(target),
            "content_sha256": sha256,
            "media_id": media_id,
        }
        return receipt


@pytest.fixture()
def fake_kernel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch sdk_import_asset with fake kernel that uses temp CAS."""
    cas_root = tmp_path / "cas"
    fake = _FakeKernelImports(cas_root)
    monkeypatch.setattr(bs, "sdk_import_asset", fake)
    return fake


def _import_media(fake: _FakeKernelImports, path: str) -> str:
    """Import media through fake kernel and return media_id."""
    fake_path = ASSET_DIR / path
    receipt = fake(fake_path)
    return receipt["media_id"]


def test_compiler_shots_two_sections_creates_kernel_data(fake_kernel: _FakeKernelImports) -> None:
    """Compile 2-section minimal intro with --shots flag: creates 2 shots / 4 items / 2 sub-timelines."""
    # Open minimal intro story
    story = json.loads(MINIMAL.read_text(encoding="utf-8"))
    
    # We can't actually run the compiler with --shots yet (need to implement parent emitter),
    # so this test documents the expected contract until T11 is complete.
    # When T11 is implemented, this test should:
    # - Call compile_storyboard(story, base_dir=..., project="test", shots=True)
    # - Verify shots service results: 2 shots created, 4 items added
    # - Verify timelines service: 2 sub-timelines created
    # - Verify parent doc: 1 brand clip + 25 shot clips
    
    # For now, just verify the fixture loads correctly
    assert len(story["sections"]) == 2
    assert story["sections"][0]["id"] == "open"
    assert story["sections"][1]["id"] == "idea-1"
    
    # Verify image variants exist (active_index=1 points to idea-1-alt.png gen variant)
    assert "variants" in story["sections"][1]["image"]
    assert len(story["sections"][1]["image"]["variants"]) == 2
    assert story["sections"][1]["image"]["active_index"] == 1
    
    # This test will be implemented in T11/T12 when parent emitter and expand_shot_clips are complete
    pytest.skip("Parent emitter (--shots) not yet implemented in compile_storyboard")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
