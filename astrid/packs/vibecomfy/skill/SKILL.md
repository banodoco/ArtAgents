---
name: vibecomfy
description: >
  VibeComfy pack — run and validate ComfyUI / VibeComfy workflow JSON
  to generate images, video, and audio.  The escape hatch for LoRAs,
  IP-adapter, ControlNet, custom samplers, and graph composition beyond
  the standard generation contracts.
---

# VibeComfy

The vibecomfy pack is the **escape hatch** for ComfyUI generation features
that fall outside the standard `generation` pack contracts. Use it directly
for LoRAs, IP-adapter, ControlNet, custom samplers, or any node-graph surgery
not covered by the opinionated `generation.generate_image` path.

## Executors

| Executor | What it does |
|---|---|
| `vibecomfy.run` | Execute a ComfyUI / VibeComfy workflow JSON — maps to `python -m vibecomfy.cli run {workflow}`. |
| `vibecomfy.validate` | Validate a ComfyUI / VibeComfy workflow JSON without executing it — maps to `python -m vibecomfy.cli validate {workflow}`. |

## When to use

- Use `vibecomfy.run` when you need LoRAs, IP-adapter, ControlNet, custom
  samplers (DPM++ 3M, UniPC, LCM), exotic conditioning, regional prompting,
  attention injection, CFG scheduling, or any path the standard registry
  does not cover.
- Use `vibecomfy.validate` to check a workflow JSON before execution.

## When NOT to use

- Do not use for standard image generation — use `generation.generate_image`
  (the recommended primary entry point).
- Do not use to understand existing media (use `understanding`) or to
  cut/render timelines (use `video_editing`).

## Quick-start

```python
import astrid.sdk as sdk

# Run a workflow
result = sdk.invoke("vibecomfy.run", inputs={"workflow": "./my_workflow.json"}, out="./out")

# Validate a workflow
result = sdk.invoke("vibecomfy.validate", inputs={"workflow": "./my_workflow.json"})
```
