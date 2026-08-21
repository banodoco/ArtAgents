---
name: generation
description: >
  Generate images and videos from text prompts using the elegant
  `astrid.generate` facade.  Image and video generation route through
  the same executor code path (SDK, project-bound, or ad-hoc output
  directory).  Covers generate_image, generate_video, and
  generate_image_openai (executor-only).
---

# Generation

The generation pack provides a first-class **library facade** for image and
video generation and also exposes the underlying executors for direct (SDK)
and automation use.

## Quick-start — the `astrid.generate` facade

Import `astrid` and call `.image()` or `.video()`.  Every call returns a typed
`GenerationResult` with `.path`, `.ok`, `.image_paths` / `.video_paths`,
`.model_actual`, `.seed_used`, `.manifest`, and `.run_dir`.

### Image

```python
import astrid

# Simplest: text-to-image, default project, automatic mode/execution inference
img = astrid.generate.image(
    model="flux-schnell",
    prompt="a serene mountain lake at dawn",
)
img.path          # Path to the output PNG
img.ok            # True on success
img.seed_used     # the seed that was actually used
img.manifest      # full manifest dict (schema v2)
```

Mode (`t2i` / `i2i`) and execution (`cloud` / `local`) are inferred when
possible (SD-002).  Pass them explicitly to override:

```python
# Image-to-image (image_ref triggers i2i inference)
img = astrid.generate.image(
    model="flux-dev",
    image_ref="./sketch.png",
    prompt="turn this into a watercolor painting",
    strength=0.7,
)

# Explicit mode + execution
img = astrid.generate.image(
    model="flux-dev",
    mode="t2i",
    execution="cloud",
    prompt="cyberpunk city",
    seed=42,
)
```

> **Note:** `edit`, `inpaint`, `outpaint`, and `upscale` always require an
> explicit `mode` argument — they cannot be inferred from inputs (SD-002).

### Video

```python
# Text-to-video (cloud)
clip = astrid.generate.video(
    model="wan-2.2",
    mode="t2v",
    prompt="a wave crashing on rocks",
)
clip.path          # first output .mp4
clip.video_paths   # list[Path] — same object as .image_paths
```

```python
# Image-to-video
clip = astrid.generate.video(
    model="wan-2.2",
    mode="i2v",
    image_ref="./start_frame.png",
    prompt="continue this scene",
)
```

```python
# First-last-frame interpolation
clip = astrid.generate.video(
    model="wan-2.2",
    mode="flf",
    image_ref=["./first.png", "./last.png"],
)
```

### LoRA and extra params

All keyword arguments beyond the explicit parameter list pass through to the
executor unchanged:

```python
img = astrid.generate.image(
    model="flux-dev",
    prompt="a weathered fisherman, golden hour",
    loras="z-realgen-v2@1.1",      # registry id @ scale
    steps=28,
    guidance_scale=3.5,
)
```

### Output routing

The facade supports three mutually-exclusive routing strategies:

```python
# 1. Explicit output directory
img = astrid.generate.image(
    model="flux-schnell",
    prompt="test",
    out="./my-outputs",
)

# 2. Explicit project (assets land in the project's canonical run dir)
img = astrid.generate.image(
    model="flux-schnell",
    prompt="test",
    project="my-project",
)

# 3. Neither — resolves the configured default project automatically
#    (no ceremony, no session mutation)
img = astrid.generate.image(
    model="flux-schnell",
    prompt="test",
)
# .run_dir is now inside the default project's run tree
```

When both `out` and `project` are supplied, `out` wins and `project` is
ignored.

### Self-describing outputs

Every generated file carries its own provenance, so an image stays identifiable
after it leaves its run directory:

- **PNG outputs** get the generation metadata embedded as `astrid_*` tEXt chunks
  (`astrid_prompt`, `astrid_model`, `astrid_model_actual` = the actual endpoint,
  `astrid_seed`, `astrid_request_id`, `astrid_created`, plus `astrid_loras` when
  used). Local (vibecomfy/ComfyUI) outputs additionally keep ComfyUI's own
  `prompt`/`workflow` chunks — both are preserved.
- A full `manifest.json` sidecar (schema v2) sits beside the outputs in the run
  dir with the complete record (request, outputs + sha256 hashes, cost, timings).

Read the embedded fields with `PIL.Image.open(path).text` or any PNG tEXt reader.

