# Refine

**Executor**: `editorial.refine`  
**Status**: implemented  
**Pipeline step**: 11 (last editorial pass before cut)

Applies targeted reviewer-driven refinements to an existing arrangement.
Refine is the final editorial pass before the render pipeline — it accepts
arrangement feedback (from human review or automated quality checks) and
mutates the timeline, assets, and metadata JSON triple produced by
video_editing.cut.

The executor reads the current arrangement, timeline, assets, and metadata,
then applies corrections: clip replacement, timing adjustments, text
overlay edits, effect parameter tweaks, and transition refinements.
Output includes a `refine.json` record of applied changes, plus mutated
copies of the timeline, assets, and metadata files ready for rendering.

## SDK quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.refine",
    inputs={
        "arrangement": "./out/arrangement.json",
        "pool": "./out/unified_pool.json",
        "timeline": "./out/hype.timeline.json",
        "assets": "./out/hype.assets.json",
        "metadata": "./out/hype.metadata.json",
        "transcript": "./out/transcript.json",
    },
    out="./out",
)
```

With an explicit env file for API credentials:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.refine",
    inputs={
        "arrangement": "./out/arrangement.json",
        "pool": "./out/unified_pool.json",
        "timeline": "./out/hype.timeline.json",
        "assets": "./out/hype.assets.json",
        "metadata": "./out/hype.metadata.json",
        "env_file": ".env.local",
    },
    out="./out",
)
```

## Inputs

| Name        | Type | Required | Description                                |
|-------------|------|----------|--------------------------------------------|
| arrangement | file | no       | Current shot arrangement JSON              |
| pool        | file | no       | Unified clip pool for replacement clips    |
| timeline    | file | no       | Timeline JSON from video_editing.cut       |
| assets      | file | no       | Assets JSON from video_editing.cut         |
| metadata    | file | no       | Metadata JSON from video_editing.cut       |
| transcript  | file | no       | Original transcript for reference          |
| env_file    | file | no       | Optional environment file for API credentials |

## Outputs

| Name    | Type | Path                                 | Description                        |
|---------|------|--------------------------------------|------------------------------------|
| refine  | file | `{brief_out}/refine.json`            | Record of applied refinements      |
| timeline| file | `{brief_out}/hype.timeline.json`     | Refined timeline (mutated)         |
| assets  | file | `{brief_out}/hype.assets.json`       | Refined assets manifest (mutated)  |
| metadata| file | `{brief_out}/hype.metadata.json`     | Refined metadata (mutated)         |

## Pipeline position

Step 11 of the editorial pipeline. This is the last editorial pass before
cut and render. It depends on video_editing.cut (step 10) for the initial
timeline/assets/metadata triple and editorial.arrange (step 9) for the
arrangement. Output feeds directly into rendering.render (step 12).

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
- `training.pool_build`
- `training.pool_merge`
- `editorial.arrange`
- `video_editing.cut`
