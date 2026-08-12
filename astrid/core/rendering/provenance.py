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
    RenderPlan,
    RenderProfile,
    RenderSegment,
    VideoArtifact,
    _json_safe_mapping,
    _require_sha256,
    _require_string,
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


def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
    """Derive one v1 segment projection from an authoritative v2 segment."""

    numerator, denominator = segment.window.fps_rational
    return {
        "engine": segment.renderer.id.rsplit(".", 1)[-1],
        "from": segment.window.start_frame * denominator / numerator,
        "to": segment.window.end_frame * denominator / numerator,
    }


def _normalize_artifact_profiles(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, profile in value.items():
            path = _require_string(str(key), "artifact key")
            if isinstance(profile, VideoArtifact):
                result[path] = _artifact_lineage(profile)
            elif isinstance(profile, Mapping) and "profile" in profile and "sha256" in profile:
                result[path] = _artifact_lineage_from_mapping(profile)
            else:
                raise TypeError(
                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                    "hashed lineage record {profile, sha256, attachments}; "
                    "profile-only entries carry no output hash"
                )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            (
                _artifact_lineage(profile)
                if isinstance(profile, VideoArtifact)
                else _artifact_lineage_from_mapping(profile)
            )
            for profile in value
        ]
    raise TypeError("artifact_profiles must be an object or array")


def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
    data = _json_safe_mapping(raw, label="artifact")
    if "sha256" not in data or data["sha256"] is None:
        raise ValueError("artifact lineage sha256 is required and must not be null")
    profile = data["profile"]
    attachments: dict[str, Any] = {}
    for name, att in (data.get("attachments") or {}).items():
        att = _json_safe_mapping(att, label=f"artifact attachment {name!r}")
        if att.get("sha256") is None:
            raise ValueError(f"artifact attachment {name!r} sha256 must not be null")
        attachments[str(name)] = {
            "path": _require_string(str(att.get("path")), f"attachment {name!r} path"),
            "kind": _require_string(str(att.get("kind")), f"attachment {name!r} kind"),
            "sha256": _require_sha256(str(att.get("sha256")), f"attachment {name!r} sha256"),
        }
    return {
        "profile": (
            profile
            if isinstance(profile, RenderProfile)
            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
        ).to_dict(),
        "sha256": _require_sha256(str(data["sha256"]), "artifact sha256"),
        "attachments": attachments,
    }


def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
    """One hashed artifact lineage record: profile, sha256, attachments."""
    return {
        "profile": artifact.profile.to_dict(),
        "sha256": artifact.sha256,
        "attachments": {
            name: {
                "path": attachment.path,
                "kind": attachment.kind,
                "sha256": attachment.sha256,
            }
            for name, attachment in artifact.attachments.items()
        },
    }


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
    plan: RenderPlan | Mapping[str, Any],
    artifact_profiles: Any = None,
    audio_ownership: AudioOwnership | str | None = None,
    normalization: Sequence[str] = (),
    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
    v1_compatibility: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble additive provenance v2 with protected ownership boundaries.

    ``engine`` is intentionally the legacy request projection. Routing and
    replay lineage come exclusively from the validated ``RenderPlan`` so a
    hybrid invocation cannot collapse multiple renderer identities. Optional
    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
    any v2 core field.
    """

    legacy_engine = _require_string(engine, "engine")
    output_path = _require_string(str(output), "output")
    timeline_path = _require_string(str(timeline), "timeline")
    assets_path = None if assets_registry is None else _require_string(
        str(assets_registry), "assets_registry"
    )
    normalized_plan = (
        plan
        if isinstance(plan, RenderPlan)
        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
    )
    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
    legacy_segments = [
        _legacy_segment_projection(segment) for segment in normalized_plan.segments
    ]
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
        "request_digest": normalized_plan.request_digest,
        "requested_policy": normalized_plan.requested_policy,
        "planner": normalized_plan.planner.to_dict(),
        # V1-compatible segment projection: flat {engine, from, to} entries,
        # exactly the shape legacy consumers read from `segments`.
        "segments": legacy_segments,
        # Additive normalized v2 segment records; never overwrite v1 fields.
        "segments_v2": normalized_segments,
        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
        "audio_ownership": _normalize_audio_ownership(audio_ownership),
        "normalization": normalized_normalization,
        "finalizer": normalized_plan.finalizer.to_dict(),
        "attachments": _normalize_attachments(attachments),
        "backend_fragments": validate_backend_fragments(backend_fragments),
    }
    compatibility = _normalize_v1_compatibility(v1_compatibility)
    payload.update(compatibility)
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
