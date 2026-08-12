"""Verified source inspection for timeline visualization (R12).

R5 acceptance: originals and rendered sampling appear only after
expected-hash verification.  This module is the visualizer's single
verified-source gate.  It never falls back, never fetches, and never
substitutes a thumbnail or proxy for a missing original.

:func:`verified_source_path` returns a local path only for the
``verified_original`` state; every other state yields ``None`` while the
:class:`~astrid.core.timeline.resolution.AssetIntegrity` reason keeps the
block explicit and deterministic.

:func:`source_card` produces one layout descriptor per asset.  The display id
comes from ``page_ctx`` (the stable id allocated for that asset, e.g.
``AS02``).  Dimensions are read with Pillow only for verified local images;
missing/remote/unsupported states skip them so a card is never built from
unverified bytes.

:func:`guard_sampling` is the sampling gate: filmstrips call it *before*
sampling any frame, and it returns ``None`` only for ``verified_original``.

:func:`verify_now` closes the TOCTOU window: it re-hashes the contained local
path *right now* and returns a fresh :class:`AssetIntegrity` describing the
current bytes.  The executor calls it immediately before every Pillow/ffmpeg
read, so the bytes that are opened are the bytes that were just verified.

No timestamps, no randomness, and no writes: this module is pure inspection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from astrid.core.timeline.resolution import (
    AssetIntegrity,
    resolve_asset_local_path_contained,
)

#: Integrity state that unlocks original inspection and sampling.
VERIFIED_STATE = "verified_original"

_READ_CHUNK = 1024 * 1024

#: Local image suffixes whose dimensions may be read with Pillow.
_IMAGE_DIMENSION_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})

#: Deterministic badge per integrity state (verified vs. everything derived).
_BADGES: Mapping[str, str] = {
    "verified_original": "VERIFIED ORIGINAL",
    "thumbnail_only": "THUMBNAIL ONLY",
}

#: Deterministic sampling-block reason per integrity state.
_SAMPLING_BLOCKED: Mapping[str, str] = {
    "missing": "missing — asset file is not present; sampling requires a verified original",
    "hash_mismatch": (
        "hash_mismatch — observed bytes differ from the expected sha256; "
        "sampling blocked"
    ),
    "hash_unrecorded": (
        "hash_unrecorded — no expected sha256 is recorded; sampling blocked"
    ),
    "remote": "remote — media is never fetched; sampling blocked",
    "unsupported": "unsupported — path escapes project sources; sampling blocked",
    "thumbnail_only": "thumbnail_only — no original to sample",
}


def verified_source_path(integrity: AssetIntegrity) -> Path | None:
    """Return the contained local path only for a verified original.

    Returns ``None`` for every other state (missing, hash mismatch, hash
    unrecorded, remote, thumbnail-only, unsupported) with the reason
    available on ``integrity.reason``.  There is deliberately no fallback,
    no fetch, and no thumbnail substitution: an unverified file is never
    handed to inspection or sampling.
    """

    if not isinstance(integrity, AssetIntegrity):
        raise TypeError("integrity must be an AssetIntegrity")
    if integrity.state != VERIFIED_STATE:
        return None
    if not isinstance(integrity.path, str) or not integrity.path:
        return None
    return Path(integrity.path)


def _image_dimensions(integrity: AssetIntegrity) -> dict[str, int] | None:
    """Return ``{"width_px", "height_px"}`` for a verified local image.

    Pillow is consulted only for verified local files with an image suffix;
    missing/remote/unsupported states and non-image files skip it.  Any
    decode failure yields ``None`` so the card remains deterministic.
    """

    path = verified_source_path(integrity)
    if path is None or path.suffix.lower() not in _IMAGE_DIMENSION_SUFFIXES:
        return None
    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
    except Exception:
        return None
    return {"width_px": int(width), "height_px": int(height)}


def _card_label(integrity: AssetIntegrity, display_id: str) -> str:
    if integrity.state == VERIFIED_STATE:
        parts = [display_id, _BADGES[VERIFIED_STATE]]
        dimensions = _image_dimensions(integrity)
        if dimensions is not None:
            parts.append(f"{dimensions['width_px']}x{dimensions['height_px']}")
        return " · ".join(parts)
    state = integrity.state.upper()
    if integrity.reason:
        return f"{display_id} · {state} · {integrity.reason}"
    return f"{display_id} · {state}"


def source_card(
    integrity: AssetIntegrity,
    *,
    page_ctx: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one deterministic source-card descriptor for layout.

    ``page_ctx`` must carry the asset's display id under ``display_id``
    (e.g. ``"AS02"``); extra keys are tolerated and ignored.  The descriptor
    carries the display id, role, integrity state, contained path or None,
    verified/derived badge, image dimensions when available, and a label
    such as ``AS02 · VERIFIED ORIGINAL · 1920x1080`` or
    ``AS03 · MISSING · <reason>``.  No timestamps appear anywhere.
    """

    if not isinstance(integrity, AssetIntegrity):
        raise TypeError("integrity must be an AssetIntegrity")
    if not isinstance(page_ctx, Mapping):
        raise TypeError("page_ctx must be a mapping")
    display_id = page_ctx.get("display_id")
    if not isinstance(display_id, str) or not display_id:
        raise ValueError("page_ctx['display_id'] must be a non-empty string")

    contained_path = integrity.path if isinstance(integrity.path, str) else None
    badge = _BADGES.get(integrity.state, "DERIVED")
    return {
        "display_id": display_id,
        "asset_key": integrity.asset_key,
        "role": integrity.role,
        "integrity_state": integrity.state,
        "contained_path": contained_path,
        "badge": badge,
        "dimensions": _image_dimensions(integrity),
        "label": _card_label(integrity, display_id),
    }


