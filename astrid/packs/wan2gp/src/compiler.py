"""Deterministic Wan2GP settings compiler for Astrid.

Compiles the typed Astrid inputs into the Wan2GP settings dict that
``WanGPSession.submit_task(settings)`` expects.  The compiler is pure
(no I/O, no model access) and deterministic: same portable inputs produce
identical settings bytes.

Portable inputs (capability identity) are those that affect output bytes:
prompt, model, resolution, frames, fps, seed, guidance, loras, etc.
Machine-local inputs (wan2gp_path, attempt_root, device) are excluded from
the portable digest and only affect placement.

The Wan2GP native runner normalizes ``force_fps`` to string (api.py:
_normalize_settings_values).  The compiler mirrors that normalization so
portable digests match what the engine actually sees.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Portable keys that define the generation contract.  Mirrors a subset of
# reigh-worker/source/task_handlers/tasks/task_conversion.py param_whitelist
# that the managed Wan2GP runtime understands for video generation.
PORTABLE_KEYS: tuple[str, ...] = (
    "prompt",
    "negative_prompt",
    "model",
    "model_type",
    "resolution",
    "video_length",
    "num_inference_steps",
    "guidance_scale",
    "seed",
    "force_fps",
    "loras",
    "loras_multipliers",
    "activated_loras",
    "additional_loras",
    "flow_shift",
    "embedded_guidance_scale",
    "tea_cache_setting",
    "slg_switch",
    "cfg_star_switch",
    "image_refs_strengths",
)

# Inputs that are intentionally excluded from the portable digest.
MACHINE_LOCAL_KEYS: tuple[str, ...] = (
    "wan2gp_path",
    "attempt_root",
    "output_dir",
    "device",
    "wan2gp_pin",
    "wan2gp_sha",
)


def _coerce_force_fps(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not value.is_integer():
            return str(value)
        return str(int(value))
    return value


def compile_settings(
    *,
    prompt: str,
    model: str = "wan-2.2",
    resolution: str | None = None,
    video_length: int | None = None,
    num_inference_steps: int | None = None,
    guidance_scale: float | None = None,
    seed: int | None = None,
    force_fps: Any | None = None,
    negative_prompt: str | None = None,
    loras: Any | None = None,
    model_type: str | None = None,
    image_refs_strengths: Any | None = None,
    extra: dict[str, Any] | None = None,
    # Machine-local (not portable, not in digest)
    wan2gp_path: str | Path | None = None,
    attempt_root: str | Path | None = None,
) -> dict[str, Any]:
    """Compile typed inputs into a deterministic Wan2GP settings dict.

    Returns a JSON-serializable dict suitable for ``WanGPSession.submit_task``.
    """
    settings: dict[str, Any] = {}
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt is required and must be a non-empty string")
    settings["prompt"] = prompt.strip()
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    settings["model"] = model.strip()
    if resolution is not None:
        settings["resolution"] = str(resolution).strip()
    if video_length is not None:
        settings["video_length"] = int(video_length)
    if num_inference_steps is not None:
        settings["num_inference_steps"] = int(num_inference_steps)
    if guidance_scale is not None:
        settings["guidance_scale"] = float(guidance_scale)
    if seed is not None:
        settings["seed"] = int(seed)
    if force_fps is not None:
        settings["force_fps"] = _coerce_force_fps(force_fps)
    if negative_prompt is not None and str(negative_prompt).strip():
        settings["negative_prompt"] = str(negative_prompt).strip()
    if loras is not None:
        settings["loras"] = loras
    if model_type is not None:
        settings["model_type"] = model_type
    if image_refs_strengths is not None:
        settings["image_refs_strengths"] = image_refs_strengths
    if extra:
        for key, value in extra.items():
            if key in MACHINE_LOCAL_KEYS:
                continue
            if value is not None:
                settings[str(key)] = value
    settings.setdefault("model_type", "vace_fun_14B_2_2")
    settings.setdefault("image_refs_strengths", [])
    # Machine-local values are carried separately, not compiled into settings
    # They are used only for placement/fingerprint, not for identity.
    return settings


def portable_digest(settings: dict[str, Any]) -> str:
    """Stable sha256 over canonical JSON of portable settings only."""
    portable = {k: v for k, v in settings.items() if k not in MACHINE_LOCAL_KEYS}
    # Also drop None values and normalize force_fps string form already
    portable = {k: v for k, v in portable.items() if v is not None}
    canonical = json.dumps(portable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_from_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Compile from the raw executor ``inputs`` dict (typed, from GenericPackHost)."""
    prompt = inputs.get("prompt") or inputs.get("text") or ""
    model = inputs.get("model") or "wan-2.2"
    resolution = inputs.get("resolution")
    # Support both video_length and frames aliases
    video_length = inputs.get("video_length")
    if video_length is None and inputs.get("frames") is not None:
        video_length = inputs.get("frames")
    steps = inputs.get("num_inference_steps")
    if steps is None and inputs.get("steps") is not None:
        steps = inputs.get("steps")
    guidance = inputs.get("guidance_scale")
    seed = inputs.get("seed")
    force_fps = inputs.get("force_fps") if "force_fps" in inputs else inputs.get("fps")
    negative_prompt = inputs.get("negative_prompt")
    loras = inputs.get("loras")
    # Pass through any extra portable keys not explicitly handled
    extra: dict[str, Any] = {}
    known = {"prompt", "text", "model", "resolution", "video_length", "frames", "num_inference_steps", "steps", "guidance_scale", "seed", "force_fps", "fps", "negative_prompt", "loras", "wan2gp_path", "attempt_root", "output_dir", "device"}
    for key, value in inputs.items():
        if key not in known and key not in MACHINE_LOCAL_KEYS:
            extra[key] = value
    return compile_settings(
        prompt=str(prompt),
        model=str(model),
        resolution=resolution,
        video_length=video_length,
        num_inference_steps=steps,
        guidance_scale=guidance,
        seed=seed,
        force_fps=force_fps,
        negative_prompt=negative_prompt,
        loras=loras,
        extra=extra or None,
        wan2gp_path=inputs.get("wan2gp_path"),
        attempt_root=inputs.get("attempt_root"),
    )

