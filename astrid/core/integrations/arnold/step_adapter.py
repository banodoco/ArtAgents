"""Astrid → Arnold step-invocation adapter.

This module imports from ``arnold.pipeline`` — the ONLY place in Astrid that
may touch Arnold.  If Arnold is not installed the import raises an
``ImportError`` with installation instructions; the rest of Astrid is
unaffected.

Design constraints (settled — do not re-litigate):

* **SD1:** Arnold imports are lazy and optional, gated inside this module only.
  Astrid core startup must never trigger Arnold imports.
* **SD2:** Judge lowering uses ``executor.metadata['arnold']['judge'] is True``
  as the opt-in, not a pre-existing convention.
* **SD3:** Multi-output CAS uses
  ``canonical_json_digest({'identity_key': identity_key, 'output': output_name})``
  per output, not a single bundle key.
"""

from __future__ import annotations

import mimetypes
import os
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from astrid.core.execution.executor.runner import (
    ExecutorRunRequest,
    ExecutorRunResult,
    resolve_declared_output_paths,
)
from astrid.core.foundation.project_paths import project_dir
from astrid.core.io.cas import (
    canonical_json_digest,
    cas_path,
    executor_definition_digest,
    identity_digest,
)

# ── Lazy Arnold imports (gated — the ONLY Arnold import surface in Astrid) ───
try:
    from arnold.pipeline import (
        ContentValidatorRegistry,
        ContractResult,
        ContractStatus,
        EvidenceArtifactRef,
        PipelineVerdict,
        Provenance,
        StepInvocation,
        StepInvocationAdapter,
        StepInvocationAdapterRegistry,
        StepResult,
        no_op_content_validator,
    )
except ImportError as exc:
    raise ImportError(
        "The Astrid Arnold integration requires the 'arnold' package. "
        "Install it with:  pip install arnold\n"
        "The rest of Astrid remains fully functional without Arnold — "
        "only this integration package requires it."
    ) from exc


# ── Compatibility helper — centralised Arnold symbol surface ──────────────────


class _ArnoldCompat:
    """Centralised namespace for all Arnold symbols the adapter uses.

    Every Arnold type that the adapter constructs, consumes, or passes through
    is referenced through this helper.  This keeps the adapter code decoupled
    from Arnold import paths, makes the compatibility contract explicit, and
    gives linters / import analysers a single point to inspect.

    This is an internal implementation detail — adapter consumers should use
    the Arnold types directly or go through the adapter's public API.
    """

    # protocol
    StepInvocationAdapter = StepInvocationAdapter
    StepInvocationAdapterRegistry = StepInvocationAdapterRegistry

    # data
    StepInvocation = StepInvocation
    StepResult = StepResult
    ContractResult = ContractResult
    ContractStatus = ContractStatus
    Provenance = Provenance
    EvidenceArtifactRef = EvidenceArtifactRef
    PipelineVerdict = PipelineVerdict
    ContentValidatorRegistry = ContentValidatorRegistry
    no_op_content_validator = no_op_content_validator


# ── Metadata parsing ─────────────────────────────────────────────────────────


# Canonical keys for the adapter_config dict.  Any key not listed here is
# silently ignored so callers can pass through extra metadata without
# breaking the adapter.
_VALID_ADAPTER_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "executor_id",  # required
        "input_map",
        "inputs",
        "state",
        "mode",
        "project",
        "run_root",
        "artifact_root",
        "cas_project_dir",
        "requires_ack",
        "content_validator_registry",
    }
)

# Keys that may appear at the top level of invocation.metadata as a legacy
# fallback.  These are only consulted when adapter_config is absent.
_LEGACY_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "executor_id",
        "input_map",
        "inputs",
        "state",
        "mode",
        "project",
        "run_root",
        "artifact_root",
        "cas_project_dir",
        "requires_ack",
        "content_validator_registry",
    }
)

