# Music Generation — Fal Model Research

> Research note for adding a `generation.generate_music` / `generation.generate_audio`
> capability that mirrors the existing image-generation stack.
> Data gathered from the public Fal model pages and OpenAPI schemas on 2026-06-15.

## Where the image-generation capability lives

The image stack is the template to copy:

| Concern | Location |
|---------|----------|
| Executor (CLI + SDK + manifest) | `astrid/packs/generation/executors/generate_image/run.py` |
| Executor manifest | `astrid/packs/generation/executors/generate_image/executor.yaml` |
| Stage docs / contract | `astrid/packs/generation/executors/generate_image/STAGE.md` |
| Shared executor helpers | `astrid/packs/generation/executors/_common.py` |
| Model registry | `astrid/core/model_catalog/models.yaml` |
| Registry dataclasses / validation | `astrid/core/model_catalog/schema.py` |
| Taxonomy (features, modes, modalities) | `astrid/core/model_catalog/taxonomy.py` |
| Cloud backend adapter (fal.ai) | `astrid/core/generation/backends/fal.py` |
| Backend registry / discovery | `astrid/core/generation/backends/registry.py` |
| Per-modality contracts | `docs/generation/30-image-contract.md`, `docs/generation/32-audio-contract.md` |

The executor uses a **model → mode → backend** taxonomy:

- `--model` picks a registry entry (e.g. `flux-dev`).
- `--mode` picks a mode inside that entry (e.g. `t2i`).
- `--execution` picks a backend (`local`, `cloud`, `codex`).
- `FalBackend.generate()` maps canonical features to Fal parameters via
  `BackendSpec.param_map`, submits the job, polls, downloads the asset, and
  writes a `manifest.json`.

## Fal music / text-to-audio models surveyed

| Model ID (Fal endpoint) | What it does | Required / notable inputs | Output key | Pricing (Fal) |
|-------------------------|--------------|---------------------------|------------|---------------|
| `fal-ai/minimax-music/v2` | Text + lyrics → song (MiniMax Music 2.0) | `prompt` (style), `lyrics_prompt` (required), nested `audio_setting` optional | `audio` (mp3) | **$0.03 / generation** |
| `fal-ai/minimax-music` | Lyrics + reference audio → cover | `prompt` (lyrics), `reference_audio_url` (required) | `audio` | **$0.035 / generation** |
| `fal-ai/elevenlabs/music` | High-quality prompt/composition-plan → music | `prompt`, `music_length_ms`, `force_instrumental`, `output_format`, `composition_plan` | `audio` (mp3) | **$0.80 / output minute** (rounded up) |
| `fal-ai/stable-audio-3/medium/base/text-to-audio` | Long-form stereo music up to ~6 min | `prompt`, `duration` (s), `negative_prompt`, `guidance_scale`, `num_inference_steps`, `seed`, `output_format`, `bitrate` | `audio` | **$0.0479 / audio** |
| `fal-ai/stable-audio-25/text-to-audio` | Music / SFX up to 190 s | `prompt`, `seconds_total`, `guidance_scale`, `num_inference_steps`, `seed` | `audio` (wav) | **$0.20 / audio** |
| `fal-ai/ace-step/prompt-to-audio` | Prompt → music, with lyrics/tags metadata | `prompt`, `duration` (s), `instrumental`, `seed`, many guidance/step knobs | `audio`, `tags`, `lyrics` | **$0.0002 / second** |
| `fal-ai/stable-audio` | Open-weight text-to-audio, short clips | `prompt`, `seconds_total` (≤47), `steps`, `seconds_start` | `audio_file` | **$0 / compute second** (open / pending enterprise status) |

All endpoints return a single audio file; none expose a native `count`/`num_outputs`
parameter, so Astrid’s sequential N=1 loop would be used for `count > 1`.

## Recommended starter set

For a first music-generation executor, add **four cloud-only models** that cover
cheap/fast, lyrical, high-quality, and long-form use cases:

1. **`minimax-music-v2`** — default lyric-driven music. Cheapest ($0.03/gen),
   good quality, commercial use.
2. **`stable-audio-3-medium`** — best open-weights-style option. Supports
   `negative_prompt`, long duration (up to 380 s), guidance/steps, multiple
   output formats. $0.0479/audio.
3. **`ace-step`** — ultra-cheap experimentation ($0.0002/s), instrumental toggle,
   returns tags/lyrics metadata.
4. **`elevenlabs-music`** — premium option when quality matters more than cost.
   Fine-grained length, instrumental toggle, output format control. $0.80/min.

`stable-audio-25` and the original `minimax-music` (reference-audio cover) are
reasonable follow-ups; `stable-audio` is free but capped at 47 s and has a
pending enterprise status.

