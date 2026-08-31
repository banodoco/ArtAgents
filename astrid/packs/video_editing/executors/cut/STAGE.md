# Cut

**Executor**: `video_editing.cut`  
**Status**: implemented  
**Pipeline step**: 10

Assembles the editorial arrangement into a canonical triple of JSON
files: **timeline**, **assets**, and **metadata**. This is the bridge between
the editorial pipeline and the Remotion renderer — `cut` consumes the
arrangement from `editorial.arrange`, the merged pool from
`training.pool_merge`, and the brief/theme, then produces three files consumed
by `rendering.render`.

## Three-file output

| File                   | Description                                     |
|------------------------|-------------------------------------------------|
| `hype.timeline.json`   | Clip sequence, transitions, effects, and timing |
| `hype.assets.json`     | Asset registry mapping clip IDs to media files  |
| `hype.metadata.json`   | Render metadata (fps, resolution, theme refs)   |

All three files are written under `{brief_out}/` (the brief's output directory).
The `hype.timeline.json` and `hype.assets.json` pair is the canonical input to
`rendering.render`. Cache uses a three-sentinel gate: all three files must be
present to satisfy the cache hit.

## Quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "video_editing.cut",
        kind="executor", project="demo",
    inputs={
        "pool": "./out/pool.json",
        "arrangement": "./out/arrangement.json",
        "brief": "./brief.json",
        "theme": "./themes/my-theme",
    },
)
```

With optional video/audio sources:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "video_editing.cut",
        kind="executor", project="demo",
    inputs={
        "pool": "./out/pool.json",
        "arrangement": "./out/arrangement.json",
        "brief": "./brief.json",
        "video": "./source.mp4",
        "audio": "./source.mp3",
        "theme": "./themes/my-theme",
    },
)
```

## Inputs

| Name        | Type | Required | Description                     |
|-------------|------|----------|---------------------------------|
| brief       | file | yes      | Creative brief (required)       |
| pool        | file | no       | Merged clip pool                |
| arrangement | file | no       | Arrangement decisions           |
| video       | file | no       | Source video file               |
| audio       | file | no       | Source audio file               |
| theme       | file | no       | Theme configuration             |

## Outputs

| Name     | Type | Path                            | Description              |
|----------|------|---------------------------------|--------------------------|
| timeline | file | `{brief_out}/hype.timeline.json` | Canonical timeline |
| assets   | file | `{brief_out}/hype.assets.json`   | Asset registry           |
| metadata | file | `{brief_out}/hype.metadata.json` | Render metadata          |

## Pipeline position

Step 10 of the editorial pipeline. Runs after `editorial.arrange` and
`training.pool_merge`, before `rendering.render` (step 12) and
`editorial.refine`.

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