def _sha256_file(path: Path) -> str:
    """Raw hex SHA-256 of *path* using 1 MB chunked reads (stdlib only)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fresh_integrity(
    integrity: AssetIntegrity,
    *,
    state: str,
    observed_sha256: str | None,
    reason: str,
    path: str | None,
) -> AssetIntegrity:
    """Build the fresh :class:`AssetIntegrity` for :func:`verify_now`."""
    return AssetIntegrity(
        asset_key=integrity.asset_key,
        role=integrity.role,
        state=state,
        expected_sha256=integrity.expected_sha256,
        observed_sha256=observed_sha256,
        path=path,
        reason=reason,
        source_id=integrity.source_id,
        source_version=integrity.source_version,
    )


def verify_now(
    integrity: AssetIntegrity,
    *,
    project_root: Path,
) -> AssetIntegrity:
    """Re-verify the contained local path RIGHT NOW; return a fresh integrity.

    The classification stored on *integrity* may be stale: the file could have
    been modified, deleted, or moved since it was hashed.  This function
    recomputes the observed sha256 of the contained local path at call time and
    returns a fresh :class:`AssetIntegrity` describing the *current* state:

    * ``verified_original`` — an expected hash is recorded and equals the
      fresh hash;
    * ``hash_mismatch`` — an expected hash is recorded but differs;
    * ``hash_unrecorded`` — no expected hash is recorded (a hash computed now
      never retroactively verifies an unrecorded one);
    * ``missing`` — the contained file is gone;
    * ``unsupported`` — the recorded path no longer resolves under
      ``project_root/sources``.

    Reasons never carry absolute paths (R13 pack containment).  Deterministic;
    stdlib :mod:`hashlib` only.
    """

    if not isinstance(integrity, AssetIntegrity):
        raise TypeError("integrity must be an AssetIntegrity")
    root = Path(project_root)
    raw_path = integrity.path
    if not isinstance(raw_path, str) or not raw_path.strip():
        return _fresh_integrity(
            integrity,
            state="unsupported",
            observed_sha256=None,
            reason="unsupported — no contained local path is recorded; sampling blocked",
            path=None,
        )
    contained = resolve_asset_local_path_contained(raw_path, project_root=root)
    if contained is None:
        return _fresh_integrity(
            integrity,
            state="unsupported",
            observed_sha256=None,
            reason="unsupported — path no longer resolves under project sources; sampling blocked",
            path=None,
        )
    try:
        present = contained.is_file()
    except OSError:
        present = False
    if not present:
        return _fresh_integrity(
            integrity,
            state="missing",
            observed_sha256=None,
            reason="missing — file not found under sources; sampling blocked",
            path=str(contained),
        )
    expected = integrity.expected_sha256
    if expected is None:
        return _fresh_integrity(
            integrity,
            state="hash_unrecorded",
            observed_sha256=None,
            reason="hash_unrecorded — no expected sha256 is recorded; sampling blocked",
            path=str(contained),
        )
    try:
        observed = _sha256_file(contained)
    except OSError:
        return _fresh_integrity(
            integrity,
            state="missing",
            observed_sha256=None,
            reason="missing — file not readable under sources; sampling blocked",
            path=str(contained),
        )
    if observed == expected:
        return _fresh_integrity(
            integrity,
            state=VERIFIED_STATE,
            observed_sha256=observed,
            reason="observed sha256 matches expected sha256 (re-verified now)",
            path=str(contained),
        )
    return _fresh_integrity(
        integrity,
        state="hash_mismatch",
        observed_sha256=observed,
        reason=f"observed sha256 {observed} != expected {expected} (re-verified now)",
        path=str(contained),
    )


def guard_sampling(integrity: AssetIntegrity) -> None | str:
    """Return ``None`` when sampling is allowed, else the block reason.

    Sampling is allowed only for ``verified_original``.  Every other state
    returns a deterministic reason string (missing / hash_mismatch /
    hash_unrecorded / remote / unsupported / thumbnail_only).  R12 filmstrips
    call this before sampling any frame.
    """

    if not isinstance(integrity, AssetIntegrity):
        raise TypeError("integrity must be an AssetIntegrity")
    if integrity.state == VERIFIED_STATE:
        return None
    return _SAMPLING_BLOCKED.get(
        integrity.state,
        f"{integrity.state} — sampling requires a verified original",
    )


__all__ = [
    "VERIFIED_STATE",
    "guard_sampling",
    "source_card",
    "verify_now",
    "verified_source_path",
]
