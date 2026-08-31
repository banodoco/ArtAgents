"""Verified source inspection for timeline visualization (R12).

R5 acceptance: originals and rendered sampling appear only after
expected-hash verification.  This module is the visualizer's single
verified-source gate.  It never falls back, never fetches, and never
substitutes a thumbnail or proxy for a missing original.

:func:`source_card` produces one layout descriptor per asset.  The display id
comes from ``page_ctx`` (the stable id allocated for that asset, e.g.
``AS02``). Cards contain identity, role, admission state, and deterministic
reason text; no source locator is emitted.

:func:`guard_sampling` is the sampling gate: filmstrips call it *before*
sampling any frame, and it returns ``None`` only for ``verified_original``.

:func:`verify_now` is the visualizer's runtime-boundary check. It does not open
a path; source bytes must arrive through the attempt's managed-object boundary.

No timestamps, no randomness, and no writes: this module is pure inspection.
"""

from __future__ import annotations

from typing import Any, Mapping

from astrid.core.timeline.resolution import AssetIntegrity

#: Integrity state that unlocks original inspection and sampling.
VERIFIED_STATE = "verified_original"

#: Deterministic badge per integrity state (verified vs. everything derived).
_BADGES: Mapping[str, str] = {
    "verified_original": "VERIFIED ORIGINAL",
    "thumbnail_only": "THUMBNAIL ONLY",
}

#: Deterministic sampling-block reason per integrity state.
_SAMPLING_BLOCKED: Mapping[str, str] = {
    "missing": "missing — asset file is not present; sampling requires a verified original",
    "hash_mismatch": (
        "hash_mismatch — observed bytes differ from the expected sha256; sampling blocked"
    ),
    "hash_unrecorded": ("hash_unrecorded — no expected sha256 is recorded; sampling blocked"),
    "remote": "remote — media is never fetched; sampling blocked",
    "unsupported": "unsupported — no runtime-managed object admission; sampling blocked",
    "thumbnail_only": "thumbnail_only — no original to sample",
}


def _card_label(integrity: AssetIntegrity, display_id: str) -> str:
    if integrity.state == VERIFIED_STATE:
        parts = [display_id, _BADGES[VERIFIED_STATE]]
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
    carries the display id, role, integrity state, verified/derived badge, and
    a label such as ``AS02 · VERIFIED ORIGINAL`` or
    ``AS03 · MISSING · <reason>``.  No timestamps appear anywhere.
    """

    if not isinstance(integrity, AssetIntegrity):
        raise TypeError("integrity must be an AssetIntegrity")
    if not isinstance(page_ctx, Mapping):
        raise TypeError("page_ctx must be a mapping")
    display_id = page_ctx.get("display_id")
    if not isinstance(display_id, str) or not display_id:
        raise ValueError("page_ctx['display_id'] must be a non-empty string")

    badge = _BADGES.get(integrity.state, "DERIVED")
    return {
        "display_id": display_id,
        "asset_key": integrity.asset_key,
        "role": integrity.role,
        "integrity_state": integrity.state,
        "badge": badge,
        "label": _card_label(integrity, display_id),
    }


def _fresh_integrity(
    integrity: AssetIntegrity,
    *,
    state: str,
    observed_sha256: str | None,
    reason: str,
) -> AssetIntegrity:
    """Build the fresh :class:`AssetIntegrity` for :func:`verify_now`."""
    return AssetIntegrity(
        asset_key=integrity.asset_key,
        role=integrity.role,
        state=state,
        expected_sha256=integrity.expected_sha256,
        observed_sha256=observed_sha256,
        reason=reason,
        source_id=integrity.source_id,
        source_version=integrity.source_version,
    )


def verify_now(
    integrity: AssetIntegrity,
    *,
    runtime_client: Any | None = None,
    media_snapshot: Any | None = None,
    materialized_objects: Mapping[str, Any] | None = None,
    materialized_root: Any | None = None,
) -> AssetIntegrity:
    """Fail closed when visualization lacks a host-managed byte handle.

    The host, rather than this visualizer, verifies and stages runtime object
    bytes. A timeline snapshot alone never authorizes a filesystem read.
    """

    if not isinstance(integrity, AssetIntegrity):
        raise TypeError("integrity must be an AssetIntegrity")
    del runtime_client, media_snapshot
    if isinstance(materialized_objects, Mapping):
        object_id = integrity.source_id
        expected = integrity.expected_sha256
        candidate = None
        for key in (object_id, expected, f"sha256:{expected}" if expected else None):
            if key and key in materialized_objects:
                candidate = materialized_objects[key]
                break
        if candidate is not None:
            from pathlib import Path
            import hashlib
            source = Path(str(candidate)).expanduser()
            try:
                if materialized_root is None:
                    raise ValueError("materialized root is missing")
                root = Path(str(materialized_root)).expanduser().resolve(strict=True)
                resolved = source.resolve(strict=True)
                if source.is_symlink() or not resolved.is_file() or not resolved.is_relative_to(root):
                    raise ValueError("materialized object escaped its attempt root")
                observed = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except (OSError, ValueError):
                return _fresh_integrity(
                    integrity,
                    state="missing",
                    observed_sha256=None,
                    reason="materialized object bytes are unavailable under the attempt root",
                )
            if expected is None:
                return _fresh_integrity(
                    integrity,
                    state="hash_unrecorded",
                    observed_sha256=observed,
                    reason="materialized object has no expected sha256",
                )
            if observed != expected:
                return _fresh_integrity(
                    integrity,
                    state="hash_mismatch",
                    observed_sha256=observed,
                    reason="materialized object bytes differ from the expected sha256",
                )
            return _fresh_integrity(
                integrity,
                state=VERIFIED_STATE,
                observed_sha256=observed,
                reason="verified runtime materialization",
            )
    # Live visualization receives attempt-local managed bytes from the host;
    # this helper must never reopen a project path or CAS locator.
    return _fresh_integrity(
        integrity,
        state="unsupported",
        observed_sha256=None,
        reason=(
            "unsupported — media is not runtime-managed; sampling requires a "
            "runtime-materialized managed object"
        ),
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
]