## Scratchpad convention

For quick experiments and throwaway scripts, drop a `.py` file that calls the
`astrid.generate` facade and run it with plain Python — the facade resolves
the configured default project automatically, so there is zero boilerplate:

```python
# my_experiment.py
import astrid

img = astrid.generate.image(
    model="flux-schnell",
    prompt="a glass teapot on basalt",
)
print(img.path)
print(img.seed_used)
```

```bash
python my_experiment.py
```

The facade resolves the configured default project itself and provides the
same `astrid.generate` surface — no manual context management.

## Plugin verbs

The `astrid.generate` namespace is extensible.  Packs can register additional
verbs under `extensions.generation.verbs` in their manifest.  Registered verbs
appear as `astrid.generate.<name>` and are resolved lazily — `import astrid`
does NOT eagerly load plugin modules.

```python
# After a third-party pack registers "animate":
import astrid
astrid.generate.animate(model="...", prompt="...")
```

The built-in `image` and `video` methods always take priority over plugin
verbs.

## Executors (direct access)

The pack's three executors remain available for direct use through the SDK
(`astrid.sdk.invoke(...)`) and for subprocess/cron automation.

| Executor | What it does |
|---|---|
| `generation.generate_image` | Generate images from text prompts via local (vibecomfy) or cloud (fal) backends. v2: model→mode→backend taxonomy with a required `mode` input. Supports t2i, i2i, and edit modes. |
| `generation.generate_video` | Generate videos from text prompts via local or cloud backends. v2: model→mode→backend with t2v, i2v, and flf (first-last-frame) modes. |
| `generation.generate_image_openai` | Generate image files with OpenAI GPT Image models from a prompt file. Requires `OPENAI_API_KEY`. |

> **⚠️  `generate_image_openai` is executor-only for this sprint.**
> The `astrid.generate.image()` facade explicitly rejects
> `execution="openai"` with a diagnostic pointing to
> `generation.generate_image_openai`.  Direct executor access via the SDK is
> the supported path for OpenAI image generation.

For detailed image generation guidance — mode selection (t2i/i2i/edit),
model decision tree, drop-with-warning behavior, and escape hatches — see
the executor-level skill at
`astrid/packs/generation/executors/generate_image/skill/SKILL.md`.

### Quick-start (SDK)

Pass every declared input as a snake_case entry in `inputs` (each is forwarded
to the executor's `run.py` as a `--kebab-case` flag); pass the output
directory as the `out` kwarg, not inside `inputs`.

```python
import astrid.sdk as sdk

# Image from text (cloud, fast)
result = sdk.invoke("generation.generate_image", inputs={
    "model": "flux-schnell", "mode": "t2i", "execution": "cloud",
    "prompt": "a serene mountain lake at dawn",
}, out="./out")

# Image from text (local, open model)
result = sdk.invoke("generation.generate_image", inputs={
    "model": "z-image", "mode": "t2i", "execution": "local",
    "prompt": "a serene mountain lake at dawn",
}, out="./out")

# Video from text (cloud)
result = sdk.invoke("generation.generate_video", inputs={
    "model": "wan-2.2", "mode": "t2v", "execution": "cloud",
    "prompt": "a wave crashing on rocks",
}, out="./out")

# OpenAI image generation from a prompt file
result = sdk.invoke("generation.generate_image_openai", inputs={
    "prompts_file": "./prompts.jsonl",
}, out="./out")
```

## When to use

- Use `astrid.generate.image(...)` for standard image generation from text
  prompts (the recommended primary entry point).
- Use `astrid.generate.video(...)` for video generation from text or image
  prompts.
- Use `generation.generate_image_openai` via direct executor access (the
  SDK) when you specifically need OpenAI GPT Image models and have a prompt
  file ready.

For LoRAs, IP-adapter, controlnet, custom samplers, or graph composition,
use the `vibecomfy` skill instead (escape hatch).

## Credentials

| Env var | Used by |
|---|---|
| `FAL_KEY` | generate_image (cloud), generate_video (cloud) |
| `OPENAI_API_KEY` | generate_image_openai |

Set these in the process environment, or in a `.env` / `.env.local` file at the
repo root (both are searched; `.env.local` is gitignored and wins over `.env`).
The resolver also walks `~/.env` and a few workspace locations — see
`astrid.core.util.secrets.candidate_env_files`.
