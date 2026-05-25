---
name: vibecomfy
description: >-
  Escape hatch. For standard image generation use the generate-image skill and
  astrid start generation.generate_image. Reach for vibecomfy directly when you
  need LoRAs, IP-adapter, controlnet, custom samplers, graph composition, or
  any path the registry does not cover.
---

# VibeComfy — the escape hatch

For standard image generation use the `generate-image` skill and
`astrid start generation.generate_image`.  Reach for this skill when you need
LoRAs, IP-adapter, controlnet, custom samplers, graph composition, or any
path the registry doesn't cover.

`vibecomfy.run` is the **escape hatch** for generation features that fall
outside the basic happy-path contracts of `generation.generate_image` and
`generation.generate_video` (and the planned audio executor).  Use it directly for:

- **LoRAs** — attach custom weights to any node in the ComfyUI graph.
- **IP-adapter** — image-prompt / style-reference conditioning.
- **ControlNet** — depth, canny, pose, scribble, and other structural conditioning.
- **Custom samplers** — DPM++ 3M, UniPC, LCM, etc.
- **Exotic conditioning** — regional prompting, attention injection, CFG
  scheduling, and any other node-graph surgery not covered by the opinionated
  `generation.generate_image` contract.

The builtin image executor supports six canonical modes (`t2i`, `i2i`, `edit`,
`inpaint`, `outpaint`, `upscale`) across a growing Tier-1 model list.  Everything
beyond those modes — LoRAs, IP-adapter, ControlNet, custom samplers — belongs here.

## How to use

- `vibecomfy.run` maps to `python -m vibecomfy.cli run {workflow}`
- `vibecomfy.validate` maps to `python -m vibecomfy.cli validate {workflow}`

Install the executor package through the explicit Astrid executor install flow before
running these actions. Both executors share the `vibecomfy` package environment via
the folder-level `PACKAGE_ID`.

## Cross-links

- `astrid/docs/generation/` — modality contracts, manifest schema, feature list
- `astrid/packs/builtin/generate_image/skill/SKILL.md` — the `generate-image` skill (primary entry point)
- `astrid/packs/builtin/generate_image/STAGE.md` — the basic image executor
- `astrid/packs/builtin/generate_video/STAGE.md` — the basic video executor (Sprint 04)
- `astrid/docs/generation/30-image-contract.md` — image modality contract (all six canonical modes)
- `astrid/docs/generation/31-video-contract.md` — video modality contract (implemented Sprint 04)
- `astrid/docs/generation/32-audio-contract.md` — audio modality contract (spec-only)