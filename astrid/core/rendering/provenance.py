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
    _ECMA_WHITESPACE,
    Attachment,
    AudioOwnership,
    RenderPlan,
    RenderProfile,
    RenderSegment,
    VideoArtifact,
    _json_safe_mapping,
    _require_sha256,
    _require_string,
    _require_workspace_relative_path,
    _validate_backend_fragments,
)


PROVENANCE_SCHEMA_VERSION = 2
ADDITIVE_PROVENANCE_V2_CORE_KEYS = frozenset({"resolved_policy", "routing"})
CORE_OWNED_KEYS = frozenset(
    PROVENANCE_V2_CORE_KEYS
    | PROVENANCE_V1_COMPATIBILITY_KEYS
    | ADDITIVE_PROVENANCE_V2_CORE_KEYS
)


def validate_backend_fragments(
    fragments: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Validate namespaces and reject top-level core-key collisions."""

    normalized = _validate_backend_fragments(fragments or {})
    for namespace, fragment in normalized.items():
        conflicts = sorted(set(fragment) & ADDITIVE_PROVENANCE_V2_CORE_KEYS)
        if conflicts:
            raise ValueError(
                f"backend fragment {namespace!r} attempts to overwrite core-owned "
                f"keys: {', '.join(conflicts)}"
            )
    return normalized


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
            Attachment.from_dict(
                {
                    "name": raw_attachment.name,
                    "path": raw_attachment.path,
                    "kind": raw_attachment.kind,
                    "sha256": raw_attachment.sha256,
                }
            )
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


def _resolution_request_id(segment: RenderSegment) -> str:
    """Recover the registry id that selected one validated renderer.

    Alias chains retain their requested id first.  An override without an
    alias retains its source in ``override.from``.  Otherwise the resolved id
    was also the requested id.  This is enough to distinguish the legacy
    ``remotion`` policy's FFmpeg-first route without accepting parallel,
    caller-authored routing evidence.
    """

    renderer = segment.renderer
    if renderer.alias_chain:
        return renderer.alias_chain[0]
    if renderer.override is not None:
        return renderer.override["from"]
    return renderer.id


def _resolved_policy(plan: RenderPlan) -> dict[str, Any]:
    """Return the complete set of capability ids selected by one plan."""

    renderer_ids = list(
        dict.fromkeys(segment.renderer.id for segment in plan.segments)
    )
    return {
        "planner": plan.planner.id,
        "renderers": renderer_ids,
        "finalizer": plan.finalizer.id,
    }


def _routing_record(
    legacy_engine: str,
    plan: RenderPlan,
    resolved_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive selected-policy lineage and visible legacy translation.

    The service's legacy ``remotion`` policy tries the qualified FFmpeg route
    first and emits a warning when that supported route wins.  The plan pins
    the selected renderer but cannot by itself explain why its legacy
    ``engine`` projection still says ``remotion``.  Record that explanation
    additively while leaving the frozen nested resolution records authoritative
    for aliases, overrides, trust, manifests, and support decisions.
    """

    renderer_ids = list(resolved_policy["renderers"])
    resolved_backend = renderer_ids[0] if len(renderer_ids) == 1 else None
    auto_routed = (
        legacy_engine == "remotion"
        and len(plan.segments) == 1
        and _resolution_request_id(plan.segments[0]) == "rendering.ffmpeg"
    )
    auto_route_reason = None
    if auto_routed:
        auto_route_reason = (
            "legacy selector 'remotion' auto-routed the supported request to "
            f"{plan.segments[0].renderer.id}"
        )
    return {
        "requested_engine": legacy_engine,
        "requested_policy": plan.requested_policy,
        "resolved_policy": dict(resolved_policy),
        "resolved_backend": resolved_backend,
        "resolved_backends": renderer_ids,
        "auto_route": auto_routed,
        "auto_route_reason": auto_route_reason,
        "segment_reasons": dict(plan.reasons),
    }


def _reject_duplicate_attachment_names(
    lineage: Mapping[str, Any],
    seen: set[str],
) -> None:
    """Reject attachment names repeated across segment artifacts."""
    for name in (lineage.get("attachments") or {}):
        if name in seen:
            raise ValueError(
                f"duplicate attachment name {name!r} across segment artifacts"
            )
        seen.add(name)


def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
    if value is None:
        value = {}
    if isinstance(value, Mapping):
        if segments and len(segments) > 1:
            raise TypeError(
                "mapping-form artifact_profiles is unordered; use sequence form "
                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
            )
        result: dict[str, Any] = {}
        seen_attachment_names: set[str] = set()
        for key, profile in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
                )
            path = _require_workspace_relative_path(key, "artifact key")
            if isinstance(profile, VideoArtifact):
                if path != profile.path:
                    raise ValueError(
                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
                        f"{profile.path!r}"
                    )
                profile = VideoArtifact.from_dict(
                    _json_safe_mapping(profile.to_dict(), label="artifact")
                )
                lineage = _artifact_lineage(profile)
            elif isinstance(profile, Mapping):
                lineage = _artifact_lineage_from_mapping(profile, key=path)
            else:
                raise TypeError(
                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                    "hashed lineage record {profile, sha256, attachments}; "
                    "profile-only entries carry no output hash"
                )
            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
            result[path] = lineage
        # A positive plan must record exactly one hashed artifact per segment.
        if segments:
            if len(result) != len(segments):
                raise ValueError(
                    f"artifact_profiles must record exactly one hashed lineage entry "
                    f"per segment: expected {len(segments)}, got {len(result)}"
                )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        lineage: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        seen_attachment_names: set[str] = set()
        for raw_profile in value:
            if isinstance(raw_profile, VideoArtifact):
                # Reconstruct through the DTO so mutation cannot smuggle
                # invalid paths, profiles, or attachments past validation.
                profile = VideoArtifact.from_dict(
                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
                )
                path = profile.path
                record = _artifact_lineage(profile)
            elif isinstance(raw_profile, Mapping):
                # Already-emitted lineage record: re-validate and re-key by
                # its (validated) path so emitted provenance round-trips.
                raw_path = raw_profile.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip(_ECMA_WHITESPACE):
                    raise ValueError(
                        "emitted lineage record must carry a non-empty string path"
                    )
                record = _artifact_lineage_from_mapping(
                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
                )
                path = record["path"]
            else:
                raise TypeError(
                    "sequence artifact_profiles entries must be VideoArtifacts "
                    "or emitted lineage records"
                )
            if path in seen_paths:
                raise ValueError(
                    f"artifact_profiles sequence contains duplicate path "
                    f"{path!r}"
                )
            seen_paths.add(path)
            _reject_duplicate_attachment_names(record, seen_attachment_names)
            lineage.append(record)
        if segments:
            if len(lineage) != len(segments):
                raise ValueError(
                    f"artifact_profiles must record exactly one hashed lineage entry "
                    f"per segment: expected {len(segments)}, got {len(lineage)}"
                )
        return lineage
    raise TypeError("artifact_profiles must be an object or array")


