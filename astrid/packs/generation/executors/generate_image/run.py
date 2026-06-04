#!/usr/bin/env python3
"""Generate images from text prompts using local (vibecomfy) or cloud (fal) backends.


v2: model → mode → backend taxonomy.  ``--mode`` is required (SD-005).
Backend dispatch goes through ``BackendAdapter`` (SD-004).
Features are validated per-mode (SD-003).
"""

from __future__ import annotations

from astrid.contracts.errors import AstridError
from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint, warn_if_unledgered

guard_canonical_entrypoint('generation.generate_image')
import argparse
import hashlib
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrid.core.cli_choices import add_choice_arg
from astrid.core.generation import GENERATION_RESULT_KEY
from astrid.core.generation.backends import (
    BackendAdapter,
    GenerationBackendRegistry,
    GenerationResult,
    load_default_generation_backend_registry,
)
from astrid.core.model_catalog.registry import ModelRegistry
from astrid.core.util.atomic_io import write_json_atomic
from astrid.core.util.png_metadata import embed_png_text

logger = logging.getLogger(__name__)

_IMAGE_CLI_FEATURES: tuple[str, ...] = (
    "prompt",
    "negative_prompt",
    "seed",
    "count",
    "size",
    "image_ref",
    "strength",
    "guidance_scale",
    "steps",
)
_PROMPT_ENTRY_CONTROL_KEYS = frozenset({"model", "mode"})


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


def _load_prompts(path: Path, model: str, mode: str) -> list[dict[str, Any]]:
    """Load generation requests from a JSON or JSONL file.

    Each line is a JSON object that may override ``prompt``, ``seed``,
    ``count``, ``size``, ``negative_prompt``, ``image_ref``, ``strength``,
    ``guidance_scale``, ``steps``, and ``model``.  A bare JSON array is
    also accepted.

    Per-entry ``model`` overrides must include an explicit ``mode`` field
    matching CLI ``--mode`` or be rejected (SD-005, FLAG-004).
    """
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        data = json.loads(text)
        if isinstance(data, list):
            return _normalise_prompts(data, model, mode)
        raise SystemExit(f"{path}: top-level JSON must be an array or JSONL")

    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(json.loads(line))
    if not entries:
        raise SystemExit(f"{path}: no valid entries found")
    return _normalise_prompts(entries, model, mode)


def _normalise_prompts(
    raw: list[dict[str, Any]], model: str, mode: str
) -> list[dict[str, Any]]:
    """Ensure every entry has a ``prompt`` and a ``model`` key.

    Per-entry ``model`` overrides are validated for mode consistency
    (FLAG-004): a ``mode`` field matching CLI ``--mode`` is required.
    """
    result: list[dict[str, Any]] = []
    for i, entry in enumerate(raw):
        if "prompt" not in entry:
            raise SystemExit(
                f"Entry {i} in prompts file is missing required 'prompt' key"
            )
        entry.setdefault("model", model)

        # FLAG-004: per-entry model override must have explicit mode field
        # matching CLI --mode (or no override at all).
        entry_model = entry.get("model", model)
        if entry_model != model:
            entry_mode = entry.get("mode")
            if entry_mode is None:
                raise SystemExit(
                    f"Entry {i} overrides model to {entry_model!r} but "
                    f"has no 'mode' field.  Per-entry model overrides must "
                    f"include 'mode' matching CLI --mode ({mode!r})."
                )
            if entry_mode != mode:
                raise SystemExit(
                    f"Entry {i} has mode {entry_mode!r} which does not match "
                    f"CLI --mode {mode!r}.  Per-entry model overrides must "
                    f"use the same mode."
                )

        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Feature validation (per-mode — SD-003)
# ---------------------------------------------------------------------------


def _feature_is_missing(feature: str, value: Any) -> bool:
    """Return ``True`` when a supplied feature value should count as missing."""
    if value is None:
        return True
    if feature == "count":
        return not bool(value)
    if isinstance(value, str):
        return not value.strip()
    return False


