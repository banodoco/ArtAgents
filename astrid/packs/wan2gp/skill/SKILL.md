---
name: wan2gp
description: >
  Native Wan2GP pack — generate video via the in-process Wan2GP engine
  (shared.api.init / WanGPSession.submit_task) behind a private per-runner
  output spool and one-shot runner. Pinned to banodoco/Wan2GP@181bb71a
  (reigh-sprint-3).
---

# Wan2GP

Native Wan2GP is the **local** video-generation engine for Astrid. It runs
inside the Reigh Worker GPU substrate but is owned as an Astrid pack
capability. The engine itself lives in `reigh-worker/Wan2GP/` and is **not**
copied into Astrid; Astrid only owns the typed capability, settings compiler,
native driver, private spool, one-shot runner, and lifecycle hooks.

## Engine seam

```
shared.api.init(root=..., output_dir=...) -> WanGPSession
WanGPSession.submit_task(settings: dict) -> SessionJob
SessionJob.result(timeout=...) -> GenerationResult
```

- `root` is the Wan2GP checkout root (contains `wgp.py`, `shared/`, `wgp_config.json`).
- `output_dir` is the per-runner private spool (attempt-scoped, not shared).
- `settings` is the compiled Wan2GP settings dict (deterministic compiler in `astrid/packs/wan2gp/src/compiler.py`).
- Cancellation is cooperative via `SessionJob.cancel()` / `WanGPSession.cancel()`.

## Executors

| Executor | What it does |
|---|---|
| `wan2gp.generate_video` | Typed one-shot generation: compiles inputs to Wan2GP settings, runs the native driver in a private spool, and returns structured terminal evidence. |
| `wan2gp.validate_settings` | Validates and compiles inputs without executing the engine. |

## One-shot vs persistent

- **C-M1 (this checkpoint):** one-shot runner — `init()` → `submit_task()` → `result()` → `close()` (model release) per attempt. No warm session reuse.
- **C-M2:** persistent session with exact reuse fingerprint, bounded cooperative cancellation, and release hooks (awaits B-M2).

## Inputs (portable vs machine-local)

Portable (part of capability digest): `prompt`, `negative_prompt`, `model`, `resolution`, `num_frames`/`video_length`, `fps`/`force_fps`, `seed`, `guidance_scale`, `loras`, etc.

Machine-local (excluded from digest, part of reuse fingerprint): `wan2gp_path`, `attempt_root`, `device`, `output_dir`.

## Quick-start

```python
import astrid.sdk as sdk

# Validate without running
sdk.invoke("wan2gp.validate_settings", kind="executor", inputs={"prompt": "a cat", "model": "wan-2.2"})

# One-shot generation (requires Worker GPU substrate with Wan2GP checkout)
sdk.invoke("wan2gp.generate_video", kind="executor", inputs={"prompt": "a cat", "model": "wan-2.2", "resolution": "1280x720"})
```
