"""Output-name validation for the ``rendering.render`` facade (T4.2).

The executor manifest exposes ``output_name`` as an ordinary input defaulting
to Hype's ``hype.mp4`` sentinel.  The facade validates it: separators,
traversal, and non-``.mp4`` extensions are rejected; declared plain ``.mp4``
names (including the default) are preserved unchanged.
"""

from __future__ import annotations

import pytest

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
        "out.mov",  # wrong extension
        "out",  # no extension
        "out.mp3",
        "hype.mp4.txt",
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
    with pytest.raises(ValueError, match=r"\.mp4"):
        validate_output_name("out.mov")
    with pytest.raises(ValueError, match="empty"):
        validate_output_name("")
