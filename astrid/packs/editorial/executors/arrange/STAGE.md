# Arrange

**Executor**: `editorial.arrange`  
**Status**: implemented  
**Pipeline step**: 9 (brief-specific shot arrangement)

Composes a brief-specific shot arrangement from the unified source clip
pool. This is the most complex editorial executor — it requires the full
pool (built by training.pool_build and merged by training.pool_merge),
the creative brief, and an optional theme file. An LLM composes a
sequenced arrangement of clips, transitions, effects, and text overlays
that satisfies the brief's creative direction.

The LLM-driven composition considers clip quality grades (from
quality_zones), scene descriptions (from scene_describe), quote
candidates (from quote_scout), and the brief's tone, pacing, and
structural requirements. Output is `arrangement.json` — a structured
shot-by-shot plan that feeds directly into video_editing.cut for
timeline assembly.

## SDK quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.arrange",
        kind="executor", project="demo",
    inputs={
        "pool": "./out/unified_pool.json",
        "brief": "./briefs/my-hype.md",
        "theme": "./themes/default.json",
        "target_duration": "60",
    },
)
```

With an explicit env file for API credentials:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.arrange",
        kind="executor", project="demo",
    inputs={
        "pool": "./out/unified_pool.json",
        "brief": "./briefs/my-hype.md",
        "env_file": ".env.local",
    },
)
```

## Inputs

| Name           | Type   | Required | Description                                  |
|----------------|--------|----------|----------------------------------------------|
| pool           | file   | no       | Unified clip pool from training.pool_merge    |
| brief          | file   | yes      | Creative brief describing the desired output  |
| theme          | file   | no       | Theme/style configuration                     |
| target_duration| number | no       | Target duration in seconds                    |
| env_file       | file   | no       | Optional environment file for API credentials |

## Outputs

| Name        | Type | Path                          | Description                      |
|-------------|------|-------------------------------|----------------------------------|
| arrangement | file | `{brief_out}/arrangement.json` | Brief-specific shot arrangement  |

## Pipeline position

Step 9 of the editorial pipeline. Depends on the full upstream stack
including cross-pack dependencies on training.pool_build and
training.pool_merge for the unified clip pool. The arrangement output
feeds into video_editing.cut (step 10) for timeline assembly.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
- `training.pool_build` (cross-pack)
- `training.pool_merge` (cross-pack)
