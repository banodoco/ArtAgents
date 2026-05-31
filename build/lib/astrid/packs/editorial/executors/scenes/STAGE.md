# Scenes

**Executor**: `editorial.scenes`  
**Status**: implemented  
**Pipeline step**: 1

Detects scene boundaries in the source video using ffmpeg-driven analysis.
The executor runs content-aware scene detection (comparing frame deltas over
configurable thresholds) and emits two JSON artifacts: `scenes.json` (the
canonical scene list with start/end timestamps) and `scene_items.json`
(individual scene metadata for downstream inspection and triage).

Does not require an internet connection — all analysis runs locally via
ffmpeg. The `scenes.json` sentinel gates cache invalidation for this step.

## CLI quick-start

```bash
python -m astrid executors run editorial.scenes -- \
  --video ./source.mp4 --out ./out
```

## Inputs

| Name  | Type | Required | Description                           |
|-------|------|----------|---------------------------------------|
| video | file | yes      | Source video to segment into scenes   |

## Outputs

| Name        | Type | Path                      | Description                        |
|-------------|------|---------------------------|------------------------------------|
| scenes      | file | `{out}/scenes.json`       | Canonical scene boundary list      |
| scene_items | file | `{out}/scene_items.json`  | Per-scene metadata for downstream  |

## Pipeline position

Step 1 of the editorial pipeline. Runs after `editorial.transcribe` and
provides `scenes` to quality_zones, shots, triage, scene_describe, and all
subsequent downstream stages.

## Depends on

- `editorial.transcribe`
