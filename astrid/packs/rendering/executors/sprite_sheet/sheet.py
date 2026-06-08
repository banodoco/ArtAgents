"""Layout, slicing, and sheet assembly helpers for sprite sheet processing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from astrid.packs.generation.executors.generate_image_openai.run import (
    GPT_IMAGE_2_MAX_EDGE,
    GPT_IMAGE_2_MAX_PIXELS,
    GPT_IMAGE_2_MAX_RATIO,
    GPT_IMAGE_2_MIN_PIXELS,
    _die,
)

from .png_io import (
    _png_dimensions,
    _write_rgb_png,
)


def _parse_hex_color(raw: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", raw.strip())
    if not match:
        _die("color must be a hex RGB value like #ff00ff")
    value = match.group(1)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex_color_no_hash(raw: str) -> str:
    _parse_hex_color(raw)
    return raw.strip().lstrip("#").lower()


def _key_color_name(raw: str) -> str:
    normalized = "#" + _hex_color_no_hash(raw)
    if normalized == "#ff00ff":
        return "pure magenta #ff00ff"
    if normalized == "#00ff00":
        return "pure green #00ff00"
    if normalized == "#0000ff":
        return "pure blue #0000ff"
    return normalized


def _set_pixel(pixels: bytearray, width: int, height: int, x: int, y: int, rgb: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    offset = (y * width + x) * 3
    pixels[offset : offset + 3] = bytes(rgb)


def _draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    if x0 == x1:
        for x in range(x0 - thickness // 2, x0 + (thickness + 1) // 2):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                _set_pixel(pixels, width, height, x, y, rgb)
        return
    if y0 == y1:
        for y in range(y0 - thickness // 2, y0 + (thickness + 1) // 2):
            for x in range(min(x0, x1), max(x0, x1) + 1):
                _set_pixel(pixels, width, height, x, y, rgb)
        return
    steps = max(abs(x1 - x0), abs(y1 - y0))
    for step in range(steps + 1):
        t = step / max(1, steps)
        x = round(x0 + (x1 - x0) * t)
        y = round(y0 + (y1 - y0) * t)
        for yy in range(y - thickness // 2, y + (thickness + 1) // 2):
            for xx in range(x - thickness // 2, x + (thickness + 1) // 2):
                _set_pixel(pixels, width, height, xx, yy, rgb)


def _layout_is_valid(cols: int, rows: int, frame_width: int, frame_height: int) -> bool:
    width = cols * frame_width
    height = rows * frame_height
    if width % 16 or height % 16:
        return False
    if max(width, height) > GPT_IMAGE_2_MAX_EDGE:
        return False
    if max(width, height) / min(width, height) > GPT_IMAGE_2_MAX_RATIO:
        return False
    pixels = width * height
    return GPT_IMAGE_2_MIN_PIXELS <= pixels <= GPT_IMAGE_2_MAX_PIXELS


def choose_layout(frame_count: int, *, frame_width: int, frame_height: int, fixed_cols: int | None = None, fixed_rows: int | None = None) -> dict[str, int]:
    if frame_count < 1:
        _die("--frames must be >= 1")
    if fixed_cols is not None and fixed_cols < 1:
        _die("--cols must be >= 1")
    if fixed_rows is not None and fixed_rows < 1:
        _die("--rows must be >= 1")

    candidates: list[tuple[float, int, int]] = []
    max_cols = GPT_IMAGE_2_MAX_EDGE // frame_width
    max_rows = GPT_IMAGE_2_MAX_EDGE // frame_height

    if fixed_cols is not None and fixed_rows is not None:
        if fixed_cols * fixed_rows < frame_count:
            _die(f"Grid {fixed_cols}x{fixed_rows} only has {fixed_cols * fixed_rows} cells for {frame_count} frames")
        if not _layout_is_valid(fixed_cols, fixed_rows, frame_width, frame_height):
            _die(f"Grid {fixed_cols}x{fixed_rows} at {frame_width}x{frame_height} per frame violates gpt-image-2 size limits")
        return {"cols": fixed_cols, "rows": fixed_rows, "frame_count": frame_count, "capacity": fixed_cols * fixed_rows}

    if fixed_cols is not None:
        rows = (frame_count + fixed_cols - 1) // fixed_cols
        if not _layout_is_valid(fixed_cols, rows, frame_width, frame_height):
            _die(f"Auto rows for {fixed_cols} columns violates gpt-image-2 size limits")
        return {"cols": fixed_cols, "rows": rows, "frame_count": frame_count, "capacity": fixed_cols * rows}

    if fixed_rows is not None:
        cols = (frame_count + fixed_rows - 1) // fixed_rows
        if not _layout_is_valid(cols, fixed_rows, frame_width, frame_height):
            _die(f"Auto columns for {fixed_rows} rows violates gpt-image-2 size limits")
        return {"cols": cols, "rows": fixed_rows, "frame_count": frame_count, "capacity": cols * fixed_rows}

    for rows in range(1, max_rows + 1):
        cols = (frame_count + rows - 1) // rows
        if cols < 1 or cols > max_cols:
            continue
        if not _layout_is_valid(cols, rows, frame_width, frame_height):
            continue
        capacity = cols * rows
        empty = capacity - frame_count
        sheet_width = cols * frame_width
        sheet_height = rows * frame_height
        aspect_penalty = abs((sheet_width / sheet_height) - 1.0)
        area_penalty = (sheet_width * sheet_height) / GPT_IMAGE_2_MAX_PIXELS
        row_penalty = rows * 0.001
        score = empty * 100.0 + aspect_penalty * 10.0 + area_penalty + row_penalty
        candidates.append((score, cols, rows))

    if not candidates:
        _die(
            f"Could not fit {frame_count} frames at {frame_width}x{frame_height}. "
            "Lower the frame size, lower frame count, or set explicit rows/cols."
        )

    _, cols, rows = min(candidates)
    return {"cols": cols, "rows": rows, "frame_count": frame_count, "capacity": cols * rows}


def write_layout_guide(
    path: Path,
    *,
    cols: int,
    rows: int,
    frame_width: int,
    frame_height: int,
    frame_count: int | None = None,
    safe_margin: int | None = None,
    background_color: str = "#ffffff",
) -> dict[str, Any]:
    width = cols * frame_width
    height = rows * frame_height
    bg = _parse_hex_color(background_color)
    pixels = bytearray(list(bg) * width * height)

    grid = (20, 20, 20)
    border = (0, 0, 0)
    safe = (255, 255, 255)
    for col in range(cols + 1):
        x = min(width - 1, col * frame_width)
        _draw_line(pixels, width, height, x, 0, x, height - 1, border if col in {0, cols} else grid, 5 if col in {0, cols} else 3)
    for row in range(rows + 1):
        y = min(height - 1, row * frame_height)
        _draw_line(pixels, width, height, 0, y, width - 1, y, border if row in {0, rows} else grid, 5 if row in {0, rows} else 3)

    inset = safe_margin if safe_margin is not None else max(24, min(frame_width, frame_height) // 8)
    for row in range(rows):
        for col in range(cols):
            x0 = col * frame_width + inset
            y0 = row * frame_height + inset
            x1 = (col + 1) * frame_width - inset
            y1 = (row + 1) * frame_height - inset
            _draw_line(pixels, width, height, x0, y0, x1, y0, safe)
            _draw_line(pixels, width, height, x0, y1, x1, y1, safe)
            _draw_line(pixels, width, height, x0, y0, x0, y1, safe)
            _draw_line(pixels, width, height, x1, y0, x1, y1, safe)
            center_x = col * frame_width + frame_width // 2
            center_y = row * frame_height + frame_height // 2
            cross = max(8, min(frame_width, frame_height) // 24)
            _draw_line(pixels, width, height, center_x - cross, center_y, center_x + cross, center_y, safe, 2)
            _draw_line(pixels, width, height, center_x, center_y - cross, center_x, center_y + cross, safe, 2)

    _write_rgb_png(path, width, height, pixels)
    capacity = cols * rows
    actual_frame_count = frame_count if frame_count is not None else capacity
    if actual_frame_count > capacity:
        _die(f"frame_count {actual_frame_count} exceeds grid capacity {capacity}")
    frames = []
    for index in range(actual_frame_count):
        col = index % cols
        row = index // cols
        frames.append(
            {
                "index": index + 1,
                "x": col * frame_width,
                "y": row * frame_height,
                "width": frame_width,
                "height": frame_height,
            }
        )
    return {
        "cols": cols,
        "rows": rows,
        "capacity": capacity,
        "frame_count": actual_frame_count,
        "sheet_width": width,
        "sheet_height": height,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "safe_margin": inset,
        "frames": frames,
    }


def validate_sheet_dimensions(sheet_path: Path, *, expected_width: int, expected_height: int) -> None:
    width, height = _png_dimensions(sheet_path)
    if width != expected_width or height != expected_height:
        _die(f"Sprite sheet is {width}x{height}, expected {expected_width}x{expected_height}")
