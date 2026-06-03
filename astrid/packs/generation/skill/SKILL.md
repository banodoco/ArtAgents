---
name: generation
description: >
  Generate images and videos from text prompts using local (vibecomfy) or
  cloud (fal, OpenAI) backends.  Uses the model → mode → backend taxonomy
  (schema v2) with required --mode.  Covers generate_image,
  generate_video, and generate_image_openai.
---

# Generation

The generation pack covers three executors for creating images and videos
from text prompts via local or cloud backends.

## Executors

| Executor | What it does |
|---|---|
| `generation.generate_image` | Generate images from text prompts via local (vibecomfy) or cloud (fal) backends. v2: model→mode→backend taxonomy with required `--mode`. Supports t2i, i2i, and edit modes. |
| `generation.generate_video` | Generate videos from text prompts via local or cloud backends. v2: model→mode→backend with t2v, i2v, and flf (first-last-frame) modes. |
| `generation.generate_image_openai` | Generate image files with OpenAI GPT Image models from a prompt file. Requires `OPENAI_API_KEY`. |

For detailed image generation guidance — mode selection (t2i/i2i/edit),
model decision tree, drop-with-warning behavior, and escape hatches — see
the executor-level skill at
`astrid/packs/generation/executors/generate_image/skill/SKILL.md`.

## When to use

- Use `generation.generate_image` for standard image generation from text
  prompts (the primary entry point).
- Use `generation.generate_video` for video generation from text or image
  prompts.
- Use `generation.generate_image_openai` when you specifically need OpenAI
  GPT Image models and have a prompt file ready.

For LoRAs, IP-adapter, controlnet, custom samplers, or graph composition,
use the `vibecomfy` skill instead (escape hatch).

## Credentials

| Env var | Used by |
|---|---|
| `FAL_KEY` | generate_image (cloud), generate_video (cloud) |
| `OPENAI_API_KEY` | generate_image_openai |

## CLI quick-start

Pass every declared input with `--input NAME=VALUE` (snake_case names; the
runner forwards them to the executor as `--kebab-case` flags). `--out` is a
top-level run flag, not an input. The CLI does not accept arbitrary passthrough
arguments after `--`.

```bash
# Image from text (cloud, fast)
python3 -m astrid executors run generation.generate_image \
  --input model=flux-schnell --input mode=t2i --input execution=cloud \
  --input prompt="a serene mountain lake at dawn" --out ./out

# Image from text (local, open model)
python3 -m astrid executors run generation.generate_image \
  --input model=z-image --input mode=t2i --input execution=local \
  --input prompt="a serene mountain lake at dawn" --out ./out

# Video from text (cloud)
python3 -m astrid executors run generation.generate_video \
  --input model=wan-2.2 --input mode=t2v --input execution=cloud \
  --input prompt="a wave crashing on rocks" --out ./out

# OpenAI image generation from a prompt file
python3 -m astrid executors run generation.generate_image_openai \
  --input prompts_file=./prompts.jsonl --out ./out
```
