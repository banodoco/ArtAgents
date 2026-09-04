#!/usr/bin/env python3
"""One-shot native Wan2GP video generation (C-M1).

Typed capability ``wan2gp.generate_video`` — compiles inputs deterministically,
runs the native ``shared.api.init / WanGPSession.submit_task`` seam in a
private per-attempt spool, verifies output containment, and emits structured
terminal evidence with disclosure.
"""

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint("wan2gp.generate_video")

import argparse
import json
import sys
import time
from pathlib import Path

from astrid.core._shared.result_manifest import build_manifest
from astrid.packs.wan2gp.src.compiler import compile_from_inputs, portable_digest
from astrid.packs.wan2gp.src.driver import one_shot_run, validate_settings as driver_validate


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Wan2GP one-shot native video generation (C-M1).")
    p.add_argument("--prompt", required=True, help="Text prompt.")
    p.add_argument("--model", default="wan-2.2", help="Model id (default wan-2.2).")
    p.add_argument("--negative-prompt", dest="negative_prompt", default=None, help="Negative prompt.")
    p.add_argument("--resolution", default=None, help="WxH, e.g. 1280x720.")
    p.add_argument("--frames", type=int, default=None, dest="video_length", help="Frames / video_length.")
    p.add_argument("--fps", default=None, help="FPS (stringified to force_fps).")
    p.add_argument("--seed", type=int, default=None, help="Seed.")
    p.add_argument("--guidance-scale", dest="guidance_scale", type=float, default=None)
    p.add_argument("--steps", type=int, default=None, dest="num_inference_steps", help="Sampling steps.")
    p.add_argument("--loras", default=None, help="LoRAs JSON/path (pass-through).")
    p.add_argument("--out", type=Path, default=Path.cwd() / "wan2gp_output", help="Attempt root (spool is out/outputs).")
    p.add_argument("--wan2gp-path", dest="wan2gp_path", type=Path, default=None, help="Explicit Wan2GP checkout root.")
    return p


def generate_core(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    t0 = time.time()
    inputs: dict[str, object] = {
        "prompt": args.prompt,
        "model": args.model,
        "negative_prompt": args.negative_prompt,
        "resolution": args.resolution,
        "video_length": args.video_length,
        "fps": args.fps,
        "seed": args.seed,
        "guidance_scale": args.guidance_scale,
        "steps": args.num_inference_steps,
        "loras": args.loras,
    }
    # Drop Nones for compiler
    clean: dict[str, object] = {k: v for k, v in inputs.items() if v is not None}
    try:
        settings = compile_from_inputs({**clean, "wan2gp_path": str(args.wan2gp_path) if args.wan2gp_path else None})
        driver_validate(settings)
    except ValueError as exc:
        return 2, {"ok": False, "error": str(exc), "code": "invalid_inputs"}

    attempt_root = (args.out or Path.cwd() / "wan2gp_output").expanduser().resolve()
    attempt_root.mkdir(parents=True, exist_ok=True)
    digest = portable_digest(settings)

    result = one_shot_run(
        settings=settings,
        attempt_root=attempt_root,
        wan2gp_root=str(args.wan2gp_path) if args.wan2gp_path else None,
    )

    # If engine checkout absent, treat as structured failure with disclosure, not crash.
    # Build a manifest regardless so callers have durable evidence.
    outputs: list[dict[str, object]] = []
    for f in result.generated_files:
        try:
            p = Path(f)
            size = p.stat().st_size if p.exists() else None
        except Exception:
            size = None
        outputs.append({"path": f, "size": size} if size is not None else {"path": f})

    manifest = build_manifest(
        kind="video",
        inputs={"prompt": args.prompt, "model": args.model},
        outputs=outputs,
        created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        schema_version=2,
        warnings=[],
        model=args.model,
        portable_digest=digest,
        disclosed_engine=result.disclosed_engine,
        spool=str(result.spool),
    )

    # Write manifest under attempt root for the host to publish
    manifest_path = attempt_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    if not result.success:
        return 1, {
            "ok": False,
            "error": "; ".join(result.errors) if result.errors else "generation failed",
            "manifest": manifest,
            "disclosed_engine": result.disclosed_engine,
            "spool": str(result.spool),
            "duration_ms": int((time.time() - t0) * 1000),
        }

    return 0, {
        "ok": True,
        "manifest": manifest,
        "files": result.generated_files,
        "disclosed_engine": result.disclosed_engine,
        "spool": str(result.spool),
        "duration_ms": int((time.time() - t0) * 1000),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code, payload = generate_core(args)
    # Emit JSON on stdout for host capture; errors also go to stderr.
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if code != 0 and payload.get("error"):
        print(payload["error"], file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
