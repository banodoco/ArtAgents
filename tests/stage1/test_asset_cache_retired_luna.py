from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.media import require_runtime_materialized_file

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_FILES = (
    REPO_ROOT / "astrid/core/execution/executor/runner.py",
    REPO_ROOT / "astrid/packs/editorial/executors/human_notes/run.py",
    REPO_ROOT / "astrid/packs/editorial/executors/quality_zones/run.py",
    REPO_ROOT / "astrid/packs/editorial/executors/scenes/run.py",
    REPO_ROOT / "astrid/packs/editorial/executors/shots/run.py",
    REPO_ROOT / "astrid/packs/editorial/executors/transcribe/run.py",
    REPO_ROOT / "astrid/packs/understanding/executors/scene_describe/run.py",
    REPO_ROOT / "astrid/packs/video_editing/orchestrators/thumbnail_maker/run.py",
    REPO_ROOT / "astrid/packs/video_editing/executors/cut/attempt_assets.py",
    REPO_ROOT / "astrid/packs/rendering/executors/timeline_storyboard/run.py",
)


def test_live_media_code_has_no_retired_asset_cache_boundary() -> None:
    for path in LIVE_FILES:
        source = path.read_text(encoding="utf-8")
        assert "asset_cache" not in source, path
        assert "HYPE_CACHE_DIR" not in source, path
        assert "urlopen" not in source, path
        assert "require_runtime_materialized_file" in source, path


@pytest.mark.parametrize("value", ["https://example.invalid/clip.mp4", "relative/clip.mp4"])
def test_runtime_media_boundary_rejects_urls_and_relative_paths(value: str) -> None:
    with pytest.raises(ValueError, match="absolute runtime-materialized file"):
        require_runtime_materialized_file(value)


def test_runtime_media_boundary_accepts_existing_absolute_file(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"materialized")
    assert require_runtime_materialized_file(source) == source


def test_runtime_media_boundary_rejects_missing_absolute_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="runtime materialization is unavailable"):
        require_runtime_materialized_file(tmp_path / "missing.mp4")


def test_retired_cache_capability_is_not_shipped() -> None:
    assert not (REPO_ROOT / "astrid/core/rendering/asset_cache.py").exists()
    # Ignore stale ignored bytecode directories left by an interrupted test
    # run.  The product contract is about shipped source/manifest inventory,
    # not whether an ignored cache directory happens to remain on disk.
    retired_pack_dir = REPO_ROOT / "astrid/packs/training/executors/asset_cache"
    shipped_sources = [
        path
        for path in retired_pack_dir.rglob("*")
        if path.is_file() and path.suffix in {".py", ".yaml", ".yml", ".json"}
    ] if retired_pack_dir.exists() else []
    assert shipped_sources == []
    pack_manifest = (REPO_ROOT / "astrid/packs/training/pack.yaml").read_text(encoding="utf-8")
    assert "asset_cache" not in pack_manifest
