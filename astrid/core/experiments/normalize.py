"""Provider-independent manifest normalization.

Normalizes Astrid universal result manifests (v1) and generation manifests (v2)
into the provider-independent review case model.

Key properties:
- Provider-specific execution logic does not enter this module.
- Only reads manifest.json files; never mutates source runs.
- Ordered input roles are preserved.
- Secrets, tokens, signed URLs are stripped.
- Failures produce structured records with capture gaps.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from astrid.core.experiments.capture import sanitize_portable
from astrid.core.experiments.media import probe_artifact
from astrid.core.experiments.schema import (
    ExperimentValidationError,
    is_valid_content_hash,
    normalize_status,
    require_relative_path,
)
from astrid.core.foundation.hash import sha256_file


def resolve_manifest_path(
    run_path: Path,
    manifest_path: str,
) -> tuple[Path | None, str | None]:
    """Resolve a manifest only when it remains inside its resolved run directory.

    The returned path is the resolved target, not the potentially symlinked
    spelling supplied by the experiment.  Callers must not read or hash the
    manifest when this function returns an error.
    """
    try:
        resolved_run = run_path.resolve(strict=True)
    except FileNotFoundError:
        return None, f"Cannot read manifest: {manifest_path}"
    except (OSError, RuntimeError):
        return None, "Cannot resolve run directory"
    if not resolved_run.is_dir():
        return None, "Run path is not a directory"

    try:
        resolved_manifest = (resolved_run / manifest_path).resolve(strict=True)
    except FileNotFoundError:
        return None, f"Cannot read manifest: {manifest_path}"
    except (OSError, RuntimeError):
        return None, "Cannot resolve source manifest"
    try:
        resolved_manifest.relative_to(resolved_run)
    except ValueError:
        return None, "Source manifest resolves outside the run directory"
    if not resolved_manifest.is_file():
        return None, "Source manifest is not a regular file"
    return resolved_manifest, None


def normalize_case_from_manifest(
    *,
    manifest: Mapping[str, Any],
    manifest_path: str,
    case: Mapping[str, Any],
    run_path: Path,
    manifest_content_hash: str | None = None,
) -> dict[str, Any]:
    """Normalize a single experiment case from its source manifest.

    Args:
        manifest: The parsed manifest.json content.
        manifest_path: Relative path to the manifest within the run.
        case: The experiment case definition.
        run_path: Absolute path to the run directory containing the manifest.

    Returns:
        A normalized review case dict.

    Raises:
        ExperimentValidationError: If the manifest is invalid or missing required fields.
    """
    review_case: dict[str, Any] = {
        "case_id": case["case_id"],
        "run_id": case["run_id"],
        "label": case.get("label", case["case_id"]),
        "attempt": case.get("attempt", 1),
        "factors": dict(case.get("factors", {})),
        "relationship": dict(case.get("relationship", {})),
        "expected_input_roles": list(case.get("expected_input_roles", [])),
        "included": case.get("included", True),
    }

    # Defaults
    review_case.setdefault("status", "draft")
    review_case.setdefault("provider", "unknown")
    review_case.setdefault("backend", None)
    review_case.setdefault("model", None)
    review_case.setdefault("model_actual", None)
    review_case.setdefault("mode", None)
    review_case.setdefault("prompt", None)
    review_case.setdefault("parameters", {})
    review_case.setdefault("inputs", [])
    review_case.setdefault("outputs", [])
    review_case.setdefault("timing", {})
    review_case.setdefault("cost_usd", None)
    review_case.setdefault("warnings", [])
    review_case.setdefault("error", None)
    review_case.setdefault("capture_gaps", [])
    resolved_manifest, containment_error = resolve_manifest_path(
        run_path, manifest_path
    )
    if containment_error is not None:
        review_case["status"] = "failed"
        review_case["error"] = containment_error
        review_case["capture_gaps"].append({
            "kind": "missing_manifest",
            "detail": containment_error,
        })
        source_manifest: dict[str, Any] = {
            "path": manifest_path,
            "verified": False,
        }
        expected_ref = case.get("source_manifest")
        if isinstance(expected_ref, Mapping):
            expected_hash = expected_ref.get("content_hash")
            if isinstance(expected_hash, str):
                source_manifest["expected_content_hash"] = expected_hash
        review_case["source_manifest"] = source_manifest
        sanitized = sanitize_portable(review_case)
        assert isinstance(sanitized, dict)
        return sanitized

    assert resolved_manifest is not None
    actual_manifest_hash = manifest_content_hash or (
        f"sha256:{sha256_file(resolved_manifest)}"
    )
    source_manifest: dict[str, Any] = {
        "path": manifest_path,
        "content_hash": actual_manifest_hash,
        "verified": True,
    }
    expected_ref = case.get("source_manifest")
    if isinstance(expected_ref, Mapping):
        expected_hash = expected_ref.get("content_hash")
        if isinstance(expected_hash, str):
            source_manifest["expected_content_hash"] = expected_hash
            source_manifest["verified"] = expected_hash == actual_manifest_hash
            if expected_hash != actual_manifest_hash:
                review_case["status"] = "failed"
                review_case["error"] = "Source manifest digest does not match the experiment pin"
                review_case["capture_gaps"].append({
                    "kind": "ambiguous_provenance",
                    "detail": (
                        f"Source manifest {manifest_path!r} digest mismatch: "
                        f"expected {expected_hash}, found {actual_manifest_hash}"
                    ),
                })
                review_case["source_manifest"] = source_manifest
                return review_case
    review_case["source_manifest"] = source_manifest

    # Capture error text (but don't decide status yet — let _resolve_status handle it)
    if isinstance(manifest.get("error"), str) and manifest["error"]:
        review_case["error"] = manifest["error"]

    schema_ver = manifest.get("schema_version")
    if type(schema_ver) is not int:
        review_case["status"] = "failed"
        review_case["error"] = "manifest has no valid integer schema_version"
        review_case["capture_gaps"].append({
            "kind": "missing_manifest",
            "detail": "manifest has no valid schema_version",
        })
        sanitized = sanitize_portable(review_case)
        assert isinstance(sanitized, dict)
        return sanitized

    # Parse generation v2 fields
    if schema_ver == 2:
        _normalize_v2(manifest, review_case, run_path)
    elif schema_ver == 1:
        _normalize_v1(manifest, review_case, run_path)
    else:
        review_case["capture_gaps"].append({
            "kind": "missing_manifest",
            "detail": f"unknown manifest schema_version: {schema_ver}",
        })

    # Capture gaps are evidence, not provider-specific decoration. Preserve
    # importer/adapter gaps in the common review model before adding any gaps
    # mechanically detected during normalization.
    manifest_gaps = manifest.get("capture_gaps")
    if isinstance(manifest_gaps, list):
        for gap in manifest_gaps:
            if not isinstance(gap, Mapping) or not isinstance(gap.get("kind"), str):
                continue
            normalized_gap = {"kind": gap["kind"]}
            if isinstance(gap.get("detail"), str):
                normalized_gap["detail"] = gap["detail"]
            review_case["capture_gaps"].append(normalized_gap)

    # Extract prompt from v1 inputs if not already set
    if review_case["prompt"] is None and isinstance(manifest.get("inputs"), Mapping):
        inputs = manifest["inputs"]
        if isinstance(inputs.get("prompt"), str):
            review_case["prompt"] = inputs["prompt"]
        elif isinstance(inputs.get("query"), str):
            review_case["prompt"] = inputs["query"]

    # Resolve status from lifecycle fields
    _resolve_status(manifest, review_case)

    # Detect capture gaps
    _detect_capture_gaps(review_case)

    sanitized = sanitize_portable(review_case)
    assert isinstance(sanitized, dict)
    return sanitized


def _normalize_v2(manifest: Mapping[str, Any], review_case: dict[str, Any], run_path: Path) -> None:
    """Populate review_case from a generation v2 manifest."""
    # Provider
    kind = str(manifest.get("kind", ""))
    execution = str(manifest.get("execution", "")) if manifest.get("execution") else None
    review_case["provider"] = _provider_from_kind(kind, execution=execution)
    if isinstance(manifest.get("provider"), str):
        review_case["provider"] = manifest["provider"]
    if isinstance(manifest.get("backend"), str):
        review_case["backend"] = manifest["backend"]
    if isinstance(manifest.get("provider_extension"), Mapping):
        review_case["provider_extension"] = dict(manifest["provider_extension"])

    # Model
    model = manifest.get("model")
    if isinstance(model, str):
        review_case["model"] = model
    model_actual = manifest.get("model_actual")
    if isinstance(model_actual, str):
        review_case["model_actual"] = model_actual

    # Mode
    mode_used = manifest.get("mode_used")
    if isinstance(mode_used, str):
        review_case["mode"] = mode_used

    # Request fields
    request = manifest.get("request")
    if isinstance(request, Mapping):
        review_case["prompt"] = request.get("prompt")
        # Preserve the complete non-secret request.  The final recursive
        # sanitizer redacts secret-bearing keys/headers and provider URLs;
        # provider-specific knobs are not silently discarded.
        review_case["request"] = dict(request)
        # Collect parameters
        params: dict[str, Any] = {}
        for key in ("seed", "count", "size", "negative_prompt", "duration", "resolution",
                     "aspect_ratio", "fps", "quality", "style"):
            if key in request:
                params[key] = request[key]
        if params:
            review_case["parameters"] = params

    # Timing
    duration_ms = manifest.get("duration_ms")
    if isinstance(duration_ms, (int, float)):
        review_case["timing"]["duration_ms"] = int(duration_ms)

    # Cost
    cost = manifest.get("cost_usd")
    if isinstance(cost, (int, float)):
        review_case["cost_usd"] = cost

    # Warnings
    manifest_warnings = manifest.get("warnings")
    if isinstance(manifest_warnings, list):
        review_case["warnings"] = [
            w if isinstance(w, str) else json.dumps(w)
            for w in manifest_warnings
        ]

    # Seed
    seed = manifest.get("seed")
    if isinstance(seed, int):
        review_case["parameters"].setdefault("seed", seed)

    # Applied/dropped features
    applied = manifest.get("applied_features")
    if isinstance(applied, list):
        review_case.setdefault("applied_features", applied)
    dropped = manifest.get("dropped_features")
    if isinstance(dropped, list):
        review_case.setdefault("dropped_features", dropped)

    # Requested features — the tunable knobs the experiment asked for, taken
    # verbatim from the request object.  Kept distinct from applied/dropped so
    # the viewer can show all three columns without implying equivalence.
    requested = _extract_requested_features(manifest)
    if requested:
        review_case.setdefault("requested_features", requested)

    # Source URLs — signed / temporary URLs must never survive normalization.
    # Persist no provider URL strings at all.  Replace with safe non-string
    # evidence: source_url_count and source_urls_present.
    source_urls = manifest.get("source_urls")
    if isinstance(source_urls, list) and source_urls:
        count = sum(1 for u in source_urls if isinstance(u, str))
        if count > 0:
            review_case.setdefault("source_url_count", count)
            review_case.setdefault("source_urls_present", True)

    # Request ID
    request_id = manifest.get("request_id")
    if isinstance(request_id, str):
        review_case.setdefault("request_id", request_id)

    # Outputs
    _normalize_outputs(manifest.get("outputs", []), review_case)

    # Inputs from v2 request
    _normalize_v2_inputs(manifest, review_case)

    # Verify local artifacts against the run directory
    _verify_case_artifacts(review_case, run_path)


def _normalize_v1(manifest: Mapping[str, Any], review_case: dict[str, Any], run_path: Path) -> None:
    """Populate review_case from a universal result manifest v1."""
    kind = str(manifest.get("kind", ""))
    review_case["provider"] = _provider_from_kind(kind)
    if isinstance(manifest.get("provider_extension"), Mapping):
        review_case["provider_extension"] = dict(manifest["provider_extension"])

    # Try to pull model info from inputs
    inputs = manifest.get("inputs")
    if isinstance(inputs, Mapping):
        if isinstance(inputs.get("model"), str):
            review_case["model"] = inputs["model"]
        if isinstance(inputs.get("mode"), str):
            review_case["mode"] = inputs["mode"]
        if isinstance(inputs.get("execution"), str):
            review_case.setdefault("execution", inputs["execution"])

        # Prompt (also handled later in normalize_case_from_manifest, but set
        # it here so v1-only manifests surface it promptly).
        if isinstance(inputs.get("prompt"), str):
            review_case["prompt"] = inputs["prompt"]
        elif isinstance(inputs.get("query"), str):
            review_case["prompt"] = inputs["query"]
        if isinstance(inputs.get("prompt_capture"), str):
            review_case["prompt_capture"] = inputs["prompt_capture"]

        # Capture tunable parameters from the inputs map (ComfyUI runs often
        # record seed/steps/cfg/duration here).  Additive only.
        params = dict(review_case.get("parameters") or {})
        for key in ("seed", "steps", "cfg", "duration", "resolution",
                    "aspect_ratio", "fps", "quality", "style", "count",
                    "sampler", "scheduler", "guidance_scale", "negative_prompt"):
            if key in inputs and key not in params:
                params[key] = inputs[key]
        if params:
            review_case["parameters"] = params

        # Requested-feature knobs for v1 manifests (parallel to v2 handling).
        requested = sorted(
            k for k in _REQUEST_FEATURE_KEYS if k in inputs
        )
        if requested:
            review_case.setdefault("requested_features", requested)

        # Preserve the workflow reference and declared bindings for ComfyUI
        # runs without forcing them into canonical generation fields.
        if (
            isinstance(inputs.get("workflow"), str)
            and review_case["provider"] == "comfyui"
        ):
            workflow_ext: dict[str, Any] = {"workflow_path": inputs["workflow"]}
            for binding_key in ("template_id", "template", "bindings", "checkpoint", "lora"):
                if isinstance(inputs.get(binding_key), (str, list, dict)):
                    workflow_ext[binding_key] = inputs[binding_key]
            review_case.setdefault("provider_extension", {}).setdefault(
                "comfyui", {}
            ).update(workflow_ext)

    # Outputs
    _normalize_outputs(manifest.get("outputs", []), review_case)

    # Inputs — v1 manifests often have input references in the inputs map
    _normalize_v1_inputs(manifest, review_case)

    # Warnings
    manifest_warnings = manifest.get("warnings")
    if isinstance(manifest_warnings, list):
        review_case["warnings"] = [
            w if isinstance(w, str) else json.dumps(w)
            for w in manifest_warnings
        ]

    # Verify local artifacts against the run directory
    _verify_case_artifacts(review_case, run_path)


def _normalize_outputs(
    outputs: Sequence[Any],
    review_case: dict[str, Any],
) -> None:
    """Normalize output entries, stripping forbidden fields."""
    normalized = []
    for out in outputs:
        if not isinstance(out, Mapping):
            continue
        # Skip optional entries that are marked as missing
        if out.get("missing"):
            continue
        entry: dict[str, Any] = {}

        # Path
        path = out.get("path")
        if isinstance(path, str):
            try:
                entry["path"] = require_relative_path(path)
            except ExperimentValidationError:
                review_case.setdefault("capture_gaps", []).append({
                    "kind": "ambiguous_provenance",
                    "detail": "Output path was unsafe and was omitted",
                })
                continue

        # Content hash
        content_hash = out.get("content_hash")
        if isinstance(content_hash, str) and is_valid_content_hash(content_hash):
            entry["content_hash"] = content_hash
        elif isinstance(out.get("sha256"), str):
            raw = out["sha256"]
            entry["content_hash"] = f"sha256:{raw}" if not raw.startswith("sha256:") else raw

        # Media type
        media_type = out.get("media_type")
        if isinstance(media_type, str):
            entry["media_type"] = media_type

        # Metadata
        metadata = out.get("metadata")
        if isinstance(metadata, Mapping):
            entry["metadata"] = dict(metadata)

        # Skip entries without required fields
        if "path" not in entry and "content_hash" not in entry:
            # Directory entries may have entries array
            if "entries" in out:
                entry["path"] = path if isinstance(path, str) else "."
                content_hash = out.get("content_hash")
                if isinstance(content_hash, str) and is_valid_content_hash(content_hash):
                    entry["content_hash"] = content_hash

        if "path" in entry:
            # Never fabricate a digest.  If no verified hash is available the
            # entry must appear without content_hash and a capture gap must
            # record the missing evidence honestly.
            if "content_hash" not in entry:
                review_case.setdefault("capture_gaps", []).append({
                    "kind": "missing_output_hash",
                    "detail": f"Output {entry.get('path', '?')} has no verified content hash",
                })
            normalized.append(entry)

    review_case["outputs"] = normalized


def _normalize_v2_inputs(
    manifest: Mapping[str, Any],
    review_case: dict[str, Any],
) -> None:
    """Extract ordered inputs from a v2 generation manifest."""
    inputs_list: list[dict[str, Any]] = []
    ordinal = 0
    request = manifest.get("request")

    # Image reference (i2i, edit modes)
    if isinstance(request, Mapping):
        image_ref = request.get("image_ref_resolved")
        if isinstance(image_ref, str) and image_ref:
            ordinal += 1
            entry: dict[str, Any] = {
                "ordinal": ordinal,
                "role": "appearance_reference",
                "path": image_ref,
            }
            inputs_list.append(entry)

        # Video reference (v2v mode)
        video_ref = request.get("video_ref")
        if isinstance(video_ref, str) and video_ref:
            ordinal += 1
            entry = {
                "ordinal": ordinal,
                "role": "motion_reference",
                "path": video_ref,
            }
            inputs_list.append(entry)

        # Start/end frames
        for frame_key, role in [
            ("start_frame_ref", "start_frame"),
            ("end_frame_ref", "end_frame"),
        ]:
            frame_val = request.get(frame_key)
            if isinstance(frame_val, str) and frame_val:
                ordinal += 1
                entry = {
                    "ordinal": ordinal,
                    "role": role,
                    "path": frame_val,
                }
                inputs_list.append(entry)

        # Style reference
        style_ref = request.get("style_ref")
        if isinstance(style_ref, str) and style_ref:
            ordinal += 1
            entry = {
                "ordinal": ordinal,
                "role": "style_reference",
                "path": style_ref,
            }
            inputs_list.append(entry)

        # Mask
        mask_ref = request.get("mask_ref")
        if isinstance(mask_ref, str) and mask_ref:
            ordinal += 1
            entry = {
                "ordinal": ordinal,
                "role": "mask",
                "path": mask_ref,
            }
            inputs_list.append(entry)

        # Control signal
        control_ref = request.get("control_ref")
        if isinstance(control_ref, str) and control_ref:
            ordinal += 1
            entry = {
                "ordinal": ordinal,
                "role": "control_signal",
                "path": control_ref,
            }
            inputs_list.append(entry)

    # Inputs from v1-style inputs map
    manifest_inputs = manifest.get("inputs")
    if isinstance(manifest_inputs, Mapping):
        # Look for input_artifacts or media references
        for key in ("image", "video", "audio", "reference", "source"):
            val = manifest_inputs.get(key)
            if isinstance(val, str) and val:
                # Don't duplicate if already captured via request object
                if not any(inp["path"] == val for inp in inputs_list):
                    ordinal += 1
                    role_map = {
                        "image": "appearance_reference",
                        "video": "source_video",
                        "audio": "source_audio",
                        "reference": "other",
                        "source": "source_video",
                    }
                    entry = {
                        "ordinal": ordinal,
                        "role": role_map.get(key, "other"),
                        "path": val,
                    }
                    inputs_list.append(entry)

    review_case["inputs"] = inputs_list


def _normalize_v1_inputs(
    manifest: Mapping[str, Any],
    review_case: dict[str, Any],
) -> None:
    """Extract ordered inputs from a v1 universal result manifest."""
    inputs_list: list[dict[str, Any]] = []
    ordinal = 0
    manifest_inputs = manifest.get("inputs")
    if not isinstance(manifest_inputs, Mapping):
        review_case["inputs"] = inputs_list
        return

    declared = manifest_inputs.get("ordered_artifacts")
    if isinstance(declared, list):
        for item in declared:
            if not isinstance(item, Mapping):
                continue
            path = item.get("path")
            role = item.get("role", "other")
            if not isinstance(path, str) or not isinstance(role, str):
                continue
            try:
                safe_path = require_relative_path(path)
            except ExperimentValidationError:
                review_case.setdefault("capture_gaps", []).append({
                    "kind": "ambiguous_provenance",
                    "detail": "Declared ordered input had an unsafe path and was omitted",
                })
                continue
            ordinal += 1
            entry = {
                "ordinal": ordinal,
                "role": role,
                "path": safe_path,
            }
            content_hash = item.get("content_hash")
            if isinstance(content_hash, str) and is_valid_content_hash(content_hash):
                entry["content_hash"] = content_hash
            if isinstance(item.get("media_type"), str):
                entry["media_type"] = item["media_type"]
            inputs_list.append(entry)

    for key, role in [
        ("image", "appearance_reference"),
        ("video", "source_video"),
        ("audio", "source_audio"),
        ("reference", "other"),
        ("source", "source_video"),
        ("workflow", "workflow"),
    ]:
        val = manifest_inputs.get(key)
        if isinstance(val, str) and val:
            ordinal += 1
            try:
                safe_path = require_relative_path(val)
            except ExperimentValidationError:
                review_case.setdefault("capture_gaps", []).append({
                    "kind": "ambiguous_provenance",
                    "detail": f"Input slot {key!r} had an unsafe path and was omitted",
                })
                continue
            entry: dict[str, Any] = {
                "ordinal": ordinal,
                "role": role,
                "path": safe_path,
            }
            # Try to find content hash
            if isinstance(manifest_inputs.get(f"{key}_sha256"), str):
                sha = manifest_inputs[f"{key}_sha256"]
                if is_valid_content_hash(f"sha256:{sha}"):
                    entry["content_hash"] = f"sha256:{sha}"
                elif is_valid_content_hash(sha):
                    entry["content_hash"] = sha
            inputs_list.append(entry)

    review_case["inputs"] = inputs_list


# Tunable request knobs surfaced as "requested features".  Prompt text is
# intentionally excluded — it is not a feature, it is the request itself.
_REQUEST_FEATURE_KEYS = (
    "seed",
    "count",
    "size",
    "negative_prompt",
    "duration",
    "resolution",
    "aspect_ratio",
    "fps",
    "quality",
    "style",
    "steps",
    "cfg",
    "sampler",
    "scheduler",
    "guidance_scale",
    "num_frames",
)


def _extract_requested_features(manifest: Mapping[str, Any]) -> list[str]:
    """Return the sorted feature knobs present on the request object.

    Pure metadata: we record *which* knobs were requested, never their secret
    values.  Values remain available under ``parameters`` for the renderer.
    """
    request = manifest.get("request")
    if not isinstance(request, Mapping):
        return []
    found = [k for k in _REQUEST_FEATURE_KEYS if k in request]
    return sorted(found)


def _provider_from_kind(kind: str, *, execution: str | None = None) -> str:
    """Derive a provider hint from the manifest kind and execution mode.

    Only explicit evidence (kind string, execution field) is used.
    Generic Astrid capability names such as ``generation.generate_image``
    map to ``\"unknown\"`` — never assume a specific provider.
    """
    kind_lower = kind.lower()
    tokens = {token for token in re.split(r"[^a-z0-9]+", kind_lower) if token}
    kind_lower = kind.lower()
    # Check openai before generic generate_image
    if "openai" in tokens:
        return "openai"
    # Local generation: check execution mode
    if execution == "local" or "local" in tokens:
        return "local"
    # Only return fal when the word 'fal' appears explicitly
    if "fal" in tokens:
        return "fal"
    if "comfy" in tokens or "comfyui" in tokens or "vibecomfy" in tokens:
        return "comfyui"
    if "discord" in tokens:
        return "discord_browser"
    return "unknown"


def _resolve_status(manifest: Mapping[str, Any], review_case: dict[str, Any]) -> None:
    """Resolve lifecycle status from manifest fields."""
    # If already set to failed by error field, keep it
    if review_case["status"] == "failed":
        return

    # Check explicit status field
    raw_status = manifest.get("status")
    if isinstance(raw_status, str):
        canonical = normalize_status(raw_status)
        if canonical not in {
            "completed", "partial", "provider_rejected", "failed",
            "timed_out", "interrupted", "draft",
        }:
            review_case["status"] = "draft"
            review_case.setdefault("capture_gaps", []).append({
                "kind": "unknown",
                "detail": f"Unrecognized lifecycle status {raw_status!r}",
            })
            return
        # A success status accompanied by an error is contradictory evidence.
        # With recoverable outputs it is partial; without outputs it is failed.
        if canonical == "completed" and review_case.get("error"):
            canonical = "partial" if review_case.get("outputs") else "failed"
        review_case["status"] = canonical
        return

    # Infer from outputs
    outputs = review_case.get("outputs", [])
    manifest_outputs = manifest.get("outputs", [])
    if isinstance(manifest_outputs, list) and manifest_outputs:
        # Has outputs — check for partial (optional missing)
        has_partial = any(
            isinstance(o, Mapping) and o.get("missing") for o in manifest_outputs
        )
        if has_partial and outputs:
            review_case["status"] = "partial"
        elif outputs:
            review_case["status"] = "completed"
        else:
            review_case["status"] = "draft"
    else:
        # No outputs — check for error
        if review_case.get("error"):
            review_case["status"] = "partial" if outputs else "failed"
        elif manifest.get("error"):
            review_case["status"] = "failed"
        else:
            review_case["status"] = "draft"


def _detect_capture_gaps(review_case: dict[str, Any]) -> None:
    """Detect missing or ambiguous provenance."""
    gaps = list(review_case.get("capture_gaps", []))

    if not review_case.get("prompt"):
        gaps.append({
            "kind": "missing_prompt",
            "detail": "No prompt text found in manifest",
        })

    expected_roles = review_case.get("expected_input_roles", [])
    actual_roles = [inp.get("role") for inp in review_case.get("inputs", [])]
    for role in expected_roles:
        if role not in actual_roles:
            gaps.append({
                "kind": "ambiguous_provenance",
                "detail": f"Expected input role {role!r} was not captured",
            })

    # Check inputs for missing hashes
    for inp in review_case.get("inputs", []):
        if "content_hash" not in inp:
            gaps.append({
                "kind": "missing_input_hash",
                "detail": f"Input at ordinal {inp.get('ordinal', '?')} has no content hash",
            })

    # Check outputs for missing hashes
    for out in review_case.get("outputs", []):
        if "content_hash" not in out:
            gaps.append({
                "kind": "missing_output_hash",
                "detail": f"Output {out.get('path', '?')} has no content hash",
            })

    # Input-output echo detection (input mistaken for output)
    for inp in review_case.get("inputs", []):
        inp_hash = inp.get("content_hash")
        if not inp_hash:
            continue
        for out in review_case.get("outputs", []):
            out_hash = out.get("content_hash")
            if out_hash and inp_hash == out_hash:
                gaps.append({
                    "kind": "unknown",
                    "detail": (
                        f"Input {inp.get('path')} hash matches output "
                        f"{out.get('path')} — possible input echo"
                    ),
                })

    # Deduplicate
    seen = set()
    unique_gaps = []
    for g in gaps:
        key = (g["kind"], g.get("detail", ""))
        if key not in seen:
            seen.add(key)
            unique_gaps.append(g)

    review_case["capture_gaps"] = unique_gaps


def _verify_artifact(
    rel_path: str,
    run_path: Path,
) -> dict[str, Any]:
    """Verify a single artifact on local disk.

    Resolves *rel_path* against *run_path*, verifies filesystem containment,
    and computes the actual SHA-256 digest for existing regular files.

    Returns a dict with:
    - verified: bool — True if the file exists, is a regular file, and is
      safely contained within the run directory
    - local_content_hash: sha256:-prefixed actual digest (only when verified)
    - media_type: guessed MIME type (from extension)
    - metadata: probed media metadata (from ffprobe, when available)
    - capture_gaps: list of capture gap dicts for any issues found
    """
    result: dict[str, Any] = {
        "verified": False,
        "capture_gaps": [],
    }

    # Resolve against run_path
    try:
        resolved = (run_path / rel_path).resolve()
    except (OSError, ValueError, RuntimeError):
        result["capture_gaps"].append({
            "kind": "ambiguous_provenance",
            "detail": f"Cannot resolve path {rel_path!r} against run directory",
        })
        return result

    # Containment check: resolved path must be within run_path.
    # Use os.path.realpath on both to resolve symlinks for containment.
    try:
        real_resolved = Path(os.path.realpath(str(resolved)))
        real_run = Path(os.path.realpath(str(run_path)))
    except (OSError, ValueError, RuntimeError):
        result["capture_gaps"].append({
            "kind": "ambiguous_provenance",
            "detail": f"Cannot check path containment for {rel_path!r}",
        })
        return result

    # Must be within the run directory (or equal to it)
    try:
        real_resolved.relative_to(real_run)
    except ValueError:
        result["capture_gaps"].append({
            "kind": "ambiguous_provenance",
            "detail": f"Path {rel_path!r} escapes run directory (resolved to {str(real_resolved)!r})",
        })
        return result

    # Must exist
    if not resolved.exists():
        result["capture_gaps"].append({
            "kind": "missing_input_hash",
            "detail": f"Artifact {rel_path!r} not found on disk",
        })
        return result

    # Must be a regular file (no dirs, pipes, devices, etc.)
    if not resolved.is_file():
        result["capture_gaps"].append({
            "kind": "ambiguous_provenance",
            "detail": f"Artifact {rel_path!r} is not a regular file",
        })
        return result

    # Compute actual SHA-256
    try:
        local_digest = f"sha256:{sha256_file(resolved)}"
    except (OSError, ValueError):
        result["capture_gaps"].append({
            "kind": "missing_input_hash",
            "detail": f"Cannot hash artifact {rel_path!r}",
        })
        return result

    result["verified"] = True
    result["local_content_hash"] = local_digest

    # Probe metadata (media type, ffprobe metadata, file size)
    probed = probe_artifact(resolved)
    if probed:
        if "media_type" in probed:
            result["media_type"] = probed["media_type"]
        if "metadata" in probed:
            result["metadata"] = probed["metadata"]
        if "bytes" in probed:
            result["bytes"] = probed["bytes"]

    return result


def _verify_case_artifacts(
    review_case: dict[str, Any],
    run_path: Path,
) -> None:
    """Verify all input and output artifacts in a review case on disk.

    For each input/output with a path, resolves against the run directory,
    computes the actual local SHA-256, and updates the entry with verified
    evidence.  Digest mismatches are recorded without discarding either value.
    """
    safe_inputs: list[dict[str, Any]] = []
    for inp in review_case.get("inputs", []):
        path = inp.get("path")
        if not isinstance(path, str):
            continue
        try:
            require_relative_path(path)
        except ExperimentValidationError:
            review_case.setdefault("capture_gaps", []).append({
                "kind": "ambiguous_provenance",
                "detail": (
                    f"Input at ordinal {inp.get('ordinal', '?')} had an unsafe "
                    "path and was omitted"
                ),
            })
            continue
        safe_inputs.append(inp)
    review_case["inputs"] = safe_inputs

    # Verify inputs
    for inp in review_case.get("inputs", []):
        path = inp.get("path")
        if not isinstance(path, str):
            continue
        reported_hash = inp.get("content_hash")
        verification = _verify_artifact(path, run_path)

        if verification["verified"]:
            inp["verified"] = True
            local_hash = verification["local_content_hash"]
            # If provider-reported hash differs from local, keep both
            if reported_hash and reported_hash != local_hash:
                inp["content_hash"] = local_hash
                inp["reported_content_hash"] = reported_hash
                review_case.setdefault("capture_gaps", []).append({
                    "kind": "ambiguous_provenance",
                    "detail": (
                        f"Input {path!r}: reported hash {reported_hash} "
                        f"differs from verified local hash {local_hash}"
                    ),
                })
            elif not reported_hash:
                inp["content_hash"] = local_hash
            # else: reported == local, keep content_hash as-is
            # Set media type and metadata if not already present
            if "media_type" not in inp and "media_type" in verification:
                inp["media_type"] = verification["media_type"]
            if "metadata" not in inp and "metadata" in verification:
                inp["metadata"] = verification["metadata"]
        else:
            # Not verified — add capture gaps, preserve reported as non-canonical
            inp["verified"] = False
            if reported_hash and "content_hash" in inp:
                inp["reported_content_hash"] = inp.pop("content_hash")
            for gap in verification["capture_gaps"]:
                review_case.setdefault("capture_gaps", []).append(gap)

    # Verify outputs
    for out in review_case.get("outputs", []):
        path = out.get("path")
        if not isinstance(path, str):
            continue
        reported_hash = out.get("content_hash")
        verification = _verify_artifact(path, run_path)

        if verification["verified"]:
            out["verified"] = True
            local_hash = verification["local_content_hash"]
            if reported_hash and reported_hash != local_hash:
                out["content_hash"] = local_hash
                out["reported_content_hash"] = reported_hash
                review_case.setdefault("capture_gaps", []).append({
                    "kind": "ambiguous_provenance",
                    "detail": (
                        f"Output {path!r}: reported hash {reported_hash} "
                        f"differs from verified local hash {local_hash}"
                    ),
                })
            elif not reported_hash:
                out["content_hash"] = local_hash
            if "media_type" not in out and "media_type" in verification:
                out["media_type"] = verification["media_type"]
            if "metadata" not in out and "metadata" in verification:
                out["metadata"] = verification["metadata"]
        else:
            out["verified"] = False
            if reported_hash and "content_hash" in out:
                out["reported_content_hash"] = out.pop("content_hash")
            for gap in verification["capture_gaps"]:
                review_case.setdefault("capture_gaps", []).append(gap)


def build_normalized_review(
    *,
    experiment: Mapping[str, Any],
    cases_with_manifests: Sequence[tuple[Mapping[str, Any], str, Path]],
) -> dict[str, Any]:
    """Build a complete normalized review.json from experiment and manifests.

    Args:
        experiment: The validated experiment definition.
        cases_with_manifests: Sequence of (case, manifest_path, run_path) tuples,
            where each tuple pairs a case definition with the resolved manifest
            path and the run directory.

    Returns:
        A normalized review dict suitable for writing as review.json.

    Timestamps are derived from the experiment definition so that repeated
    runs over identical bytes produce byte-identical output.
    """
    review_cases = []
    for case, manifest_rel_path, run_path in cases_with_manifests:
        manifest_full_path, containment_error = resolve_manifest_path(
            run_path, manifest_rel_path
        )
        if containment_error is not None:
            review_case = _unreadable_manifest_case(
                case=case,
                manifest_rel_path=manifest_rel_path,
                detail=containment_error,
            )
            review_cases.append(review_case)
            continue

        assert manifest_full_path is not None
        try:
            manifest_bytes = manifest_full_path.read_bytes()
            manifest_data = json.loads(manifest_bytes.decode("utf-8"))
            manifest_hash = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            review_case = _unreadable_manifest_case(
                case=case,
                manifest_rel_path=manifest_rel_path,
                detail=f"Failed to read {manifest_rel_path}",
            )
            review_cases.append(review_case)
            continue

        review_case = normalize_case_from_manifest(
            manifest=manifest_data,
            manifest_path=manifest_rel_path,
            case=case,
            run_path=run_path,
            manifest_content_hash=manifest_hash,
        )
        review_cases.append(review_case)

    # Derive a stable creation timestamp from the experiment definition.
    # Prefer 'created', fall back to 'updated', else use an epoch sentinel
    # so that the output is deterministic.
    created = experiment.get("created") or experiment.get("updated")
    if not isinstance(created, str):
        created = "1970-01-01T00:00:00Z"

    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": experiment["experiment_id"],
        "title": experiment.get("title"),
        "question": experiment.get("question"),
        "hypotheses": experiment.get("hypotheses", []),
        "factors": experiment.get("factors", []),
        "rubric": experiment.get("rubric", []),
        "cases": review_cases,
        "created": created,
    }

    return result


def _unreadable_manifest_case(
    *,
    case: Mapping[str, Any],
    manifest_rel_path: str,
    detail: str,
) -> dict[str, Any]:
    """Build a truthful failed review case without reading manifest bytes."""
    source_manifest: dict[str, Any] = {
        "path": manifest_rel_path,
        "verified": False,
    }
    expected_ref = case.get("source_manifest")
    if isinstance(expected_ref, Mapping):
        expected_hash = expected_ref.get("content_hash")
        if isinstance(expected_hash, str):
            source_manifest["expected_content_hash"] = expected_hash
    return {
        "case_id": case["case_id"],
        "run_id": case["run_id"],
        "label": case.get("label", case["case_id"]),
        "attempt": case.get("attempt", 1),
        "factors": dict(case.get("factors", {})),
        "relationship": dict(case.get("relationship", {})),
        "expected_input_roles": list(case.get("expected_input_roles", [])),
        "status": "failed",
        "provider": "unknown",
        "backend": None,
        "model": None,
        "model_actual": None,
        "mode": None,
        "prompt": None,
        "parameters": {},
        "inputs": [],
        "outputs": [],
        "timing": {},
        "cost_usd": None,
        "warnings": [],
        "error": detail,
        "capture_gaps": [{
            "kind": "missing_manifest",
            "detail": detail,
        }],
        "source_manifest": source_manifest,
        "included": case.get("included", True),
    }


def build_diagnostics(review: Mapping[str, Any]) -> dict[str, Any]:
    """Build diagnostics.json from a normalized review."""
    from collections import Counter

    cases = review.get("cases", [])
    if not isinstance(cases, list):
        cases = []

    total = len(cases)
    included = sum(1 for c in cases if c.get("included", True))
    excluded = total - included

    status_counts = dict(Counter(
        c.get("status", "draft") for c in cases
    ))

    # Duplicate output groups
    hash_to_cases: dict[str, set[str]] = {}
    for c in cases:
        for out in c.get("outputs", []):
            ch = out.get("content_hash")
            if ch:
                hash_to_cases.setdefault(ch, set()).add(c["case_id"])
    duplicate_groups = [
        {"content_hash": h, "case_ids": sorted(cids)}
        for h, cids in hash_to_cases.items()
        if len(cids) > 1
    ]

    # Input echo detection (more thorough scan)
    input_echo_cases = []
    for c in cases:
        in_hashes = {inp["content_hash"] for inp in c.get("inputs", []) if "content_hash" in inp}
        for out in c.get("outputs", []):
            out_hash = out.get("content_hash")
            if out_hash and out_hash in in_hashes:
                input_echo_cases.append({
                    "case_id": c["case_id"],
                    "input_hash": out_hash,
                    "output_hash": out_hash,
                    "detail": f"Output {out.get('path')} hash matches an input hash",
                })
                break
        extension = c.get("provider_extension")
        reclassified = (
            extension.get("reclassified_input_echoes", [])
            if isinstance(extension, Mapping)
            else []
        )
        if reclassified and not any(
            item["case_id"] == c["case_id"] for item in input_echo_cases
        ):
            first = reclassified[0] if isinstance(reclassified[0], Mapping) else {}
            content_hash = first.get("content_hash")
            input_echo_cases.append({
                "case_id": c["case_id"],
                "input_hash": content_hash,
                "output_hash": content_hash,
                "detail": (
                    f"Captured output {first.get('path', '?')} matched a manually "
                    "declared input and was reclassified; it is not displayed as "
                    "a generated output"
                ),
                "reclassified": True,
            })

    # Capture gap counts
    gap_counter: Counter[str] = Counter()
    for c in cases:
        for g in c.get("capture_gaps", []):
            gap_counter[g["kind"]] += 1

    # Warnings collection
    all_warnings: list[str] = []
    if input_echo_cases:
        all_warnings.append(
            f"{len(input_echo_cases)} case(s) have input-output hash equality"
        )
    if duplicate_groups:
        all_warnings.append(
            f"{len(duplicate_groups)} duplicate output group(s) across cases"
        )

    return {
        "schema_version": 1,
        "experiment_id": review["experiment_id"],
        "total_cases": total,
        "included_cases": included,
        "excluded_cases": excluded,
        "status_counts": status_counts,
        "duplicate_output_groups": duplicate_groups,
        "input_echo_cases": input_echo_cases,
        "capture_gap_counts": dict(gap_counter),
        "source_manifest_mismatches": [
            {
                "case_id": c.get("case_id"),
                "run_id": c.get("run_id"),
                "expected_content_hash": c.get("source_manifest", {}).get(
                    "expected_content_hash"
                ),
                "content_hash": c.get("source_manifest", {}).get("content_hash"),
            }
            for c in cases
            if isinstance(c.get("source_manifest"), Mapping)
            and c["source_manifest"].get("verified") is False
        ],
        "warnings": all_warnings,
    }
