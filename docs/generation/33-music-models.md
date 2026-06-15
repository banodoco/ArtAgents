# Music Generation Models

This document summarises the cloud music models registered in
`astrid/core/model_catalog/models.yaml`, their capabilities, and the local
workflow follow-up.

## Cloud models

All cloud music models are wired through `FalBackend` and require `FAL_KEY`.

### `stable-audio-3-medium`

| | |
|---|---|
| Endpoint | `fal-ai/stable-audio-3/medium/base/text-to-audio` |
| Mode | `music` |
| Price | `$0.0479 / audio` |
| Supports | `prompt`, `negative_prompt`, `seed`, `count`, `duration`, `guidance_scale`, `steps`, `output_format` |
| Param map | `steps → num_inference_steps` |

Long-form stereo music up to 380 seconds.  Good default for general text-to-music
generation.  `output_format` can be used to request `mp3`, `wav`, etc. when the
backend accepts it.

### `minimax-music-v2.6`

| | |
|---|---|
| Endpoint | `fal-ai/minimax-music/v2.6` |
| Mode | `music` |
| Price | `$0.15 / audio` |
| Supports | `prompt`, `lyrics_prompt`, `instrumental`, `seed`, `count`, `duration` |
| Param map | `lyrics_prompt → lyrics`, `instrumental → is_instrumental` |

Latest MiniMax music model.  Provide `lyrics_prompt` for vocal tracks, or set
`--instrumental true` to generate instrumental music.

### `ace-step`

| | |
|---|---|
| Endpoint | `fal-ai/ace-step/prompt-to-audio` |
| Mode | `music` |
| Price | `$0.0002 / second` |
| Supports | `prompt`, `instrumental`, `seed`, `count`, `duration`, `guidance_scale`, `steps` |
| Param map | `steps → number_of_steps` |

Style prompt auto-generates tags and lyrics.  Cost fallback uses the requested
`duration` in seconds.

## Registry wiring

Each model is declared under `schema_version: 2` with `modality: audio` and a
single `music` mode.  The mode declares `supports`, `requires: [prompt]`, and a
`cloud` backend with `endpoint`, `param_map`, and `price`.

Example snippet:

```yaml
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
        - guidance_scale
        - steps
        - output_format
      requires:
        - prompt
      backends:
        cloud:
          endpoint: fal-ai/stable-audio-3/medium/base/text-to-audio
          param_map:
            prompt: prompt
            negative_prompt: negative_prompt
            seed: seed
            duration: duration
            guidance_scale: guidance_scale
            steps: num_inference_steps
            output_format: output_format
          price:
            unit: audio
            usd: 0.0479
```

## Local workflow follow-up

Cloud music is implemented first.  Local ComfyUI support is a documented
follow-up:

- **Stable Audio 3 Medium** — native ComfyUI support; official Comfy-Org
  workflow available.
- **ACE-Step 1.5** — native + custom nodes; an official
  `audio/ace_step_1_5_t2a_song` ready-template exists in vibecomfy but is bare
  and needs `bind_input` calls or `VibeComfyBackend._NODE_TARGET_TABLE` entries
  for audio nodes (`TextEncodeAceStepAudio1_5`, `EmptyAceStep1_5LatentAudio`,
  `KSampler`, `VAEDecodeAudio`, `SaveAudioMP3`).
- **Stable Audio Open 1.0** — custom nodes + native nodes; official workflow
  available.
- **MiniMax Music / ElevenLabs Music** — no public local weights; API-only.

When local templates are ready, add:

1. VibeComfy ready-templates under the appropriate pack.
2. `VibeComfyBackend.DEFAULT_PARAM_MAP["music"]` entries.
3. Local backend entries in `models.yaml` for the supported models.
4. A golden demo exercising local + cloud parity.

## CLI quick-start

```bash
# Stable Audio 3
python -m astrid.packs.generation.executors.generate_audio.run \
  --model stable-audio-3-medium --mode music --execution cloud \
  --prompt "a serene ambient drone" --out ./out

# MiniMax with lyrics
python -m astrid.packs.generation.executors.generate_audio.run \
  --model minimax-music-v2.6 --mode music --execution cloud \
  --prompt "upbeat synth-pop chorus" \
  --lyrics-prompt "We are the robots, beep boop" --out ./out

# MiniMax instrumental
python -m astrid.packs.generation.executors.generate_audio.run \
  --model minimax-music-v2.6 --mode music --execution cloud \
  --prompt "cinematic orchestral score" --instrumental true --out ./out

# ACE-Step
python -m astrid.packs.generation.executors.generate_audio.run \
  --model ace-step --mode music --execution cloud \
  --prompt "lo-fi hip hop beat" --duration 30 --steps 50 --out ./out
```

## Related docs

- `astrid/packs/generation/executors/generate_audio/STAGE.md` — executor usage
- `docs/generation/00-features.md` — canonical audio features
- `docs/generation/10-registry-schema.md` — registry schema and price units
- `docs/generation/32-audio-contract.md` — audio modality contract
