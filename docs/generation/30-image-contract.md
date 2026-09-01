# Image Modality Contract (schema_version: 2)

**Status**: Implemented (Sprint 02 — v2 model → mode → backend taxonomy)
**Executor**: `generation.generate_image`
**Escape hatch**: `vibecomfy.run` (LoRAs, IP-adapter, controlnet, custom samplers,
graph composition)

## Canonical image modes

The image modality has six canonical modes (SD-002).  Three are wired in
Sprint 2; three are enumerated for future sprints.

### Wired modes (Sprint 2)

| Mode | Description | Key inputs | Key outputs |
|------|-------------|------------|-------------|
| `t2i` | Text-to-image | `prompt` (required). `negative_prompt`, `seed`, `count`, `size`, `guidance_scale`, `steps` (optional). | `images/` dir, `manifest.json`. |
| `i2i` | Image-to-image | `prompt`, `image_ref` (required). `strength`, `seed`, `size`, `guidance_scale`, `steps` (optional). | `images/` dir, `manifest.json`. |
| `edit` | Instruction-guided edit | `prompt` (the instruction), `image_ref` (required). `seed`, `size`, `guidance_scale`, `steps` (optional).  **No** `negative_prompt`, **no** `strength`. | `images/` dir, `manifest.json`. |

### Enumerated modes (future sprints)

| Mode | Description | Planned for |
|------|-------------|-------------|
| `inpaint` | Masked region replacement (prompt + image + mask → image). | Sprint 3+ |
| `outpaint` | Boundary extension (prompt + image + direction/extent → image). | Sprint 3+ |
| `upscale` | Super-resolution (image → larger image; prompt may or may not apply). | Sprint 3+ |

## Inputs (all wired modes)

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `--mode` | `string` | **yes** | Generation mode: `t2i`, `i2i`, or `edit`. REQUIRED (SD-005). |
| `--model` | `string` | **yes** | Model ID from the registry (e.g. `z-image`, `flux-dev`). |
| `--execution` | `string` | **yes** | `"local"` (vibecomfy) or `"cloud"` (fal). |
| `--prompt` | `string` | no* | Text prompt (or edit instruction for `edit` mode). |
| `--prompts-file` | `file` | no* | Path to a JSONL file of generation requests. |
| `--image-ref` | `string` | varies | Singular (SD-005) path or URL to a reference image. Required for `i2i` and `edit` modes. |
| `--count` | `integer` | no | Number of images to generate (default `1`). |
| `--seed` | `integer` | no | Deterministic seed. Randomly generated and recorded if omitted. |
| `--negative-prompt` | `string` | no | Text describing what to avoid. Only meaningful for `t2i` and `i2i` modes. |
| `--size` | `string` | no | Output dimensions (e.g. `"1024x1024"` or `"square_hd"`). |
| `--strength` | `float` | no | Denoising strength for `i2i` mode (0.0–1.0). NOT meaningful for `t2i` or `edit`. |
| `--guidance-scale` | `float` | no | Classifier-free guidance scale. Varies per model. |
| `--steps` | `int` | no | Number of sampling steps. Model-dependent. |
| `--out` | `path` | no | Output directory (default: `./generated_output`). |

\* `--prompt` and `--prompts-file` are mutually exclusive — exactly one must
be provided.  Supplying both is rejected at argparse.

### prompts_file format (JSONL)

One JSON object per line.  Each line may override `model`, `mode`, `seed`,
`count`, `size`, `negative_prompt`, `image_ref`, `strength`,
`guidance_scale`, and `steps`.  Example:

```jsonl
{"prompt": "a cat in a spacesuit", "seed": 42, "count": 2}
{"prompt": "a dog on a skateboard", "negative_prompt": "blurry", "size": "1024x1024"}
{"prompt": "replace the background with a forest", "model": "qwen-image-edit", "mode": "edit", "image_ref": "/path/to/source.png"}
```

Per-entry `model` overrides **must** include an explicit `mode` field
matching CLI `--mode` or they are rejected (FLAG-004).

### image_ref path resolution

- Absolute paths are honoured as-is.
- Relative paths are resolved against the executor's current working directory
  (the CWD at the time the executor is invoked).

## Edit mode specifics

