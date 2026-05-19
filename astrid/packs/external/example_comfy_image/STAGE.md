---
name: example_comfy_image
description: >-
  Wrap a fixed SDXL ComfyUI workflow as a prompt-parameterized Astrid image
  executor. Routes through the same `vibecomfy.cli` surface that
  `external.vibecomfy.run` uses — no new HTTP client.
---

# external.example_comfy_image

Render an image from a text prompt by injecting the prompt into a staged
ComfyUI workflow JSON and submitting it through the VibeComfy CLI.

This is a thin, opinionated wrapper around one specific workflow shape (SDXL
text-to-image, originally captured at `/tmp/example_comfy.json`). For
LoRAs / IP-adapter / controlnet / sampler surgery, reach for
`external.vibecomfy.run` directly with your own workflow JSON.

## Inputs

- `--prompt` (required, string) — positive prompt; injected into node `"6"`,
  key `inputs.text`.
- `--out` (required, path) — where the rendered image is written.
- `--workflow` (optional, path) — override the staged workflow JSON. Defaults
  to `workflow.json` inside this pack.

## How it works

1. Loads the workflow JSON from disk (pack-staged `workflow.json` by default,
   or `--workflow <path>`).
2. Mutates node `"6"` (`CLIPTextEncode`)'s `inputs.text` to the supplied prompt.
3. Writes the mutated graph into a temp dir as `workflow.staged.json`.
4. Shells out to `python -m vibecomfy.cli run <workflow>` — the same comfy
   submission path used by `external.vibecomfy.run`.
5. Copies the resulting image to `--out`.

The workflow JSON is **never** embedded in Python — it lives as
`astrid/packs/external/example_comfy_image/workflow.json` and is read at run
time, so the graph stays editable in JSON.

## Inspect

```bash
python3 -m astrid executors inspect external.example_comfy_image --json
```

## Run

```bash
python3 -m astrid executors run external.example_comfy_image \
  --input prompt="a serene mountain lake at dawn" \
  --out runs/example_comfy_image/out.png
```

## When to use this vs external.vibecomfy.run

- **This executor** — you have a fixed graph and just want
  "give me an image of X" to route through it.
- **`external.vibecomfy.run`** — you want to author / swap arbitrary workflow
  JSON (LoRAs, IP-adapter, controlnet, custom samplers).
