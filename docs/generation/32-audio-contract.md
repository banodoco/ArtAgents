# Audio Modality Contract (schema_version: 2)

**Status**: `music` mode implemented (cloud-first).  
**Executor**: `generation.generate_audio`  
**Escape hatch**: `vibecomfy.run` (custom audio pipelines, spectrogram conditioning)

## Canonical audio modes

The audio modality has three canonical modes:

| Mode | Status | Description |
|------|--------|-------------|
| `music` | ✅ Wired | Music generation (prompt → audio; supports lyrics/instrumental controls). |
| `tts` | Reserved | Text-to-speech (prompt → audio). |
| `sfx` | Reserved | Sound effects generation (prompt → audio; short duration, specific sound). |

## Inputs

| Port | Type | Required | Description |
|------|------|----------|-------------|
| `--mode` | `string` | **yes** | Generation mode: `music`. `tts`/`sfx` are not wired yet. REQUIRED (SD-005). |
| `--model` | `string` | **yes** | Model ID from the registry. |
| `--execution` | `string` | **yes** | `"local"` or `"cloud"`. Cloud is wired; local is a follow-up. |
| `--prompt` | `string` | no* | Text prompt for audio generation. |
| `--prompts-file` | `file` | no* | JSONL file of per-line generation requests. |
| `--count` | `integer` | no | Number of audio clips (default `1`). |
| `--seed` | `integer` | no | Deterministic seed. |
| `--negative-prompt` | `string` | no | Negative prompt. |
| `--duration` | `float` | no | Audio duration in seconds. |
| `--guidance-scale` | `float` | no | Classifier-free guidance scale. |
| `--steps` | `integer` | no | Number of sampling steps. |
| `--lyrics-prompt` | `string` | no | Lyrics prompt for vocal models (e.g. MiniMax). |
| `--instrumental` | `string` | no | `"true"` or `"false"` — request instrumental output. |
| `--output-format` | `string` | no | Output format, e.g. `mp3`, `wav`, `flac` (backend-dependent). |

\* `--prompt` and `--prompts-file` are mutually exclusive.

## Outputs

| Port | Type | Description |
|------|------|-------------|
| `generated_audio` | `dir` | Directory at `{out}/audio/` containing generated audio files. |
| `audio_manifest` | `file` | JSON manifest at `{out}/manifest.json` (common shape + audio extensions). |

## Request validation

Same hard-fail semantics as image modality: missing `requires` features fail
before the generation loop; unsupported features are dropped-with-warning
(SD-004).  `--mode` is required.

## Backends

- **cloud**: `FalBackend` drives fal.ai audio endpoints (`stable-audio-3-medium`,
  `minimax-music-v2.6`, `minimax-music-3`, `ace-step`).
- **local**: Reserved for a follow-up sprint.  VibeComfy ready-templates for
  Stable Audio 3, ACE-Step, and Stable Audio Open will be wired, along with
  `VibeComfyBackend` node-target injection.

## Audio-modality manifest extensions

The `request` object includes audio-specific fields: `duration`.  Output entries
carry `content_hash`, `bytes`, and `duration_seconds` (via ffprobe best-effort).
Manifest `schema_version` is 2 (per SD-006).

## Escape hatch

For spectrogram conditioning, multi-track generation, vocal inpainting, or exotic
audio samplers, use `vibecomfy.run` directly.  The `generation.generate_audio`
executor covers the basic happy path only.

See:
- `astrid/packs/generation/executors/generate_audio/STAGE.md` — executor usage and examples
- `astrid/packs/vibecomfy/executors/run/STAGE.md` — VibeComfy workflow runner
- `docs/generation/33-music-models.md` — cloud model and local workflow reference