def _build_requested_params(
    args: argparse.Namespace,
    *,
    prompt_text: str | None,
    prompt_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge prompt-entry and CLI feature values into canonical params."""
    params: dict[str, Any] = {}
    if prompt_entry:
        for key, value in prompt_entry.items():
            if key in _PROMPT_ENTRY_CONTROL_KEYS:
                continue
            params[key] = value

    if prompt_text is not None:
        params["prompt"] = prompt_text
    elif "prompt" not in params:
        params["prompt"] = getattr(args, "prompt", None)

    for feature in _IMAGE_CLI_FEATURES:
        if feature == "prompt":
            continue
        if feature not in params:
            params[feature] = getattr(args, feature, None)

    return {
        feature: value
        for feature, value in params.items()
        if value is not None
    }


def _check_required(
    mode_spec: Any,
    mode_name: str,
    model_id: str,
    requested_params: dict[str, Any],
) -> None:
    """Hard-fail if any feature in *mode_spec.requires* is missing."""
    missing: list[str] = []
    for req in mode_spec.requires:
        if _feature_is_missing(req, requested_params.get(req)):
            missing.append(req)

    if missing:
        raise SystemExit(
            f"model {model_id!r} mode {mode_name!r} requires: "
            f"{', '.join(sorted(missing))}. "
            f"Provide {'it' if len(missing) == 1 else 'them'} "
            f"and retry."
        )


def _drop_unsupported(
    mode_spec: Any,
    mode_name: str,
    model_id: str,
    requested_params: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    """Drop caller-supplied features absent from *mode_spec.supports*.

    Returns ``(filtered_params, warnings, dropped_features)``.
    """
    filtered_params: dict[str, Any] = {}
    warnings: list[dict[str, str]] = []
    dropped: list[str] = []
    for feature, value in requested_params.items():
        if _feature_is_missing(feature, value):
            continue
        if feature not in mode_spec.supports:
            warnings.append(
                {
                    "feature": feature,
                    "reason": (
                        f"not supported by model {model_id!r} "
                        f"mode {mode_name!r}"
                    ),
                }
            )
            dropped.append(feature)
            continue
        filtered_params[feature] = value
    return filtered_params, warnings, dropped


# ---------------------------------------------------------------------------
# Seed resolution
# ---------------------------------------------------------------------------


def _resolve_seed(requested: int | None, index: int) -> int:
    """Return ``requested + index`` if *requested* is set, else a random seed."""
    if requested is not None:
        return requested + index
    return random.randint(0, 2**31 - 1)


# ---------------------------------------------------------------------------
# Manifest emission
# ---------------------------------------------------------------------------


def _build_manifest(
    args: argparse.Namespace,
    entry: Any,
    mode_name: str,
    model_actual: str,
    outputs: list[dict[str, Any]],
    seed: int,
    warnings: list[dict[str, str]],
    dropped_features: list[str],
    image_ref_resolved: str | None,
    prompt_text: str | None,
    cost_usd: float | None,
    duration_ms: int,
    request_id: str | None,
    source_urls: list[str] | None,
    applied_features: list[str],
) -> dict[str, Any]:
    """Build the canonical manifest dict (20-manifest-schema.md v2)."""
    request: dict[str, Any] = {
        "prompt": prompt_text or getattr(args, "prompt", None),
        "negative_prompt": getattr(args, "negative_prompt", None),
        "seed": seed,
        "count": max(1, args.count or 1),
        "size": getattr(args, "size", None),
        "image_ref_resolved": image_ref_resolved,
    }
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "modality": entry.modality,
        "model": entry.id,
        "mode_used": mode_name,
        "model_actual": model_actual,
        "execution": args.execution,
        "request": request,
        "outputs": outputs,
        "seed": seed,
        "created": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
    }
    if dropped_features:
        manifest["dropped_features"] = dropped_features
    if applied_features:
        manifest["applied_features"] = applied_features
    if cost_usd is not None:
        manifest["cost_usd"] = cost_usd
    if duration_ms:
        manifest["duration_ms"] = duration_ms
    if request_id:
        manifest["request_id"] = request_id
    if source_urls:
        manifest["source_urls"] = source_urls
    return manifest


def _available_backend_ids(mode_spec: Any) -> tuple[str, ...]:
    """Return the backend ids available for one resolved mode."""
    return tuple(sorted(mode_spec.backends))


def _parse_loras_arg(raw: str | None) -> list[str | dict[str, Any]]:
    """Parse the ``--loras`` CLI value into a list for the backend.

    Format: comma-separated tokens.  Each token is either:
    * A registry id (kebab-case, no ``@`` or ``://``) → passed as a str
    * A ``path@scale`` spec (URL or path containing ``://`` or ``.safetensors``
      followed by ``@`` and a float) → passed as ``{"path": ..., "scale": ...}``
    """
    if not raw or not raw.strip():
        return []
    result: list[str | dict[str, Any]] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        # Check for path@scale syntax
        if "@" in token and ("://" in token or ".safetensors" in token):
            parts = token.rsplit("@", 1)
            path = parts[0].strip()
            try:
                scale = float(parts[1].strip())
            except (ValueError, IndexError):
                scale = 1.0
            result.append({"path": path, "scale": scale})
        else:
            # Registry id
            result.append(token)
    return result


def _create_backend_adapter(
    backend_registry: GenerationBackendRegistry,
    execution: str,
    *,
    env_file: Path | None,
) -> BackendAdapter:
    """Instantiate the selected backend with CLI-friendly errors."""
    try:
        return backend_registry.create(execution, env_file=env_file)
    except KeyError as exc:
        raise AstridError(
            f"generation backend {execution!r} is not registered: {exc}",
            recovery_command="check available backends and retry with a registered backend",
        ) from exc
    except Exception as exc:
        raise AstridError(
            f"failed to initialize generation backend {execution!r}: {exc}",
            recovery_command="check backend configuration and environment, then retry",
        ) from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate images from text prompts via local or cloud backends.",
    )
    add_choice_arg(
        p,
        "--mode",
        values=("t2i", "i2i", "edit", "inpaint", "outpaint", "upscale"),
        required=True,
        help="Generation mode: t2i (text-to-image), i2i (image-to-image), "
        "edit (instruction-guided edit), inpaint, outpain, upscale.  "
        "Only t2i, i2i, edit are wired this sprint (SD-005).",
    )
    prompt_group = p.add_mutually_exclusive_group()
    prompt_group.add_argument(
        "--prompt",
        help="Text prompt for generation.",
    )
    prompt_group.add_argument(
        "--prompts-file",
        type=Path,
        help="JSONL file of prompts (one object per line).",
    )
    p.add_argument(
        "--model",
        required=True,
        help="Model ID from the registry (e.g. 'z-image', 'flux-dev').",
    )
    p.add_argument(
        "--image-ref",
        dest="image_ref",
        help="Reference image path or URL for i2i/edit modes.",
    )
    p.add_argument(
        "--execution",
        required=True,
        help="Backend: 'local' (vibecomfy) or 'cloud' (fal).",
    )
    p.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of images to generate (default 1).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Deterministic seed (base_seed + i for sequential images).",
    )
    p.add_argument(
        "--negative-prompt",
        dest="negative_prompt",
        help="Text describing what to avoid.",
    )
    p.add_argument(
        "--size",
        help="Output dimensions, e.g. '1024x1024' or fal size preset.",
    )
    p.add_argument(
        "--strength",
        type=float,
        default=None,
        help="Denoising strength for i2i mode (0.0-1.0).",
    )
    p.add_argument(
        "--guidance-scale",
        type=float,
        dest="guidance_scale",
        default=None,
        help="Classifier-free guidance scale.",
    )
    p.add_argument(
        "--steps",
        type=int,
        default=None,
        help="Number of sampling steps.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path.cwd() / "generated_output",
        help="Output directory (default: ./generated_output).",
    )
    p.add_argument(
        "--env-file",
        type=Path,
        help="Env file holding FAL_KEY (for cloud execution).",
    )
    p.add_argument(
        "--loras",
        default=None,
        help="Comma-separated LoRA registry ids and/or path@scale specs "
        "(e.g. 'flux-realism' or 'https://...lora.safetensors@0.8').",
    )
    return p


def _request_to_argv(request: Any) -> list[str]:
    """Translate an executor-style request object into CLI argv."""
    argv: list[str] = []
    inputs = getattr(request, "inputs", {}) or {}
    flag_names = (
        "mode",
        "prompt",
        "prompts_file",
        "model",
        "image_ref",
        "execution",
        "count",
        "seed",
        "negative_prompt",
        "size",
        "strength",
        "guidance_scale",
        "steps",
        "env_file",
        "loras",
    )
    for name in flag_names:
        value = inputs.get(name)
        if value in (None, ""):
            continue
        if name == "loras" and not isinstance(value, str):
            value = json.dumps(value)
        argv.extend([f"--{name.replace('_', '-')}", str(value)])
    out = getattr(request, "out", None)
    if out not in (None, ""):
        argv.extend(["--out", str(out)])
    return argv


def _coerce_args(
    args_or_request: argparse.Namespace | list[str] | tuple[str, ...] | Any | None,
) -> argparse.Namespace:
    """Return a parsed args namespace from CLI argv, a namespace, or a request."""
    if isinstance(args_or_request, argparse.Namespace):
        return args_or_request
    if args_or_request is None or isinstance(args_or_request, (list, tuple)):
        return build_parser().parse_args(args_or_request)
    if hasattr(args_or_request, "inputs"):
        return build_parser().parse_args(_request_to_argv(args_or_request))
    raise TypeError(
        "generate_core expected argparse.Namespace, argv list/tuple, or executor request"
    )


def _manifest_path_for_run_dir(run_dir: Path | None) -> Path:
    if run_dir is None:
        raise AstridError(
            "generation result is missing run_dir",
            recovery_command="run generation through generate_core/main so the executor can write manifest metadata",
        )
    return run_dir / "manifest.json"


# ---------------------------------------------------------------------------
# core entrypoints
# ---------------------------------------------------------------------------


def generate_core(
    args_or_request: argparse.Namespace | list[str] | tuple[str, ...] | Any | None,
) -> GenerationResult:
    args = _coerce_args(args_or_request)

    mode_name: str = args.mode  # SD-005: explicit --mode required

    # --- load backend registry ----------------------------------------------
    try:
        backend_registry = load_default_generation_backend_registry()
    except Exception as exc:
        raise AstridError(
            f"Failed to load generation backend registry: {exc}",
            recovery_command="ensure generation backend packages are installed and retry",
        ) from exc

    # --- load registry -------------------------------------------------------
    try:
        registry = ModelRegistry.load_default()
    except Exception as exc:
        raise AstridError(
            f"Failed to load model registry: {exc}",
            recovery_command="ensure model registry packages are installed and retry",
        ) from exc

    # --- validate (model, mode) pair exists ----------------------------------
    try:
        entry, mode_spec = registry.get_by_mode(args.model, mode_name)
    except KeyError as exc:
        raise AstridError(
            f"Error: {exc}",
            recovery_command="check available models and modes with --help and retry with a valid (model, mode) pair",
        ) from exc

    # --- check backend availability for --execution --------------------------
    if not registry.backend_available(args.model, mode_name, args.execution):
        available = ", ".join(_available_backend_ids(mode_spec))
        raise AstridError(
            f"model {args.model!r} mode {mode_name!r} has no "
            f"{args.execution!r} backend",
            valid_options=list(_available_backend_ids(mode_spec)),
            recovery_command=f"choose one of the available backends: {available}",
        )

    warnings: list[dict[str, str]] = []
    dropped_features: list[str] = []

    # --- setup output directory ----------------------------------------------
    out = args.out.expanduser().resolve()
    images_dir = out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # --- load prompts --------------------------------------------------------
    if args.prompts_file:
        prompts = _load_prompts(args.prompts_file, args.model, mode_name)
    else:
        if not args.prompt:
            raise AstridError(
                "either --prompt or --prompts-file is required",
                recovery_command="provide --prompt 'your text' or --prompts-file path/to/prompts.jsonl",
            )
        prompts = [{"prompt": args.prompt, "model": args.model}]

    # --- build adapter (SD-004: dispatch through BackendAdapter) -------------
    adapter = _create_backend_adapter(
        backend_registry,
        args.execution,
        env_file=args.env_file,
    )

    # --- resolve image_ref path (for manifest tracking) ----------------------
    image_ref_resolved: str | None = None
    if args.image_ref:
        ref = args.image_ref
        ref_path = Path(ref)
        if ref_path.exists():
            image_ref_resolved = str(ref_path.resolve())
        else:
            image_ref_resolved = ref

    # --- sequential N=1 generation loop -------------------------------------
    loras_parsed = _parse_loras_arg(args.loras)
    all_outputs: list[dict[str, Any]] = []
    generated_paths: list[Path] = []
    count = max(1, args.count or 1)
    prompt_text: str | None = None
    final_seed: int = 0
    model_actual: str = ""
    cost_usd: float | None = None
    duration_ms: int = 0
    request_id: str | None = None
    source_urls: list[str] | None = None
    all_applied_features: list[str] = []
    result_error = None

    for i in range(count):
        # Determine the prompt entry for this iteration
        if args.prompts_file:
            prompt_entry = prompts[i % len(prompts)]
            prompt_text = prompt_entry["prompt"]

            # Per-entry model override — re-validate (model, mode, backend)
            entry_override_model: str = prompt_entry.get("model", args.model)
            if entry_override_model != args.model:
                # Mode field already validated in _normalise_prompts
                # (FLAG-004): skip row with warning if override fails validation
                skip_reason: str | None = None
                try:
                    entry, mode_spec = registry.get_by_mode(
                        entry_override_model, mode_name
                    )
                except KeyError as exc:
                    skip_reason = str(exc)
                if skip_reason is None and not registry.backend_available(
                    entry_override_model, mode_name, args.execution
                ):
                    available = ", ".join(sorted(mode_spec.backends))
                    skip_reason = (
                        f"model {entry_override_model!r} mode "
                        f"{mode_name!r} has no {args.execution!r} backend. "
                        f"Available: {available}"
                    )
                if skip_reason is not None:
                    logger.warning(
                        "skipping row %d (%r): %s",
                        i, prompt_text, skip_reason,
                    )
                    continue

            requested_params = _build_requested_params(
                args,
                prompt_text=prompt_text,
                prompt_entry=prompt_entry,
            )
            try:
                _check_required(
                    mode_spec,
                    mode_name,
                    entry.id,
                    requested_params,
                )
            except SystemExit as exc:
                logger.warning(
                    "skipping row %d (%r): %s",
                    i, prompt_text, exc.code,
                )
                continue
            params, extra_warns, extra_drops = _drop_unsupported(
                mode_spec,
                mode_name,
                entry.id,
                requested_params,
            )
            warnings.extend(extra_warns)
            dropped_features.extend(extra_drops)
            seed = _resolve_seed(params.get("seed", args.seed), i)
        else:
            prompt_text = args.prompt
            requested_params = _build_requested_params(args, prompt_text=prompt_text)
            _check_required(mode_spec, mode_name, entry.id, requested_params)
            params, extra_warns, extra_drops = _drop_unsupported(
                mode_spec,
                mode_name,
                entry.id,
                requested_params,
            )
            warnings.extend(extra_warns)
            dropped_features.extend(extra_drops)
            seed = _resolve_seed(args.seed, i)

        # --- build canonical params dict for adapter -------------------------
        params["seed"] = seed
        params["count"] = 1  # N=1 per loop iteration
        if loras_parsed:
            params["loras"] = loras_parsed

        # --- dispatch to adapter (SD-004) ------------------------------------
        try:
            result: GenerationResult = adapter.generate(
                entry=entry,
                mode=mode_name,
                params=params,
                out_dir=images_dir,
            )
            generated_paths.extend(result.image_paths)

            # Convert GenerationResult to manifest output dicts
            for img_path in result.image_paths:
                content_hash = (
                    "sha256:"
                    + hashlib.sha256(img_path.read_bytes()).hexdigest()
                )
                rel = str(img_path.relative_to(out))
                output_entry: dict[str, Any] = {
                    "path": rel,
                    "content_hash": content_hash,
                    "bytes": img_path.stat().st_size,
                }
                all_outputs.append(output_entry)

                # Embed Astrid metadata as astrid_* tEXt chunks (PR-017).
                _embed_fields: dict[str, str] = {
                    "prompt": prompt_text or getattr(args, "prompt", ""),
                    "negative_prompt": getattr(args, "negative_prompt", None) or "",
                    "model": entry.id,
                    "model_actual": result.model_actual,
                    "seed": str(seed),
                    "request_id": result.request_id or "",
                    "created": datetime.now(timezone.utc).isoformat(),
                }
                if params.get("loras"):
                    _embed_fields["loras"] = str(params["loras"])
                embed_png_text(img_path, _embed_fields)

            final_seed = result.seed_used
            model_actual = result.model_actual
            cost_usd = result.cost_usd
            duration_ms = result.duration_ms
            request_id = result.request_id
            source_urls = result.source_urls
            result_error = result.error
            if result.applied_features:
                all_applied_features = list(result.applied_features)
        except BaseException:
            if all_outputs:
                try:
                    manifest = _build_manifest(
                        args,
                        entry,
                        mode_name,
                        model_actual,
                        all_outputs,
                        final_seed,
                        warnings,
                        dropped_features,
                        image_ref_resolved,
                        prompt_text,
                        cost_usd,
                        duration_ms,
                        request_id,
                        source_urls,
                        all_applied_features,
                    )
                    manifest_path = out / "manifest.json"
                    if loras_parsed:
                        manifest["loras"] = loras_parsed
                    write_json_atomic(manifest_path, manifest)
                except Exception:
                    pass
            raise

    # --- emit manifest -------------------------------------------------------
    manifest = _build_manifest(
        args,
        entry,
        mode_name,
        model_actual,
        all_outputs,
        final_seed,
        warnings,
        dropped_features,
        image_ref_resolved,
        prompt_text,
        cost_usd,
        duration_ms,
        request_id,
        source_urls,
        all_applied_features,
    )
    manifest_path = out / "manifest.json"
    if loras_parsed:
        manifest["loras"] = loras_parsed
    write_json_atomic(manifest_path, manifest)

    generation_result = GenerationResult(
        image_paths=generated_paths,
        seed_used=final_seed,
        model_actual=model_actual,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        applied_features=list(all_applied_features),
        dropped_features=list(dropped_features),
        request_id=request_id,
        source_urls=source_urls,
        error=result_error,
        manifest=manifest,
        run_dir=out,
    )
    return generation_result


def run_sdk(argv: list[str] | None = None) -> dict[str, Any]:
    """In-process entrypoint returning a JSON-safe payload dict.

    On success returns ``{GENERATION_RESULT_KEY: result, \"returncode\": 0}``.
    On failure returns a JSON-safe diagnostic with a non-zero ``returncode``,
    preserving the original exception type and message for the caller.

    Subprocess / CLI compatibility is preserved through ``main()`` and the
    ``__main__`` guard at the bottom of this module.
    """
    try:
        result = generate_core(argv)
    except AstridError as exc:
        diagnostic: dict[str, Any] = {
            "type": "AstridError",
            "cause": exc.cause,
            "recovery_command": exc.recovery_command,
        }
        if exc.valid_options:
            diagnostic["valid_options"] = exc.valid_options
        return {"returncode": 1, "error": diagnostic}
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int) and code != 0:
            returncode = code
        elif code and str(code):
            returncode = 1
        else:
            returncode = 0
        return {
            "returncode": returncode,
            "error": {
                "type": "SystemExit",
                "message": str(code) if code else "",
            },
        }
    except Exception as exc:
        return {
            "returncode": 1,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
    return {"returncode": 0, GENERATION_RESULT_KEY: result}


def main(argv: list[str] | None = None) -> int:
    warn_if_unledgered()
    result = generate_core(argv)
    manifest_path = _manifest_path_for_run_dir(result.run_dir)
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
