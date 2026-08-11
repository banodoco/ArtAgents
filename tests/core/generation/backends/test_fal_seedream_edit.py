"""Fal wiring for ByteDance Seedream 5.0 Pro image editing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from astrid.core.generation.backends.fal import FalBackend
from astrid.core.model_catalog.registry import ModelRegistry


def test_seedream_edit_wraps_single_image_ref_for_plural_fal_input(
    tmp_path: Path,
) -> None:
    """Astrid's singular image_ref becomes fal's required image_urls array."""
    from astrid.core.generation.backends import fal as fal_mod

    entry = ModelRegistry.load_default().get("seedream-v5-pro")
    captured: dict[str, object] = {}

    def capture_submit(client, endpoint, payload, api_key):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {
            "images": [{"url": "https://example.com/seedream-output.png"}],
            "request_id": "seedream-test-request",
        }

    backend = FalBackend()
    with (
        patch.object(fal_mod, "fal_submit_and_poll", side_effect=capture_submit),
        patch.object(FalBackend, "_resolve_api_key", return_value="test-key"),
        patch.object(
            backend._client,
            "get_bytes",
            return_value=b"\x89PNG\r\n\x1a\n",
        ),
    ):
        result = backend.generate(
            entry=entry,
            mode="edit",
            params={
                "prompt": "Keep the landscape fixed; thicken only the plant feeder.",
                "image_ref": "https://example.com/source.png",
                "size": "landscape_16_9",
            },
            out_dir=tmp_path / "out",
        )

    assert captured["endpoint"] == "bytedance/seedream/v5/pro/edit"
    assert captured["payload"] == {
        "prompt": "Keep the landscape fixed; thicken only the plant feeder.",
        "image_urls": ["https://example.com/source.png"],
        "image_size": "landscape_16_9",
        "output_format": "png",
    }
    assert result.error is None
    assert len(result.image_paths) == 1
    assert result.cost_usd == 0.0675
