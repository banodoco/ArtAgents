"""URL extraction contracts for WaveSpeed completed predictions."""

from __future__ import annotations

from astrid.core.generation.backends.wavespeed import _extract_asset_urls


def test_outputs_list_of_strings() -> None:
    url = "https://cdn.wavespeed.ai/predictions/abc/1.mp3"
    assert _extract_asset_urls({"outputs": [url], "status": "completed"}) == [url]


def test_outputs_list_of_audio_dicts() -> None:
    assert _extract_asset_urls({"outputs": [{"audio": {"url": "https://cdn/1.mp3"}}, {"audio": {"url": "https://cdn/2.wav"}}]}) == [
        "https://cdn/1.mp3", "https://cdn/2.wav"
    ]


def test_outputs_list_of_plain_dict_urls() -> None:
    assert _extract_asset_urls({"outputs": [{"url": "https://cdn/1.mp3"}]}) == ["https://cdn/1.mp3"]


def test_outputs_dict_with_audio() -> None:
    assert _extract_asset_urls({"outputs": {"audio": {"url": "https://cdn/1.mp3"}}}) == ["https://cdn/1.mp3"]


def test_single_audio_object() -> None:
    assert _extract_asset_urls({"audio": {"url": "https://cdn/1.mp3"}}) == ["https://cdn/1.mp3"]


def test_output_direct_url() -> None:
    assert _extract_asset_urls({"output": "https://cdn/1.mp3"}) == ["https://cdn/1.mp3"]


def test_output_object_url() -> None:
    assert _extract_asset_urls({"output": {"url": "https://cdn/1.mp3"}}) == ["https://cdn/1.mp3"]


def test_url_key_fallback() -> None:
    assert _extract_asset_urls({"audio_url": "https://cdn/1.mp3"}) == ["https://cdn/1.mp3"]


def test_empty_result_returns_empty_list() -> None:
    assert _extract_asset_urls({}) == []


def test_mixed_string_and_dict_outputs() -> None:
    assert _extract_asset_urls({"outputs": ["https://cdn/1.mp3", {"audio": {"url": "https://cdn/2.wav"}}]}) == [
        "https://cdn/1.mp3", "https://cdn/2.wav"
    ]
