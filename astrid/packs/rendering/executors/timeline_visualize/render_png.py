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
_FOCUS_RING = (255, 214, 100)  # #FFD664 — bright gold focus outline
_LANE_EDGE = (58, 58, 68)  # #3A3A44
_CLIP = (183, 156, 228)  # #B79CE4
_CLIP_EDGE = (143, 111, 208)  # #8F6FD0
_CONTINUATION = (95, 168, 160)  # #5FA8A0
_GAP_MARKER = (224, 164, 88)  # #E0A458
_SPEECH = (70, 183, 200)  # #46B7C8
_CAPTION = (231, 196, 90)  # #E7C45A
_PIXEL_TEXT = (116, 116, 128)  # #747480
_TICK = (138, 138, 150)  # #8A8A96
_TEXT = (250, 250, 250)  # #FAFAFA
_MUTED = (184, 184, 196)  # #B8B8C4

_FILL_BY_KIND = {
    "clip": _CLIP,
    "continuation": _CONTINUATION,
    "gap_marker": _GAP_MARKER,
    "speech": _SPEECH,
    "caption": _CAPTION,
    "pixel_text": _PIXEL_TEXT,
}

_BADGE_KINDS = frozenset({"breadcrumb", "snapshot_badge", "scope_badge", "cue"})

_FONT_SIZE_BY_KIND = {
    "breadcrumb": 26,
    "snapshot_badge": 26,
    "scope_badge": 24,
    "cue": 22,
    "label": 16,
    "track_lane": 18,
    "clip": 18,
    "continuation": 18,
    "gap_marker": 16,
    "ruler_tick": 16,
    "speech": 16,
    "caption": 16,
    "pixel_text": 16,
    "text_lane": 16,
}

#: Bottom strip inside clip-family cards reserved for the object label; the
#: thumbnail is pasted above it (with a small top buffer).
_LABEL_STRIP_H = 20.0

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


_CUT_EDGE = (20, 20, 25)  # background color for the torn notches

#: Page chrome gutters (matches layout.py's page margins) used to detect which
#: side of an in-lane continuation card is cut by the page boundary.
_PAGE_LEFT_X = 40.0
_PAGE_RIGHT_X = 1840.0


