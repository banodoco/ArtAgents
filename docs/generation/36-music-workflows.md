# Music Generation — ComfyUI Workflows

> Workflow inventory for the music/text-to-audio models discussed in
> `35-music-models-research.md`.  URLs are direct raw JSON downloads from the
> official Comfy-Org repositories.

## How these were found

- ComfyUI Manager custom-node list (`ltdrdata/ComfyUI-Manager`)
- `Comfy-Org/workflow_templates` GitHub repo (official ComfyUI templates)
- `Comfy-Org/example_workflows` GitHub repo
- ComfyUI docs at https://docs.comfy.org/tutorials/audio
- GitHub / HuggingFace search for model weights and node repos

I also downloaded and inspected each JSON file to confirm the exposed inputs
and node types.

## Local (native / custom-node) workflows

### Stable Audio 3 Medium

| Workflow | Direct JSON URL | Type |
|----------|-----------------|------|
| Stable Audio 3 Medium (subgraph) | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_stable_audio_3_medium.json | local blueprint |
| Stable Audio 3 Medium Base | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_stable_audio_3_medium_base.json | local blueprint |
| Stable Audio 3 generation blueprint | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/blueprints/audio_generation_stable_audio_3_medium.json | subgraph blueprint |

**Exposed subgraph inputs** (from `audio_stable_audio_3_medium.json`):

- `user_input` (STRING) — the text prompt
- `duration` (FLOAT)
- `seed` (INT)
- `use_reprompt` (BOOLEAN)
- `category` (COMBO) — reprompt category
- `ckpt_name` (COMBO) — e.g. `stable_audio_3_medium.safetensors`
- `sa_clip` (COMBO) — Stable Audio CLIP
- `qwen_clip` (COMBO) — Qwen prompt-expansion CLIP
- Output: `AUDIO`

**Required weights** (from Comfy-Org):

- https://huggingface.co/Comfy-Org/stable-audio-3
- Text encoders: `t5gemma_b_b_ul2.safetensors`, `qwen3.5_2b_bf16.safetensors`

### Stable Audio Open 1.0

| Workflow | Direct JSON URL | Type |
|----------|-----------------|------|
| Stable Audio Open example | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_stable_audio_example.json | local native nodes |

**Key nodes / defaults**:

- `CheckpointLoaderSimple` → `stable-audio-open-1.0.safetensors`
- `CLIPLoader` → `t5-base.safetensors` (type `stable_audio`)
- `CLIPTextEncode` → prompt (e.g. `heaven church electronic dance music`)
- `CLIPTextEncode` → negative prompt (empty by default)
- `EmptyLatentAudio` → seconds / batch_size
- `KSampler` → seed, steps, cfg, sampler, scheduler, denoise
- `VAEDecodeAudio` → audio
- `SaveAudioMP3`

**Custom-node alternative**:

- `lks-ai/ComfyUI-StableAudioSampler` — https://github.com/lks-ai/ComfyUI-StableAudioSampler
- `smthemex/ComfyUI_StableAudio_Open` — https://github.com/smthemex/ComfyUI_StableAudio_Open

### ACE-Step

| Workflow | Direct JSON URL | Type |
|----------|-----------------|------|
| ACE-Step 1.5 text-to-audio (subgraph) | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/05_audio_ace_step_1_t2a_song_subgraphed.json | local blueprint |
| ACE-Step 1.5 text-to-audio song | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_t2a_song.json | local native/custom nodes |
| ACE-Step 1.5 instrumental | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_t2a_instrumentals.json | local native/custom nodes |
| ACE-Step 1.5 checkpoint (AIO) | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_5_checkpoint.json | local native/custom nodes |
| ACE-Step 1.5 XL turbo | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step1_5_xl_turbo.json | local native/custom nodes |
| ACE-Step v1 text-to-music (example) | https://raw.githubusercontent.com/Comfy-Org/example_workflows/main/audio/ace-step/ace_step_1_t2m.json | local native/custom nodes |
| ACE-Step v1 music-to-music editing | https://raw.githubusercontent.com/Comfy-Org/example_workflows/main/audio/ace-step/ace_step_1_m2m_editing.json | local native/custom nodes |

**Exposed subgraph inputs** (from `05_audio_ace_step_1_t2a_song_subgraphed.json`):

- `tags` (STRING) — style/genre tags
- `lyrics` (STRING)
- `timesignature` (COMBO)
- `language` (COMBO)
- `keyscale` (COMBO)
- `generate_audio_codes` (BOOLEAN)
- `cfg_scale` (FLOAT)
- `value` (FLOAT, labelled `duration`)
- `unet_name`, `clip_name1`, `clip_name2`, `vae_name` (COMBO)
- Output: `AUDIO`

