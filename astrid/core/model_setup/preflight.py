"""Disk preflight for setup acquisition (Batch B8, doc 27 §6.1).

Headroom = download bytes + unpack/working bytes + output headroom.
The working factor covers decompression/unpack expansion (a compressed
bundle unpacks to more bytes than the download); the output margin keeps
generation output from colliding with setup on the same volume.

Refusal is typed and names the exact shortfall — never a warning after
the download already filled the disk (disk-full is a named fixture).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

#: Decompression working-space multiplier over the download size.
DEFAULT_WORKING_FACTOR = 2
#: Fixed output headroom kept free beside setup activity (bytes).
DEFAULT_OUTPUT_HEADROOM_BYTES = 256 << 20  # 256 MiB


class DiskPreflightError(RuntimeError):
    """Typed refusal: the target volume lacks the required headroom."""


@dataclass(frozen=True, slots=True)
class PreflightResult:
    """Outcome of one preflight check."""

    ok: bool
    required_bytes: int
    free_bytes: int
    detail: str

    @property
    def missing_bytes(self) -> int:
        return max(0, self.required_bytes - self.free_bytes)


def required_bytes(
    download_bytes: int,
    *,
    working_factor: int = DEFAULT_WORKING_FACTOR,
    output_headroom_bytes: int = DEFAULT_OUTPUT_HEADROOM_BYTES,
) -> int:
    """Total headroom one acquisition needs on its target volume."""
    return download_bytes * working_factor + output_headroom_bytes


def preflight_disk(
    target_root: str | Path,
    download_bytes: int,
    *,
    working_factor: int = DEFAULT_WORKING_FACTOR,
    output_headroom_bytes: int = DEFAULT_OUTPUT_HEADROOM_BYTES,
) -> PreflightResult:
    """Check the volume holding *target_root* for full acquisition headroom."""
    need = required_bytes(
        download_bytes,
        working_factor=working_factor,
        output_headroom_bytes=output_headroom_bytes,
    )
    root = Path(target_root)
    probe = root if root.exists() else root.parent
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    free = shutil.disk_usage(probe).free
    if free >= need:
        return PreflightResult(
            ok=True,
            required_bytes=need,
            free_bytes=free,
            detail=f"{free} bytes free, {need} required",
        )
    return PreflightResult(
        ok=False,
        required_bytes=need,
        free_bytes=free,
        detail=(
            f"disk preflight failed on {probe}: {free} bytes free but "
            f"{need} required (download {download_bytes} x "
            f"working factor {working_factor} + output headroom "
            f"{output_headroom_bytes}); short by "
            f"{need - free} bytes"
        ),
    )


def require_disk(
    target_root: str | Path,
    download_bytes: int,
    *,
    working_factor: int = DEFAULT_WORKING_FACTOR,
    output_headroom_bytes: int = DEFAULT_OUTPUT_HEADROOM_BYTES,
) -> PreflightResult:
    """Preflight or raise :class:`DiskPreflightError` with the shortfall."""
    result = preflight_disk(
        target_root,
        download_bytes,
        working_factor=working_factor,
        output_headroom_bytes=output_headroom_bytes,
    )
    if not result.ok:
        raise DiskPreflightError(result.detail)
    return result

