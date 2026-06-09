#!/usr/bin/env python3
"""Generate images from text prompts using local (vibecomfy) or cloud (fal) backends.


v2: model → mode → backend taxonomy.  ``--mode`` is required (SD-005).
Backend dispatch goes through ``BackendAdapter`` (SD-004).
Features are validated per-mode (SD-003).
"""

from __future__ import annotations

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.entrypoint import guard_canonical_entrypoint, warn_if_unledgered

guard_canonical_entrypoint('generation.generate_image')
import argparse
import hashlib
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrid.core._shared.result_manifest import complete_output_metadata
from astrid.packs.generation.executors._common import (
    build_generation_manifest,
    _available_backend_ids,
    _build_requested_params as _build_requested_params_base,
    _check_required,
    _coerce_args as _coerce_args_base,
    _create_backend_adapter,
    _drop_unsupported,
    _feature_is_missing,
    _load_prompts,
    _manifest_path_for_run_dir,
    _normalise_prompts,
    _PROMPT_ENTRY_CONTROL_KEYS,
    _request_to_argv as _request_to_argv_base,
    _resolve_seed,
)
from astrid.core.cli_choices import add_choice_arg
from astrid.core.generation import GENERATION_RESULT_KEY
from astrid.core.generation.backends import (
    BackendAdapter,
    GenerationBackendRegistry,
    GenerationResult,
    load_default_generation_backend_registry,
)
from astrid.core.generation.backends.codex import codex_unavailable_reason
from astrid.core.model_catalog.registry import ModelRegistry
from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.util.png_metadata import embed_png_text

logger = logging.getLogger(__name__)

CODEX_BACKEND_ID = "codex"
CLOUD_BACKEND_ID = "cloud"

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

_IMAGE_ARGV_FLAG_NAMES: tuple[str, ...] = (
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
    "quality",
    "background",
    "timeout",
    "strength",
    "guidance_scale",
    "steps",
    "env_file",
    "loras",
)


# ---------------------------------------------------------------------------
# Thin wrappers that fill in image-specific parameters
# ---------------------------------------------------------------------------