DEFAULT_ENGINE_IDENTITY = "wan2gp@181bb71a21008032e4771e11663f33e4489c4512"


def runner_fingerprint(
    settings: dict[str, Any],
    *,
    runner_kind: str = "wan2gp",
    engine_identity: str = DEFAULT_ENGINE_IDENTITY,
) -> str:
    """Return a stable identity for reusable runner state.

    Portable settings define the output contract.  Runner kind and engine
    identity define the implementation contract.  Machine-local paths and
    devices remain excluded through :func:`portable_digest`.
    """
    if not isinstance(settings, dict):
        raise TypeError("settings must be a dict")
    if not runner_kind or not engine_identity:
        raise ValueError("runner_kind and engine_identity are required")
    canonical = {
        "engine_identity": str(engine_identity),
        "portable_digest": portable_digest(settings),
        "runner_kind": str(runner_kind),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def warmth_identity(
    settings: dict[str, Any],
    *,
    runner_kind: str = "wan2gp",
    warmth_profile: str = "default",
    engine_identity: str = DEFAULT_ENGINE_IDENTITY,
) -> str:
    """Return a stable identity for a warm reusable runner profile."""
    if not warmth_profile:
        raise ValueError("warmth_profile is required")
    canonical = {
        "runner_fingerprint": runner_fingerprint(
            settings,
            runner_kind=runner_kind,
            engine_identity=engine_identity,
        ),
        "warmth_profile": str(warmth_profile),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# Explicit name for callers that use "identity" rather than "fingerprint".
runner_identity = runner_fingerprint
