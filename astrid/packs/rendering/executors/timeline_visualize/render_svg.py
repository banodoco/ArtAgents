"""Deterministic raw-SVG rendering of one :class:`LayoutPage`.

R11: the SVG adapter consumes the renderer-independent :class:`LayoutPage`
geometry exactly (no re-layout) and emits a 1920 x 1080 SVG document that is
byte-stable for identical input.  It never shells out to an SVG rasterizer,
never reads a system font (text uses a generic ``font-family`` stack only),
and embeds no timestamps or entropy sources.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from astrid.packs.rendering.executors.timeline_visualize.layout import (
    Box,
    LayoutPage,
)

# Theme-consistent palette shared with the PNG adapter by convention only;
# each adapter keeps its own copy so both stay independent consumers of the
# layout model.
_BG = "#141419"
_LANE = "#26262E"
_LANE_EDGE = "#3A3A44"
_CLIP = "#B79CE4"
_CLIP_EDGE = "#8F6FD0"
_CONTINUATION = "#5FA8A0"
_GAP_MARKER = "#E0A458"
_SPEECH = "#46B7C8"
_CAPTION = "#E7C45A"
_PIXEL_TEXT = "#747480"
_TICK = "#8A8A96"
_TEXT = "#FAFAFA"
_MUTED = "#B8B8C4"

# Generic font families only: no system-font dependency and no named system
# faces.  Consumers (browsers, editors) resolve the generic keywords locally;
# nothing in this module rasterizes text.
_FONT_FAMILY = "ui-monospace, monospace"

_FILL_BY_KIND = {
    "clip": _CLIP,
    "continuation": _CONTINUATION,
    "gap_marker": _GAP_MARKER,
    "speech": _SPEECH,
    "caption": _CAPTION,
    "pixel_text": _PIXEL_TEXT,
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
    "speech": 16,
    "caption": 16,
    "pixel_text": 16,
    "text_lane": 16,
}


def _num(value: float) -> str:
    """Format a coordinate without scientific notation or trailing zeros."""

    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _rect(box: Box, fill: str, *, stroke: str | None = None, sw: float = 1.0) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{_num(sw)}"' if stroke else ""
    return (
        f'<rect x="{_num(box.x)}" y="{_num(box.y)}" '
        f'width="{_num(box.w)}" height="{_num(box.h)}" fill="{fill}"{stroke_attr}/>'
    )


def _text(
    box: Box,
    content: str,
    *,
    size: int,
    fill: str,
    baseline_ratio: float = 0.62,
    pad_x: float = 8.0,
    pad_y: float = 0.0,
) -> str:
    """One text element anchored inside ``box`` (top-left-ish placement)."""

    x = box.x + pad_x
    y = box.y + pad_y + box.h * baseline_ratio
    return (
        f'<text x="{_num(x)}" y="{_num(y)}" '
        f'font-family="{_FONT_FAMILY}" font-size="{size}" fill="{fill}">'
        f"{escape(content)}</text>"
    )


def render_page_svg(page: LayoutPage) -> str:
    """Return a byte-stable 1920 x 1080 SVG document for one layout page.

    Paint order is deterministic: background, lane bands (topmost-first),
    clip/continuation/gap boxes (bottom-to-top by ``z_order``), ruler ticks,
    chrome badges, object labels, then footer continuation markers.
    """

    if not isinstance(page, LayoutPage):
        raise TypeError("page must be a LayoutPage")

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page.width}" '
        f'height="{page.height}" viewBox="0 0 {page.width} {page.height}">',
        _rect(Box(0.0, 0.0, float(page.width), float(page.height)), _BG),
    ]

    # Lane bands: topmost-first reading order from page.objects.
    for item in page.objects:
        if item.kind in {"track_lane", "text_lane"}:
            parts.append(_rect(item.box, _LANE, stroke=_LANE_EDGE))
            if item.label:
                parts.append(
                    _text(
                        item.box,
                        item.label,
                        size=_FONT_SIZE_BY_KIND[item.kind],
                        fill=_MUTED,
                        baseline_ratio=0.38,
                        pad_x=10.0,
                    )
                )

    # Clip-family boxes painted bottom-to-top by z_order.
    clip_family = [
        item
        for item in page.objects
        if item.kind in _FILL_BY_KIND and item.lane_index is not None
    ]
    for item in sorted(clip_family, key=lambda obj: obj.z_order):
        parts.append(
            _rect(
                item.box,
                _FILL_BY_KIND[item.kind],
                stroke=_CLIP_EDGE if item.kind == "clip" else None,
            )
        )

    # Ruler ticks (the tick itself; its text is a separate ``label`` object).
    for item in page.objects:
        if item.kind == "ruler_tick":
            parts.append(_rect(item.box, _TICK))

    # Axis/ruler labels: every ``label`` LayoutObject is drawn at the box the
    # layout provided (no invented geometry), as muted text over the page.
    for item in page.objects:
        if item.kind == "label" and item.label is not None:
            parts.append(
                _text(
                    item.box,
                    item.label,
                    size=_FONT_SIZE_BY_KIND["label"],
                    fill=_MUTED,
                    baseline_ratio=0.8,
                    pad_x=4.0,
                )
            )

    # Chrome badges.
    for item in page.objects:
        if item.kind in _BADGE_KINDS:
            parts.append(_rect(item.box, _LANE, stroke=_LANE_EDGE))
            if item.label:
                parts.append(
                    _text(
                        item.box,
                        item.label,
                        size=_FONT_SIZE_BY_KIND.get(item.kind, 20),
                        fill=_TEXT,
                    )
                )

    # Object labels (clip-family objects only, omitted labels stay out).
    for item in page.objects:
        if item.kind not in _FILL_BY_KIND or item.lane_index is None:
            continue
        if item.label is None or item.omitted_reason is not None:
            continue
        parts.append(
            _text(
                item.box,
                item.label,
                size=_FONT_SIZE_BY_KIND[item.kind],
                fill=_TEXT,
            )
        )

    # Footer continuation markers (lane_index is None).
    for item in page.objects:
        if item.kind == "continuation" and item.lane_index is None:
            parts.append(
                _rect(item.box, _CONTINUATION, stroke=_CLIP_EDGE)
            )
            if item.label:
                parts.append(
                    _text(
                        item.box,
                        item.label,
                        size=_FONT_SIZE_BY_KIND["continuation"],
                        fill=_TEXT,
                    )
                )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_page_svg_bytes(page: LayoutPage) -> bytes:
    """UTF-8 bytes of :func:`render_page_svg`."""

    return render_page_svg(page).encode("utf-8")


__all__ = ["render_page_svg", "render_page_svg_bytes"]
