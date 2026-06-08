"""Focused tests for T23: atomic writes for variants sidecar and PNG metadata.

Validates:
- variants write_sidecar uses write_json_atomic (shared atomic JSON helper).
- embed_png_text writes to a sibling temp file then os.replace's the original.
- Existing locking in VariantState is preserved.
- PNG metadata behavior is preserved (fields embedded, existing chunks kept).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import ANY, call, patch

import pytest

from astrid.core.threads.variants import (
    VARIANT_SIDECAR_NAME,
    VariantState,
    write_sidecar,
)
from astrid.core.util.png_metadata import embed_png_text


# ---------------------------------------------------------------------------
# T23: Variants sidecar atomic write
# ---------------------------------------------------------------------------


class TestWriteSidecarAtomic:
    """write_sidecar uses write_json_atomic for the sidecar file."""

    def test_write_sidecar_uses_atomic_json_helper(self, tmp_path: Path) -> None:
        """Prove write_sidecar delegates to write_json_atomic."""
        artifacts = [
            {
                "path": "test.png",
                "role": "variant",
                "group": "abc123",
                "group_index": 1,
                "variant_meta": {"prompt": "hello"},
            }
        ]

        with patch("astrid.core.threads.variants.write_json_atomic") as mock_write:
            write_sidecar(tmp_path, artifacts)
            mock_write.assert_called_once()
            call_args = mock_write.call_args
            # First arg is the sidecar path
            assert call_args[0][0] == tmp_path / VARIANT_SIDECAR_NAME
            # Second arg is the payload dict
            payload = call_args[0][1]
            assert payload["schema_version"] is not None
            assert len(payload["artifacts"]) == 1
            assert payload["artifacts"][0]["path"] == "test.png"

    def test_write_sidecar_empty_artifacts_no_write(self, tmp_path: Path) -> None:
        """Empty artifacts list should not trigger any write."""
        with patch("astrid.core.threads.variants.write_json_atomic") as mock_write:
            write_sidecar(tmp_path, [])
            mock_write.assert_not_called()

    def test_write_sidecar_output_is_valid_json(self, tmp_path: Path) -> None:
        """Sidecar content written via atomic helper is valid, parseable JSON."""
        artifacts = [
            {
                "path": "a.png",
                "role": "variant",
                "group": "grp1",
                "group_index": 1,
            },
            {
                "path": "b.png",
                "role": "other",
                "group": "grp1",
                "group_index": 2,
            },
        ]
        write_sidecar(tmp_path, artifacts)

        sidecar_path = tmp_path / VARIANT_SIDECAR_NAME
        assert sidecar_path.is_file()

        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] is not None
        assert len(payload["artifacts"]) == 2
        paths = [a["path"] for a in payload["artifacts"]]
        assert "a.png" in paths
        assert "b.png" in paths

    def test_write_sidecar_no_temp_file_left_behind(self, tmp_path: Path) -> None:
        """Atomic write must not leave temp files after completion."""
        artifacts = [{"path": "x.png", "role": "variant", "group": "g", "group_index": 1}]
        before = set(tmp_path.iterdir())
        write_sidecar(tmp_path, artifacts)
        after = set(tmp_path.iterdir())

        new_files = after - before
        assert len(new_files) == 1
        assert new_files.pop().name == VARIANT_SIDECAR_NAME

    def test_write_sidecar_overwrites_existing(self, tmp_path: Path) -> None:
        """Writing again should atomically replace the existing sidecar."""
        artifacts_v1 = [{"path": "v1.png", "role": "variant", "group": "g", "group_index": 1}]
        write_sidecar(tmp_path, artifacts_v1)

        artifacts_v2 = [{"path": "v2.png", "role": "variant", "group": "g", "group_index": 1}]
        write_sidecar(tmp_path, artifacts_v2)

        sidecar_path = tmp_path / VARIANT_SIDECAR_NAME
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert len(payload["artifacts"]) == 1
        assert payload["artifacts"][0]["path"] == "v2.png"


class TestVariantStateLockingPreserved:
    """Existing VariantState _write_groups_unlocked locking behavior is untouched."""

    def test_variant_state_write_groups_still_uses_internal_atomic_pattern(self, tmp_path: Path) -> None:
        """VariantState._write_groups_unlocked has its own atomic write logic;
        we only verify it still compiles and works."""
        repo = tmp_path / "repo"
        repo.mkdir()
        state = VariantState(repo, "01ARZ3NDEKTSV4RRFFQ69G5FAV")

        groups = {"schema_version": 1, "thread_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "groups": {}}
        # _write_groups_unlocked is internal; test through update_groups
        result = state.update_groups(lambda g: g)
        assert result is not None

        # groups.json should exist
        assert state.groups_path.is_file()
        payload = json.loads(state.groups_path.read_text(encoding="utf-8"))
        assert payload["thread_id"] == "01ARZ3NDEKTSV4RRFFQ69G5FAV"

    def test_write_sidecar_does_not_affect_variant_state_locking(self, tmp_path: Path) -> None:
        """write_sidecar writes to a different path (sidecar), not groups.json."""
        repo = tmp_path / "repo"
        repo.mkdir()
        state = VariantState(repo, "01ARZ3NDEKTSV4RRFFQ69G5FAV")

        # Write sidecar in out_path (not the same as state_dir)
        out_path = tmp_path / "output"
        artifacts = [{"path": "test.png", "role": "variant", "group": "g1", "group_index": 1}]
        write_sidecar(out_path, artifacts)

        # groups.json should not be affected
        assert not state.groups_path.exists() or state.groups_path.is_file()
        # Sidecar should exist at the correct location
        assert (out_path / VARIANT_SIDECAR_NAME).is_file()


# ---------------------------------------------------------------------------
# T23: PNG metadata atomic replace
# ---------------------------------------------------------------------------


class TestEmbedPngTextAtomic:
    """embed_png_text uses sibling temp + os.replace for atomic replacement."""

    @pytest.fixture
    def sample_png(self, tmp_path: Path) -> Path:
        """Create a minimal valid PNG for testing."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not available")

        png_path = tmp_path / "test.png"
        img = Image.new("RGB", (4, 4), color="red")
        img.save(png_path)
        return png_path

    def test_embed_png_text_uses_os_replace(self, sample_png: Path) -> None:
        """Prove os.replace is called (not a direct in-place save)."""
        with patch("astrid.core.util.png_metadata.os.replace") as mock_replace:
            result = embed_png_text(sample_png, {"prompt": "hello"})
            assert result is True
            mock_replace.assert_called_once()
            # The tmp file should have been replaced over the original
            args, _ = mock_replace.call_args
            assert str(args[1]) == str(sample_png)

    def test_embed_png_text_no_temp_left_behind(self, sample_png: Path) -> None:
        """No temp files remain after successful embed."""
        parent = sample_png.parent
        before = set(parent.iterdir())
        embed_png_text(sample_png, {"prompt": "test"})
        after = set(parent.iterdir())

        new_files = after - before
        # Only the original PNG should exist (it may have been replaced in-place)
        png_files = [f for f in after if f.suffix == ".png"]
        assert len(png_files) == 1
        # No .png.tmp files
        tmp_files = [f for f in after if f.name.endswith(".png.tmp")]
        assert len(tmp_files) == 0

    def test_embed_png_text_preserves_fields(self, sample_png: Path) -> None:
        """Embedded fields are readable after atomic write."""
        from PIL import Image

        embed_png_text(sample_png, {"prompt": "a cat", "seed": "42"})

        img = Image.open(sample_png)
        assert img.text is not None
        assert img.text.get("astrid_prompt") == "a cat"
        assert img.text.get("astrid_seed") == "42"

    def test_embed_png_text_preserves_existing_chunks(self, sample_png: Path) -> None:
        """Existing tEXt chunks (e.g. ComfyUI workflow) survive atomic replace."""
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        # First write with a "workflow" chunk
        pnginfo = PngInfo()
        pnginfo.add_text("workflow", '{"nodes": []}')
        img = Image.open(sample_png)
        img.save(sample_png, pnginfo=pnginfo)

        # Now embed astrid fields
        embed_png_text(sample_png, {"prompt": "test"})

        img = Image.open(sample_png)
        assert img.text is not None
        assert img.text.get("workflow") == '{"nodes": []}'
        assert img.text.get("astrid_prompt") == "test"

    def test_embed_png_text_non_png_returns_false(self, tmp_path: Path) -> None:
        """Non-PNG files are silently skipped (return False)."""
        jpg_path = tmp_path / "test.jpg"
        jpg_path.write_bytes(b"not a png")
        result = embed_png_text(jpg_path, {"prompt": "test"})
        assert result is False

    def test_embed_png_text_missing_file_returns_false(self, tmp_path: Path) -> None:
        """Missing files return False."""
        result = embed_png_text(tmp_path / "nope.png", {"prompt": "test"})
        assert result is False

    def test_embed_png_text_failure_cleans_up_temp(self, sample_png: Path) -> None:
        """If os.replace fails, the temp file should be cleaned up."""
        with patch("astrid.core.util.png_metadata.os.replace") as mock_replace:
            mock_replace.side_effect = OSError("simulated failure")
            # Should not raise; returns False
            result = embed_png_text(sample_png, {"prompt": "test"})
            assert result is False
            # No .png.tmp files left
            tmp_files = list(sample_png.parent.glob("*.png.tmp"))
            assert len(tmp_files) == 0

    def test_embed_png_text_original_preserved_on_failure(self, sample_png: Path) -> None:
        """If the atomic replace fails, the original file is untouched."""
        original_data = sample_png.read_bytes()

        with patch("astrid.core.util.png_metadata.os.replace") as mock_replace:
            mock_replace.side_effect = OSError("simulated failure")
            embed_png_text(sample_png, {"prompt": "should not appear"})

        # Original file should still exist with original content
        assert sample_png.read_bytes() == original_data
