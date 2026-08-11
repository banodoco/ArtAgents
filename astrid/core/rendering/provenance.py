"""Core-owned provenance v2 assembly for timeline renders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file

from .contracts import (
    PROVENANCE_V1_ALWAYS_KEYS,
    PROVENANCE_V1_COMPATIBILITY_KEYS,
    PROVENANCE_V2_CORE_KEYS,
    Attachment,
    AudioOwnership,
    RenderProfile,
    RenderSegment,
    SupportReport,
    _json_safe,
    _json_safe_mapping,
    _require_qualified_id,
    _require_sha256,
    _require_string,
    _require_string_mapping,
    _validate_backend_fragments,
)


PROVENANCE_SCHEMA_VERSION = 2
CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)


def validate_backend_fragments(
    fragments: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Validate namespaces and reject top-level core-key collisions."""

    return _validate_backend_fragments(fragments or {})


def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, AudioOwnership):
        return value.value
    try:
        return AudioOwnership(value).value
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "audio_ownership must be rendered, passthrough, none, or null"
        ) from exc


def _normalize_attachments(
    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_name, raw_attachment in (attachments or {}).items():
        name = _require_string(raw_name, "attachment key")
        attachment = (
            raw_attachment
            if isinstance(raw_attachment, Attachment)
            else Attachment.from_dict(raw_attachment)
        )
        if attachment.name != name:
            raise ValueError(
                f"attachment key {name!r} must match attachment.name {attachment.name!r}"
            )
        if name in result:
            raise ValueError(f"duplicate attachment name: {name}")
        result[name] = attachment.to_dict()
    return result


def _segment_with_v1_projection(segment: RenderSegment | Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalized segment retaining legacy ``engine/from/to`` data."""

    if isinstance(segment, RenderSegment):
        payload = segment.to_dict()
    else:
        payload = _json_safe_mapping(segment, label="provenance segment")

    window = payload.get("window")
    backend = payload.get("backend")
    if isinstance(window, Mapping) and isinstance(backend, str):
        fps = window.get("fps_rational")
        start_frame = window.get("start_frame")
        end_frame = window.get("end_frame")
        if (
            isinstance(fps, Sequence)
            and not isinstance(fps, (str, bytes))
            and len(fps) == 2
            and type(fps[0]) is int
            and type(fps[1]) is int
            and fps[0] > 0
            and fps[1] > 0
            and type(start_frame) is int
            and type(end_frame) is int
        ):
            frames_per_second = fps[0] / fps[1]
            payload.setdefault("engine", backend.rsplit(".", 1)[-1])
            payload.setdefault("from", start_frame / frames_per_second)
            payload.setdefault("to", end_frame / frames_per_second)
    return payload


def _normalize_artifact_profiles(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return {
            str(key): (
                profile.to_dict() if isinstance(profile, RenderProfile) else _json_safe(profile)
            )
            for key, profile in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            profile.to_dict() if isinstance(profile, RenderProfile) else _json_safe(profile)
            for profile in value
        ]
    raise TypeError("artifact_profiles must be an object or array")


def _normalize_v1_compatibility(
    fields: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if fields is None:
        raise ValueError(
            "v1_compatibility is required and must preserve all always-emitted v1 fields"
        )
    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
    if unknown:
        raise ValueError(
            "v1 compatibility projection contains non-v1 or core-owned keys: "
            + ", ".join(unknown)
        )
    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
    if missing:
        raise ValueError(
            "v1 compatibility projection is missing always-emitted fields: "
            + ", ".join(missing)
        )
    return compatibility


def assemble_provenance_v2(
    *,
    engine: str,
    output: str | Path,
    timeline: str | Path,
    assets_registry: str | Path | None,
    requested_policy: str | Mapping[str, Any] | None,
    resolved_backend: str | None,
    source_pack: Mapping[str, Any] | None,
    alias_chain: Sequence[str] = (),
    override: Mapping[str, Any] | None = None,
    trust_eligibility: Mapping[str, Any] | None = None,
    manifest_digest: str | None = None,
    support_decision: SupportReport | Mapping[str, Any] | None = None,
    input_hashes: Mapping[str, str] | None = None,
    segments: Sequence[RenderSegment | Mapping[str, Any]] = (),
    artifact_profiles: Any = None,
    audio_ownership: AudioOwnership | str | None = None,
    normalization: Sequence[str] = (),
    finalizer: str | None = None,
    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
    v1_compatibility: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble additive provenance v2 with protected ownership boundaries.

    ``engine`` is intentionally the legacy request projection.  The actual
    selected implementation belongs in ``resolved_backend``.  Optional v1
    fields are accepted only through ``v1_compatibility`` and cannot replace
    any v2 core field.
    """

    legacy_engine = _require_string(engine, "engine")
    output_path = _require_string(str(output), "output")
    timeline_path = _require_string(str(timeline), "timeline")
    assets_path = None if assets_registry is None else _require_string(
        str(assets_registry), "assets_registry"
    )
    if isinstance(requested_policy, str):
        normalized_policy: Any = _require_string(requested_policy, "requested_policy")
    elif requested_policy is None:
        normalized_policy = None
    else:
        normalized_policy = _json_safe_mapping(requested_policy, label="requested_policy")
    normalized_backend = (
        None
        if resolved_backend is None
        else _require_qualified_id(resolved_backend, "resolved_backend")
    )
    normalized_finalizer = (
        None if finalizer is None else _require_qualified_id(finalizer, "finalizer")
    )
    aliases = [
        _require_string(alias, f"alias_chain[{index}]")
        for index, alias in enumerate(alias_chain)
    ]
    digest = None if manifest_digest is None else _require_sha256(
        manifest_digest, "manifest_digest"
    )
    support = (
        None
        if support_decision is None
        else support_decision.to_dict()
        if isinstance(support_decision, SupportReport)
        else _json_safe_mapping(support_decision, label="support_decision")
    )
    hashes = _require_string_mapping(input_hashes or {}, "input_hashes")
    normalized_segments = [_segment_with_v1_projection(segment) for segment in segments]
    normalized_normalization = [
        _require_string(item, f"normalization[{index}]")
        for index, item in enumerate(normalization)
    ]

    payload: dict[str, Any] = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "engine": legacy_engine,
        "output": output_path,
        "timeline": timeline_path,
        "assets_registry": assets_path,
        "requested_policy": normalized_policy,
        "resolved_backend": normalized_backend,
        "source_pack": _json_safe_mapping(source_pack or {}, label="source_pack"),
        "alias_chain": aliases,
        "override": None
        if override is None
        else _json_safe_mapping(override, label="override"),
        "trust_eligibility": _json_safe_mapping(
            trust_eligibility or {}, label="trust_eligibility"
        ),
        "manifest_digest": digest,
        "support_decision": support,
        "input_hashes": hashes,
        "segments": normalized_segments,
        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
        "audio_ownership": _normalize_audio_ownership(audio_ownership),
        "normalization": normalized_normalization,
        "finalizer": normalized_finalizer,
        "attachments": _normalize_attachments(attachments),
        "backend_fragments": validate_backend_fragments(backend_fragments),
    }
    payload.update(_normalize_v1_compatibility(v1_compatibility))
    return _json_safe_mapping(payload, label="provenance")


def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
    """Compatibility spelling for :func:`assemble_provenance_v2`."""

    return assemble_provenance_v2(**kwargs)


def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Assemble and atomically write a provenance v2 sidecar."""

    payload = assemble_provenance_v2(**kwargs)
    write_json_atomic(path, payload)
    return payload


def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
    """Return stable SHA-256 input hashes using Astrid's shared helper."""

    return {
        _require_string(name, "input hash name"): sha256_file(Path(path))
        for name, path in paths.items()
    }


def digest_manifest(path: str | Path) -> str:
    """Return the SHA-256 digest used to pin one static manifest."""

    return sha256_file(Path(path))


__all__ = [
    "CORE_OWNED_KEYS",
    "PROVENANCE_SCHEMA_VERSION",
    "assemble_provenance",
    "assemble_provenance_v2",
    "digest_manifest",
    "hash_input_files",
    "validate_backend_fragments",
    "write_provenance_v2",
]
