"""Tests for URL extraction from WaveSpeedAI prediction result shapes."""

from __future__ import annotations

from astrid.core.generation.backends.wavespeed import _extract_asset_urls


class TestExtractWavespeedUrls:
    """Real-world shapes for WavespeedBackend._extract_asset_urls.

    WaveSpeed's completed prediction ``data`` carries ``outputs`` as a list
    of plain URL strings (observed live: music-3.0 returned
    ``["https://.../1.mp3"]``).  Dict-shaped outputs are handled too.
    """

    def test_outputs_list_of_strings(self) -> None:
        result = {
            "outputs": [
                "https://d1q70pf5vjeyhc.cloudfront.net/predictions/abc/1.mp3",
            ],
            "status": "completed",
        }
        assert _extract_asset_urls(result) == [
            "https://d1q70pf5vjeyhc.cloudfront.net/predictions/abc/1.mp3",
        ]

    def test_outputs_list_of_audio_dicts(self) -> None:
        result = {
            "outputs": [
                {"audio": {"url": "https://cdn.wavespeed.ai/1.mp3"}},
                {"audio": {"url": "https://cdn.wavespeed.ai/2.wav"}},
            ]
        }
        assert _extract_asset_urls(result) == [
            "https://cdn.wavespeed.ai/1.mp3",
            "https://cdn.wavespeed.ai/2.wav",
        ]

    def test_outputs_list_of_plain_dict_urls(self) -> None:
        result = {"outputs": [{"url": "https://cdn.wavespeed.ai/1.mp3"}]}
        assert _extract_asset_urls(result) == ["https://cdn.wavespeed.ai/1.mp3"]

    def test_outputs_dict_with_audio(self) -> None:
        result = {"outputs": {"audio": {"url": "https://cdn.wavespeed.ai/1.mp3"}}}
        assert _extract_asset_urls(result) == ["https://cdn.wavespeed.ai/1.mp3"]

    def test_single_audio_object(self) -> None:
        result = {"audio": {"url": "https://cdn.wavespeed.ai/1.mp3"}}
        assert _extract_asset_urls(result) == ["https://cdn.wavespeed.ai/1.mp3"]

    def test_output_direct_url(self) -> None:
        result = {"output": "https://cdn.wavespeed.ai/1.mp3"}
        assert _extract_asset_urls(result) == ["https://cdn.wavespeed.ai/1.mp3"]

    def test_output_object_url(self) -> None:
        result = {"output": {"url": "https://cdn.wavespeed.ai/1.mp3"}}
        assert _extract_asset_urls(result) == ["https://cdn.wavespeed.ai/1.mp3"]

    def test_url_key_fallback(self) -> None:
        result = {"audio_url": "https://cdn.wavespeed.ai/1.mp3"}
        assert _extract_asset_urls(result) == ["https://cdn.wavespeed.ai/1.mp3"]

    def test_empty_result_returns_empty_list(self) -> None:
        assert _extract_asset_urls({}) == []

    def test_mixed_string_and_dict_outputs(self) -> None:
        result = {
            "outputs": [
                "https://cdn.wavespeed.ai/1.mp3",
                {"audio": {"url": "https://cdn.wavespeed.ai/2.wav"}},
            ]
        }
        assert _extract_asset_urls(result) == [
            "https://cdn.wavespeed.ai/1.mp3",
            "https://cdn.wavespeed.ai/2.wav",
        ]
