# Generation Features (schema_version: 2)

The generation ecosystem uses a closed set of **features** to declare what a
model's **mode** supports.  Features are declared **per-mode** (SD-003) — the
same model can have different feature sets across its modes (e.g., edit mode
does not take `negative_prompt` or `strength`).

## Canonical feature list (image modality)

| Feature           | Meaning                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `prompt`          | Text prompt for generation (virtually always supported).                |
| `negative_prompt` | Additional prompt describing what the model should *avoid*.             |
| `seed`            | Deterministic seed for reproducibility (`seed + i` for count > 1).     |
| `count`           | Generation of multiple images in a single invocation (batch).           |
| `size`            | User-specified output dimensions (e.g. `"1024x1024"`).                  |
| `image_ref`       | Reference image input (required for i2i and edit modes; singular per SD-005). |
| `strength`        | Denoising strength for image-to-image mode (0.0–1.0).  NOT meaningful for edit mode. |
| `guidance_scale`  | Classifier-free guidance scale (varies per model; Schnell always 1.0).  |
| `steps`           | Sampling steps (model-dependent; Schnell = 4, Dev = 28, etc.).          |

## Per-mode applicability

Not all features apply to every mode:

| Mode     | `negative_prompt` | `strength` | `image_ref` | Notes |
|----------|-------------------|------------|-------------|-------|
| `t2i`    | ✅ (optional)     | ❌          | ❌           | Text-to-image; no reference image. |
| `i2i`    | ✅ (optional)     | ✅ (optional) | ✅ (required) | Image-to-image; `strength` controls denoising level. |
| `edit`   | ❌                | ❌          | ✅ (required) | Instruction-guided edit; `prompt` is the instruction. |
| `inpaint`| ✅ (optional)     | ✅ (optional) | ✅ (required) | Masked region replacement (future sprint). |
| `outpaint`| ✅ (optional)    | ✅ (optional) | ✅ (required) | Boundary extension (future sprint). |
| `upscale`| —                  | —            | ✅ (required) | Super-resolution; prompt may or may not apply (future sprint). |

Edit mode specifically excludes `negative_prompt` and `strength` from its
`supports` list because the instruction *is* the prompt — there is no
separate negative-instruction channel, and edit strength is governed by the
model's internal edit mechanism, not a user-facing denoising slider.

## Per-mode supports semantics (SD-003)

Every mode entry declares `supports: [<Feature>]`.  A feature listed here is
**guaranteed honoured by ALL backends** declared for that mode.  If a feature
works on local but fails silently on cloud (or vice versa), the entry is
invalid — split it into two distinct model IDs (SD-001).

When a caller requests a feature that is **not** in the mode's `supports`,
the executor **warns loudly in the manifest** and drops the feature
gracefully.  It never hard-fails on unsupported features (SD-004).

When a caller omits a feature that is in the mode's `requires`, the executor
**hard-fails before the generation loop** with a clear error message.

## Local-only / cloud-only divergence

If a feature is available on only one backend:

1. Create **two model IDs** (e.g., one with the feature in its mode's
   `supports` and both backends, another cloud-only or local-only).
2. Each ID declares only the features it can honour on its declared backends.
3. Document the divergence in the model's registry entry comment.

This keeps the registry simple and prevents orchestrators from silently
getting different behaviour depending on which backend they happen to hit.

## Canonical feature list (video modality)

| Feature           | Meaning                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `prompt`          | Text prompt for generation.                                             |
| `negative_prompt` | Additional prompt describing what the model should *avoid*.             |
| `seed`            | Deterministic seed for reproducibility (`seed + i` for count > 1).     |
| `count`           | Generation of multiple videos in a single invocation (batch).           |
| `resolution`      | Output resolution (e.g. `"1280x720"`).                                  |
| `image_ref`       | Reference image input (required for i2v and flf modes).                 |
| `image_end_ref`   | End-frame reference image (required for flf mode).                      |
| `frames`          | Number of frames to generate.                                           |
| `fps`             | Frames per second.                                                      |
| `duration`        | Duration in seconds (alternative to `frames`; used with `fps`).         |
| `guidance_scale`  | Classifier-free guidance scale.                                         |
| `steps`           | Sampling steps.                                                         |
| `shift`           | Flow / timestep shift.                                                  |
| `loras`           | LoRAs to attach (backend-dependent).                                    |
| `enable_safety_checker` | Toggle safety checker (wan/cloud).                                |
| `enable_prompt_expansion` | Toggle prompt expansion (wan/cloud).                            |
| `acceleration`    | Inference acceleration preset (wan/cloud).                              |

## Canonical feature list (audio modality)

| Feature           | Meaning                                                                 |
|-------------------|-------------------------------------------------------------------------|
| `prompt`          | Text prompt for generation.                                             |
| `negative_prompt` | Additional prompt describing what the model should *avoid*.             |
| `seed`            | Deterministic seed for reproducibility (`seed + i` for count > 1).     |
| `count`           | Generation of multiple audio clips in a single invocation (batch).      |
| `duration`        | Audio duration in seconds.                                              |
| `guidance_scale`  | Classifier-free guidance scale.                                         |
| `steps`           | Sampling steps.                                                         |
| `lyrics_prompt`   | Lyrics prompt for vocal music models (e.g. MiniMax).                    |
| `instrumental`    | Request instrumental output (boolean).                                  |
| `output_format`   | Output audio format, e.g. `mp3`, `wav`, `flac` (backend-dependent).     |

## Per-mode applicability (audio)

The `music` mode (wired) requires `prompt` and supports the full audio feature
set above.  `tts` and `sfx` are canonical audio modes reserved for future
sprints.

## Future modalities

Additional modalities and features will be enumerated in future sprints as
new backends and model families are integrated.
