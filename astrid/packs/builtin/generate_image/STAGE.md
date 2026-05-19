# Generate Image

**Executor**: `builtin.generate_image`  
**Modality**: image (`schema_version: 2`)  
**Status**: implemented (Sprint 02 — v2 model → mode → backend taxonomy)

Generates images from text prompts (or prompt files) using local (vibecomfy)
or cloud (fal) backends.  A single executor dispatches through `BackendAdapter`
(SD-004) — callers pick a model, a mode, and a backend; the executor does
the rest.  **`--mode` is required** (SD-005).

## Starting models (Tier-1)

| Model               | Modes wired       | Local template(s)              | Cloud endpoint(s)                     |
|---------------------|-------------------|--------------------------------|---------------------------------------|
| `z-image`           | t2i, i2i          | `image/z_image`, `image/z_image_img2img` | `fal-ai/z-image/turbo`, `fal-ai/z-image/turbo/image-to-image` |
| `qwen-image-2512`   | t2i               | `image/qwen_image_2512`       | `fal-ai/qwen-image`                  |
| `qwen-image-edit`   | edit              | `edit/qwen_image_edit`        | `fal-ai/qwen-image-edit`             |
| `flux-dev`          | t2i, i2i (cloud-only) | — (cloud-only per SD-001) | `fal-ai/flux/dev`, `fal-ai/flux/dev/image-to-image` |
| `flux-schnell`      | t2i (cloud-only)  | — (cloud-only per SD-001)     | `fal-ai/flux/schnell`                |

All entries are registered in `astrid/core/model_catalog/models.yaml` under
`schema_version: 2`.  Each entry declares per-mode `supports: [...]`,
`requires: [...]`, and per-backend `param_map` entries (SD-003).

## Execution modes

### Local (`--execution local`)

Dispatches through `VibeComfyBackend` adapter (SD-004).  Uses
[vibecomfy](https://github.com/nosresearch/vibecomfy) to drive a local
ComfyUI backend.  The `vibecomfy` package is **lazy-imported** inside the
adapter — only loaded when `execution=local`.  Cloud-only invocations never
touch the package (SD-009).

Requires a running ComfyUI instance reachable from the executor process
(configured via the vibecomfy package defaults or environment).

### Cloud (`--execution cloud`)

Dispatches through `FalBackend` adapter (SD-004).  Pure HTTP against
[fal.ai](https://fal.ai) using `astrid/core/util/http.py` `HttpClient`.
No fal SDK required (SD-009).

Requires `FAL_KEY` to be resolvable via the candidate-env-file walk
(see `astrid/core/util/secrets.py`).

## Escape hatch

**For LoRAs, IP-adapter, controlnet, custom samplers, and exotic conditioning,
use `external.vibecomfy` directly.**  The `builtin.generate_image` executor is
scoped to *basic generation only* (prompt, negative_prompt, seed, count, size,
single image_ref, strength, guidance_scale, steps).  Everything else belongs in
the escape hatch.

See:
- `astrid/packs/external/vibecomfy/STAGE.md` — VibeComfy workflow runner
- `astrid/docs/generation/` — modality contracts, manifest schema, feature list

## CLI quick-start

```bash
# Cloud text-to-image
python -m astrid.packs.builtin.generate_image.run \
  --model flux-dev --mode t2i --execution cloud \
  --prompt "a serene mountain lake at dawn" --out ./out

# Local text-to-image (requires vibecomfy + ComfyUI)
python -m astrid.packs.builtin.generate_image.run \
  --model z-image --mode t2i --execution local \
  --prompt "a serene mountain lake at dawn" --out ./out

# Image-to-image (cloud)
python -m astrid.packs.builtin.generate_image.run \
  --model flux-dev --mode i2i --execution cloud \
  --prompt "turn this into a watercolor painting" \
  --image-ref ./input.png --out ./out

# Image-to-image (local)
python -m astrid.packs.builtin.generate_image.run \
  --model z-image --mode i2i --execution local \
  --prompt "turn this into a watercolor painting" \
  --image-ref ./input.png --out ./out

# Instruction-guided edit
python -m astrid.packs.builtin.generate_image.run \
  --model qwen-image-edit --mode edit --execution cloud \
  --prompt "replace the background with a forest" \
  --image-ref ./input.png --out ./out

# Multiple images with seed
python -m astrid.packs.builtin.generate_image.run \
  --model flux-schnell --mode t2i --execution cloud \
  --prompt "cyberpunk city" --count 3 --seed 42 --out ./out
```

## Prompts file (JSONL)

For batch generation, use `--prompts-file` with a JSONL file (one JSON object
per line).  Each line may override `model`, `seed`, `count`, `size`,
`negative_prompt`, `image_ref`, `strength`, `guidance_scale`, and `steps`.
**Per-entry `model` overrides must include an explicit `mode` field matching
CLI `--mode`** (SD-005, FLAG-004):

```jsonl
{"prompt": "a cat in a spacesuit", "seed": 42, "count": 2}
{"prompt": "a dog on a skateboard", "negative_prompt": "blurry", "size": "1024x1024"}
{"prompt": "replace the background with a forest", "model": "qwen-image-edit", "mode": "edit", "image_ref": "/path/to/source.png"}
```

`--prompt` and `--prompts-file` are mutually exclusive — providing both is
rejected at argparse.

## Validation rules

1. **Missing `--mode`** → rejected at argparse (required argument, SD-005).
2. **Missing `requires`** (e.g. `flux-dev --mode i2i` without `--image-ref`)
   → hard-fail BEFORE any HTTP call or vibecomfy import.
3. **`--execution` must be `local` or `cloud`** — rejected at argparse.
4. **Unsupported features** (e.g. `--negative-prompt` on `flux-dev --mode t2i` cloud) →
   dropped with a `Warning` in the manifest; never hard-fail (SD-004).
5. **Per-entry mode mismatch**: If a prompts-file entry overrides `model`
   without a matching `mode` field, the entry is rejected (FLAG-004).

## Output

- `{out}/images/` — generated image files (e.g. `0-flux-dev.png`)
- `{out}/manifest.json` — canonical manifest conforming to `astrid/docs/generation/20-manifest-schema.md` (v2)

## Design docs

- `astrid/docs/generation/00-features.md` — canonical feature list
- `astrid/docs/generation/10-registry-schema.md` — model registry schema (v2)
- `astrid/docs/generation/20-manifest-schema.md` — manifest JSON shape (v2)
- `astrid/docs/generation/30-image-contract.md` — image modality contract with six canonical modes
