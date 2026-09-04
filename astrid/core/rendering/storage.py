"""Deterministic storage estimates for canonical managed timeline renders.

The estimate is both a transparent, JSON-safe audit record and the source of
the runtime's small top-level per-task storage request.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from fractions import Fraction
from typing import Any

from astrid.core.rendering.contracts import RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.timeline.duration import clip_timeline_duration, timeline_duration_frames

_MIB = 1024**2

# These are visible policy inputs, not hidden blanket reservations. H.264 is
# modelled at a generous quarter bit per pixel per frame, while ProRes 4444 is
# modelled near its high-quality mezzanine data rate. The result remains an
# bound is enforced by the matching max-rate/buffer flags in the renderer.
_H264_BITS_PER_PIXEL_FRAME = Fraction(1, 4)
_H264_MIN_VIDEO_BITRATE = 4_000_000
_H264_MAX_VIDEO_BITRATE = 80_000_000
_PRORES_4444_BITS_PER_PIXEL_FRAME = Fraction(6, 1)
_AAC_BITRATE = 320_000
_PCM_S16LE_STEREO_BITRATE = 48_000 * 2 * 16
_MUX_OVERHEAD_PERCENT = 3
_MUX_FIXED_OVERHEAD_BYTES = _MIB
_MIN_OPERATIONAL_GUARD_BYTES = 256 * _MIB
_OPERATIONAL_GUARD_PERCENT = 20
_PARALLEL_ENCODE_WORKING_COPIES = 1


class StorageEstimateError(ValueError):
    """Raised when an exact estimate input is absent or malformed."""


def _canonical_json_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def _normalized_digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.removeprefix("sha256:")
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        return None
    return normalized


def managed_object_sizes(
    registry: Mapping[str, Any],
    media_rows: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    """Return exact, digest-deduplicated sizes for registry-managed objects.

    Runtime media rows are the size authority. Registry hints are intentionally
    ignored: an authored document may identify an object, but it cannot assert
    how many bytes the runtime will materialize.
    """

    indexed: dict[str, tuple[str, int]] = {}
    for row in media_rows:
        if not isinstance(row, Mapping):
            continue
        digest = _normalized_digest(
            row.get("digest")
            or row.get("content_hash")
            or row.get("content_sha256")
            or row.get("object_id")
        )
        size = row.get("size")
        if digest is None or isinstance(size, bool) or not isinstance(size, int) or size < 0:
            continue
        identities = {
            value
            for value in (row.get("media_id"), row.get("id"), row.get("object_id"), digest, f"sha256:{digest}")
            if isinstance(value, str) and value
        }
        for identity in identities:
            previous = indexed.get(identity)
            current = (digest, size)
            if previous is not None and previous != current:
                raise StorageEstimateError(
                    f"runtime media identity {identity!r} has contradictory digest/size rows"
                )
            indexed[identity] = current

    raw_assets = registry.get("assets", {})
    if not isinstance(raw_assets, Mapping):
        raise StorageEstimateError("managed registry assets must be an object")
    result: dict[str, int] = {}
    for asset_id, raw in raw_assets.items():
        if not isinstance(raw, Mapping):
            continue
        identity = raw.get("media_id") or raw.get("object_id")
        digest = _normalized_digest(
            raw.get("content_sha256")
            or raw.get("digest")
            or raw.get("sha256")
            or raw.get("hash")
        )
        record = indexed.get(identity) if isinstance(identity, str) else None
        if record is None and digest is not None:
            record = indexed.get(digest) or indexed.get(f"sha256:{digest}")
        if record is None:
            raise StorageEstimateError(
                f"managed asset {asset_id!r} has no exact runtime object size"
            )
        actual_digest, size = record
        if digest is not None and actual_digest != digest:
            raise StorageEstimateError(
                f"managed asset {asset_id!r} size row does not match its admitted digest"
            )
        previous_size = result.get(actual_digest)
        if previous_size is not None and previous_size != size:
            raise StorageEstimateError(
                f"managed object {actual_digest!r} has contradictory sizes"
            )
        result[actual_digest] = size
    return result


def used_effect_asset_sizes(
    timeline: Mapping[str, Any],
    *,
    element_registry: Any | None = None,
) -> dict[str, int]:
    """Return exact sizes of declared effect assets used by the timeline.

    Discovery is kept outside :func:`estimate_managed_render_storage`, leaving
    the estimator itself pure. Paths are digest-independent source inputs and
    are deduplicated because the renderer stages each used effect asset once.
    """

    if element_registry is None:
        from astrid.core.element.registry import load_default_registry
        from astrid.core.foundation.paths import REPO_ROOT

        element_registry = load_default_registry(project_root=REPO_ROOT)
    effects = {element.id: element for element in element_registry.list(kind="effects")}
    aliases: dict[str, str] = {}
    for effect_id, element in effects.items():
        raw_aliases = element.metadata.get("clipTypeAliases")
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias:
                    aliases[alias] = effect_id
    if "text-card" in effects:
        aliases.setdefault("text", "text-card")

    used: set[str] = set()
    for clip in timeline.get("clips", []):
        if not isinstance(clip, Mapping):
            continue
        clip_type = clip.get("clipType")
        if not isinstance(clip_type, str):
            continue
        effect_id = clip_type if clip_type in effects else aliases.get(clip_type)
        if effect_id is not None:
            used.add(effect_id)

    sizes: dict[str, int] = {}
    for effect_id in sorted(used):
        element = effects[effect_id]
        for asset in element.assets:
            path = (element.root / asset.path).resolve()
            if not path.is_file():
                raise StorageEstimateError(
                    f"effect asset is unavailable for storage estimation: {path}"
                )
            sizes[str(path)] = path.stat().st_size
    return sizes


def _is_alpha_timeline(timeline: Mapping[str, Any]) -> bool:
    metadata = timeline.get("metadata")
    layer = metadata.get("astrid_layer") if isinstance(metadata, Mapping) else None
    return isinstance(layer, Mapping) and layer.get("alpha") is True


def h264_encoder_bitrates(
    *, width: int, height: int, fps_rational: tuple[int, int]
) -> tuple[int, int]:
    """Return the opaque render max-rate and 2x VBV buffer in whole Kbit/s."""

    fps = Fraction(*fps_rational)
    modelled = math.ceil(
        Fraction(width * height, 1) * fps * _H264_BITS_PER_PIXEL_FRAME
    )
    clamped = min(_H264_MAX_VIDEO_BITRATE, max(_H264_MIN_VIDEO_BITRATE, modelled))
    max_rate = math.ceil(clamped / 1000) * 1000
    return max_rate, max_rate * 2


def _render_profile(
    timeline: Mapping[str, Any],
    registry: Mapping[str, Any],
    requested_profile: Mapping[str, Any] | RenderProfile | None,
) -> RenderProfile:
    if isinstance(requested_profile, RenderProfile):
        return requested_profile
    if isinstance(requested_profile, Mapping):
        return RenderProfile.from_dict(requested_profile)
    return resolve_render_profile(timeline, registry)


def estimate_managed_render_storage(
    *,
    timeline: Mapping[str, Any],
    registry: Mapping[str, Any],
    object_sizes: Mapping[str, int],
    effect_asset_sizes: Mapping[str, int] | None = None,
    requested_profile: Mapping[str, Any] | RenderProfile | None = None,
) -> dict[str, Any]:
    """Estimate peak task storage from one expanded canonical snapshot.

    ``object_sizes`` must contain exact runtime-owned sizes, keyed by unique
    SHA-256 digest. The estimate models the measured materialization,
    pre-encode, frame-sequence, output-staging, and settlement phases, then
    adds an explicit operational guard. ``estimated_output_bytes`` is the
    output copy published into runtime CAS at settlement.
    """

    normalized_sizes: dict[str, int] = {}
    managed_input_bytes = 0
    for digest, size in object_sizes.items():
        normalized = _normalized_digest(digest)
        if normalized is None:
            raise StorageEstimateError(f"invalid managed object digest: {digest!r}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise StorageEstimateError(f"invalid managed object size for {digest!r}")
        previous = normalized_sizes.get(normalized)
        if previous is not None and previous != size:
            raise StorageEstimateError(f"contradictory managed object size for {digest!r}")
        normalized_sizes[normalized] = size
    managed_input_bytes = sum(normalized_sizes.values())

    raw_assets = registry.get("assets", {})
    if not isinstance(raw_assets, Mapping):
        raise StorageEstimateError("managed registry assets must be an object")
    managed_entry_bytes = 0
    for asset_id, raw in raw_assets.items():
        if not isinstance(raw, Mapping):
            continue
        digest = _normalized_digest(
            raw.get("content_sha256")
            or raw.get("digest")
            or raw.get("sha256")
            or raw.get("hash")
        )
        if digest is None or digest not in normalized_sizes:
            raise StorageEstimateError(
                f"managed asset {asset_id!r} has no exact entry size"
            )
        managed_entry_bytes += normalized_sizes[digest]

    effect_asset_bytes = 0
    for path, size in (effect_asset_sizes or {}).items():
        if not isinstance(path, str) or not path:
            raise StorageEstimateError("effect asset size keys must be non-empty paths")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise StorageEstimateError(f"invalid effect asset size for {path!r}")
        effect_asset_bytes += size

    profile = _render_profile(timeline, registry, requested_profile)
    fps = Fraction(*profile.fps_rational)
    frames = timeline_duration_frames(timeline, float(fps))
    duration = Fraction(frames, 1) / fps
    pixel_rate = Fraction(profile.width * profile.height, 1) * fps
    alpha = _is_alpha_timeline(timeline)

    encoder_buffer_bps = 0
    if alpha:
        codec = "prores-4444"
        video_bitrate = math.ceil(pixel_rate * _PRORES_4444_BITS_PER_PIXEL_FRAME)
        audio_bitrate = _PCM_S16LE_STEREO_BITRATE
        bitrate_basis = "6 bits_per_pixel_frame plus 48kHz stereo PCM"
    else:
        codec = "h264"
        video_bitrate, encoder_buffer_bps = h264_encoder_bitrates(
            width=profile.width,
            height=profile.height,
            fps_rational=profile.fps_rational,
        )
        # Remotion's opaque path always muxes AAC, including a silent track.
        audio_bitrate = _AAC_BITRATE
        bitrate_basis = "0.25 bits_per_pixel_frame clamped to 4-80Mbps plus 320kbps AAC"

    encoded_payload = (
        (duration * video_bitrate + encoder_buffer_bps) / 8
        + duration * audio_bitrate / 8
    )
    encoded_payload_bytes = math.ceil(encoded_payload)
    estimated_output_bytes = (
        math.ceil(
            encoded_payload
            * Fraction(100 + _MUX_OVERHEAD_PERCENT, 100)
        )
        + _MUX_FIXED_OVERHEAD_BYTES
    )
    container_overhead_bytes = estimated_output_bytes - encoded_payload_bytes
    snapshot_bytes = _canonical_json_size(timeline) + _canonical_json_size(registry)
    audio_tracks = {
        track.get("id")
        for track in timeline.get("tracks", [])
        if isinstance(track, Mapping) and track.get("kind") == "audio"
    }
    effective_audio_duration = sum(
        (
            Fraction(str(clip_timeline_duration(clip)))
            for clip in timeline.get("clips", [])
            if isinstance(clip, Mapping) and clip.get("track") in audio_tracks
        ),
        Fraction(0),
    )
    audio_asset_count = sum(
        1
        for clip in timeline.get("clips", [])
        if isinstance(clip, Mapping) and clip.get("track") in audio_tracks
    )
    merge_pcm_outputs = 1
    merge_level_inputs = audio_asset_count
    while merge_level_inputs >= 32:
        merge_level_inputs = math.ceil(merge_level_inputs / 10)
        merge_pcm_outputs += merge_level_inputs
    audio_pcm_working_bytes = math.ceil(
        4
        * 48_000
        * (effective_audio_duration + duration * merge_pcm_outputs)
    )
    encoded_working_copy_bytes = estimated_output_bytes * _PARALLEL_ENCODE_WORKING_COPIES
    alpha_frame_bytes_per_frame = (
        math.ceil(
            Fraction(profile.width * profile.height * 4 + profile.height, 1)
            * Fraction(101, 100)
        )
        if alpha
        else 0
    )
    alpha_frame_working_bytes = alpha_frame_bytes_per_frame * frames
    base_bytes = (
        managed_input_bytes
        + managed_entry_bytes
        + effect_asset_bytes
        + snapshot_bytes
    )
    if alpha:
        phase_working_bytes = max(
            managed_entry_bytes
            + effect_asset_bytes
            + audio_pcm_working_bytes
            + alpha_frame_working_bytes
            + estimated_output_bytes,
            2 * estimated_output_bytes,
        )
    else:
        phase_working_bytes = max(
            managed_entry_bytes + effect_asset_bytes + audio_pcm_working_bytes,
            2 * estimated_output_bytes,
        )
    peak_before_guard_bytes = base_bytes + phase_working_bytes
    operational_guard_bytes = max(
        _MIN_OPERATIONAL_GUARD_BYTES,
        math.ceil(peak_before_guard_bytes * _OPERATIONAL_GUARD_PERCENT / 100),
    )
    estimated_total_bytes = peak_before_guard_bytes + operational_guard_bytes
    estimated_scratch_bytes = estimated_total_bytes - estimated_output_bytes

    return {
        "schema_version": 1,
        "kind": "rendering.timeline_storage_estimate",
        "status": "runtime_enforced",
        "basis": "expanded_canonical_snapshot",
        "codec": codec,
        "bitrate_basis": bitrate_basis,
        "width": profile.width,
        "height": profile.height,
        "fps_rational": list(profile.fps_rational),
        "duration_frames": frames,
        "duration_seconds_rational": [duration.numerator, duration.denominator],
        "managed_object_count": len(normalized_sizes),
        "managed_input_bytes": managed_input_bytes,
        "managed_entry_bytes": managed_entry_bytes,
        "effect_asset_bytes": effect_asset_bytes,
        "snapshot_bytes": snapshot_bytes,
        "video_bitrate_bps": video_bitrate,
        "audio_bitrate_bps": audio_bitrate,
        "encoder_buffer_bps": encoder_buffer_bps,
        "encoded_payload_bytes": encoded_payload_bytes,
        "container_overhead_bytes": container_overhead_bytes,
        "effective_audio_seconds_rational": [
            effective_audio_duration.numerator,
            effective_audio_duration.denominator,
        ],
        "audio_asset_count": audio_asset_count,
        "merge_pcm_outputs": merge_pcm_outputs,
        "audio_pcm_working_bytes": audio_pcm_working_bytes,
        "alpha_frame_bytes_per_frame": alpha_frame_bytes_per_frame,
        "alpha_frame_working_bytes": alpha_frame_working_bytes,
        "parallel_encode_working_copies": _PARALLEL_ENCODE_WORKING_COPIES,
        "encoded_working_copy_bytes": encoded_working_copy_bytes,
        "staged_output_bytes": estimated_output_bytes,
        "base_bytes": base_bytes,
        "phase_working_bytes": phase_working_bytes,
        "peak_before_guard_bytes": peak_before_guard_bytes,
        "operational_guard_bytes": operational_guard_bytes,
        "estimated_scratch_bytes": estimated_scratch_bytes,
        "estimated_output_bytes": estimated_output_bytes,
        "estimated_total_bytes": estimated_total_bytes,
    }


__all__ = [
    "StorageEstimateError",
    "estimate_managed_render_storage",
    "h264_encoder_bitrates",
    "managed_object_sizes",
    "used_effect_asset_sizes",
]
