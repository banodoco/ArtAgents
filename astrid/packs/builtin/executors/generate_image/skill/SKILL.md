---
name: generate-image
description: >
  Generate images from text prompts using local (vibecomfy) or cloud (fal)
  backends.  Uses the model → mode → backend taxonomy (schema v2).
  Supports t2i (text-to-image), i2i (image-to-image), and edit
  (instruction-guided edit) modes.  For LoRAs, IP-adapter, controlnet,
  custom samplers, or graph composition, use the vibecomfy skill instead
  (escape hatch).
---

# Generate Image

Primary entry point for standard image generation via the Astrid model
registry.  Dispatches through `BackendAdapter` (SD-004) — local goes to
vibecomfy ready-templates, cloud goes to fal.ai endpoints.

## CLI quick-start

```bash
# Cloud text-to-image (fast, cheap)
astrid start builtin.generate_image --model flux-schnell --mode t2i --execution cloud \
  --prompt "a serene mountain lake at dawn" --out ./out

# Cloud text-to-image (best quality)
astrid start builtin.generate_image --model flux-dev --mode t2i --execution cloud \
  --prompt "a serene mountain lake at dawn" --out ./out

# Local text-to-image (best open quality)
astrid start builtin.generate_image --model z-image --mode t2i --execution local \
  --prompt "a serene mountain lake at dawn" --out ./out

# Image-to-image
astrid start builtin.generate_image --model flux-dev --mode i2i --execution cloud \
  --prompt "turn this into a watercolor painting" \
  --image-ref ./input.png --out ./out

# Instruction-guided edit
astrid start builtin.generate_image --model qwen-image-edit --mode edit --execution cloud \
  --prompt "replace the background with a forest" \
  --image-ref ./input.png --out ./out

# Multiple images with seed
astrid start builtin.generate_image --model flux-schnell --mode t2i --execution cloud \
  --prompt "cyberpunk city" --count 3 --seed 42 --out ./out
```

**`--mode` is required** (SD-005).  No auto-inference from inputs.

## Canonical image modes

Six canonical modes (SD-002).  Three are wired in Sprint 2:

| Mode | Description | Wired | Key inputs |
|------|-------------|-------|------------|
| `t2i` | Text-to-image (prompt → image). | ✅ | `--prompt` (required). |
| `i2i` | Image-to-image (prompt + ref image + strength → image). | ✅ | `--prompt`, `--image-ref` (required). `--strength` (optional). |
| `edit` | Instruction-guided edit (prompt = instruction, ref image required). | ✅ | `--prompt`, `--image-ref` (required). NO `negative_prompt`, NO `strength`. |
| `inpaint` | Masked region replacement (prompt + image + mask → image). | ❌ | Future sprint. |
| `outpaint` | Boundary extension (prompt + image + direction/extent → image). | ❌ | Future sprint. |
| `upscale` | Super-resolution (image → larger image). | ❌ | Future sprint. |

## Tier-1 model decision tree

```
What do you need?

├─ Fast, cheap iteration (cloud, ~1s)
│  → flux-schnell --mode t2i --execution cloud
│     - guidance_scale always 1.0
│     - 4 steps, very fast
│
├─ Best cloud quality (text-to-image)
│  → flux-dev --mode t2i --execution cloud
│     - 28 steps, higher quality
│     - no negative_prompt, no image_ref in t2i mode
│
├─ Best local quality (text-to-image, open model)
│  → z-image --mode t2i --execution local
│     - Requires running ComfyUI + vibecomfy
│     - Supports negative_prompt, guidance_scale, steps
│
├─ Image-to-image (cloud)
│  → flux-dev --mode i2i --execution cloud
│     - Requires --image-ref
│     - Supports --strength (denoising level)
│
├─ Image-to-image (local)
│  → z-image --mode i2i --execution local
│     - Requires --image-ref
│     - Supports --strength
│
├─ Instruction-guided edit (cloud)
│  → qwen-image-edit --mode edit --execution cloud
│     - --prompt is the edit instruction
│     - Requires --image-ref
│     - NO negative_prompt, NO strength
│
└─ Instruction-guided edit (local)
   → qwen-image-edit --mode edit --execution local
      - Same as cloud but via ComfyUI
```

Model list: `astrid models list` shows all registered models with mode
and backend columns.  `astrid models show <id>` shows per-mode supports,
requires, and per-backend templates/endpoints.

## Drop-with-warning behavior

Features that the chosen (model, mode, backend) cell does not support are
**dropped with a warning** in the manifest — never a hard failure (SD-004).

Examples:
- `--negative-prompt` on `flux-dev --mode t2i --execution cloud` → dropped, warning
- `--image-ref` on `flux-dev --mode t2i` → dropped, warning
- `--strength` on `qwen-image-edit --mode edit` → dropped, warning

Missing required features (e.g., `--image-ref` for `--mode i2i`) are a
**hard failure** before any HTTP call or vibecomfy import.

## Escape hatch

**For LoRAs, IP-adapter, controlnet, custom samplers, graph composition,
or any path the registry does not cover, use the `vibecomfy` skill
instead.**  The `generate-image` skill is scoped to standard generation
through the registry.  Everything else goes through the vibecomfy escape
hatch, which gives direct access to ready-templates, custom workflows,
and the full ComfyUI node graph.

See: `vibecomfy` skill, `astrid/packs/external/vibecomfy/STAGE.md`
