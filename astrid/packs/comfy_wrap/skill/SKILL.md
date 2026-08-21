---
name: comfy_wrap
description: >
  Comfy Workflow Wrapper — generate images by injecting a text prompt into
  a ComfyUI workflow JSON and running it via vibecomfy.  Single-executor
  pack for parameterized ComfyUI workflow execution.
---

# Comfy Workflow Wrapper

The comfy_wrap pack provides a single executor that wraps a ComfyUI workflow
JSON: inject a text prompt, execute via vibecomfy, and collect the output image.

## Executors

| Executor | What it does |
|---|---|
| `comfy_wrap.run` | Load a ComfyUI workflow JSON from `/tmp/example_comfy.json`, inject a user prompt into the positive CLIPTextEncode node, execute through vibecomfy, and copy the result to the `out` directory. |

## When to use

- Use `comfy_wrap.run` when you have a pre-built ComfyUI workflow JSON and want
  to parameterize it with a text prompt.
- Use `comfy_wrap.run` when you need a quick txt2img path through ComfyUI without
  writing a full pipeline.

## When NOT to use

- Do not use for arbitrary model selection or multi-modal generation — use
  `generation.generate_image` for the standard happy path.
- Do not use for LoRAs, IP-adapter, ControlNet, or custom samplers — use
  `vibecomfy.run` directly (the escape hatch).

## Quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke("comfy_wrap.run", inputs={"prompt": "a serene mountain lake at dawn"}, out="./output.png")
```

## Requirements

- `vibecomfy` package installed
- ComfyUI workflow JSON at `/tmp/example_comfy.json`
- GPU recommended for ComfyUI model inference
