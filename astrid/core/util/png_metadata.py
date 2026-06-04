"""Embed Astrid metadata into PNG tEXt chunks.

Writes namespaced ``astrid_*`` keys alongside any existing tEXt chunks
(e.g. ComfyUI's ``prompt`` / ``workflow``) to make an image
self-describing independent of its ``manifest.json`` sidecar.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

_ASTRID_KEY_PREFIX = "astrid_"


def embed_png_text(
    path: Union[str, Path],
    fields: dict[str, str],
    *,
    preserve_existing: bool = True,
) -> bool:
    """Add *fields* as ``astrid_<key>`` tEXt chunks in the PNG at *path*.

    If *preserve_existing* is ``True`` (the default), any tEXt chunks
    already present (like ComfyUI's ``prompt`` and ``workflow``) are
    read and re-written before the new Astrid chunks are added.

    Writes to a sibling temporary file then atomically replaces the
    original via ``os.replace()`` so concurrent readers never observe
    a half-written PNG.

    Returns ``True`` on success, ``False`` for non-PNG or missing paths
    (silent no-op — no exception raised).
    """
    path = Path(path)

    # --- guard: path must exist and be a file --------------------------------
    if not path.is_file():
        logger.debug("embed_png_text: %s is not a file — skipping", path)
        return False

    # --- guard: must be a PNG ------------------------------------------------
    if path.suffix.lower() != ".png":
        logger.debug("embed_png_text: %s is not a PNG — skipping", path)
        return False

    try:
        from PIL.PngImagePlugin import PngInfo
        from PIL import Image
    except ImportError:
        logger.warning("embed_png_text: Pillow not available — skipping %s", path)
        return False

    try:
        img = Image.open(path)

        # Build PngInfo: start with existing chunks so ComfyUI's
        # "prompt" / "workflow" are preserved.
        pnginfo = PngInfo()
        if preserve_existing and img.text:
            for key, value in img.text.items():
                pnginfo.add_text(key, value)

        # Add each field under the astrid_ namespace.
        for key, value in fields.items():
            astrid_key = f"{_ASTRID_KEY_PREFIX}{key}"
            # tEXt values must be Latin-1; encode and replace
            # non-encodable characters to avoid crashes.
            safe_value = _to_latin1_safe(str(value))
            pnginfo.add_text(astrid_key, safe_value)

        # Save to a sibling temp file, then atomically replace the original.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".png.tmp", dir=path.parent
        )
        tmp_path = Path(tmp_name)
        try:
            os.close(fd)  # Pillow will open its own handle
            img.save(tmp_path, format="PNG", pnginfo=pnginfo)
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

        logger.debug("embed_png_text: embedded %d fields into %s", len(fields), path)
        return True

    except Exception:
        logger.exception("embed_png_text: failed for %s", path)
        return False


def _to_latin1_safe(text: str) -> str:
    """Return *text* with any non-Latin-1 characters replaced by ``?``."""
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("latin-1", errors="replace").decode("latin-1")


__all__ = ["embed_png_text"]
