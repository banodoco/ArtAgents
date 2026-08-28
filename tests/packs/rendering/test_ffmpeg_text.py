"""Unit tests for FFmpeg backend text support: the raster helper and the
pure overlay argv builder (no ffmpeg needed).

Color/shadow/fade/empty-content/window/anchor tests call helpers directly and
never skip. Wrap and rasterize tests need a real system TTF; they resolve one
via the module's font resolver and skip when it returns None (no bundled
font, no CI font package).
"""

from __future__ import annotations

import dataclasses

import pytest
from PIL import Image, ImageFont

from astrid.packs.rendering.backends.ffmpeg import command
from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_run
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


# ---------------------------------------------------------------------------
# Overlay argv tests (T3): the command builder consumes caller-provided
# TextOverlaySpec tuples — no rasterization, no asset demands from text
# clips, PNG inputs capped at absolute END.
# ---------------------------------------------------------------------------


def _overlay_timeline() -> dict:
    return {
        "theme_overrides": {
            "visual": {"canvas": {"width": 320, "height": 180, "fps": 30}}
        },
        "tracks": [
            {"id": "v", "kind": "visual", "label": "V"},
            {"id": "a", "kind": "audio", "label": "A"},
        ],
        "clips": [
            {
                "id": "video",
                "at": 0,
                "track": "v",
                "clipType": "media",
                "asset": "main",
                "from": 0,
                "to": 4,
                "speed": 1,
                "volume": 0,
            },
            {
                "id": "music",
                "at": 0,
                "track": "a",
                "clipType": "media",
                "asset": "main",
                "from": 0,
                "to": 4,
                "speed": 1,
                "volume": 0.75,
            },
            # Text clip: no asset key — must not demand one.
            {
                "id": "title",
                "at": 1.0,
                "track": "v",
                "clipType": "text",
                "hold": 2.0,
                "text": {"content": "Hello"},
            },
        ],
    }


def _overlay_inputs(tmp_path, **overrides) -> command.RenderCommandInputs:
    registry = {
        "assets": {
            "main": {
                "file": str(tmp_path / "source.mp4"),
                "type": "video/mp4",
                "duration": 4,
                "resolution": "320x180",
                "fps": 30,
            }
        }
    }
    inputs = command.RenderCommandInputs(
        timeline_path=tmp_path / "timeline.json",
        assets_path=tmp_path / "assets.json",
        output_path=tmp_path / "out.mp4",
        timeline_data=_overlay_timeline(),
        registry=registry,
        text_overlays=(
            command.TextOverlaySpec(
                path=str(tmp_path / "title.png"),
                at=1.0,
                end=3.0,
                fade_in=0.25,
                fade_out=0.5,
            ),
        ),
    )
    return dataclasses.replace(inputs, **overrides) if overrides else inputs


def _filter_complex(argv: list[str]) -> str:
    return argv[argv.index("-filter_complex") + 1]


def test_overlay_png_inputs_come_after_asset_inputs(tmp_path) -> None:
    argv = command.build_render_command_from_inputs(_overlay_inputs(tmp_path))
    i_asset = argv.index(str(tmp_path / "source.mp4"))
    i_png = argv.index(str(tmp_path / "title.png"))
    # PNG inputs are appended after the asset inputs, looped and capped.
    assert argv[i_asset + 1 : i_png] == ["-loop", "1", "-t", "3.000000", "-i"]
    assert argv.count("-i") == 2  # the text clip demanded no extra asset


def test_overlay_input_t_is_absolute_end_not_duration(tmp_path) -> None:
    argv = command.build_render_command_from_inputs(_overlay_inputs(tmp_path))
    i_png = argv.index(str(tmp_path / "title.png"))
    overlay_input_index = argv[:i_png].count("-i") - 1
    assert overlay_input_index == 1  # the PNG sits after the one asset input
    # ONE assertion: -t caps the looped PNG input at absolute END (3.0),
    # not the window length (2.0).
    assert argv[i_png - 5 : i_png] == ["-loop", "1", "-t", "3.000000", "-i"]


def test_no_shortest_with_overlays(tmp_path) -> None:
    argv = command.build_render_command_from_inputs(_overlay_inputs(tmp_path))
    assert "-shortest" not in argv


def test_overlay_chain_spine_first_png_secondary(tmp_path) -> None:
    steps = _filter_complex(
        command.build_render_command_from_inputs(_overlay_inputs(tmp_path))
    ).split(";")
    assert any(f.endswith("concat=n=1:v=1:a=0[vout]") for f in steps)
    source = next(f for f in steps if f.startswith("[1:v]format=rgba"))
    assert source == (
        "[1:v]format=rgba,"
        "fade=t=in:st=1.000000:d=0.250000:alpha=1,"
        "fade=t=out:st=2.500000:d=0.500000:alpha=1[ov0]"
    )
    overlay = next(f for f in steps if "overlay=0:0" in f)
    # spine [vout] is the overlay main; the PNG [ov0] is secondary; the
    # final spine label stays [vout].
    assert overlay == (
        "[vout][ov0]overlay=0:0:"
        "enable='between(t,1.000000,3.000000)':format=auto[vout]"
    )


