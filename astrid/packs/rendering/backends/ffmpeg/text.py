"""Text rasterization for the FFmpeg backend.

Paints one ``clipType: "text"`` clip onto a full-canvas RGBA PNG with the
position baked in, so the later overlay stage pastes at ``0:0``. Semantics
mirror ``remotion/src/ThreeTimelineComposition.tsx`` (the overlay-parity
reference): compound anchor + offsets, greedy word wrap, CSS ``text-shadow``,
line height ``1.2 * fontSize``. Fades are deliberately NOT baked in — they
drive overlay alpha downstream. Pure Pillow; unit-testable without ffmpeg.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

from astrid.core.timeline.validators.timeline import _clip_duration_seconds

DEFAULT_FONT_SIZE = 48
DEFAULT_TEXT_COLOR = "#ffffff"
DEFAULT_ALIGN = "center"
LINE_HEIGHT_MULTIPLIER = 1.2

# Font candidates per face, in priority order: Supplemental Arial, then
# /Library/Fonts Arial, then DejaVu (Linux). First existing path wins;
# none -> None. Bold text gets a bold face or fails — no silent swap.
_REGULAR_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)
_BOLD_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/Library/Fonts/Arial Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)

_FADE_KEYS = frozenset({"fade_in", "fade_out"})
_CSS_NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


class _Shadow(NamedTuple):
    offset_x: float
    offset_y: float
    blur: float
    color: tuple[int, int, int, int]


def _finite_number(value: Any) -> float | None:
    """Finite int/float (bool excluded), else None."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _positive_number(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and number > 0 else None