## How they map to Astrid’s generation stack

### New canonical audio/music features

The audio contract (`docs/generation/32-audio-contract.md`) already sketches
`tts`, `music`, and `sfx` modes. To wire the models above, add these features
(at minimum) to the generation taxonomy:

- `prompt`
- `negative_prompt`
- `seed`
- `count`
- `duration`
- `output_format`
- `lyrics_prompt`
- `instrumental`
- `audio_ref` (for future cover / style-transfer modes)

### Suggested `models.yaml` entries

```yaml
  - id: minimax-music-v2
    modality: audio
    modes:
      music:
        supports:
          - prompt
          - lyrics_prompt
          - count
        requires:
          - prompt
          - lyrics_prompt
        backends:
          cloud:
            endpoint: fal-ai/minimax-music/v2
            price:
              unit: output
              usd: 0.03

  - id: stable-audio-3-medium
    modality: audio
    modes:
      music:
        supports:
          - prompt
          - negative_prompt
          - seed
          - count
          - duration
          - output_format
          - guidance_scale
          - steps
        requires:
          - prompt
        backends:
          cloud:
            endpoint: fal-ai/stable-audio-3/medium/base/text-to-audio
            price:
              unit: output
              usd: 0.0479

  - id: ace-step
    modality: audio
    modes:
      music:
        supports:
          - prompt
          - seed
          - count
          - duration
          - instrumental
          - guidance_scale
          - steps
        requires:
          - prompt
        backends:
          cloud:
            endpoint: fal-ai/ace-step/prompt-to-audio
            price:
              unit: output
              usd: 0.012   # ~60 s * $0.0002/s; Fal bills per second

  - id: elevenlabs-music
    modality: audio
    modes:
      music:
        supports:
          - prompt
          - count
          - duration
          - output_format
          - instrumental
        requires:
          - prompt
        backends:
          cloud:
            endpoint: fal-ai/elevenlabs/music
            price:
              unit: output
              usd: 0.8     # per rounded minute; registry price is a coarse fallback
```

Notes:

- **Fal price units** are heterogeneous (`generations`, `audios`, `minutes`,
  `seconds`). Astrid’s `_ALLOWED_PRICE_UNITS` currently only allows
  `image`, `output`, `video`; it needs to accept audio units (or the entries
  can use a generic `output` unit and document the real billing model).
- **`duration` mapping** differs per endpoint:
  - `stable-audio-3-medium`: `duration`
  - `stable-audio-25`: `seconds_total`
  - `ace-step`: `duration`
  - `elevenlabs-music`: `music_length_ms`
  - These are handled via per-backend `param_map` entries, just like `size` is
    mapped to `image_size` for image models.
- **`lyrics_prompt`** is required for MiniMax v2 and can be optional for other
  models if desired.
- **`output_format`** for MiniMax v2 lives inside a nested `audio_setting`
  object (`audio_setting.format`). The Fal adapter would need a small helper
  to build that object, or `audio_setting` could be exposed as its own
  structured feature.

### `FalBackend` changes

1. **Add a `music` default param map** in `FalBackend.DEFAULT_PARAM_MAP`:
   ```python
   "music": {
       "prompt": "prompt",
       "negative_prompt": "negative_prompt",
       "seed": "seed",
       "duration": "duration",
       "output_format": "output_format",
       "lyrics_prompt": "lyrics_prompt",
       "instrumental": "instrumental",
       "guidance_scale": "guidance_scale",
       "steps": "num_inference_steps",
   }
   ```
2. **Teach `_extract_asset_urls()` about audio results.** Today it looks for
   `images`, `videos`, and `output`. Music endpoints return either `audio`
   (most) or `audio_file` (`stable-audio`). Add explicit extraction for both.
3. **Optional:** add a small `_build_audio_setting()` helper for MiniMax v2 if
   `audio_setting` features are surfaced.

### New executor

Create one of:

- `astrid/packs/generation/executors/generate_music/run.py` + `executor.yaml`
  (focused, matches your "music" request), or
- `astrid/packs/generation/executors/generate_audio/run.py` + `executor.yaml`
  with `--mode music` (aligns with the existing `docs/generation/32-audio-contract.md`
  forward spec and leaves room for `tts`/`sfx` later).

It should reuse `astrid/packs/generation/executors/_common.py` for prompts,
seed resolution, manifest building, and backend adapter creation — exactly the
same pattern as `generate_image`.

### Schema / taxonomy prerequisites

Before the registry entries above will validate, you must:

1. Add `AUDIO_MODALITY = "audio"` to `astrid/core/model_catalog/taxonomy.py`.
2. Add `AUDIO_FEATURES` and a `CANONICAL_AUDIO_MODES` tuple (at least `music`).
3. Update `_require_modality()` and `_validate_mode_spec()` in
   `astrid/core/model_catalog/schema.py` to accept `audio`.
4. Expand `_ALLOWED_PRICE_UNITS` in `schema.py` to include audio units, or
   collapse them to a generic unit.

## Open questions before implementing

1. **Executor scope:** Do you want a focused `generation.generate_music`
   executor, or the broader `generation.generate_audio` with `--mode music`
   (and future `tts`/`sfx`) per the existing audio contract?
2. **Local backend:** Do you want a ComfyUI/vibecomfy local path for any of
   these (Stable Audio Open has public weights), or is cloud-only acceptable
   for the first pass?
3. **Lyrics handling:** Should `lyrics_prompt` be a top-level CLI flag, or
   read from a file / from the prompts-file entry?
4. **Pricing units:** Should the registry reflect Fal’s real units
   (`audio`, `minute`, `second`) or use a generic `output` unit?

## ComfyUI / local availability

I searched the ComfyUI Manager custom-node list (`ltdrdata/ComfyUI-Manager`),
GitHub, HuggingFace, and the official ComfyUI docs for local nodes/weights.

| Model | Local ComfyUI status | Key repos / weights |
|-------|----------------------|---------------------|
| **Stable Audio 3 Medium** | ✅ Native day-0 support in ComfyUI | ComfyUI tutorial: https://docs.comfy.org/tutorials/audio/stable-audio/stable-audio-3 <br> Comfy-Org checkpoints: https://huggingface.co/Comfy-Org/stable-audio-3 <br> Stability weights: https://huggingface.co/stabilityai/stable-audio-3-medium |
| **Stable Audio 2.5** | ✅ Native in ComfyUI | ComfyUI blog: https://comfyui.org/en/stable-audio-25-is-now-in-comfyui |
| **Stable Audio Open 1.0** | ✅ Custom node available | `lks-ai/ComfyUI-StableAudioSampler` (271 ⭐) — https://github.com/lks-ai/ComfyUI-StableAudioSampler <br> `smthemex/ComfyUI_StableAudio_Open` — https://github.com/smthemex/ComfyUI_StableAudio_Open <br> Comfy-Org repack: https://huggingface.co/Comfy-Org/stable-audio-open-1.0_repackaged <br> Weights: https://huggingface.co/stabilityai/stable-audio-open-1.0 |
| **ACE-Step 1.5** | ✅ Native + custom nodes | ComfyUI tutorial: https://docs.comfy.org/tutorials/audio/ace-step/ace-step-v1 <br> Official node: `ace-step/ACE-Step-ComfyUI` — https://github.com/ace-step/ACE-Step-ComfyUI <br> Popular node: `billwuhao/ComfyUI_ACE-Step` — https://github.com/billwuhao/ComfyUI_ACE-Step <br> Comfy-Org repack: https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files <br> Weights: https://huggingface.co/ACE-Step/Ace-Step1.5 |
| **MiniMax Music** | ❌ No local weights / no native node | Only API wrappers/workflows exist (e.g. `synthetai/ComfyUI-JM-MiniMax-API`). No public inference weights found. |
| **ElevenLabs Music** | ❌ No local weights | ElevenLabs is available in ComfyUI via an official/API integration, but it is not a local model. No public weights found. |

### Bottom line for a local backend

If you want a **local (ComfyUI/vibecomfy) backend** for music, the realistic
options are:

1. **Stable Audio 3 Medium** — best quality + long duration; needs the
   `stable_audio_3_medium.safetensors` checkpoint + T5/Gemma or Qwen text
   encoder from Comfy-Org.
2. **Stable Audio 2.5** — native ComfyUI, good middle ground.
3. **Stable Audio Open 1.0** — shortest/clips, easiest weights, custom-node
   path already exists.
4. **ACE-Step 1.5** — native ComfyUI support, strong for prompt-to-music with
   lyrics/tags metadata.

**MiniMax Music v2** and **ElevenLabs Music** should be treated as **cloud-only**
(Fal API) for now.

## Sources

- Fal model cards and API docs:
  - https://fal.ai/models/fal-ai/minimax-music/v2/api
  - https://fal.ai/models/fal-ai/elevenlabs/music/api
  - https://fal.ai/models/fal-ai/stable-audio-3/medium/base/text-to-audio/api
  - https://fal.ai/models/fal-ai/ace-step/prompt-to-audio/api
  - https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/api
  - https://fal.ai/models/fal-ai/stable-audio/api
- Fal OpenAPI endpoint:
  `https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=<endpoint_id>`
