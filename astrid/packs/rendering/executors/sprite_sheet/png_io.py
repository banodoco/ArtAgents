"""PNG read/write and alpha analysis helpers for sprite sheet processing."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

from astrid.packs.generation.executors.generate_image_openai.run import _die


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _write_rgb_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            _png_chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_rgba_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])
    payload = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            _png_chunk(b"IEND", b""),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _read_rgba_png(path: Path) -> tuple[int, int, bytearray]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        _die(f"Expected PNG image: {path}")
    pos = 8
    width = height = bit_depth = color_type = None
    idat: list[bytes] = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break
    if width is None or height is None or bit_depth != 8 or color_type != 6:
        _die(f"Expected 8-bit RGBA PNG: {path}")
    raw = zlib.decompress(b"".join(idat))
    bpp = 4
    stride = width * bpp
    prev = bytearray(stride)
    pixels = bytearray()
    i = 0
    for _ in range(height):
        filter_type = raw[i]
        i += 1
        scan = bytearray(raw[i : i + stride])
        i += stride
        out = bytearray(stride)
        for x in range(stride):
            left = out[x - bpp] if x >= bpp else 0
            up = prev[x]
            upper_left = prev[x - bpp] if x >= bpp else 0
            if filter_type == 0:
                value = scan[x]
            elif filter_type == 1:
                value = (scan[x] + left) & 255
            elif filter_type == 2:
                value = (scan[x] + up) & 255
            elif filter_type == 3:
                value = (scan[x] + ((left + up) // 2)) & 255
            elif filter_type == 4:
                predictor = left + up - upper_left
                pa = abs(predictor - left)
                pb = abs(predictor - up)
                pc = abs(predictor - upper_left)
                predicted = left if pa <= pb and pa <= pc else (up if pb <= pc else upper_left)
                value = (scan[x] + predicted) & 255
            else:
                _die(f"Unsupported PNG filter type {filter_type} in {path}")
            out[x] = value
        pixels.extend(out)
        prev = out
    return width, height, pixels


def scrub_fully_transparent_rgb(path: Path) -> None:
    width, height, pixels = _read_rgba_png(path)
    for offset in range(0, len(pixels), 4):
        if pixels[offset + 3] == 0:
            pixels[offset : offset + 3] = b"\x00\x00\x00"
    _write_rgba_png(path, width, height, pixels)


def _alpha_bbox(
    pixels: bytearray, width: int, height: int, threshold: int = 8
) -> tuple[int, int, int, int] | None:
    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    for y in range(height):
        row = y * width * 4
        for x in range(width):
            if pixels[row + x * 4 + 3] > threshold:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < min_x or max_y < min_y:
        return None
    return min_x, min_y, max_x, max_y


def analyze_frames(frames: list[str], *, edge_margin: int) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for frame in frames:
        path = Path(frame)
        width, height, pixels = _read_rgba_png(path)
        bbox = _alpha_bbox(pixels, width, height)
        if bbox is None:
            report.append({"path": str(path), "empty": True, "touches_edge": False})
            continue
        min_x, min_y, max_x, max_y = bbox
        touches_edge = (
            min_x <= edge_margin
            or min_y <= edge_margin
            or max_x >= width - 1 - edge_margin
            or max_y >= height - 1 - edge_margin
        )
        report.append(
            {
                "path": str(path),
                "empty": False,
                "bbox": [min_x, min_y, max_x, max_y],
                "width": max_x - min_x + 1,
                "height": max_y - min_y + 1,
                "center": [(min_x + max_x) / 2.0, (min_y + max_y) / 2.0],
                "touches_edge": touches_edge,
            }
        )
    return report


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
        _die(f"Expected PNG image: {path}")
    return struct.unpack(">II", data[16:24])
