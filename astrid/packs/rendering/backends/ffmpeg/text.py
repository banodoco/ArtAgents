"""Text-to-image rasterization for FFmpeg text overlays."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import importlib.util


_BUNDLED_FONT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "executors"
    / "timeline_visualize"
    / "fonts"
    / "PowerGrotesk-Regular.ttf"
)


def rasterize_text(
    *,
    content: str,
    fontSize: int,
    color: str,
    align: str,
    bold: bool,
    anchor: str = "top-left",
    offsetX: float = 0,
    offsetY: float = 0,
    maxWidth: float | None = None,
    textShadow: dict | None = None,
    weight: int = 400,
) -> Image.Image:
    """Rasterize text to an RGBA PNG image.

    Args:
        content: Text to render.
        fontSize: Font size in pixels.
        color: Color string in hex format (e.g., "#FFFFFF").
        align: Horizontal alignment ("left", "center", "right").
        bold: Whether to use bold variant.
        anchor: Text anchor point ("top-left", "top-center", "top-right", "center", "bottom-left", "bottom-center", "bottom-right").
        offsetX: Horizontal offset in pixels.
        offsetY: Vertical offset in pixels.
        maxWidth: Optional maximum width in pixels. Text will be wrapped greedily.
        textShadow: Optional text shadow parameters:
            - blur: blur radius
            - color: shadow color hex
            - offsetX: horizontal offset
            - offsetY: vertical offset
        weight: Font weight (400 = regular, 700 = bold).

    Returns:
        PIL Image with RGBA mode.

    Raises:
        FileNotFoundError: If the bundled font is not found.
        RuntimeError: If Pillow is unavailable.
    """
    try:
        importlib.util.find_spec("PIL")
    except (ImportError, ModuleNotFoundError):
        raise RuntimeError("Pillow is required for text rasterization")

    # Load font with appropriate variant
    font_path = _BUNDLED_FONT_PATH
    if not font_path.is_file():
        raise FileNotFoundError(
            f"Bundled font not found at {font_path}. "
            "This is a dependency of Astrid's rendering pack."
        )

    if bold:
        # Try bold variant if available
        bold_path = font_path.with_stem(font_path.stem.replace("Regular", "Bold"))
        if bold_path.is_file():
            font_path = bold_path

    try:
        font = ImageFont.truetype(str(font_path), size=fontSize)
    except OSError as exc:
        raise FileNotFoundError(f"Unable to load font from {font_path}: {exc}") from exc

    # Parse hex color
    if not color.startswith("#"):
        color = f"#{color}"
    if len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        rgba = (r, g, b, 255)
    else:
        raise ValueError(f"Invalid color format: {color}")

    # Determine text wrap
    if maxWidth is not None and maxWidth > 0:
        lines = []
        cur_line = ""
        for word in content.split():
            test_line = f"{cur_line} {word}" if cur_line else word
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            if width > maxWidth:
                if cur_line:
                    lines.append(cur_line)
                cur_line = word
            else:
                cur_line = test_line
        if cur_line:
            lines.append(cur_line)
    else:
        lines = [content]

    # Measure lines
    line_height = fontSize
    total_height = len(lines) * line_height + (len(lines) - 1) * line_height * 0.2

    # Determine anchor adjustments
    anchor_map = {
        "top-left": (0, 0),
        "top-center": (0, 0),
        "top-right": (0, 0),
        "center": (0, 0),
        "bottom-left": (0, 0),
        "bottom-center": (0, 0),
        "bottom-right": (0, 0),
    }

    anchor_offsets = anchor_map.get(anchor, (0, 0))
    baseline_adjust = {
        "top-left": 0,
        "top-center": 0,
        "top-right": 0,
        "center": -total_height / 2,
        "bottom-left": -total_height,
        "bottom-center": -total_height,
        "bottom-right": -total_height,
    }

    # Calculate image size
    max_line_width = max(font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines)
    img_width = int(max(max_line_width + offsetX + 100, maxWidth or max_line_width + 100))
    img_height = int(total_height + offsetY + 100)

    # Create image and draw text
    image = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw with shadow if specified
    if textShadow:
        shadow_color = textShadow.get("color", color)
        blur = textShadow.get("blur", 0)
        shadow_offset_x = textShadow.get("offsetX", 2)
        shadow_offset_y = textShadow.get("offsetY", 2)

        # Parse shadow color
        if not shadow_color.startswith("#"):
            shadow_color = f"#{shadow_color}"
        if len(shadow_color) == 7:
            sr, sg, sb, _ = (
                int(shadow_color[1:3], 16),
                int(shadow_color[2:4], 16),
                int(shadow_color[4:6], 16),
                255,
            )
        else:
            sr, sg, sb = 0, 0, 0

        shadow_offsets = [
            (
                int(img_width / 2 - (max_line_width / 2 + offsetX) + shadow_offset_x),
                int(offsetY + baseline_adjust.get(anchor, 0) + shadow_offset_y + fontSize),
            ),
            (
                int(img_width / 2 - (max_line_width / 2 + offsetX) - shadow_offset_x),
                int(offsetY + baseline_adjust.get(anchor, 0) + shadow_offset_y + fontSize),
            ),
            (
                int(img_width / 2 - (max_line_width / 2 + offsetX) + shadow_offset_x),
                int(offsetY + baseline_adjust.get(anchor, 0) - shadow_offset_y + fontSize),
            ),
            (
                int(img_width / 2 - (max_line_width / 2 + offsetX) - shadow_offset_x),
                int(offsetY + baseline_adjust.get(anchor, 0) - shadow_offset_y + fontSize),
            ),
        ]

        # Draw shadow for each line
        for line in lines:
            for sx, sy in shadow_offsets:
                draw_shadow = ImageDraw.Draw(image)
                if blur > 0:
                    draw_shadow.text((sx, sy), line, font=font, fill=(sr, sg, sb))
                else:
                    draw_shadow.text((sx, sy), line, font=font, fill=(sr, sg, sb, 150))

    # Text anchor offsets based on alignment
    align_offsets = {
        "left": (0, 0),
        "center": (-(max_line_width + offsetX) // 2, 0),
        "right": (-(max_line_width + offsetX), 0),
    }
    align_x, align_y = align_offsets.get(align, (0, 0))

    for i, line in enumerate(lines):
        line_y = int(offsetY + baseline_adjust.get(anchor, 0) + i * (line_height + line_height * 0.2))
        draw.text(
            (
                int(img_width / 2 + align_x + offsetX),
                line_y,
            ),
            line,
            font=font,
            fill=rgba,
        )

    return image


def text_to_rgba_png(
    *,
    content: str,
    fontSize: int,
    color: str,
    align: str,
    bold: bool,
    anchor: str = "top-left",
    offsetX: float = 0,
    offsetY: float = 0,
    maxWidth: float | None = None,
    textShadow: dict | None = None,
    weight: int = 400,
) -> bytes:
    """Rasterize text to RGBA PNG bytes.

    This is a convenience wrapper around :func:`rasterize_text` that returns
    the image as PNG bytes instead of a PIL Image.
    """
    image = rasterize_text(
        content=content,
        fontSize=fontSize,
        color=color,
        align=align,
        bold=bold,
        anchor=anchor,
        offsetX=offsetX,
        offsetY=offsetY,
        maxWidth=maxWidth,
        textShadow=textShadow,
        weight=weight,
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


__all__ = ["rasterize_text", "text_to_rgba_png", "_BUNDLED_FONT_PATH"]