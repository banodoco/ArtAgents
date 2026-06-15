"""Tests for audio URL extraction from fal result shapes."""

from __future__ import annotations

from astrid.core.generation.backends.fal import _extract_asset_urls


class TestExtractAudioUrls:
    """Audio-specific extraction shapes for FalBackend._extract_asset_urls."""

    def test_single_audio_dict(self) -> None:
        result = {"audio": {"url": "https://cdn.fal.ai/output.mp3"}}
        assert _extract_asset_urls(result) == ["https://cdn.fal.ai/output.mp3"]

    def test_single_audio_file_dict(self) -> None:
        result = {"audio_file": {"url": "https://cdn.fal.ai/output.wav"}}
        assert _extract_asset_urls(result) == ["https://cdn.fal.ai/output.wav"]

    def test_audio_list(self) -> None:
        result = {
            "audios": [
                {"url": "https://cdn.fal.ai/output_000.mp3"},
                {"url": "https://cdn.fal.ai/output_001.flac"},
            ]
        }
        assert _extract_asset_urls(result) == [
            "https://cdn.fal.ai/output_000.mp3",
            "https://cdn.fal.ai/output_001.flac",
        ]

    def test_nested_output_audio(self) -> None:
        result = {
            "output": {
                "audio": {"url": "https://cdn.fal.ai/output.m4a"},
            }
        }
        assert _extract_asset_urls(result) == ["https://cdn.fal.ai/output.m4a"]

    def test_audio_url_strings_in_list(self) -> None:
        result = {
            "audios": [
                "https://cdn.fal.ai/output_000.mp3",
                "https://cdn.fal.ai/output_001.wav",
            ]
        }
        assert _extract_asset_urls(result) == [
            "https://cdn.fal.ai/output_000.mp3",
            "https://cdn.fal.ai/output_001.wav",
        ]

    def test_image_takes_precedence_over_audio(self) -> None:
        """Existing image/video shapes must still win before audio fallbacks."""
        result = {
            "images": [{"url": "https://cdn.fal.ai/image.png"}],
            "audio": {"url": "https://cdn.fal.ai/audio.mp3"},
        }
        assert _extract_asset_urls(result) == ["https://cdn.fal.ai/image.png"]

    def test_empty_result_returns_empty_list(self) -> None:
        assert _extract_asset_urls({}) == []
