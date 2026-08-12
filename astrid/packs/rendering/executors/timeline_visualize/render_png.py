"""Deterministic Pillow PNG rendering of one :class:`LayoutPage`.

R11: the PNG adapter consumes the same :class:`LayoutPage` geometry as the SVG
adapter (no re-layout) and emits a 1920 x 1080 x ``scale`` RGB PNG that is
byte-stable for identical input under the pinned Pillow runtime.  Text uses a
repo-bundled TrueType font (``fonts/PowerGrotesk-Regular.ttf``); there is no
system-font lookup and no SVG rasterizer anywhere in the pipeline.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

from astrid.packs.rendering.executors.timeline_visualize.layout import (
    Box,
    LayoutPage,
)

# Theme-consistent palette, intentionally duplicated from render_svg.py so the
# two adapters remain independent consumers of the layout model.
_BG = (20, 20, 25)  # #141419
_LANE = (38, 38, 46)  # #26262E
_LANE_EDGE = (58, 58, 68)  # #3A3A44
_CLIP = (183, 156, 228)  # #B79CE4
_CLIP_EDGE = (143, 111, 208)  # #8F6FD0
_CONTINUATION = (95, 168, 160)  # #5FA8A0
_GAP_MARKER = (224, 164, 88)  # #E0A458
_TICK = (138, 138, 150)  # #8A8A96
_TEXT = (250, 250, 250)  # #FAFAFA
_MUTED = (184, 184, 196)  # #B8B8C4

_FILL_BY_KIND = {
    "clip": _CLIP,
    "continuation": _CONTINUATION,
    "gap_marker": _GAP_MARKER,
}

_BADGE_KINDS = frozenset({"breadcrumb", "snapshot_badge", "scope_badge"})

_FONT_SIZE_BY_KIND = {
    "breadcrumb": 26,
    "snapshot_badge": 26,
    "scope_badge": 24,
    "label": 16,
    "track_lane": 18,
    "clip": 18,
    "continuation": 18,
    "gap_marker": 16,
    "ruler_tick": 16,
}

# Bundled TrueType font: repo-owned, license-safe (already tracked in the
# repository), identical on every host.  Never falls back to a system font.
_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_BUNDLED_FONT_PATH = _FONT_DIR / "PowerGrotesk-Regular.ttf"

# Fixed metadata so PNG bytes do not depend on environment or wall time.
_DPI = (72, 72)
_COMPRESS_LEVEL = 6
_SOFTWARE_TAG = "astrid/timeline-visualize/render_png"


def _bundled_font(size: int) -> ImageFont.FreeTypeFont:
    if not _BUNDLED_FONT_PATH.is_file():
        raise FileNotFoundError(
            f"bundled font missing at {_BUNDLED_FONT_PATH}; "
            "deterministic PNG rendering requires the repo-owned TTF"
        )
    return ImageFont.truetype(str(_BUNDLED_FONT_PATH), size)


def _px(value: float, scale: int) -> int:
    return int(round(value * scale))


def _rect(
    draw: ImageDraw.ImageDraw,
    box: Box,
    fill: tuple[int, int, int],
    *,
    scale: int,
    outline: tuple[int, int, int] | None = None,
) -> None:
    draw.rectangle(
        [
            _px(box.x, scale),
            _px(box.y, scale),
            _px(box.x + box.w, scale) - 1,
            _px(box.y + box.h, scale) - 1,
        ],
        fill=fill,
        outline=outline,
    )


def _label(
    draw: ImageDraw.ImageDraw,
    box: Box,
    content: str,
    *,
    scale: int,
    size: int,
    fill: tuple[int, int, int],
    pad_x: int = 8,
) -> None:
    font = _bundled_font(size * scale)
    draw.text(
        (_px(box.x, scale) + pad_x * scale, _px(box.y, scale)),
        content,
        font=font,
        fill=fill,
    )


def render_page_png(page: LayoutPage, *, scale: int = 1) -> bytes:
    """Render one layout page to deterministic RGB PNG bytes.

    Painting order matches the SVG adapter: background, lane bands
    (topmost-first), clip-family boxes (bottom-to-top by ``z_order``), ruler
    ticks, chrome badges, object labels, footer continuations.
    """

    if not isinstance(page, LayoutPage):
        raise TypeError("page must be a LayoutPage")
    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 1:
        raise ValueError("scale must be a positive integer")

    width = page.width * scale
    height = page.height * scale
    image = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(image)

    # Lane bands: topmost-first reading order from page.objects.
    for item in page.objects:
        if item.kind == "track_lane":
            _rect(draw, item.box, _LANE, scale=scale, outline=_LANE_EDGE)
            if item.label:
                _label(
                    draw,
                    item.box,
                    item.label,
                    scale=scale,
                    size=_FONT_SIZE_BY_KIND["track_lane"],
                    fill=_MUTED,
                    pad_x=10,
                )

    # Clip-family boxes painted bottom-to-top by z_order.
    clip_family = [
        item
        for item in page.objects
        if item.kind in _FILL_BY_KIND and item.lane_index is not None
    ]
    for item in sorted(clip_family, key=lambda obj: obj.z_order):
        _rect(
            draw,
            item.box,
            _FILL_BY_KIND[item.kind],
            scale=scale,
            outline=_CLIP_EDGE if item.kind == "clip" else None,
        )

    # Ruler ticks (the tick itself; its text is a separate ``label`` object).
    for item in page.objects:
        if item.kind == "ruler_tick":
            _rect(draw, item.box, _TICK, scale=scale)

    # Axis/ruler labels: every ``label`` LayoutObject is drawn at the box the
    # layout provided, as muted text over the page (mirrors render_svg.py).
    for item in page.objects:
        if item.kind == "label" and item.label is not None:
            _label(
                draw,
                item.box,
                item.label,
                scale=scale,
                size=_FONT_SIZE_BY_KIND["label"],
                fill=_MUTED,
                pad_x=4,
            )

    # Chrome badges.
    for item in page.objects:
        if item.kind in _BADGE_KINDS:
            _rect(draw, item.box, _LANE, scale=scale, outline=_LANE_EDGE)
            if item.label:
                _label(
                    draw,
                    item.box,
                    item.label,
                    scale=scale,
                    size=_FONT_SIZE_BY_KIND.get(item.kind, 20),
                    fill=_TEXT,
                )

    # Object labels (clip-family only; omitted labels stay out).
    for item in page.objects:
        if item.kind not in _FILL_BY_KIND or item.lane_index is None:
            continue
        if item.label is None or item.omitted_reason is not None:
            continue
        _label(
            draw,
            item.box,
            item.label,
            scale=scale,
            size=_FONT_SIZE_BY_KIND[item.kind],
            fill=_TEXT,
        )

    # Footer continuation markers (lane_index is None).
    for item in page.objects:
        if item.kind == "continuation" and item.lane_index is None:
            _rect(draw, item.box, _CONTINUATION, scale=scale, outline=_CLIP_EDGE)
            if item.label:
                _label(
                    draw,
                    item.box,
                    item.label,
                    scale=scale,
                    size=_FONT_SIZE_BY_KIND["continuation"],
                    fill=_TEXT,
                )

    info = PngInfo()
    info.add_text("Software", _SOFTWARE_TAG)
    info.add_text("Layout", page.layout)
    info.add_text("PageId", page.page_id)

    buffer = io.BytesIO()
    image.save(
        buffer,
        format="PNG",
        compress_level=_COMPRESS_LEVEL,
        dpi=_DPI,
        pnginfo=info,
    )
    return buffer.getvalue()


__all__ = ["render_page_png", "_BUNDLED_FONT_PATH"]
