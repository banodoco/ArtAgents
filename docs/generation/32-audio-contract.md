# Audio Modality Contract (schema_version: 2)

**Status**: Spec-only (Sprint 02) — implementation deferred to Sprint 05.  
**Planned executor**: `generation.generate_audio`  
**Escape hatch**: `external.vibecomfy` (custom audio pipelines, spectrogram conditioning)

## Canonical audio modes (preview)

The audio modality will have three canonical modes:

| Mode | Description | Sprint |
|------|-------------|--------|
| `tts` | Text-to-speech (prompt → audio). | Sprint 5 |
| `music` | Music generation (prompt → audio; may include genre/style controls). | Sprint 5 |
| `sfx` | Sound effects generation (prompt → audio; short duration, specific sound). | Sprint 5 |

## Inputs (planned)

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `--mode` | `string` | **yes** | Generation mode: `tts`, `music`, or `sfx`. REQUIRED (SD-005). |
| `--model` | `string` | **yes** | Model ID from the registry. |
| `--execution` | `string` | **yes** | `"local"` or `"cloud"`. |
| `--prompt` | `string` | no* | Text prompt for audio generation. |
| `--prompts-file` | `file` | no* | JSONL file of per-line generation requests. |
| `--audio-ref` | `string` | no | Singular reference audio file (style transfer / inpainting). |
| `--count` | `integer` | no | Number of audio clips (default `1`). |
| `--seed` | `integer` | no | Deterministic seed. |
| `--negative-prompt` | `string` | no | Negative prompt. |
| `--duration` | `float` | no | Audio duration in seconds. |
| `--sample-rate` | `integer` | no | Sample rate in Hz (default backend-dependent). |

\* `--prompt` and `--prompts-file` are mutually exclusive.

## Outputs (planned)

| Port | Type | Description |
|------|------|-------------|
| `generated_audio` | `dir` | Directory at `{out}/audio/` containing generated audio files. |
| `audio_manifest` | `file` | JSON manifest at `{out}/manifest.json` (common shape + audio extensions). |

## Request validation

Same hard-fail semantics as image modality: missing `requires` features fail
before the generation loop; unsupported features are dropped-with-warning
(SD-004).  `--mode` is required.

## Backends (planned)

- **local**: vibecomfy ready-templates for audio models (Stable Audio, etc.).
- **cloud**: fal.ai audio endpoints.

## Audio-modality manifest extensions (planned)

The `request` object will include audio-specific fields: `duration`,
`sample_rate`.  Output entries will carry `content_hash`, `bytes`, `duration`,
`sample_rate`, `format`.  Manifest `schema_version` is 2 (per SD-006).

## Escape hatch

For spectrogram conditioning, multi-track generation, inpainting, or exotic
audio samplers, use `external.vibecomfy` directly.  The `generation.generate_audio`
executor covers the basic happy path only.

> **Note for Sprint 05 implementers**: When the `generation.generate_audio`
> executor and its `STAGE.md` are created, add an explicit escape-hatch
> paragraph cross-linking to `astrid/packs/external/vibecomfy/STAGE.md` and
> `docs/generation/` — matching the pattern in
> `astrid/packs/builtin/generate_image/STAGE.md`.