def _resolve_font_path(bold: bool) -> Path | None:
    # visual_understand may ImageFont.load_default() for debug labels; timeline_visualize
    # fail-hard — this path follows timeline_visualize.
    candidates = _BOLD_FONT_CANDIDATES if bold else _REGULAR_FONT_CANDIDATES
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _parse_color(value: str) -> tuple[int, int, int, int]:
    """Resolve a CSS color to RGBA. Hex and named colors go through PIL;
    ``rgba(r,g,b,a)`` is hand-parsed because hype shadows carry float alpha."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid color: {value!r}")
    text = value.strip()
    if text[:5].lower() == "rgba(" and text.endswith(")"):
        parts = [part.strip() for part in text[5:-1].split(",")]
        if len(parts) != 4:
            raise ValueError(f"rgba() needs 4 channels: {value!r}")
        try:
            red, green, blue, alpha = (float(part) for part in parts)
        except ValueError as exc:
            raise ValueError(f"invalid rgba() color: {value!r}") from exc
        return (
            _clamp_channel(red),
            _clamp_channel(green),
            _clamp_channel(blue),
            _clamp_channel(alpha * 255.0),
        )
    rgba = ImageColor.getcolor(text, "RGBA")
    return (int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3]))


def _css_number(part: str, field: str) -> float:
    match = _CSS_NUMBER.match(part.strip())
    if match is None:
        raise ValueError(f"textShadow {field} is not numeric: {part!r}")
    return float(match.group(0))


def _parse_text_shadow(shadow: str | None) -> _Shadow | None:
    """Parse CSS ``offsetX offsetY blur color`` (3-part form omits blur).

    Missing/empty -> None; any other invalid input raises ValueError.
    """
    if shadow is None:
        return None
    if not isinstance(shadow, str):
        raise ValueError(f"invalid textShadow: {shadow!r}")
    if not shadow.strip():
        return None
    parts = shadow.strip().split()
    if len(parts) < 3:
        raise ValueError(f"textShadow needs 'offsetX offsetY [blur] color': {shadow!r}")
    offset_x = _css_number(parts[0], "offsetX")
    offset_y = _css_number(parts[1], "offsetY")
    if len(parts) == 3:
        blur = 0.0
        color_text = parts[2]
    else:
        blur = _css_number(parts[2], "blur")
        color_text = " ".join(parts[3:])
    return _Shadow(offset_x, offset_y, blur, _parse_color(color_text))


def _fade_seconds(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be a finite number >= 0, got {value!r}")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"{where} must be a finite number >= 0, got {value!r}")
    return seconds


def _fade_values(item: Mapping[str, Any], where: str) -> dict[str, float]:
    unknown = set(item) - _FADE_KEYS
    if unknown:
        raise ValueError(f"{where} has unsupported effect keys: {sorted(unknown)!r}")
    return {
        key: _fade_seconds(item[key], f"{where}.{key}") for key in _FADE_KEYS if key in item
    }


def _parse_fades(effects: Any) -> tuple[float, float]:
    """Return ``(fade_in, fade_out)`` seconds from ``clip.effects`` — the only
    fade reader for text clips.

    Map form or list-of-objects; the list scan takes the FIRST numeric
    ``fade_in`` and ``fade_out`` independently (Remotion getEffectValue
    semantics). ``None`` / empty map / empty list -> ``(0.0, 0.0)``.
    """
    if effects is None:
        return (0.0, 0.0)
    if isinstance(effects, Mapping):
        values = _fade_values(effects, "effects")
        return (values.get("fade_in", 0.0), values.get("fade_out", 0.0))
    if not isinstance(effects, (list, tuple)):
        raise ValueError(
            f"effects must be a map or a list of maps, got {type(effects).__name__}"
        )
    fade_in: float | None = None
    fade_out: float | None = None
    for index, item in enumerate(effects):
        if not isinstance(item, Mapping):
            raise ValueError(
                f"effects[{index}] must be an object, got {type(item).__name__}"
            )
        if not item:
            continue
        values = _fade_values(item, f"effects[{index}]")
        if fade_in is None and "fade_in" in values:
            fade_in = values["fade_in"]
        if fade_out is None and "fade_out" in values:
            fade_out = values["fade_out"]
    return (
        fade_in if fade_in is not None else 0.0,
        fade_out if fade_out is not None else 0.0,
    )


def _wrap_lines(font: Any, text: str, max_width: float) -> list[str]:
    """Greedy word wrap to ``max_width`` (``<= 0`` keeps one line), matching
    ``wrapText`` in ThreeTimelineComposition."""

    if max_width <= 0:
        return [text]
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if not current or font.getlength(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [""]


def _anchor_origin(
    anchor: str,
    offset_x: float,
    offset_y: float,
    width: int,
    height: int,
    block_height: float,
) -> tuple[float, float]:
    """Reference point of the text block per ThreeTimelineComposition.

    Compound vertical (top/middle/bottom) x horizontal (left/center/right)
    anchor, default center/center; offsets shift away from the anchor origin
    (top/left edges push right/down, bottom/right edges push inward).
    """

    name = (anchor or "").lower()
    if "left" in name:
        x = offset_x
    elif "right" in name:
        x = width - offset_x
    else:
        x = width / 2 + offset_x
    if "top" in name:
        y_top = offset_y
    elif "bottom" in name:
        y_top = height - offset_y - block_height
    else:
        y_top = height / 2 + offset_y - block_height / 2
    return x, y_top


def _text_window(clip: dict[str, Any]) -> tuple[float, float]:
    """``(at, end)`` window for a text clip over the canonical duration helper.

    Fails when the clip has no positive duration (missing/``None`` and
    ``hold: 0`` both fail).
    """

    at = clip.get("at", 0)
    start = _finite_number(at) or 0.0
    duration = _clip_duration_seconds(clip)
    if duration is None or duration <= 0:
        raise ValueError(
            f"text clip {clip.get('id')!r} needs a positive duration, got {duration!r}"
        )
    return (start, start + duration)


def text_wants_bold(clip: Mapping[str, Any]) -> bool:
    """Single bold decision shared by support and the rasterizer.

    ``text.bold`` is True or ``params.weight`` >= 600.
    """

    text_field = clip.get("text")
    params = clip.get("params")
    text_field = text_field if isinstance(text_field, Mapping) else {}
    params = params if isinstance(params, Mapping) else {}
    weight = _finite_number(params.get("weight"))
    return text_field.get("bold") is True or (weight is not None and weight >= 600)


def rasterize_text_clip(
    clip: dict[str, Any],
    width: int,
    height: int,
    dest: Path,
) -> None:
    """Paint one text clip onto a full-canvas RGBA PNG (position baked in).

    Missing font raises FileNotFoundError; empty/missing content raises
    ValueError. Fade effects are ignored here — the overlay applies them
    later; ``text.fontFamily``/``italic`` are ignored (fixed font stack).
    """

    text_field = clip.get("text")
    text_field = text_field if isinstance(text_field, Mapping) else {}
    params = clip.get("params")
    params = params if isinstance(params, Mapping) else {}

    content = text_field.get("content")
    if not isinstance(content, str) or len(content) == 0:
        raise ValueError(f"text clip {clip.get('id')!r} needs non-empty text.content")

    font_size = _positive_number(text_field.get("fontSize")) or DEFAULT_FONT_SIZE
    color_text = text_field.get("color")
    color = _parse_color(
        color_text
        if isinstance(color_text, str) and color_text.strip()
        else DEFAULT_TEXT_COLOR
    )
    align = text_field.get("align")
    align = align if align in ("left", "center", "right") else DEFAULT_ALIGN

    wants_bold = text_wants_bold(clip)
    anchor = params.get("anchor")
    anchor_name = anchor if isinstance(anchor, str) else ""
    offset_x = _finite_number(params.get("offsetX")) or 0.0
    offset_y = _finite_number(params.get("offsetY")) or 0.0
    max_width = _positive_number(params.get("maxWidth")) or 0.0
    shadow = _parse_text_shadow(params.get("textShadow"))

    font_path = _resolve_font_path(wants_bold)
    if font_path is None:
        raise FileNotFoundError(
            f"no {'bold ' if wants_bold else ''}TTF found for text clip "
            f"{clip.get('id')!r} (searched Supplemental Arial, /Library/Fonts "
            "Arial, DejaVu)"
        )
    font = ImageFont.truetype(str(font_path), size=max(1, round(font_size)))

    lines = _wrap_lines(font, content, max_width)
    line_height = font_size * LINE_HEIGHT_MULTIPLIER
    block_height = len(lines) * line_height
    x, y_top = _anchor_origin(anchor_name, offset_x, offset_y, width, height, block_height)

    def _paint(
        layer: ImageDraw.ImageDraw,
        fill: tuple[int, int, int, int],
        dx: float,
        dy: float,
    ) -> None:
        for index, line in enumerate(lines):
            line_width = font.getlength(line)
            if align == "left":
                line_x = x
            elif align == "right":
                line_x = x - line_width
            else:
                line_x = x - line_width / 2
            layer.text(
                (line_x + dx, y_top + index * line_height + dy),
                line,
                font=font,
                fill=fill,
                anchor="la",
            )

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if shadow is not None:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        _paint(ImageDraw.Draw(layer), shadow.color, shadow.offset_x, shadow.offset_y)
        if shadow.blur > 0:
            # canvas shadowBlur is roughly twice the Gaussian sigma
            layer = layer.filter(ImageFilter.GaussianBlur(radius=shadow.blur / 2))
        canvas.alpha_composite(layer)
    _paint(ImageDraw.Draw(canvas), color, 0.0, 0.0)

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, format="PNG")