_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _parse_adapter_metadata(metadata: Any) -> "dict[str, Any] | StepResult":
    """Canonicalize and validate adapter metadata from a ``StepInvocation``.

    Parameters
    ----------
    metadata:
        The ``invocation.metadata`` mapping from an Arnold
        :class:`~arnold.pipeline.StepInvocation`.

    Returns
    -------
    dict[str, Any]
        Validated adapter config dictionary on success.
    StepResult
        A failed ``StepResult`` when the metadata is malformed.  The caller
        should return this result immediately rather than proceeding with
        adapter logic.
    """
    # ── Guard: metadata must be a mapping ────────────────────────────────
    if not isinstance(metadata, dict):
        return StepResult(
            contract_result=ContractResult(
                status=ContractStatus.FAILED,
                payload={
                    "error": "adapter_metadata_type",
                    "detail": (
                        "invocation.metadata must be a dict, got "
                        f"{type(metadata).__name__}"
                    ),
                },
            ),
        )

    # ── Canonical config ─────────────────────────────────────────────────
    config: dict[str, Any]

    if "adapter_config" in metadata:
        raw = metadata["adapter_config"]
        if not isinstance(raw, dict):
            return StepResult(
                contract_result=ContractResult(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "adapter_config_type",
                        "detail": (
                            "invocation.metadata['adapter_config'] must be a dict, "
                            f"got {type(raw).__name__}"
                        ),
                    },
                ),
            )
        # Start from the canonical config dict.
        config = dict(raw)
    else:
        # Legacy fallback: gather recognised keys from the top level.
        config = {
            k: v
            for k, v in metadata.items()
            if k in _LEGACY_TOP_LEVEL_KEYS
        }

    # ── Required: executor_id ────────────────────────────────────────────
    if "executor_id" not in config or not isinstance(config["executor_id"], str) or not config["executor_id"].strip():
        return StepResult(
            contract_result=ContractResult(
                status=ContractStatus.FAILED,
                payload={
                    "error": "missing_executor_id",
                    "detail": (
                        "adapter_config must contain a non-empty string 'executor_id'"
                    ),
                },
            ),
        )

    # ── Defaults ─────────────────────────────────────────────────────────
    config.setdefault("requires_ack", False)

    # ── Strip unknown keys (forward-compatible: allow extra payload) ─────
    # We intentionally do NOT strip unknown keys.  The adapter only reads
    # the keys it knows about and ignores everything else so that callers
    # can pass through future or domain-specific metadata fields.

    return config


def _failed_step_result(error: str, detail: str, **payload: Any) -> StepResult:
    """Return a failed Arnold ``StepResult`` with a consistent payload shape."""
    provenance = payload.pop("provenance", None)
    return StepResult(
        contract_result=ContractResult(
            status=ContractStatus.FAILED,
            payload={"error": error, "detail": detail, **payload},
            provenance=provenance if provenance is not None else Provenance(),
        ),
    )


def _safe_invocation_slug(executor_id: str) -> str:
    """Return a filesystem-safe slug for out-mode artifact placement."""
    slug = _SAFE_SLUG_RE.sub("-", executor_id).strip("-._")
    return slug or "astrid-step"


def _normalize_output_value(raw_value: Any, *, run_root: Path | None) -> Path | None:
    """Normalize a runner output value into an absolute path when possible."""
    if isinstance(raw_value, Path):
        path = raw_value
    elif isinstance(raw_value, str) and raw_value.strip():
        path = Path(raw_value)
    else:
        return None
    if path.is_absolute():
        return path
    if run_root is not None:
        return run_root / path
    return path


def _infer_content_type(output: Any, path: Path) -> str:
    """Infer an evidence content type from declared output metadata or path."""
    if output.type == "directory" or path.is_dir():
        return "inode/directory"

    artifact_type = getattr(output, "artifact_type", None)
    if isinstance(artifact_type, str) and "/" in artifact_type:
        return artifact_type

    guessed_type, _ = mimetypes.guess_type(path.name)
    if guessed_type:
        return guessed_type

    extension = getattr(output, "extension", None)
    if isinstance(extension, str) and extension:
        guessed_type, _ = mimetypes.guess_type(f"placeholder{extension}")
        if guessed_type:
            return guessed_type

    if output.type == "json":
        return "application/json"
    if output.type == "html":
        return "text/html"
    return "application/octet-stream"


def _resolve_cas_project_dir(
    *,
    config: dict[str, Any],
    default_project: str,
    project_dir_resolver: Any,
) -> "Path | StepResult":
    """Resolve the project directory that anchors identity CAS state."""
    explicit_dir = config.get("cas_project_dir")
    if explicit_dir is not None:
        if not isinstance(explicit_dir, (str, Path)) or not str(explicit_dir).strip():
            return _failed_step_result(
                "cas_project_dir_type",
                "adapter_config['cas_project_dir'] must be a non-empty string or Path when provided",
            )
        return Path(explicit_dir).expanduser().resolve()

    project = config.get("project")
    project_slug = project if isinstance(project, str) and project.strip() else default_project
    try:
        resolved = (
            project_dir_resolver(project_slug)
            if callable(project_dir_resolver)
            else project_dir(project_slug)
        )
    except Exception as exc:  # noqa: BLE001
        return _failed_step_result(
            "cas_project_resolution_failed",
            f"Could not resolve CAS project dir for project {project_slug!r}: {exc}",
            project=project_slug,
        )
    if not isinstance(resolved, (str, Path)) or not str(resolved).strip():
        return _failed_step_result(
            "cas_project_resolution_type",
            (
                "project_dir_resolver must return a non-empty string or Path, got "
                f"{type(resolved).__name__}"
            ),
            project=project_slug,
        )
    return Path(resolved).expanduser().resolve()


