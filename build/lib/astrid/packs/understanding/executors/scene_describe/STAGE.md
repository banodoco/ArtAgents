# Scene Describe

**Executor**: `understanding.scene_describe`  
**Status**: implemented  
**Pipeline step**: 5

Captions each detected scene with a vision model for downstream clip
selection. The executor extracts representative frames from each scene
window, sends them to a vision-capable LLM, and produces
`scene_descriptions.json` — a manifest mapping each scene ID to a natural
language caption, detected objects/actions, and quality notes.

These descriptions feed into `pool_build` and `quote_scout`, enabling
semantic clip search ("find all scenes with a person walking") and smart
arrangement. The `scene_descriptions.json` sentinel gates cache invalidation.

## CLI quick-start

```bash
python -m astrid executors run understanding.scene_describe -- \
  --video ./source.mp4 --scenes ./out/scenes.json \
  --triage ./out/triage.json --out ./out
```

With explicit API credentials:

```bash
python -m astrid executors run understanding.scene_describe -- \
  --video ./source.mp4 --scenes ./out/scenes.json \
  --triage ./out/triage.json --env-file .env.local --out ./out
```

## Inputs

| Name     | Type | Required | Description                       |
|----------|------|----------|-----------------------------------|
| video    | file | yes      | Source video for frame extraction |
| scenes   | file | no       | Scene boundary manifest           |
| triage   | file | no       | Scene triage decisions            |
| env_file | file | no       | Optional env file for API key     |

## Outputs

| Name               | Type | Path                               | Description                   |
|--------------------|------|------------------------------------|-------------------------------|
| scene_descriptions | file | `{out}/scene_descriptions.json`    | Per-scene vision-model captions |

## Pipeline position

Step 5 of the editorial pipeline. Runs after `editorial.triage` (step 4)
and before `understanding.video_understand` (step 5.5) and `editorial.quote_scout`
(step 6).

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`

## Shared LLM API pattern

Like `understanding.audio_understand` and `understanding.video_understand`,
this executor follows the shared Astrid LLM pattern: API key resolution,
model selection, prompt → JSON output. Requires a vision-model-compatible
API key (OpenAI or compatible provider).