def test_filtergraph_is_one_argv_element_with_literal_quotes(tmp_path) -> None:
    argv = command.build_render_command_from_inputs(_overlay_inputs(tmp_path))
    assert argv.count("-filter_complex") == 1
    graph = _filter_complex(argv)
    assert "enable='between(t,1.000000,3.000000)'" in graph
    assert "[0:v]trim=start=0.000000:end=4.000000" in graph
    assert graph.count("'") == 2  # exactly the enable quoting, untouched


def test_both_fades_emitted_even_at_zero_duration(tmp_path) -> None:
    inputs = _overlay_inputs(
        tmp_path,
        text_overlays=(
            command.TextOverlaySpec(
                path=str(tmp_path / "title.png"),
                at=1.0,
                end=3.0,
                fade_in=0.0,
                fade_out=0.0,
            ),
        ),
    )
    graph = _filter_complex(command.build_render_command_from_inputs(inputs))
    assert "fade=t=in:st=1.000000:d=0.000000:alpha=1" in graph
    assert "fade=t=out:st=3.000000:d=0.000000:alpha=1" in graph


def test_stream_copy_vetoed_when_overlays_present(tmp_path) -> None:
    inputs = _overlay_inputs(tmp_path)
    overlay_argv = command.build_render_command_from_inputs(
        dataclasses.replace(inputs, stream_copy_allowed=True)
    )
    assert overlay_argv[overlay_argv.index("-c:v") + 1] == "libx264"
    assert overlay_argv[overlay_argv.index("-map") + 1] == "[vout]"
    # The same inputs without overlays still qualify for stream copy.
    plain_argv = command.build_render_command_from_inputs(
        dataclasses.replace(inputs, text_overlays=(), stream_copy_allowed=True)
    )
    assert plain_argv[plain_argv.index("-c:v") + 1] == "copy"


def test_text_clip_does_not_demand_asset(tmp_path) -> None:
    inputs = _overlay_inputs(tmp_path)
    filters, copy_video_input = command.build_filter_graph(inputs)
    assert copy_video_input is None
    assert any(f.endswith("concat=n=1:v=1:a=0[vout]") for f in filters)
    argv = command.build_render_command_from_inputs(
        dataclasses.replace(inputs, text_overlays=())
    )
    assert argv.count("-i") == 1  # only the media asset became an input


def test_multiple_overlays_chain_in_caller_order_last_on_top(tmp_path) -> None:
    overlays = (
        command.TextOverlaySpec(
            path=str(tmp_path / "a.png"),
            at=1.0,
            end=2.0,
            fade_in=0.0,
            fade_out=0.0,
        ),
        command.TextOverlaySpec(
            path=str(tmp_path / "b.png"),
            at=2.5,
            end=3.5,
            fade_in=0.0,
            fade_out=0.0,
        ),
    )
    argv = command.build_render_command_from_inputs(
        _overlay_inputs(tmp_path, text_overlays=overlays)
    )
    graph = _filter_complex(argv)
    assert (
        "[vout][ov0]overlay=0:0:"
        "enable='between(t,1.000000,2.000000)':format=auto[vout1]" in graph
    )
    assert (
        "[vout1][ov1]overlay=0:0:"
        "enable='between(t,2.500000,3.500000)':format=auto[vout]" in graph
    )
    i_a = argv.index(str(tmp_path / "a.png"))
    i_b = argv.index(str(tmp_path / "b.png"))
    assert (argv[i_a - 2], argv[i_b - 2]) == ("2.000000", "3.500000")
    assert i_a < i_b  # caller order kept; later overlays composite on top


def test_text_overlay_specs_windows_fades_and_caller_order(  # W3B-3
    tmp_path, monkeypatch
) -> None:
    rasterized: list[str] = []

    def fake_rasterize(clip, width, height, dest):
        assert (width, height) == (320, 180)  # canvas via timeline_canvas
        rasterized.append(dest.name)
        dest.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(ffmpeg_run, "rasterize_text_clip", fake_rasterize)

    timeline = _overlay_timeline()
    title = timeline["clips"][2]
    title["effects"] = [{"fade_in": 0.25}, {"fade_out": 0.5}]
    timeline["tracks"].append({"id": "v2", "kind": "visual", "label": "V2"})
    lower = {
        "id": "lower",
        "at": 0.5,
        "track": "v2",
        "clipType": "text",
        "hold": 1.5,
        "text": {"content": "Lower"},
    }
    timeline["clips"].append(lower)

    specs = ffmpeg_run._text_overlay_specs(timeline, rasterize_dir=tmp_path)

    assert rasterized == ["text-0.png", "text-1.png"]
    # Track array order first: v (index 0) before v2 even though "lower"
    # starts earlier; windows and fades come from the canonical parsers.
    assert [(spec.at, spec.end) for spec in specs] == [
        ffmpeg_text._text_window(title),
        ffmpeg_text._text_window(lower),
    ]
    assert (specs[0].fade_in, specs[0].fade_out) == ffmpeg_text._parse_fades(
        title.get("effects")
    ) == (0.25, 0.5)
    assert (specs[1].fade_in, specs[1].fade_out) == ffmpeg_text._parse_fades(
        lower.get("effects")
    ) == (0.0, 0.0)
    assert [spec.path for spec in specs] == [
        str(tmp_path / "text-0.png"),
        str(tmp_path / "text-1.png"),
    ]