def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
    raw_keys = set(raw)
    allowed = {"profile", "sha256", "attachments", "path"}
    unknown = sorted(raw_keys - allowed)
    if unknown:
        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
    if missing:
        raise ValueError(
            f"artifact lineage is missing required fields: {', '.join(missing)}"
        )
    if raw["sha256"] is None:
        raise ValueError("artifact lineage sha256 is required and must not be null")
    if not isinstance(raw["sha256"], str):
        raise TypeError("artifact lineage sha256 must be a string")
    if "path" in raw:
        if not isinstance(raw["path"], str):
            raise TypeError("artifact lineage path must be a string")
        embedded = _require_workspace_relative_path(raw["path"], "artifact path")
        if embedded != key:
            raise ValueError(
                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
            )
    profile = raw["profile"]
    attachments: dict[str, Any] = {}
    raw_attachments = raw["attachments"]
    if raw_attachments is None:
        raise ValueError("artifact lineage attachments must be an object (may be empty)")
    if not isinstance(raw_attachments, Mapping):
        raise TypeError("artifact lineage attachments must be an object")
    for name, att in raw_attachments.items():
        name = _require_string(name, "attachment name")
        if isinstance(att, Attachment):
            if att.name != name:
                raise ValueError(
                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
                )
            att = {
                "path": att.path,
                "kind": att.kind,
                "sha256": att.sha256,
            }
        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
        if att_unknown:
            raise ValueError(
                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
            )
        att_missing = sorted({"path", "kind", "sha256"} - set(att))
        if att_missing:
            raise ValueError(
                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
            )
        if not isinstance(att["sha256"], str):
            raise TypeError(f"attachment {name!r} sha256 must be a string")
        # Validate through the Attachment DTO so workspace-path containment and
        # kind grammar are enforced uniformly for raw and dataclass values.
        validated = Attachment(
            name=name,
            path=att["path"],
            kind=att["kind"],
            sha256=att["sha256"],
        )
        attachments[name] = {
            "path": validated.path,
            "kind": validated.kind,
            "sha256": validated.sha256,
        }
    return {
        "path": key,
        "profile": RenderProfile.from_dict(
            _json_safe_mapping(profile, label="artifact profile")
        ).to_dict(),
        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
        "attachments": attachments,
    }


def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
    """One hashed artifact lineage record: profile, sha256, attachments."""
    return _artifact_lineage_from_mapping(
        {
            "profile": artifact.profile,
            "sha256": artifact.sha256,
            "attachments": artifact.attachments,
        },
        key=artifact.path,
    )


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
        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
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
    compatibility = _normalize_v1_compatibility(v1_compatibility)
    resolved_policy = _resolved_policy(normalized_plan)

    payload: dict[str, Any] = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "engine": legacy_engine,
        "output": output_path,
        "timeline": timeline_path,
        "assets_registry": assets_path,
        "request_digest": normalized_plan.request_digest,
        "requested_policy": normalized_plan.requested_policy,
        "resolved_policy": resolved_policy,
        "routing": _routing_record(
            legacy_engine,
            normalized_plan,
            resolved_policy,
        ),
        "planner": normalized_plan.planner.to_dict(),
        # V1-compatible segment projection: flat {engine, from, to} entries,
        # exactly the shape legacy consumers read from `segments`.
        "segments": legacy_segments,
        # Additive normalized v2 segment records; never overwrite v1 fields.
        "segments_v2": normalized_segments,
        "artifact_profiles": _normalize_artifact_profiles(
            artifact_profiles,
            segments=normalized_plan.segments,
        ),
        "audio_ownership": _normalize_audio_ownership(audio_ownership),
        "normalization": normalized_normalization,
        "finalizer": normalized_plan.finalizer.to_dict(),
        "attachments": _normalize_attachments(attachments),
        "backend_fragments": validate_backend_fragments(backend_fragments),
    }
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
    "ADDITIVE_PROVENANCE_V2_CORE_KEYS",
    "CORE_OWNED_KEYS",
    "PROVENANCE_SCHEMA_VERSION",
    "assemble_provenance",
    "assemble_provenance_v2",
    "digest_manifest",
    "hash_input_files",
    "validate_backend_fragments",
    "write_provenance_v2",
]
