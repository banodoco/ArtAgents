from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.rendering.storage import (
    StorageEstimateError,
    estimate_managed_render_storage,
    managed_object_sizes,
    used_effect_asset_sizes,
)


def _timeline(*, alpha: bool = False) -> dict:
    value = {
        "tracks": [
            {"id": "video", "kind": "visual", "label": "Video"},
            {"id": "audio", "kind": "audio", "label": "Audio"},
        ],
        "clips": [
            {"id": "picture", "track": "video", "at": 0, "hold": 10},
            {"id": "sound", "track": "audio", "at": 0, "hold": 10},
        ],
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}
        },
    }
    if alpha:
        value["metadata"] = {"astrid_layer": {"z": 1, "alpha": True}}
    return value


def test_managed_object_sizes_use_runtime_rows_and_deduplicate_digests() -> None:
    digest = "a" * 64
    registry = {
        "assets": {
            "one": {"media_id": f"sha256:{digest}", "content_sha256": digest},
            "two": {"media_id": f"sha256:{digest}", "content_sha256": digest},
        }
    }
    sizes = managed_object_sizes(
        registry,
        [{"object_id": f"sha256:{digest}", "digest": digest, "size": 1234}],
    )
    assert sizes == {digest: 1234}


def test_managed_object_sizes_reject_missing_exact_runtime_size() -> None:
    digest = "a" * 64
    registry = {
        "assets": {"one": {"media_id": digest, "content_sha256": digest}}
    }
    with pytest.raises(StorageEstimateError, match="no exact runtime object size"):
        managed_object_sizes(registry, [{"object_id": digest, "digest": digest}])


def test_h264_estimate_exposes_every_peak_storage_component() -> None:
    digest = "a" * 64
    registry = {
        "assets": {
            "one": {"media_id": digest, "content_sha256": digest},
            "two": {"media_id": digest, "content_sha256": digest},
        }
    }
    estimate = estimate_managed_render_storage(
        timeline=_timeline(),
        registry=registry,
        object_sizes={digest: 1000},
        effect_asset_sizes={"badge.png": 2000},
    )

    assert estimate["status"] == "runtime_enforced"
    assert estimate["codec"] == "h264"
    assert estimate["duration_frames"] == 300
    assert estimate["duration_seconds_rational"] == [10, 1]
    assert estimate["video_bitrate_bps"] == 15_552_000
    assert estimate["encoder_buffer_bps"] == 31_104_000
    assert estimate["managed_input_bytes"] == 1000
    assert estimate["managed_entry_bytes"] == 2000
    assert estimate["effect_asset_bytes"] == 2000
    assert estimate["audio_pcm_working_bytes"] == 3_840_000
    expected_payload = math.ceil(
        ((15_552_000 * 10 + 31_104_000) / 8) + (320_000 * 10 / 8)
    )
    assert estimate["encoded_payload_bytes"] == expected_payload
    expected_output = math.ceil(
        ((15_552_000 * 10 + 31_104_000) / 8 + 320_000 * 10 / 8) * 1.03
    ) + 1024**2
    assert estimate["estimated_output_bytes"] == expected_output
    assert estimate["phase_working_bytes"] == max(
        2000 + 2000 + estimate["audio_pcm_working_bytes"],
        2 * expected_output,
    )
    assert estimate["peak_before_guard_bytes"] == (
        estimate["base_bytes"] + estimate["phase_working_bytes"]
    )
    assert estimate["operational_guard_bytes"] >= 256 * 1024**2
    assert estimate["estimated_total_bytes"] == (
        estimate["estimated_scratch_bytes"] + estimate["estimated_output_bytes"]
    )


def test_alpha_estimate_counts_raw_frame_workspace() -> None:
    timeline = {
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [{"id": "clip", "track": "v", "at": 0, "hold": 2}],
        "theme_overrides": {
            "visual": {"canvas": {"width": 64, "height": 64, "fps": 1}}
        },
        "metadata": {"astrid_layer": {"z": 1, "alpha": True}},
    }
    estimate = estimate_managed_render_storage(
        timeline=timeline,
        registry={"assets": {}},
        object_sizes={},
    )
    assert estimate["codec"] == "prores-4444"
    bytes_per_frame = math.ceil((64 * 64 * 4 + 64) * 1.01)
    assert estimate["alpha_frame_bytes_per_frame"] == bytes_per_frame
    assert estimate["alpha_frame_working_bytes"] == bytes_per_frame * 2
    assert estimate["audio_bitrate_bps"] == 48_000 * 2 * 16
    assert estimate["phase_working_bytes"] == max(
        estimate["audio_pcm_working_bytes"]
        + estimate["alpha_frame_working_bytes"]
        + estimate["estimated_output_bytes"],
        2 * estimate["estimated_output_bytes"],
    )


def test_pcm_estimate_counts_recursive_chunk_merge_outputs() -> None:
    timeline = {
        "tracks": [
            {"id": "v", "kind": "visual", "label": "Video"},
            {"id": "a", "kind": "audio", "label": "Audio"},
        ],
        "clips": [
            {"id": "picture", "track": "v", "at": 0, "hold": 1},
            *[
                {"id": f"audio-{index}", "track": "a", "at": 0, "hold": 1}
                for index in range(32)
            ],
        ],
        "theme_overrides": {
            "visual": {"canvas": {"width": 64, "height": 64, "fps": 1}}
        },
    }
    estimate = estimate_managed_render_storage(
        timeline=timeline,
        registry={"assets": {}},
        object_sizes={},
    )
    assert estimate["audio_asset_count"] == 32
    assert estimate["merge_pcm_outputs"] == 5
    assert estimate["audio_pcm_working_bytes"] == 4 * 48_000 * (32 + 5)


def test_used_effect_asset_sizes_are_exact_and_deduplicated(tmp_path: Path) -> None:
    asset_path = tmp_path / "assets" / "badge.bin"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"badge")
    effect = SimpleNamespace(
        id="glow",
        root=tmp_path,
        metadata={"clipTypeAliases": ["shimmer"]},
        assets=(SimpleNamespace(path=Path("assets/badge.bin")),),
    )
    registry = SimpleNamespace(list=lambda *, kind: [effect] if kind == "effects" else [])
    sizes = used_effect_asset_sizes(
        {
            "clips": [
                {"clipType": "glow"},
                {"clipType": "shimmer"},
            ]
        },
        element_registry=registry,
    )
    assert sizes == {str(asset_path.resolve()): 5}