def _torn_edge(draw: ImageDraw.ImageDraw, box: Box, *, scale: int) -> None:
    """Draw a zigzag 'torn paper' edge + ellipsis on the cut side of an
    in-lane continuation card so a page-break clip is explicit, not a
    mysterious truncated rectangle (user: 'say this is cut off')."""
    x0 = _px(box.x, scale)
    x1 = _px(box.x + box.w, scale) - 1
    y0 = _px(box.y, scale)
    y1 = _px(box.y + box.h, scale) - 1
    # Cut side: the card edge nearest a page boundary.
    near_left = (box.x - _PAGE_LEFT_X) < (box.x + box.w - _PAGE_RIGHT_X)
    edge_x = x0 if near_left else x1
    # Zigzag notches into the fill along the cut edge.
    step = max(4, (y1 - y0) // 8)
    teeth = 4
    depth = max(3, int((y1 - y0) / 12))
    for i in range(teeth):
        ty = y0 + int((i + 0.5) * (y1 - y0) / teeth)
        direction = 1 if i % 2 == 0 else -1
        draw.line(
            [(edge_x, ty - step // 2), (edge_x + direction * depth, ty), (edge_x, ty + step // 2)],
            fill=_CUT_EDGE,
            width=max(1, scale),
        )
    # "…" ellipsis badge just inside the cut edge, centered vertically.
    font = _bundled_font(20 * scale)
    dot = "…"
    dot_w = draw.textlength(dot, font=font)
    dx = edge_x + depth + 2 * scale if near_left else edge_x - depth - dot_w - 2 * scale
    draw.text((dx, y0 + (y1 - y0) // 2 - 10 * scale), dot, font=font, fill=_TEXT)


def _contain_fit(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize an image to FIT INSIDE (target_w, target_h) without cropping.

    The full frame is always visible; empty space is letterboxed (lane fill).
    """

    img_w, img_h = image.size
    if img_w <= 0 or img_h <= 0 or target_w <= 0 or target_h <= 0:
        return image.copy()
    scale = min(target_w / img_w, target_h / img_h)
    new_w = max(1, int(round(img_w * scale)))
    new_h = max(1, int(round(img_h * scale)))
    return image.resize((new_w, new_h), Image.LANCZOS)


def _cover_fit(image: Image.Image, target_w: int, target_h: int, *, anchor_left: bool) -> Image.Image:
    """Resize an image to FILL (target_w, target_h), cropping overflow.

    Used for page-break continuation cards: the visible portion of a clip
    that spans a page boundary is shown cropped to the card, anchored at the
    cut side so the revealed part aligns with the page (user: "show the
    partially revealed image, cropped off in the side with the delineation").
    """

    img_w, img_h = image.size
    if img_w <= 0 or img_h <= 0 or target_w <= 0 or target_h <= 0:
        return image.copy()
    scale = max(target_w / img_w, target_h / img_h)
    new_w = max(1, int(round(img_w * scale)))
    new_h = max(1, int(round(img_h * scale)))
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    # Crop the overflow: keep the anchor side, drop the far side.
    left = 0 if anchor_left else new_w - target_w
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _rect(
    draw: ImageDraw.ImageDraw,
    box: Box,
    fill: tuple[int, int, int],
    *,
    scale: int,
    outline: tuple[int, int, int] | None = None,
    width: int = 1,
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
        width=width,
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
        if item.kind in {"track_lane", "text_lane"}:
            _rect(draw, item.box, _LANE, scale=scale, outline=_LANE_EDGE)
            if item.label:
                _label(
                    draw,
                    item.box,
                    item.label,
                    scale=scale,
                    size=_FONT_SIZE_BY_KIND[item.kind],
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

    # Torn-edge overlay on in-lane continuation cards: a clip segment cut off
    # by a page break reads as a clipped rectangle.  A zigzag edge on the cut
    # side + a "..." badge makes the cut explicit (user: "show part of it and
    # say this is cut off").  The cut side is the one abutting the page
    # boundary: page 1 cards are cut on the right, later pages on the left.
    for item in clip_family:
        if item.kind != "continuation":
            continue
        _torn_edge(draw, item.box, scale=scale)

    # Focus rings: a bright outline around the focused clip so a VLM reading
    # the page never mistakes a wide neighbor (e.g. the audio bar) for the
    # subject. Grok UX: the root FOCUS clip needs visual emphasis. The ring
    # must be outline-only — filling it would paint over the clip bar.
    for item in page.objects:
        if item.kind == "focus_ring":
            draw.rectangle(
                [
                    _px(item.box.x, scale),
                    _px(item.box.y, scale),
                    _px(item.box.x + item.box.w, scale) - 1,
                    _px(item.box.y + item.box.h, scale) - 1,
                ],
                outline=_FOCUS_RING,
                width=4,
            )

    # Paste the verified original frame into each clip card (cover-fit inside
    # the box, leaving the bottom strip for the label). This is the "real
    # images in the pages" surface: an agent sees the actual storyboard
    # frame, not an abstract block. Only verified_original local images.
    # Continuation cards (page-break tails) paste the VISIBLE portion of the
    # frame, cover-cropped to the card and anchored at the cut side.
    for item in clip_family:
        if item.kind not in ("clip", "continuation") or not item.thumbnail_path:
            continue
        try:
            thumb = Image.open(item.thumbnail_path)
            thumb.load()
        except (OSError, ValueError):
            continue
        box = item.box
        pad = 3
        label_strip = int(_LABEL_STRIP_H) if item.label else 4
        # Buffer above the image so the frame doesn't hug the card top (user:
        # "give them a little bit of buffer for aesthetics").  The label strip
        # is reserved at the bottom; the image is centered in the remaining
        # space.
        top_buffer = 6 if item.label else 2
        target_w = max(2, int(box.w * scale) - pad * 2)
        target_h = max(2, int(box.h * scale) - top_buffer - label_strip - pad)
        if target_w < 8 or target_h < 8:
            continue
        if item.kind == "continuation":
            # The cut side: page-1 tails are cut on the right (show the head,
            # anchor left); later-page continuations are cut on the left
            # (show the tail, anchor right).
            near_left = (box.x - _PAGE_LEFT_X) < (box.x + box.w - _PAGE_RIGHT_X)
            thumb = _cover_fit(thumb, target_w, target_h, anchor_left=near_left)
            x = int(box.x * scale) + pad
        else:
            # Contain-fit: the FULL frame is always visible, centered in the
            # box (letterboxed on the lane fill — never cropped).
            thumb = _contain_fit(thumb, target_w, target_h)
            x = int(box.x * scale) + pad + (target_w - thumb.width) // 2
        y = int(box.y * scale) + top_buffer + (target_h - thumb.height) // 2
        image.paste(thumb, (x, y))

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

    # Object labels (clip-family only; omitted labels stay out).  The label
    # sits in the card's bottom strip (below the image) so it never overlaps
    # the frame (user: images should have buffer, not clip to the top).
    for item in page.objects:
        if item.kind not in _FILL_BY_KIND or item.lane_index is None:
            continue
        if item.label is None or item.omitted_reason is not None:
            continue
        size = _FONT_SIZE_BY_KIND[item.kind]
        label_box = item.box
        if item.kind in ("clip", "continuation") and item.box.h >= 40:
            # Narrow cards: bottom-aligned label inside the card.
            label_box = Box(item.box.x, item.box.y + item.box.h - _LABEL_STRIP_H, item.box.w, _LABEL_STRIP_H)
        _label(
            draw,
            label_box,
            item.label,
            scale=scale,
            size=size,
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
