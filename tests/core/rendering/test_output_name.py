"""Output-name validation for the ``rendering.render`` facade (T4.2).

The executor facade owns basename safety. The shared render-output policy owns
the media suffix because it can inspect the timeline stamp and profile.
"""

from __future__ import annotations

import pytest

from astrid.core.rendering.output_policy import (
    RenderOutputPolicyError,
    validate_render_output_policy,
)
from astrid.packs.rendering.executors.render.run import (
    DEFAULT_OUTPUT_NAME,
    validate_output_name,
)


@pytest.mark.parametrize(
    "name",
    [
        "hype.mp4",  # Hype's default sentinel is preserved.
        "iteration.mp4",
        "my.video.name.mp4",
        "clip_01.mp4",
        "alpha-layer.mov",
        "future.webm",
        "extensionless",
    ],
)
def test_valid_output_names_preserved(name: str) -> None:
    assert validate_output_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "a/b.mp4",  # forward separator
        "a\\b.mp4",  # backslash separator
        "sub/out.mp4",
        "/abs.mp4",  # absolute path
        "../evil.mp4",  # traversal
        "..",
        ".",
        "..mp4",  # traversal-looking prefix
    ],
)
def test_invalid_output_names_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        validate_output_name(name)


def test_default_output_name_is_hype_sentinel() -> None:
    assert DEFAULT_OUTPUT_NAME == "hype.mp4"
    assert validate_output_name(DEFAULT_OUTPUT_NAME) == "hype.mp4"


def test_rejection_messages_are_actionable() -> None:
    with pytest.raises(ValueError, match="separators"):
        validate_output_name("a/b.mp4")
    with pytest.raises(ValueError, match="traverse"):
        validate_output_name("../evil.mp4")
    with pytest.raises(ValueError, match="empty"):
        validate_output_name("")


def test_shared_policy_allows_only_alpha_stamped_mov() -> None:
    alpha = {"metadata": {"astrid_layer": {"z": 1, "alpha": True}}}
    opaque = {"tracks": [], "clips": []}

    assert (
        validate_render_output_policy("layer.mov", timeline=alpha, profile=None)
        == "layer.mov"
    )
    with pytest.raises(RenderOutputPolicyError, match="not stamped"):
        validate_render_output_policy("opaque.mov", timeline=opaque, profile=None)
    assert (
        validate_render_output_policy("opaque.mp4", timeline=opaque, profile=None)
        == "opaque.mp4"
    )


def test_shared_policy_rejects_incompatible_explicit_alpha_mov_profile() -> None:
    alpha = {"metadata": {"astrid_layer": {"z": 1, "alpha": True}}}
    incompatible = {
        "container": "mov",
        "time_base": [1, 90000],
        "video_codec": "h264",
        "video_profile": None,
        "video_level": None,
        "pixel_format": "yuv420p",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channel_layout": "stereo",
    }

    with pytest.raises(RenderOutputPolicyError, match="incompatible explicit") as exc_info:
        validate_render_output_policy(
            "layer.mov", timeline=alpha, profile=incompatible
        )
    assert "video_codec='h264'" in str(exc_info.value)
    assert "audio_codec='aac'" in str(exc_info.value)