def _normalize_identity_value(value: Any) -> Any:
    """Convert a value into a canonical JSON-serializable identity payload."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize_identity_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize_identity_value(item) for item in value]
    return value


def _build_input_digest_payload(
    *,
    config: dict[str, Any],
    resolved_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Build the canonical input payload used for identity digesting."""
    input_map = config.get("input_map", {}) or {}
    inputs = config.get("inputs", {}) or {}
    state = config.get("state", {}) or {}
    mapped_state_inputs = {
        input_name: {
            "state_key": state_key,
            "identity": _normalize_identity_value(state[state_key]),
        }
        for input_name, state_key in sorted(input_map.items())
    }
    literal_inputs = {
        input_name: _normalize_identity_value(value)
        for input_name, value in sorted(inputs.items())
    }
    effective_inputs = {
        input_name: _normalize_identity_value(value)
        for input_name, value in sorted(resolved_inputs.items())
    }
    return {
        "effective_inputs": effective_inputs,
        "literal_inputs": literal_inputs,
        "mapped_state_inputs": mapped_state_inputs,
    }


def _compute_identity_context(
    *,
    config: dict[str, Any],
    executor: Any,
    request: ExecutorRunRequest,
    default_project: str,
    project_dir_resolver: Any,
) -> "dict[str, Any] | StepResult":
    """Compute CAS identity metadata for the invocation without reading bytes."""
    cas_project_dir = _resolve_cas_project_dir(
        config=config,
        default_project=default_project,
        project_dir_resolver=project_dir_resolver,
    )
    if isinstance(cas_project_dir, StepResult):
        return cas_project_dir

    input_payload = _build_input_digest_payload(
        config=config,
        resolved_inputs=dict(request.inputs),
    )
    input_digest = canonical_json_digest(input_payload)
    executor_version = executor_definition_digest(executor)
    identity_key = identity_digest(
        input_digest=input_digest,
        producer_id=executor.id,
        producer_version=executor_version,
    )
    provenance_chain = (
        "cache_status=miss",
        f"cas_project_dir={cas_project_dir}",
        f"input_digest={input_digest}",
        f"identity_key={identity_key}",
        f"executor_id={executor.id}",
        f"executor_version={executor_version}",
    )
    return {
        "cas_project_dir": str(cas_project_dir),
        "cache_status": "miss",
        "executor_id": executor.id,
        "executor_version": executor_version,
        "identity_key": identity_key,
        "input_digest": input_digest,
        "provenance_chain": provenance_chain,
    }


def _identity_payload(identity_context: dict[str, Any]) -> dict[str, Any]:
    """Return identity-context fields that belong in ContractResult.payload."""
    return {
        key: value
        for key, value in identity_context.items()
        if key != "provenance_chain"
    }


def _set_cache_status(
    identity_context: dict[str, Any],
    *,
    cache_status: str,
) -> dict[str, Any]:
    """Return a copy of *identity_context* with updated cache-status metadata."""
    updated = dict(identity_context)
    updated["cache_status"] = cache_status
    updated["provenance_chain"] = (
        f"cache_status={cache_status}",
        f"cas_project_dir={updated['cas_project_dir']}",
        f"input_digest={updated['input_digest']}",
        f"identity_key={updated['identity_key']}",
        f"executor_id={updated['executor_id']}",
        f"executor_version={updated['executor_version']}",
    )
    return updated


def _output_identity_key(identity_key: str, output_name: str) -> str:
    """Return the deterministic CAS key for one declared output."""
    return canonical_json_digest(
        {"identity_key": identity_key, "output": output_name}
    )


