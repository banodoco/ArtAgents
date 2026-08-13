"""Media metadata probing and hash helpers.

Provides utilities for probing media file metadata (ffprobe) and
hashing artifacts for experiment review.

Key properties:
- Uses ffprobe for media metadata extraction where available.
- Falls back gracefully when ffprobe is not installed.
- Produces deterministic content hashes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from astrid.core.foundation.hash import sha256_file


def probe_media(path: Path) -> dict[str, Any] | None:
    """Probe media metadata using ffprobe.

    Returns a dict with width, height, duration_seconds, fps, codec,
    and other common fields. Returns None if ffprobe is unavailable
    or the file is not a media file.

    The returned dict is suitable as the ``metadata`` field in
    normalized review input/output entries.
    """
    if not path.is_file():
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    return _extract_probe_metadata(data)


def _extract_probe_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    """Extract common media metadata from ffprobe JSON output."""
    metadata: dict[str, Any] = {}

    streams = data.get("streams", [])
    fmt = data.get("format", {})

    # Find first video stream
    video_stream = None
    audio_stream = None
    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio" and audio_stream is None:
            audio_stream = stream

    if video_stream:
        width = video_stream.get("width")
        height = video_stream.get("height")
        if isinstance(width, int) and isinstance(height, int):
            metadata["width"] = width
            metadata["height"] = height

        # FPS
        fps_str = video_stream.get("r_frame_rate", "")
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            try:
                metadata["fps"] = round(float(num) / float(den), 2)
            except (ValueError, ZeroDivisionError):
                pass
        elif fps_str:
            try:
                metadata["fps"] = float(fps_str)
            except ValueError:
                pass

        codec = video_stream.get("codec_name")
        if codec:
            metadata["video_codec"] = codec

    if audio_stream:
        codec = audio_stream.get("codec_name")
        if codec:
            metadata["audio_codec"] = codec
        sample_rate = audio_stream.get("sample_rate")
        if sample_rate:
            metadata["sample_rate"] = int(sample_rate)

    # Duration
    duration_str = fmt.get("duration")
    if duration_str:
        try:
            metadata["duration_seconds"] = float(duration_str)
        except ValueError:
            pass
    elif video_stream:
        duration_str = video_stream.get("duration")
        if duration_str:
            try:
                metadata["duration_seconds"] = float(duration_str)
            except ValueError:
                pass

    # Format
    format_name = fmt.get("format_name")
    if format_name:
        metadata["format"] = format_name

    # File size
    size_str = fmt.get("size")
    if size_str:
        try:
            metadata["bytes"] = int(size_str)
        except ValueError:
            pass

    return metadata


def guess_media_type(path: Path) -> str | None:
    """Guess MIME media type from a file path's extension.

    Returns a MIME type string like 'image/png', 'video/mp4', 'audio/mpeg',
    or None for unknown extensions.
    """
    return guess_media_type_from_name(path.name)


def guess_media_type_from_name(name: str) -> str | None:
    """Guess MIME media type from a file name's extension.

    Accepts a bare filename so callers can classify media without the file
    being present on disk (e.g. when synthesizing manifests from legacy
    records).
    """
    if not isinstance(name, str) or "." not in name:
        return None
    suffix = name[name.rfind("."):].lower()
    mapping: dict[str, str] = {
        # Images
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        # Video
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        # Audio
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        # Documents
        ".json": "application/json",
        ".yaml": "application/x-yaml",
        ".yml": "application/x-yaml",
        ".txt": "text/plain",
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
    }
    return mapping.get(suffix)


def hash_artifact(path: Path) -> str:
    """Hash an artifact file and return sha256:-prefixed digest."""
    return f"sha256:{sha256_file(path)}"


def probe_artifact(path: Path) -> dict[str, Any]:
    """Probe an artifact and return combined hash + metadata info.

    Returns a dict with:
    - path: relative path (caller should set this)
    - content_hash: sha256:-prefixed digest
    - bytes: file size
    - media_type: guessed MIME type
    - metadata: ffprobe metadata if available
    """
    info: dict[str, Any] = {
        "content_hash": hash_artifact(path),
    }

    if path.is_file():
        info["bytes"] = path.stat().st_size

    media_type = guess_media_type(path)
    if media_type:
        info["media_type"] = media_type

    metadata = probe_media(path)
    if metadata:
        info["metadata"] = metadata

    return info