def _build_requested_params(
    args: argparse.Namespace,
    *,
    prompt_text: str | None,
    prompt_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge prompt-entry and CLI feature values into canonical params (image)."""
    return _build_requested_params_base(
        args,
        prompt_text=prompt_text,
        prompt_entry=prompt_entry,
        cli_features=_IMAGE_CLI_FEATURES,
    )


def _request_to_argv(request: Any) -> list[str]:
    """Translate an executor-style request object into CLI argv (image)."""
    return _request_to_argv_base(request, _IMAGE_ARGV_FLAG_NAMES)


def _coerce_args(
    args_or_request: argparse.Namespace | list[str] | tuple[str, ...] | Any | None,
) -> argparse.Namespace:
    """Return a parsed args namespace from CLI argv, a namespace, or a request (image)."""
    return _coerce_args_base(args_or_request, build_parser, _IMAGE_ARGV_FLAG_NAMES)


# ---------------------------------------------------------------------------
# Image-only: LoRA parsing (comma-separated, '@' separator for path@scale)
# ---------------------------------------------------------------------------


def _parse_loras_arg(raw: str | None) -> list[str | dict[str, Any]]:
    """Parse the ``--loras`` CLI value into a list for the backend.

    Format: comma-separated tokens.  Each token is either:
    * A registry id (kebab-case, no ``@`` or ``://``) → passed as a str
    * A ``path@scale`` spec (URL or path containing ``://`` or ``.safetensors``
      followed by ``@`` and a float) → passed as ``{\"path\": ..., \"scale\": ...}``
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


# ---------------------------------------------------------------------------
# Image-only: Codex fallback
# ---------------------------------------------------------------------------


def _resolve_execution_with_codex_fallback(
    args: argparse.Namespace,
    mode_spec: Any,
) -> dict[str, str] | None:
    """Fallback from requested Codex to cloud when local Codex is unavailable."""
    if args.execution != CODEX_BACKEND_ID:
        return None
    reason = codex_unavailable_reason()
    if reason is None:
        return None
    if CLOUD_BACKEND_ID not in mode_spec.backends:
        available = ", ".join(_available_backend_ids(mode_spec))
        raise AstridError(
            f"codex backend requested but unavailable ({reason}) and no cloud fallback is declared",
            valid_options=list(_available_backend_ids(mode_spec)),
            recovery_command=f"install/login to Codex or retry with one of: {available}",
        )
    args.execution = CLOUD_BACKEND_ID
    message = (
        f"codex backend requested but unavailable ({reason}); "
        "falling back to cloud backend"
    )
    logger.warning(message)
    return {"feature": CODEX_BACKEND_ID, "reason": message}


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
    add_choice_arg(
        p,
        "--quality",
        values=("low", "medium", "high", "auto"),
        catalog="generation-codex-quality",
        default=None,
        help="Codex quality hint folded into the prompt (hint only).",
    )
    add_choice_arg(
        p,
        "--background",
        values=("transparent", "opaque", "auto"),
        catalog="generation-codex-background",
        default=None,
        help="Codex background hint folded into the prompt (hint only).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Codex per-image timeout seconds (default 300).",
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

    warnings: list[dict[str, str]] = []
    dropped_features: list[str] = []
    fallback_warning = _resolve_execution_with_codex_fallback(args, mode_spec)
    if fallback_warning is not None:
        warnings.append(fallback_warning)

    # --- check backend availability for --execution --------------------------
    if not registry.backend_available(args.model, mode_name, args.execution):
        available = ", ".join(_available_backend_ids(mode_spec))
        raise AstridError(
            f"model {args.model!r} mode {mode_name!r} has no "
            f"{args.execution!r} backend",
            valid_options=list(_available_backend_ids(mode_spec)),
            recovery_command=f"choose one of the available backends: {available}",
        )

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
        if args.execution == CODEX_BACKEND_ID:
            params["timeout"] = args.timeout
            if args.quality:
                params["quality"] = args.quality
            if args.background:
                params["background"] = args.background

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
                    inputs, request = _build_inputs_request(
                        args, entry, mode_name, final_seed, prompt_text, image_ref_resolved,
                    )
                    manifest = build_generation_manifest(
                        kind="generation.generate_image",
                        inputs=inputs,
                        outputs=all_outputs,
                        created=datetime.now(timezone.utc).isoformat(),
                        warnings=warnings,
                        modality=entry.modality,
                        model=entry.id,
                        mode_used=mode_name,
                        model_actual=model_actual,
                        execution=args.execution,
                        request=request,
                        seed=final_seed,
                        dropped_features=dropped_features if dropped_features else None,
                        applied_features=all_applied_features if all_applied_features else None,
                        cost_usd=cost_usd,
                        duration_ms=duration_ms,
                        request_id=request_id,
                        source_urls=source_urls,
                    )
                    manifest_path = out / "manifest.json"
                    if loras_parsed:
                        manifest["loras"] = loras_parsed
                    # Route output metadata through the shared contract (M1).
                    manifest["outputs"] = complete_output_metadata(
                        manifest["outputs"], root_dir=out,
                    )
                    write_json_atomic(manifest_path, manifest)
                except Exception:
                    pass
            raise

    # --- emit manifest -------------------------------------------------------
    inputs, request = _build_inputs_request(
        args, entry, mode_name, final_seed, prompt_text, image_ref_resolved,
    )
    manifest = build_generation_manifest(
        kind="generation.generate_image",
        inputs=inputs,
        outputs=all_outputs,
        created=datetime.now(timezone.utc).isoformat(),
        warnings=warnings,
        modality=entry.modality,
        model=entry.id,
        mode_used=mode_name,
        model_actual=model_actual,
        execution=args.execution,
        request=request,
        seed=final_seed,
        dropped_features=dropped_features if dropped_features else None,
        applied_features=all_applied_features if all_applied_features else None,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        request_id=request_id,
        source_urls=source_urls,
    )
    manifest_path = out / "manifest.json"
    if loras_parsed:
        manifest["loras"] = loras_parsed
    # Route output metadata through the shared contract (M1).
    manifest["outputs"] = complete_output_metadata(
        manifest["outputs"], root_dir=out,
    )
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


def _build_inputs_request(
    args: argparse.Namespace,
    entry: Any,
    mode_name: str,
    seed: int,
    prompt_text: str | None,
    image_ref_resolved: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build inputs and request dicts for the image generation manifest."""
    requested_prompt = prompt_text or getattr(args, "prompt", None)
    request: dict[str, Any] = {
        "prompt": requested_prompt,
        "negative_prompt": getattr(args, "negative_prompt", None),
        "seed": seed,
        "count": max(1, args.count or 1),
        "size": getattr(args, "size", None),
        "image_ref_resolved": image_ref_resolved,
    }
    inputs: dict[str, Any] = {
        "model": entry.id,
        "mode": mode_name,
        "execution": args.execution,
        "prompt": requested_prompt,
        "seed": seed,
        "count": max(1, args.count or 1),
    }
    for key in ("negative_prompt", "size", "image_ref", "strength", "guidance_scale", "steps"):
        val = getattr(args, key, None)
        if val is not None:
            inputs[key] = val
    if image_ref_resolved is not None:
        inputs["image_ref_resolved"] = image_ref_resolved
    return inputs, request


# ---------------------------------------------------------------------------
# SDK / CLI entrypoints
# ---------------------------------------------------------------------------


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