def _remove_materialized_path(path: Path) -> None:
    """Remove a pre-existing materialized output path of any filesystem kind."""
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def _symlink_materialized_output(cas_target: Path, target_path: Path) -> None:
    """Materialize *cas_target* into *target_path* as a relative symlink."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() or target_path.is_symlink():
        _remove_materialized_path(target_path)
    rel_target = os.path.relpath(cas_target, target_path.parent)
    target_path.symlink_to(rel_target)


def _resolved_declared_output_paths(
    *,
    executor: Any,
    request: ExecutorRunRequest,
) -> dict[str, Path]:
    """Resolve every declared output path the runner is expected to populate."""
    try:
        resolved = resolve_declared_output_paths(executor, request)
    except Exception:  # noqa: BLE001
        return {}
    normalized: dict[str, Path] = {}
    for output_name, raw_path in resolved.items():
        normalized_path = _normalize_output_value(raw_path, run_root=None)
        if normalized_path is None:
            continue
        normalized[output_name] = normalized_path.expanduser().resolve()
    return normalized


def _materialize_cas_hit(
    *,
    executor: Any,
    request: ExecutorRunRequest,
    identity_context: dict[str, Any],
    declared_output_paths: dict[str, Path],
) -> ExecutorRunResult | None:
    """Return a synthetic cached run result when every declared output hits CAS."""
    declared_outputs = tuple(getattr(executor, "outputs", ()) or ())
    if not declared_outputs:
        return None

    project_root = Path(identity_context["cas_project_dir"])
    cached_outputs: dict[str, str] = {}
    for output in declared_outputs:
        output_path = declared_output_paths.get(output.name)
        if output_path is None:
            return None
        cas_target = cas_path(
            project_root,
            _output_identity_key(identity_context["identity_key"], output.name),
        )
        if not cas_target.exists():
            return None
        _symlink_materialized_output(cas_target, output_path)
        cached_outputs[output.name] = str(output_path)

    return ExecutorRunResult(
        executor_id=request.executor_id,
        kind="external",
        returncode=0,
        run_root=request.run_root,
        outputs=cached_outputs,
    )


def _materialize_cas_miss(
    *,
    executor: Any,
    run_result: ExecutorRunResult,
    identity_context: dict[str, Any],
    declared_output_paths: dict[str, Path],
) -> ExecutorRunResult:
    """Link produced declared outputs into CAS and back into the run directory."""
    project_root = Path(identity_context["cas_project_dir"])
    updated_outputs = dict(run_result.outputs)
    for output in tuple(getattr(executor, "outputs", ()) or ()):
        output_path = declared_output_paths.get(output.name)
        if output_path is None or not output_path.exists():
            continue
        output_key = _output_identity_key(identity_context["identity_key"], output.name)
        cas_target = cas_path(project_root, output_key)
        cas_target.parent.mkdir(parents=True, exist_ok=True)
        if not cas_target.exists():
            output_path.replace(cas_target)
        else:
            _remove_materialized_path(output_path)
        _symlink_materialized_output(cas_target, output_path)
        updated_outputs[output.name] = str(output_path)
    return replace(run_result, outputs=updated_outputs)


# ── Content-type validation helpers ───────────────────────────────────────────

# Content-type prefixes that do NOT require an explicit content validator.
# These are types whose correctness can be determined from metadata alone
# (e.g. structured text) vs binary media types that need inspection.
_NO_VALIDATION_CONTENT_TYPE_PREFIXES: frozenset[str] = frozenset(
    {
        "text/",
        "application/json",
        "application/xml",
        "inode/directory",
        "application/octet-stream",
    }
)


def _content_type_requires_validation(content_type: str) -> bool:
    """Return True if *content_type* is a media type that needs a validator."""
    if not content_type or "/" not in content_type:
        return False
    # Exact matches
    if content_type in _NO_VALIDATION_CONTENT_TYPE_PREFIXES:
        return False
    # Prefix matches (text/*)
    for prefix in _NO_VALIDATION_CONTENT_TYPE_PREFIXES:
        if prefix.endswith("/") and content_type.startswith(prefix):
            return False
    return True


def _build_judge_verdict(payload: dict[str, Any]) -> PipelineVerdict:
    """Lower executor output payload fields into a ``PipelineVerdict``.

    Conservative defaults are applied when the executor output does not
    contain the corresponding field (e.g. *score* defaults to ``0.0``).
    """
    raw_score = payload.get("score", 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0

    raw_flags = payload.get("flags", ())
    try:
        flags = tuple(raw_flags) if raw_flags else ()
    except (TypeError, ValueError):
        flags = ()

    raw_notes = payload.get("notes", "")
    notes = str(raw_notes) if raw_notes else ""

    raw_verdict_payload = payload.get("payload", {})
    verdict_payload = dict(raw_verdict_payload) if isinstance(raw_verdict_payload, dict) else {}

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, str) or not recommendation:
        recommendation = None

    override = payload.get("override")
    if not isinstance(override, str) or not override:
        override = None

    return PipelineVerdict(
        score=score,
        flags=flags,
        notes=notes,
        payload=verdict_payload,
        recommendation=recommendation,
        override=override,
    )


# ── Adapter-level judge / validator integration ───────────────────────────────


def _register_noop_validators(
    registry: ContentValidatorRegistry,
    evidence_refs: tuple[EvidenceArtifactRef, ...],
) -> None:
    """Register no-op validators for every emitted evidence content type."""
    for ref in evidence_refs:
        if ref.content_type not in registry:
            registry.register(ref.content_type, no_op_content_validator)


def _filter_evidence_refs_for_no_registry(
    evidence_refs: tuple[EvidenceArtifactRef, ...],
) -> tuple[EvidenceArtifactRef, ...]:
    """Drop evidence refs whose content type requires a validator.

    When no ``ContentValidatorRegistry`` is supplied, the pipeline cannot
    validate media content types, so we only retain evidence refs for types
    that do not need validation (text/*, application/json, etc.).
    """
    return tuple(
        ref
        for ref in evidence_refs
        if not _content_type_requires_validation(ref.content_type)
    )


def _apply_content_validator_support(
    result: StepResult,
    config: dict[str, Any],
) -> StepResult:
    """Apply content-validator registration or evidence filtering.

    When *config* supplies a ``ContentValidatorRegistry``, register no-op
    validators for every emitted evidence content type so Arnold's pipeline
    accepts them without error.

    When *config* supplies a *content_validator_registry* that is NOT a
    ``ContentValidatorRegistry`` (i.e. a misconfigured value), drop evidence
    refs whose content type requires validation, since the pipeline has no
    way to validate media types.

    When *content_validator_registry* is absent (``None`` / not in config)
    the adapter emits all evidence refs unchanged — it is the caller's
    responsibility to supply a registry when validation is needed.
    """
    registry = config.get("content_validator_registry")
    if registry is None:
        return result

    contract_result = result.contract_result
    if contract_result is None:
        return result

    evidence_refs = contract_result.evidence_refs

    if isinstance(registry, ContentValidatorRegistry) and evidence_refs:
        _register_noop_validators(registry, evidence_refs)
        return result

    # registry supplied but not a ContentValidatorRegistry → filter
    if evidence_refs:
        filtered_refs = _filter_evidence_refs_for_no_registry(evidence_refs)
        if len(filtered_refs) != len(evidence_refs):
            result = replace(
                result,
                contract_result=replace(
                    contract_result,
                    evidence_refs=filtered_refs,
                ),
            )

    return result


def _build_step_result_from_run(
    *,
    executor: Any,
    run_result: ExecutorRunResult,
    clock: Any,
    identity_context: dict[str, Any],
) -> StepResult:
    """Convert an Astrid executor run result into an Arnold ``StepResult``."""
    provenance = Provenance(
        sources=("astrid.executor", "astrid.cas"),
        generator=run_result.executor_id,
        generated_at=clock() if callable(clock) else None,
        chain=tuple(identity_context["provenance_chain"]),
    )
    if run_result.error is not None or (
        run_result.returncode is not None and run_result.returncode != 0
    ):
        detail = str(run_result.error) if run_result.error is not None else (
            f"Executor {run_result.executor_id!r} exited with return code {run_result.returncode}"
        )
        return _failed_step_result(
            "executor_run_failed",
            detail,
            returncode=run_result.returncode,
            provenance=provenance,
            **_identity_payload(identity_context),
        )

    declared_outputs = tuple(getattr(executor, "outputs", ()) or ())
    run_root_value = run_result.run_root
    run_root = (
        Path(run_root_value).expanduser().resolve()
        if isinstance(run_root_value, (str, Path)) and str(run_root_value)
        else None
    )

    missing_outputs: list[str] = []
    invalid_outputs: list[str] = []
    state_patch: dict[str, str] = {}
    evidence_refs: list[EvidenceArtifactRef] = []

    for output in declared_outputs:
        output_name = output.name
        raw_value = run_result.outputs.get(output_name)
        if raw_value in (None, ""):
            missing_outputs.append(output_name)
            continue

        output_path = _normalize_output_value(raw_value, run_root=run_root)
        if output_path is None:
            invalid_outputs.append(output_name)
            continue
        output_path = output_path.expanduser()
        if not output_path.exists():
            missing_outputs.append(output_name)
            continue

        state_patch[output_name] = str(output_path)
        stat_result = output_path.stat()
        evidence_refs.append(
            EvidenceArtifactRef(
                uri=output_path.as_uri(),
                name=output_name,
                content_type=_infer_content_type(output, output_path),
                size_bytes=stat_result.st_size,
            )
        )

    if missing_outputs or invalid_outputs:
        detail_parts: list[str] = []
        if missing_outputs:
            detail_parts.append(
                "missing declared outputs: " + ", ".join(sorted(missing_outputs))
            )
        if invalid_outputs:
            detail_parts.append(
                "invalid declared outputs: " + ", ".join(sorted(invalid_outputs))
            )
        return _failed_step_result(
            "missing_declared_outputs",
            "; ".join(detail_parts),
            missing_outputs=tuple(sorted(missing_outputs)),
            invalid_outputs=tuple(sorted(invalid_outputs)),
            provenance=provenance,
            **_identity_payload(identity_context),
        )

    contract_payload = {
        "executor_id": run_result.executor_id,
        "returncode": run_result.returncode,
        **_identity_payload(identity_context),
    }
    if run_root is not None:
        contract_payload["run_root"] = str(run_root)

    # ── Judge lowering ──────────────────────────────────────────────────
    verdict: PipelineVerdict | None = None
    executor_metadata = getattr(executor, "metadata", None)
    if isinstance(executor_metadata, dict):
        arnold_meta = executor_metadata.get("arnold")
        if isinstance(arnold_meta, dict) and arnold_meta.get("judge") is True:
            verdict = _build_judge_verdict(dict(run_result.payload))

    return StepResult(
        state_patch=state_patch,
        verdict=verdict,
        contract_result=ContractResult(
            status=ContractStatus.COMPLETED,
            payload=contract_payload,
            evidence_refs=tuple(evidence_refs),
            provenance=provenance,
        ),
    )


def _merge_executor_inputs(
    mapped_inputs: dict[str, Any],
    literal_inputs: dict[str, Any],
) -> "dict[str, Any] | StepResult":
    """Merge mapped and literal inputs, rejecting conflicting duplicate keys."""
    merged = dict(mapped_inputs)
    for key, value in literal_inputs.items():
        if key in merged and merged[key] != value:
            return _failed_step_result(
                "duplicate_input_conflict",
                (
                    f"Input {key!r} is provided by both input_map and inputs "
                    "with different values"
                ),
                key=key,
            )
        merged[key] = value
    return merged


def _resolve_invocation_inputs(config: dict[str, Any]) -> "dict[str, Any] | StepResult":
    """Resolve executor inputs from ``input_map`` and literal ``inputs``."""
    state = config.get("state", {})
    if state is None:
        state = {}
    if not isinstance(state, dict):
        return _failed_step_result(
            "state_type",
            f"adapter_config['state'] must be a dict, got {type(state).__name__}",
        )

    input_map = config.get("input_map", {})
    if input_map is None:
        input_map = {}
    if not isinstance(input_map, dict):
        return _failed_step_result(
            "input_map_type",
            f"adapter_config['input_map'] must be a dict, got {type(input_map).__name__}",
        )

    inputs = config.get("inputs", {})
    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        return _failed_step_result(
            "inputs_type",
            f"adapter_config['inputs'] must be a dict, got {type(inputs).__name__}",
        )

    mapped_inputs: dict[str, Any] = {}
    for input_name, state_key in input_map.items():
        if not isinstance(input_name, str) or not input_name.strip():
            return _failed_step_result(
                "input_map_key_type",
                "adapter_config['input_map'] keys must be non-empty strings",
            )
        if not isinstance(state_key, str) or not state_key.strip():
            return _failed_step_result(
                "input_map_value_type",
                (
                    "adapter_config['input_map'] values must be non-empty "
                    "state-key strings"
                ),
                key=input_name,
            )
        if state_key not in state:
            return _failed_step_result(
                "missing_state_input",
                f"State key {state_key!r} referenced by input_map[{input_name!r}] is missing",
                key=input_name,
                state_key=state_key,
            )
        mapped_inputs[input_name] = state[state_key]

    return _merge_executor_inputs(mapped_inputs, dict(inputs))


def _build_run_request(
    *,
    config: dict[str, Any],
    executor_registry: Any,
    artifact_root: Path,
) -> "tuple[Any, ExecutorRunRequest] | StepResult":
    """Fetch the executor definition and construct the Astrid run request."""
    executor_id = config["executor_id"]
    try:
        executor = executor_registry.get(executor_id)
    except (AttributeError, KeyError, ValueError) as exc:
        return _failed_step_result(
            "unknown_executor",
            f"Executor {executor_id!r} could not be resolved from the registry",
            executor_id=executor_id,
            cause=str(exc),
        )

    resolved_inputs = _resolve_invocation_inputs(config)
    if isinstance(resolved_inputs, StepResult):
        return resolved_inputs

    mode = config.get("mode", "subprocess")
    if mode not in {"subprocess", "in_process"}:
        return _failed_step_result(
            "execution_mode",
            (
                "adapter_config['mode'] must be 'subprocess' or 'in_process', "
                f"got {mode!r}"
            ),
        )

    project = config.get("project")
    if project is not None and (not isinstance(project, str) or not project.strip()):
        return _failed_step_result(
            "project_type",
            "adapter_config['project'] must be a non-empty string when provided",
        )
    project = project.strip() if isinstance(project, str) else None
    if project is None:
        return _failed_step_result(
            "project_required",
            (
                "Astrid executor steps require adapter_config['project']; "
                "propagate the owning Arnold/Astrid project explicitly"
            ),
        )

    run_root = config.get("run_root")
    if run_root is not None and not isinstance(run_root, (str, Path)):
        return _failed_step_result(
            "run_root_type",
            "adapter_config['run_root'] must be a string or Path when provided",
        )

    out = (
        None
        if run_root is not None
        else artifact_root / _safe_invocation_slug(executor_id)
    )
    request_run_root = run_root

    request = ExecutorRunRequest(
        executor_id=executor.id,
        out=out,
        project=project,
        inputs=resolved_inputs,
        execution_mode=mode,
        invocation="sdk",
        run_root=request_run_root,
        project_was_auto_resolved=True,
    )
    return executor, request


# ── Adapter class ────────────────────────────────────────────────────────────


class AstridStepInvocationAdapter:
    """Generic adapter that wraps Astrid's ``run_executor`` for Arnold.

    ONE adapter handles ALL Astrid executor invocations — there are no
    executor-specific or noun-specific adapter subclasses.  Behaviour is
    driven by executor manifests and invocation metadata, not by subclassing.

    Constructor dependencies are injectable so tests can supply fake
    registries and runner functions without mutating process-global state.

    Parameters
    ----------
    executor_registry:
        Astrid :class:`~astrid.core.execution.executor.registry.ExecutorRegistry`
        used to resolve executor definitions.
    run_executor_fn:
        Callable that accepts an
        :class:`~astrid.core.execution.executor.runner.ExecutorRunRequest` and
        returns an
        :class:`~astrid.core.execution.executor.runner.ExecutorRunResult`.
    artifact_root:
        Root directory for Direction-B (out-mode) artifacts.
    default_project:
        Fallback project slug used when no project is supplied in out mode.
    project_dir_resolver:
        Optional callable ``(project_slug: str) -> Path`` that resolves a
        project slug to its on-disk project directory (needed for CAS roots
        and run-dir placement).
    clock:
        Optional callable ``() -> str`` returning an ISO-8601 timestamp.
        Defaults to :func:`datetime.datetime.now(datetime.UTC).isoformat`.
    kind:
        Optional invocation kind string the adapter expects.  When set,
        :meth:`invoke` rejects invocations whose ``.kind`` does not match
        with a failed ``ContractResult``.  When ``None`` (default) the
        adapter accepts any invocation kind.
    """

    def __init__(
        self,
        *,
        executor_registry: Any,
        run_executor_fn: Any,
        artifact_root: Any,
        default_project: str = "default",
        project_dir_resolver: Any = None,
        clock: Any = None,
        kind: str | None = None,
    ) -> None:
        self._executor_registry = executor_registry
        self._run_executor_fn = run_executor_fn
        self._artifact_root = artifact_root
        self._default_project = default_project
        self._project_dir_resolver = project_dir_resolver
        self._clock = clock
        self._kind = kind

    # ── Metadata parsing (instance-level entry point) ────────────────────

    @staticmethod
    def _parse_metadata(metadata: Any) -> "dict[str, Any] | StepResult":
        """Canonicalize and validate adapter metadata.

        Delegates to :func:`_parse_adapter_metadata` — kept as a static
        method so subclasses / test harnesses can override if needed.
        """
        return _parse_adapter_metadata(metadata)

    # ── invoke ───────────────────────────────────────────────────────────

    def invoke(self, invocation: StepInvocation) -> Any:
        """Arnold ``StepInvocationAdapter.invoke`` protocol entry point.

        Rejects invocations whose ``.kind`` does not match the adapter's
        configured *kind* (when one is set).  Parses invocation metadata via
        :meth:`_parse_metadata` and returns a failed ``StepResult``
        immediately for malformed metadata.  Full adapter logic (request
        construction, CAS, result mapping) is wired in later tasks.
        """
        # ── Kind guard: reject mismatched invocation kinds ────────────────
        if self._kind is not None and invocation.kind != self._kind:
            return StepResult(
                contract_result=ContractResult(
                    status=ContractStatus.FAILED,
                    payload={
                        "error": "invocation_kind_mismatch",
                        "detail": (
                            f"Adapter expects kind '{self._kind}', "
                            f"but invocation kind is '{invocation.kind}'"
                        ),
                    },
                ),
            )

        config = self._parse_metadata(invocation.metadata)
        if isinstance(config, StepResult):
            return config

        build_result = _build_run_request(
            config=config,
            executor_registry=self._executor_registry,
            artifact_root=Path(config.get("artifact_root") or self._artifact_root),
        )
        if isinstance(build_result, StepResult):
            return build_result

        executor, request = build_result
        identity_context = _compute_identity_context(
            config=config,
            executor=executor,
            request=request,
            default_project=self._default_project,
            project_dir_resolver=self._project_dir_resolver,
        )
        if isinstance(identity_context, StepResult):
            return identity_context
        declared_outputs = tuple(getattr(executor, "outputs", ()) or ())
        declared_output_paths = _resolved_declared_output_paths(
            executor=executor,
            request=request,
        )
        can_materialize_declared_outputs = bool(declared_outputs) and (
            len(declared_output_paths) == len(declared_outputs)
        )
        if declared_outputs and not can_materialize_declared_outputs:
            identity_context = _set_cache_status(
                identity_context,
                cache_status="miss_unresolved_paths",
            )
        elif can_materialize_declared_outputs:
            cached_run_result = _materialize_cas_hit(
                executor=executor,
                request=request,
                identity_context=_set_cache_status(
                    identity_context,
                    cache_status="hit",
                ),
                declared_output_paths=declared_output_paths,
            )
            if cached_run_result is not None:
                result = _build_step_result_from_run(
                    executor=executor,
                    run_result=cached_run_result,
                    clock=self._clock,
                    identity_context=_set_cache_status(
                        identity_context,
                        cache_status="hit",
                    ),
                )
                # ── Apply content-validator support ─────────────────
                return _apply_content_validator_support(result, config)

        try:
            run_result = self._run_executor_fn(request)
        except Exception as exc:  # noqa: BLE001
            return _failed_step_result(
                "executor_runner_error",
                f"Executor runner raised {type(exc).__name__}: {exc}",
                **_identity_payload(identity_context),
                provenance=Provenance(
                    sources=("astrid.executor", "astrid.cas"),
                    generator=request.executor_id,
                    generated_at=self._clock() if callable(self._clock) else None,
                    chain=tuple(identity_context["provenance_chain"]),
                ),
            )

        if not isinstance(run_result, ExecutorRunResult):
            return _failed_step_result(
                "executor_runner_result_type",
                (
                    "Executor runner must return ExecutorRunResult, got "
                    f"{type(run_result).__name__}"
                ),
                executor_id=request.executor_id,
            )

        if can_materialize_declared_outputs and run_result.error is None and (
            run_result.returncode is None or run_result.returncode == 0
        ):
            run_result = _materialize_cas_miss(
                executor=executor,
                run_result=run_result,
                identity_context=identity_context,
                declared_output_paths=declared_output_paths,
            )

        result = _build_step_result_from_run(
            executor=executor,
            run_result=run_result,
            clock=self._clock,
            identity_context=identity_context,
        )
        # ── Apply content-validator support ─────────────────────────
        return _apply_content_validator_support(result, config)


# ── Registry install helper ──────────────────────────────────────────────────


def install_astrid_step_adapter(
    registry: StepInvocationAdapterRegistry,
    kind: str = "astrid",
    adapter: AstridStepInvocationAdapter | None = None,
    *,
    executor_registry: Any = None,
    run_executor_fn: Any = None,
    artifact_root: Any = None,
    default_project: str = "default",
    project_dir_resolver: Any = None,
    clock: Any = None,
) -> AstridStepInvocationAdapter:
    """Install the Astrid adapter into an Arnold ``StepInvocationAdapterRegistry``.

    If *adapter* is supplied it is registered directly.  Otherwise a new
    :class:`AstridStepInvocationAdapter` is constructed from the remaining
    keyword arguments.

    Parameters
    ----------
    registry:
        Arnold :class:`StepInvocationAdapterRegistry` instance.
    kind:
        Invocation kind string registered with the registry (default ``"astrid"``).
    adapter:
        Pre-built adapter instance (optional).
    executor_registry:
        Astrid executor registry (required when *adapter* is not supplied).
    run_executor_fn:
        Astrid ``run_executor``-compatible callable (required when *adapter*
        is not supplied).
    artifact_root:
        Root directory for out-mode artifacts (required when *adapter* is not
        supplied).
    default_project:
        Fallback project slug for out mode (default ``"default"``).
    project_dir_resolver:
        Optional project-directory resolver callable.
    clock:
        Optional clock callable for timestamps.

    Returns
    -------
    AstridStepInvocationAdapter
        The registered adapter instance.

    Raises
    ------
    ValueError
        If neither *adapter* nor the required construction arguments are supplied.
    """
    if adapter is None:
        if executor_registry is None or run_executor_fn is None or artifact_root is None:
            raise ValueError(
                "install_astrid_step_adapter: must supply either 'adapter' or all of "
                "'executor_registry', 'run_executor_fn', 'artifact_root'"
            )
        adapter = AstridStepInvocationAdapter(
            executor_registry=executor_registry,
            run_executor_fn=run_executor_fn,
            artifact_root=artifact_root,
            default_project=default_project,
            project_dir_resolver=project_dir_resolver,
            clock=clock,
            kind=kind,
        )
    # Delegate to Arnold's registry.register for duplicate-registration
    # behaviour — we do NOT guard against duplicate kinds here.
    registry.register(kind, adapter)
    return adapter