**Required weights**:

- Comfy-Org repack: https://huggingface.co/Comfy-Org/ACE-Step_ComfyUI_repackaged
- ACE-Step weights: https://huggingface.co/ACE-Step/Ace-Step1.5

**Custom nodes**:

- Official: `ace-step/ACE-Step-ComfyUI` — https://github.com/ace-step/ACE-Step-ComfyUI
- Popular: `billwuhao/ComfyUI_ACE-Step` — https://github.com/billwuhao/ComfyUI_ACE-Step

### Stable Audio 2.5

Stable Audio 2.5 is supported natively in current ComfyUI, but there is no
standalone `.json` template in the `Comfy-Org/workflow_templates` repo yet.
It can be built with the same core nodes as Stable Audio Open / 3:
`CheckpointLoaderSimple`, `CLIPLoader`, `EmptyLatentAudio`, `KSampler`,
`VAEDecodeAudio`, `SaveAudioMP3`.

Reference announcement: https://comfyui.org/en/stable-audio-25-is-now-in-comfyui

## Cloud / API workflows

### Stability AI audio API (Stable Audio 2.5)

These use ComfyUI’s official **Stability AI partner API nodes**, not local
weights. They match the `fal-ai/stable-audio-25/text-to-audio` and
`fal-ai/stable-audio-3/medium/base/text-to-audio` cloud endpoints conceptually.

| Workflow | Direct JSON URL | Notes |
|----------|-----------------|-------|
| Stability text-to-audio | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/api_stability_ai_text_to_audio.json | `StabilityTextToAudio` node: model, prompt, seconds_total, seed, seed_mode, steps |
| Stability audio-to-audio | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/api_stability_ai_audio_to_audio.json | `StabilityAudioToAudio` node: prompt + reference audio |
| Stability audio inpaint | https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/api_stability_ai_audio_inpaint.json | reference audio + mask |

### MiniMax Music / ElevenLabs Music

No local weights or official ComfyUI-native workflows exist for these.
Workflows on https://comfy.org/workflows/model/minimax/ and
https://comfy.org/workflows/model/elevenlabs/ are API-based (cover images only;
no raw JSON download found).

- MiniMax Music is available through API wrapper nodes such as
  `synthetai/ComfyUI-JM-MiniMax-API`.
- ElevenLabs Music is available through ComfyUI’s official ElevenLabs
  integration, but it is still an API call.

For Astrid, these two should be treated as **cloud-only (Fal)**.

## Mapping to Astrid features

| Astrid feature | Stable Audio 3 blueprint | Stable Audio Open example | ACE-Step 1.5 blueprint | Stability API workflow |
|----------------|--------------------------|---------------------------|------------------------|------------------------|
| `prompt` | `user_input` | `CLIPTextEncode` (positive) | `tags` | `prompt` |
| `negative_prompt` | (inside subgraph) | `CLIPTextEncode` (negative) | (inside subgraph) | — |
| `lyrics_prompt` | — | — | `lyrics` | — |
| `duration` | `duration` | `EmptyLatentAudio` seconds | `value` | `seconds_total` |
| `seed` | `seed` | `KSampler` seed | `seed` inside node | `seed` |
| `guidance_scale` | (inside subgraph) | `KSampler` cfg | `cfg_scale` | — |
| `steps` | (inside subgraph) | `KSampler` steps | (inside subgraph) | `steps` |
| `output_format` | MP3 (SaveAudioMP3) | MP3 (SaveAudioMP3) | MP3 (SaveAudioMP3) | MP3 (SaveAudioMP3) |

## Recommendation for local backend templates

If you add a **local (vibecomfy/ComfyUI) backend** to the music executor, start
with these three workflows as ready-templates:

1. **Stable Audio 3 Medium** — `audio_stable_audio_3_medium.json`
2. **ACE-Step 1.5 text-to-audio** — `05_audio_ace_step_1_t2a_song_subgraphed.json`
3. **Stable Audio Open 1.0** — `audio_stable_audio_example.json`

Each has a clear set of exposed inputs that map cleanly to the canonical audio
features sketched in `docs/generation/32-audio-contract.md`.

## Downloaded copies

I saved inspected copies of these workflows locally at:

`.tmp/music_workflows/`

Files include the JSONs above plus a few variant/instrumental versions.