Edit mode (`--mode edit`) is **instruction-guided**: the `--prompt` is the
edit instruction (e.g. "replace the background with a forest").  It does NOT
accept `--negative-prompt` or `--strength` — these are dropped with a warning
if supplied.

Edit mode requires `--image-ref` (the source image to edit).

Edit mode uses dedicated instruction-tuned checkpoints (e.g., Qwen Image
Edit).  These are separate model IDs from text-to-image checkpoints
(SD-001).

## Outputs

| Port | Type | Description |
|------|------|-------------|
| `generated_images` | `dir` | Directory at `{out}/images/` containing generated image files. |
| `image_manifest` | `file` | JSON manifest at `{out}/manifest.json` conforming to `20-manifest-schema.md` (v2). |

## Request validation (hard-fail BEFORE the generation loop)

The typed `astrid.generate.image()` facade uses `execution` as its sole
backend-selection parameter.  The retired `backend` spelling is rejected before
kernel admission; callers must provide `execution` explicitly when the model
and mode expose more than one backend.  Supplying an unavailable pair such as
`model="flux-schnell", execution="local"` fails with the model's valid backend
list and creates no run.

1. **Missing `--mode`**: Rejected at argparse (required argument).
2. **Unknown (model, mode) pair**: Exits non-zero with a clear error.
3. **Backend not available**: If the chosen (model, mode) has no
   `--execution` backend, exits with available backends listed.
4. **Missing `requires`**: If the mode declares `requires: [image_ref]`
   and the caller does not supply `--image-ref`, the executor exits non-zero
   with a clear message before any HTTP call or vibecomfy import.
5. **Invalid `--execution`**: Must be `"local"` or `"cloud"`.  Any other
   value is rejected at argparse.
6. **Mutual exclusion**: `--prompt` and `--prompts-file` cannot both be
   supplied.
7. **Per-entry mode mismatch**: If a prompts-file entry overrides `model`
   without a matching `mode` field, the entry is rejected (FLAG-004).

## Feature dropping (warn-loudly-in-manifest, never hard-fail)

Any caller-supplied feature absent from the mode's `supports` list is
dropped with a `Warning` entry in the manifest (SD-004).  Examples:

- `flux-dev` in `t2i` mode does not support `negative_prompt` → the feature
  is dropped and recorded in `warnings` + `dropped_features`.
- `z-image` in `t2i` mode called with `--image-ref` → the feature is dropped
  (t2i has no `image_ref` in supports) and recorded.
- `qwen-image-edit` in `edit` mode called with `--negative-prompt` or
  `--strength` → both features are dropped (edit mode explicitly excludes
  them per SD-003).

## Sequential execution

When `count > 1`, images are generated sequentially (N=1 loop).  If `seed`
is provided, image `i` uses `seed + i`.  Concurrency is out of scope for
Sprint 2.

## Local branch (execution=local)

- Dispatches through `VibeComfyBackend` adapter (SD-004).
- Lazy-imports `vibecomfy` inside the adapter only.  A `cloud` execution must
  never import `vibecomfy` (SD-009).
- Uses the mode's `backends.local.template` and `backends.local.param_map`
  to drive the vibecomfy ready-template engine.
- Supports both `bind_input`-curated templates and `wf.inputs` name-matching
  fallback (for templates like `z_image_img2img` that lack `bind_input`).

## Cloud branch (execution=cloud)

- Dispatches through `FalBackend` adapter (SD-004).
- Pure HTTP via `astrid.core.util.http.HttpClient` (no fal SDK — SD-009).
- Uses the mode's `backends.cloud.endpoint` and `backends.cloud.param_map`.
- Local-file `image_ref` is uploaded via `fal_upload()` data URI.
- Polls via `fal_submit_and_poll()` with exponential backoff.
- Downloads result bytes, computes SHA-256 `content_hash`, records
  `{path, content_hash, source_url, bytes, request_id}`.
- `source_url` is debug-only (fal URLs are temporary).

## Manifest shape

See `20-manifest-schema.md` (v2) for the canonical JSON shape.  Key v2
additions: `mode_used`, `model_actual`, `applied_features`, `cost_usd`,
`duration_ms`, `request_id`, `source_urls`.
