# Pool Merge

**Executor**: `training.pool_merge`  
**Status**: implemented  
**Pipeline step**: 8

Merges multiple candidate clip pools into a single unified pool for downstream
arrangement and cutting. When the hype pipeline generates multiple pools (e.g.,
from different source videos, quality tiers, or clip categories), this executor
deduplicates overlapping clips, normalizes metadata, and produces one canonical
`pool.json` that `arrange` can consume.

Uses `cache.mode: always_run` — this step always executes because pool
composition depends on upstream pool contents, which cannot be predicted from
sentinels alone. The output pool is written via `mode: mutate` (in-place update
of the existing pool file).

## CLI quick-start

```bash
python -m astrid executors run training.pool_merge -- \
  --pool ./out/pool.json --theme ./theme.json --out ./out
```

## Inputs

| Name  | Type | Required | Description                  |
|-------|------|----------|------------------------------|
| pool  | file | no       | Input pool(s) to merge       |
| theme | file | no       | Theme configuration file     |

## Outputs

| Name | Type | Path              | Mode   | Description              |
|------|------|-------------------|--------|--------------------------|
| pool | file | `{out}/pool.json` | mutate | Unified merged clip pool |

## Pipeline position

Step 8 of the editorial pipeline. Runs after `training.pool_build` and before
`editorial.arrange`. Always executes (cache bypass) to guarantee freshness.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
- `training.pool_build`
