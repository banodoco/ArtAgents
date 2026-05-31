# Pool Build

**Executor**: `training.pool_build`  
**Status**: implemented  
**Pipeline step**: 7

Builds the candidate clip pool from triaged source-video scenes. Consumes
the outputs of the early editorial pipeline (transcript, scenes, quality
zones, shots, scene triage, scene descriptions, and quote candidates) and
constructs a `pool.json` manifest enumerating every viable clip with its
source time range, quality grade, and metadata.

The pool is the central data structure for the back half of the pipeline:
`pool_merge` combines multiple pools, `arrange` selects from the pool, and
`cut` assembles the final timeline from the arrangement. The `pool.json`
sentinel gates cache invalidation.

## CLI quick-start

```bash
python -m astrid executors run training.pool_build -- \
  --triage ./out/triage.json \
  --scene_descriptions ./out/scene_descriptions.json \
  --quote_candidates ./out/quote_candidates.json \
  --transcript ./out/transcript.json \
  --scenes ./out/scenes.json \
  --out ./out
```

## Inputs

| Name               | Type | Required | Description                          |
|--------------------|------|----------|--------------------------------------|
| triage             | file | no       | Scene triage decisions               |
| scene_descriptions | file | no       | Vision-model scene captions          |
| quote_candidates   | file | no       | Quote-scout candidate selections     |
| transcript         | file | no       | Whisper transcript JSON              |
| scenes             | file | no       | Scene boundary manifest              |

## Outputs

| Name | Type | Path              | Description            |
|------|------|-------------------|------------------------|
| pool | file | `{out}/pool.json` | Candidate clip pool    |

## Pipeline position

Step 7 of the editorial pipeline. Sits at the boundary between scene analysis
and clip selection. Runs after all early-pipeline analysis stages and before
arrangement/merge.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
