# Shots

**Executor**: `editorial.shots`  
**Status**: implemented  
**Pipeline step**: 3

Slices each detected scene into individual shot windows for downstream pool
building. The executor subdivides scene boundaries into finer-grained shots
using ffmpeg shot-detection filters, producing a `shots.json` manifest that
maps each shot to its parent scene, time range, and metadata.

Shot windows are the fundamental unit for clip extraction — each shot
boundary defines a candidate clip start/end point that the pool-building
stage uses to construct the candidate clip pool. The `shots.json` sentinel
gates cache invalidation.

## SDK quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.shots",
        kind="executor", project="demo",
    inputs={"video": "./source.mp4"},
)
```

Optionally provide a pre-existing scenes file:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.shots",
        kind="executor", project="demo",
    inputs={"video": "./source.mp4", "scenes": "./out/scenes.json"},
)
```

## Inputs

| Name   | Type | Required | Description                         |
|--------|------|----------|-------------------------------------|
| video  | file | yes      | Source video to split into shots    |
| scenes | file | no       | Existing scenes.json input          |

## Outputs

| Name  | Type | Path                  | Description                |
|-------|------|-----------------------|----------------------------|
| shots | file | `{out}/shots.json`    | Shot window manifest       |

## Pipeline position

Step 3 of the editorial pipeline. Runs after `editorial.transcribe`,
`editorial.scenes`, and `editorial.quality_zones`. Provides `shots` to
triage, pool_build, and all downstream stages.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
