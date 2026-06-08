# Model Registry Schema (schema_version: 2)

The model registry is a YAML (or JSON) file that declares every generation
model known to the system.  It is the single source of truth for model
capabilities, backend mappings, and feature support.

## Architecture: model → mode → backend

Schema v2 uses a nested taxonomy:

```
model_id (one real checkpoint — SD-001)
  └── modes (t2i, i2i, edit, inpaint, outpaint, upscale)
        ├── supports: [prompt, seed, ...]
        ├── requires: [prompt, image_ref]
        └── backends
              ├── local:  {template, template_hash?, param_map}
              └── cloud:  {endpoint, param_map}
```

Each `model_id` refers to **one real-world model checkpoint** (a vendor
offering, a specific fine-tune).  Local and cloud backends for the same
`model_id` MUST produce semantically comparable output — they run the same
actual model (SD-001).

## Top-level shape

```yaml
schema_version: 2
models:
  - id: z-image
    modality: image
    modes:
      t2i:
        supports: [prompt, negative_prompt, seed, count, size, guidance_scale, steps]
        requires: [prompt]
        backends:
          local:
            template: image/z_image
            template_hash: "sha256:a8bb7..."
            param_map:
              prompt: prompt
              negative_prompt: negative_prompt
              seed: seed
              count: count
              size: size
              guidance_scale: guidance
              steps: steps
          cloud:
            endpoint: fal-ai/z-image/turbo
            param_map:
              prompt: prompt
              seed: seed
              count: num_images
              size: image_size
              guidance_scale: guidance_scale
              steps: num_inference_steps
      i2i:
        supports: [prompt, seed, image_ref, size, strength, guidance_scale, steps]
        requires: [prompt, image_ref]
        backends:
          local:
            template: image/z_image_img2img
            template_hash: "sha256:32d0..."
            param_map:
              prompt: prompt
              seed: seed
              image_ref: image_ref
              size: size
              strength: denoise
              guidance_scale: guidance
              steps: steps
          cloud:
            endpoint: fal-ai/z-image/turbo/image-to-image
            param_map:
              prompt: prompt
              seed: seed
              image_ref: image_url
              size: image_size
              strength: strength
              guidance_scale: guidance_scale
              steps: num_inference_steps
```

## Entry fields

### ModelEntry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` | yes | Unique model identifier (e.g. `"z-image"`). |
| `modality` | `string` | yes | `"image"`, `"video"`, or `"audio"`. |
| `modes` | `dict<string, ModeSpec>` | yes | Map from canonical mode name to its specification. |
| `closed` | `boolean` | no | If `true`, the model is closed-weight and hidden from default `astrid models list` (shown only with `--include-closed`). |

### ModeSpec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `supports` | `list<string>` | yes | Features this mode honours on ALL declared backends. Every value must be a canonical `Feature`. |
| `requires` | `list<string>` | yes | Features the caller MUST provide. Must be a subset of `supports`. Hard-fail at request-validation if missing. |
| `backends` | `dict<string, BackendSpec>` | yes | Map from backend name (`"local"`, `"cloud"`) to its specification. At least one backend required. |

### BackendSpec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `template` | `string` | local: yes | Vibecomfy ready-template identifier (e.g. `"image/z_image"`). |
| `template_hash` | `string` | no | SHA-256 of the template source file (for integrity verification). |
| `endpoint` | `string` | cloud: yes | Falcon endpoint slug (e.g. `"fal-ai/flux/dev"`). |
| `param_map` | `dict<string,string>` | yes | Maps canonical `Feature` names to backend-specific parameter names. All mapped features must be in the mode's `supports`. |

## Canonical image modes

Six canonical modes for the image modality (SD-002):

| Mode | Sprint 2 Status | Description |
|------|-----------------|-------------|
| `t2i` | ✅ Wired | Text-to-image (prompt → image). |
| `i2i` | ✅ Wired | Image-to-image (prompt + ref image + strength → image). |
| `edit` | ✅ Wired | Instruction-guided edit (prompt = instruction, ref image required). |
| `inpaint` | Spec-only | Masked region replacement (prompt + image + mask → image). |
| `outpaint` | Spec-only | Boundary extension (prompt + image + direction/extent → image). |
| `upscale` | Spec-only | Super-resolution (image → larger image). |

These names are **canonical** — no variants like `img2img`, `editing`, or
`super-res` are accepted.

## `closed: true` flag (SD-008)

Models marked `closed: true` are hidden from the default `astrid models list`
output.  They appear only with `--include-closed`.  Sprint 2 ships the
flag and CLI behavior; no closed-weight entries are registered yet (Sprint 3
may add Recraft, Ideogram, etc.).

## Validation rules

1. **schema_version** must be `2`.  Reject `1` with a clear error pointing
   at the sprint-2 migration (rewrite entries in v2 shape).
2. **No duplicate model IDs**.
3. **At least one mode per model**.
4. **Mode names** must be canonical (t2i, i2i, edit, inpaint, outpaint,
   upscale).  Unknown modes are rejected.
5. **`requires` ⊆ `supports`** for every mode.
6. **At least one backend per mode** (the `backends` dict must be non-empty).
7. **Valid backend keys**: only `local` and `cloud` are recognised.
8. **Local backend requires `template`** (non-empty string).
9. **Cloud backend requires `endpoint`** (non-empty string).
10. **`param_map` keys** must all be valid canonical `Feature` literals
    AND must be a subset of the mode's `supports`.
11. **Per-backend param_map must be non-empty** (each backend must map at
    least one feature).

## Loading

```python
from astrid.core.model_catalog.schema import validate_registry

with open("models.yaml") as fh:
    import yaml
    raw = yaml.safe_load(fh)

entries = validate_registry(raw)
# entries: list[ModelEntry]
```

The `validate_registry()` function raises `ValueError` with a specific
message for any validation failure.

## Migration from v1

Schema v1 is **not supported**.  There is no compat shim, no v1 reader
(SD-006).  The three v1 entries have been deleted outright.  To migrate:

1. Delete the old `models.yaml`.
2. Write new entries in the v2 shape: each model → modes → backends.
3. Each mode declares its own `supports`/`requires`/`backends` map.
4. Features that differ per-backend are handled by separate model IDs
   (SD-001) — not by omitting entries from a single backend's `param_map`
   while keeping the feature in `supports`.
