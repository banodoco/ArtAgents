#!/usr/bin/env python3
"""Generate images from text prompts using local (vibecomfy) or cloud (fal) backends.


v2: model → mode → backend taxonomy.  ``--mode`` is required (SD-005).
Backend dispatch goes through ``BackendAdapter`` (SD-004).
Features are validated per-mode (SD-003).
"""

from __future__ import annotations


from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('builtin.generate_image')
import argparse
import hashlib
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from astrid.core.generation.backends import (
    BackendAdapter,
    FalBackend,
    GenerationResult,
    VibeComfyBackend,
)
from astrid.core.model_catalog.registry import ModelRegistry

logger = logging.getLogger(__name__)


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


def _check_required(
    mode_spec: Any,
    mode_name: str,
    model_id: str,
    args: argparse.Namespace,
) -> None:
    """Hard-fail if any feature in *mode_spec.requires* is missing from *args*."""
    missing: list[str] = []
    for req in mode_spec.requires:
        if req == "prompt":
            if not (
                getattr(args, "prompt", None)
                or getattr(args, "prompts_file", None)
            ):
                missing.append("prompt")
        elif req == "image_ref":
            if not getattr(args, "image_ref", None):
                missing.append("image_ref")
        elif req == "strength":
            if getattr(args, "strength", None) is None:
                missing.append("strength")
        elif req == "guidance_scale":
            if getattr(args, "guidance_scale", None) is None:
                missing.append("guidance_scale")
        elif req == "steps":
            if getattr(args, "steps", None) is None:
                missing.append("steps")
        elif req == "seed":
            if getattr(args, "seed", None) is None:
                missing.append("seed")
        elif req == "size":
            if not getattr(args, "size", None):
                missing.append("size")
        elif req == "negative_prompt":
            if not getattr(args, "negative_prompt", None):
                missing.append("negative_prompt")
        elif req == "count":
            if not getattr(args, "count", None):
                missing.append("count")

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
    args: argparse.Namespace,
) -> tuple[list[dict[str, str]], list[str]]:
    """Drop caller-supplied features absent from *mode_spec.supports*.

    Returns ``(warnings, dropped_features)`` — both lists of canonical
    feature names.  The caller's *args* are mutated in-place (the dropped
    feature is set to ``None``).
    """
    checks: list[tuple[str, str]] = [
        ("negative_prompt", "negative_prompt"),
        ("image_ref", "image_ref"),
        ("strength", "strength"),
        ("guidance_scale", "guidance_scale"),
        ("steps", "steps"),
        ("count", "count"),
        ("size", "size"),
        ("seed", "seed"),
    ]
    warnings: list[dict[str, str]] = []
    dropped: list[str] = []
    for attr, feat in checks:
        val = getattr(args, attr, None)
        if val is None:
            continue
        if feat not in mode_spec.supports:
            warnings.append(
                {
                    "feature": feat,
                    "reason": (
                        f"not supported by model {model_id!r} "
                        f"mode {mode_name!r}"
                    ),
                }
            )
            setattr(args, attr, None)
            dropped.append(feat)
    return warnings, dropped


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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate images from text prompts via local or cloud backends.",
    )
    p.add_argument(
        "--mode",
        required=True,
        choices=["t2i", "i2i", "edit", "inpaint", "outpaint", "upscale"],
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
        choices=["local", "cloud"],
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
    return p


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    mode_name: str = args.mode  # SD-005: explicit --mode required

    # --- load registry -------------------------------------------------------
    try:
        registry = ModelRegistry.load_default()
    except Exception as exc:
        print(f"Failed to load model registry: {exc}", file=sys.stderr)
        return 1

    # --- validate (model, mode) pair exists ----------------------------------
    try:
        entry, mode_spec = registry.get_by_mode(args.model, mode_name)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # --- check backend availability for --execution --------------------------
    if not registry.backend_available(args.model, mode_name, args.execution):
        available = ", ".join(sorted(mode_spec.backends))
        print(
            f"Error: model {args.model!r} mode {mode_name!r} has no "
            f"{args.execution!r} backend. Available backends: {available}",
            file=sys.stderr,
        )
        return 1

    # --- validate required mode features (hard-fail BEFORE loop) -------------
    _check_required(mode_spec, mode_name, args.model, args)

    # --- drop unsupported features (warn, never fail) ------------------------
    warnings, dropped_features = _drop_unsupported(
        mode_spec, mode_name, args.model, args
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
            print(
                "Error: either --prompt or --prompts-file is required.",
                file=sys.stderr,
            )
            return 1
        prompts = [{"prompt": args.prompt, "model": args.model}]

    # --- build adapter (SD-004: dispatch through BackendAdapter) -------------
    adapter: BackendAdapter
    if args.execution == "cloud":
        adapter = FalBackend(env_file=args.env_file)
    else:
        adapter = VibeComfyBackend()

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
    all_outputs: list[dict[str, Any]] = []
    count = max(1, args.count or 1)
    prompt_text: str | None = None
    final_seed: int = 0
    model_actual: str = ""
    cost_usd: float | None = None
    duration_ms: int = 0
    request_id: str | None = None
    source_urls: list[str] | None = None
    all_applied_features: list[str] = []

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
                    print(
                        f"Warning: skipping row {i} ({prompt_text!r}): "
                        f"{skip_reason}",
                        file=sys.stderr,
                    )
                    continue

                # Re-validate features for the overridden model's mode.
                # Check that row-supplied values satisfy the override
                # model's mode.requires (DEBT-134).
                row_missing: list[str] = []
                for req in mode_spec.requires:
                    if req == "prompt":
                        if not prompt_text:
                            row_missing.append("prompt")
                    elif req == "image_ref":
                        row_ref = prompt_entry.get("image_ref", args.image_ref)
                        if not row_ref:
                            row_missing.append("image_ref")
                    elif req == "strength":
                        row_strength = prompt_entry.get("strength", args.strength)
                        if row_strength is None:
                            row_missing.append("strength")
                if row_missing:
                    print(
                        f"Warning: skipping row {i} ({prompt_text!r}): "
                        f"override model {entry_override_model!r} mode "
                        f"{mode_name!r} requires "
                        f"{', '.join(sorted(row_missing))}",
                        file=sys.stderr,
                    )
                    continue

                # Drop unsupported features for the override model
                extra_warns, extra_drops = _drop_unsupported(
                    mode_spec, mode_name, entry_override_model, args
                )
                warnings.extend(extra_warns)
                dropped_features.extend(extra_drops)

            seed = _resolve_seed(prompt_entry.get("seed", args.seed), i)
            neg = prompt_entry.get("negative_prompt", args.negative_prompt)
            sz = prompt_entry.get("size", args.size)
            ref = prompt_entry.get("image_ref", args.image_ref)
            strength = prompt_entry.get("strength", args.strength)
            guidance_scale = prompt_entry.get(
                "guidance_scale", args.guidance_scale
            )
            steps = prompt_entry.get("steps", args.steps)
        else:
            prompt_text = args.prompt
            seed = _resolve_seed(args.seed, i)
            neg = args.negative_prompt
            sz = args.size
            ref = args.image_ref
            strength = args.strength
            guidance_scale = args.guidance_scale
            steps = args.steps

        # --- build canonical params dict for adapter -------------------------
        params: dict[str, Any] = {}
        if prompt_text:
            params["prompt"] = prompt_text
        if neg:
            params["negative_prompt"] = neg
        params["seed"] = seed
        if sz:
            params["size"] = sz
        if ref:
            params["image_ref"] = ref
        if strength is not None:
            params["strength"] = strength
        if guidance_scale is not None:
            params["guidance_scale"] = guidance_scale
        if steps is not None:
            params["steps"] = steps
        params["count"] = 1  # N=1 per loop iteration

        # --- dispatch to adapter (SD-004) ------------------------------------
        result: GenerationResult = adapter.generate(
            entry=entry,
            mode=mode_name,
            params=params,
            out_dir=images_dir,
        )

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

        final_seed = result.seed_used
        model_actual = result.model_actual
        cost_usd = result.cost_usd
        duration_ms = result.duration_ms
        request_id = result.request_id
        source_urls = result.source_urls
        if result.applied_features:
            all_applied_features = list(result.applied_features)

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
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
