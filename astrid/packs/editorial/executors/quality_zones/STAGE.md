# Quality Zones

**Executor**: `editorial.quality_zones`  
**Status**: implemented  
**Pipeline step**: 2

Tags every detected scene with per-zone quality grades that feed into
downstream clip selection and arrangement. The executor analyzes each scene
window for visual quality signals (motion blur, exposure, framing, occlusions)
and assigns tiered grades (A/B/C/D). These grades drive the triage and
pool-building stages: high-grade zones are prioritized for clip extraction,
while low-grade zones are deprioritized or excluded.

Runs locally via ffmpeg — no network or API required. The `quality_zones.json`
sentinel gates cache invalidation.

## SDK quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.quality_zones",
        kind="executor", project="demo",
    inputs={"video": "./source.mp4"},
)
```

## Inputs

| Name  | Type | Required | Description                              |
|-------|------|----------|------------------------------------------|
| video | file | yes      | Source video to analyze for quality zones |

## Outputs

| Name          | Type | Path                          | Description                         |
|---------------|------|-------------------------------|-------------------------------------|
| quality_zones | file | `{out}/quality_zones.json`    | Per-scene quality grade assignments |

## Pipeline position

Step 2 of the editorial pipeline. Runs after `editorial.transcribe` and
`editorial.scenes`. Provides `quality_zones` to shots, triage, pool_build,
and all downstream arrangement stages.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
