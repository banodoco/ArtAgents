"""Unit tests for the FFmpeg backend text raster helper (no ffmpeg needed).

Color/shadow/fade/empty-content/window/anchor tests call helpers directly and
never skip. Wrap and rasterize tests need a real system TTF; they resolve one
via the module's font resolver and skip when it returns None (no bundled
font, no CI font package).
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageFont

from astrid.packs.rendering.backends.ffmpeg import text as ffmpeg_text


def _skip_if_no_font(bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = ffmpeg_text._resolve_font_path(bold)
    if font_path is None:
        pytest.skip("no system TTF available for text rasterization")
    return ImageFont.truetype(str(font_path), 42)


def test_wrap_respects_max_width_and_keeps_single_line_without_it() -> None:
    font = _skip_if_no_font()
    lines = ffmpeg_text._wrap_lines(font, "One track per concern", 200)
    assert len(lines) >= 2
    for line in lines:
        assert font.getlength(line) <= 200
    assert " ".join(lines) == "One track per concern"
    # a single word wider than maxWidth is still emitted on its own line
    assert ffmpeg_text._wrap_lines(font, "Extraordinarily", 10) == ["Extraordinarily"]
    # maxWidth <= 0 disables wrapping
    assert ffmpeg_text._wrap_lines(font, "One track per concern", 0) == [
        "One track per concern"
    ]
    assert ffmpeg_text._wrap_lines(font, "One track per concern", -5) == [
        "One track per concern"
    ]


def test_anchor_origin_bottom_center_and_top_right() -> None:
    # bottom-center caption (hype style): block bottom sits offsetY above the
    # bottom edge, horizontally centered
    x, y_top = ffmpeg_text._anchor_origin("bottom", 0.0, 132.0, 1280, 720, 72.0)
    assert x == 640.0
    assert y_top == pytest.approx(720.0 - 132.0 - 72.0)
    # top-right brand mark: offsets push away from the top-right corner
    x, y_top = ffmpeg_text._anchor_origin("top-right", 48.0, 40.0, 1280, 720, 33.6)
    assert x == 1280.0 - 48.0
    assert y_top == pytest.approx(40.0)
    # default anchor is center/middle; bare vertical anchors keep horizontal center
    assert ffmpeg_text._anchor_origin("", 0.0, 0.0, 100, 100, 20.0) == (50.0, 40.0)
    assert ffmpeg_text._anchor_origin("middle-center", 0.0, 0.0, 100, 100, 20.0) == (
        50.0,
        40.0,
    )
    x, _ = ffmpeg_text._anchor_origin("top", 10.0, 0.0, 100, 100, 20.0)
    assert x == 60.0


def test_rasterize_places_ink_in_anchored_top_right_region(tmp_path) -> None:  # W3B-2
    _skip_if_no_font(bold=True)
    dest = tmp_path / "brand.png"
    clip = {
        "id": "brand_wordmark",
        "at": 0.0,
        "hold": 10.0,
        "clipType": "text",
        "text": {
            "content": "ASTRID",
            "fontSize": 28,
            "color": "#ffffff",
            "align": "right",
            "bold": True,
        },
        "params": {"anchor": "top-right", "offsetX": 48, "offsetY": 40},
    }
    ffmpeg_text.rasterize_text_clip(clip, 1280, 720, dest)
    with Image.open(dest) as image:
        assert image.mode == "RGBA"
        assert image.size == (1280, 720)
        bbox = image.getchannel("A").getbbox()
    assert bbox is not None
    left, top, right, bottom = bbox
    assert top >= 40  # ink starts at/below the top offset
    assert right <= 1280 - 48 + 2  # ink ends at the anchor line (align right)
    assert left > 1280 / 2  # ink lives in the right region
    assert bottom < 720 / 2  # ink lives in the top region


def test_rasterize_bottom_center_caption_ignores_fades(tmp_path) -> None:
    _skip_if_no_font()
    dest = tmp_path / "caption.png"
    clip = {
        "id": "cap_search",
        "at": 4.5,
        "hold": 3.0,
        "clipType": "text",
        "effects": {"fade_in": 0.2, "fade_out": 0.25},
        "text": {
            "content": "One track per concern",
            "fontSize": 30,
            "color": "#ffffff",
            "align": "center",
        },
        "params": {
            "anchor": "bottom",
            "offsetY": 56,
            "maxWidth": 1500,
            "textShadow": "0 1px 4px rgba(0, 0, 0, 0.95)",
        },
    }
    ffmpeg_text.rasterize_text_clip(clip, 1280, 720, dest)
    with Image.open(dest) as image:
        assert image.mode == "RGBA"
        assert image.size == (1280, 720)
        bbox = image.getchannel("A").getbbox()
        _, max_alpha = image.getchannel("A").getextrema()
    assert bbox is not None
    assert bbox[1] > 720 / 2  # ink lives in the bottom band
    assert bbox[3] < 720  # and stays inside the canvas
    assert max_alpha == 255  # fades are NOT baked into the PNG (overlay applies them)


def test_parse_text_shadow_including_rgba_and_invalid() -> None:
    shadow = ffmpeg_text._parse_text_shadow("0 2px 10px rgba(0,0,0,0.75)")
    assert shadow is not None
    assert shadow.offset_x == 0.0
    assert shadow.offset_y == 2.0
    assert shadow.blur == 10.0
    assert shadow.color == (0, 0, 0, 191)
    three_part = ffmpeg_text._parse_text_shadow("2px 3px #ff0000")
    assert three_part is not None
    assert three_part.blur == 0.0
    assert three_part.color == (255, 0, 0, 255)
    spaced = ffmpeg_text._parse_text_shadow("0 1px 4px rgba(0, 0, 0, 0.95)")
    assert spaced is not None
    assert spaced.color == (0, 0, 0, 242)
    # missing/empty -> None
    assert ffmpeg_text._parse_text_shadow(None) is None
    assert ffmpeg_text._parse_text_shadow("") is None
    assert ffmpeg_text._parse_text_shadow("   ") is None
    # any other invalid input raises
    for bad in ("1px", "a b c", "1px 2px not-a-color"):
        with pytest.raises(ValueError):
            ffmpeg_text._parse_text_shadow(bad)


def test_parse_color_hex_named_and_rgba() -> None:
    assert ffmpeg_text._parse_color("#ffffff") == (255, 255, 255, 255)
    assert ffmpeg_text._parse_color("white") == (255, 255, 255, 255)
    assert ffmpeg_text._parse_color("rgba(0,0,0,0.75)") == (0, 0, 0, 191)


def test_parse_fades_map_none_and_empty() -> None:
    assert ffmpeg_text._parse_fades(None) == (0.0, 0.0)
    assert ffmpeg_text._parse_fades({}) == (0.0, 0.0)
    assert ffmpeg_text._parse_fades([]) == (0.0, 0.0)
    assert ffmpeg_text._parse_fades({"fade_in": 0.2, "fade_out": 0.25}) == (0.2, 0.25)
    assert ffmpeg_text._parse_fades({"fade_in": 1}) == (1.0, 0.0)


def test_parse_fades_list_independent_first_match() -> None:
    assert ffmpeg_text._parse_fades([{"fade_in": 0.5}, {"fade_out": 0.25}]) == (
        0.5,
        0.25,
    )
    # first numeric fade_in wins even when a later item repeats it
    assert ffmpeg_text._parse_fades(
        [{"fade_in": 1.0}, {"fade_in": 2.0, "fade_out": 0.75}]
    ) == (1.0, 0.75)


def test_parse_fades_rejects_unknown_negative_bool_and_non_numeric() -> None:
    for bad in (
        {"slide": 1},
        [{"fade_in": -1}],
        [{"fade_in": True}],
        [{"fade_in": "0.2"}],
        ["nope"],
        "nope",
    ):
        with pytest.raises(ValueError):
            ffmpeg_text._parse_fades(bad)


def test_rasterize_refuses_empty_or_missing_content(tmp_path) -> None:
    base = {"id": "t", "at": 0.0, "hold": 1.0, "clipType": "text"}
    with pytest.raises(ValueError):
        ffmpeg_text.rasterize_text_clip(
            {**base, "text": {"content": ""}}, 320, 180, tmp_path / "a.png"
        )
    with pytest.raises(ValueError):
        ffmpeg_text.rasterize_text_clip(
            {**base, "text": {}}, 320, 180, tmp_path / "b.png"
        )


def test_text_window_uses_canonical_duration() -> None:
    assert ffmpeg_text._text_window({"id": "t", "at": 4.5, "hold": 3.0}) == (4.5, 7.5)
    assert ffmpeg_text._text_window({"id": "t", "at": 0.0, "hold": 10.0}) == (0.0, 10.0)
    # missing `at` defaults to 0 like ThreeTimelineComposition
    assert ffmpeg_text._text_window({"id": "t", "hold": 2}) == (0.0, 2.0)
    # hold: 0, negative hold, and no duration at all fail
    with pytest.raises(ValueError):
        ffmpeg_text._text_window({"id": "t", "at": 1.0, "hold": 0})
    with pytest.raises(ValueError):
        ffmpeg_text._text_window({"id": "t", "at": 1.0, "hold": -1})
    with pytest.raises(ValueError):
        ffmpeg_text._text_window({"id": "t", "at": 1.0})
