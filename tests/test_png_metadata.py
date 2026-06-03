"""Tests for astrid.core.util.png_metadata — embed_png_text."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from astrid.core.util.png_metadata import embed_png_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_png(path: Path, size: tuple[int, int] = (4, 4)) -> Path:
    """Create a minimal solid-red PNG at *path*. Returns *path*."""
    img = Image.new("RGB", size, color=(255, 0, 0))
    img.save(path, format="PNG")
    return path


def _make_test_png_with_text(path: Path, text: dict[str, str]) -> Path:
    """Create a minimal PNG at *path* with tEXt chunks from *text*."""
    img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    pnginfo = PngImagePlugin.PngInfo()
    for k, v in text.items():
        pnginfo.add_text(k, v)
    img.save(path, pnginfo=pnginfo, format="PNG")
    return path


def _read_text_chunks(path: Path) -> dict[str, str]:
    """Return all tEXt chunks from a PNG as a dict."""
    img = Image.open(path)
    return dict(img.text) if img.text else {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmbedPngText:
    """Happy-path: embedding writes expected astrid_* keys."""

    def test_writes_astrid_keys_into_fresh_png(self, tmp_path: Path) -> None:
        png = _make_test_png(tmp_path / "test.png")

        ok = embed_png_text(png, {
            "prompt": "a red cube",
            "model": "z-image",
            "seed": "42",
        })
        assert ok is True

        text = _read_text_chunks(png)
        assert text["astrid_prompt"] == "a red cube"
        assert text["astrid_model"] == "z-image"
        assert text["astrid_seed"] == "42"

    def test_all_manifest_keys_written(self, tmp_path: Path) -> None:
        """Every key we embed from the manifest should appear."""
        png = _make_test_png(tmp_path / "full.png")

        fields = {
            "prompt": "test prompt",
            "negative_prompt": "ugly",
            "model": "flux-dev",
            "model_actual": "fal/flux-dev",
            "seed": "123456",
            "request_id": "req-abc",
            "created": "2025-01-01T00:00:00+00:00",
            "loras": "[{'name': 'detailer'}]",
        }
        ok = embed_png_text(png, fields)
        assert ok is True

        text = _read_text_chunks(png)
        for key, expected in fields.items():
            assert text[f"astrid_{key}"] == expected, f"missing astrid_{key}"
        # No non-astrid keys in a fresh PNG
        for k in text:
            assert k.startswith("astrid_"), f"unexpected key {k!r}"


class TestPreserveExisting:
    """Existing tEXt chunks (e.g. ComfyUI prompt/workflow) must survive."""

    def test_preserves_workflow_and_prompt(self, tmp_path: Path) -> None:
        existing = {
            "workflow": '{"nodes": []}',
            "prompt": '{"3": {"inputs": {}}}',
        }
        png = _make_test_png_with_text(tmp_path / "comfy.png", existing)

        ok = embed_png_text(png, {
            "prompt": "user prompt",
            "model": "z-image",
        })
        assert ok is True

        text = _read_text_chunks(png)
        # ComfyUI chunks preserved
        assert text["workflow"] == existing["workflow"]
        assert text["prompt"] == existing["prompt"]
        # Astrid chunks added (namespaced, so no collision)
        assert text["astrid_prompt"] == "user prompt"
        assert text["astrid_model"] == "z-image"

    def test_preserves_when_no_new_fields(self, tmp_path: Path) -> None:
        """Even with empty fields, existing chunks should survive."""
        existing = {"workflow": "{}"}
        png = _make_test_png_with_text(tmp_path / "comfy.png", existing)

        ok = embed_png_text(png, {})
        assert ok is True

        text = _read_text_chunks(png)
        assert text["workflow"] == "{}"
        # No astrid_ keys since fields was empty
        astrid_keys = [k for k in text if k.startswith("astrid_")]
        assert astrid_keys == []


class TestNoOp:
    """Non-PNG and missing paths are safe no-ops."""

    def test_missing_path_returns_false(self, tmp_path: Path) -> None:
        ok = embed_png_text(tmp_path / "nope.png", {"prompt": "x"})
        assert ok is False

    def test_non_png_returns_false(self, tmp_path: Path) -> None:
        jpg = tmp_path / "photo.jpg"
        jpg.write_bytes(b"not a png")
        ok = embed_png_text(jpg, {"prompt": "x"})
        assert ok is False

    def test_directory_returns_false(self, tmp_path: Path) -> None:
        d = tmp_path / "subdir"
        d.mkdir()
        ok = embed_png_text(d, {"prompt": "x"})
        assert ok is False

    def test_no_exception_raised(self, tmp_path: Path) -> None:
        """Callers never get an exception — the function handles internally."""
        # missing path
        embed_png_text(tmp_path / "gone.png", {"x": "y"})
        # non-png
        bad = tmp_path / "bad.bin"
        bad.write_bytes(b"\x00\x01")
        embed_png_text(bad, {"x": "y"})
        # directory
        d = tmp_path / "dir"
        d.mkdir()
        embed_png_text(d, {"x": "y"})
        # None of these should raise


class TestLatin1Safety:
    """Non-Latin-1 characters in field values are safely replaced."""

    def test_unicode_prompt_is_safely_encoded(self, tmp_path: Path) -> None:
        png = _make_test_png(tmp_path / "unicode.png")
        ok = embed_png_text(png, {
            "prompt": "a 🌟 starry night — émoji",
        })
        assert ok is True

        text = _read_text_chunks(png)
        # The emoji should have been replaced but the rest preserved
        result = text["astrid_prompt"]
        assert "a " in result
        assert "starry night" in result
        assert "émoji" in result
        # Emoji (🌟) is not Latin-1, so it gets replaced with '?'
        assert "?" in result
