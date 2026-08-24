# Asset Cache

**Executor**: `training.asset_cache`  
**Status**: implemented  
**Kind**: mutating (downloads, prunes, and modifies the local cache)

Manages the repo-local hype asset cache under `HYPE_CACHE_DIR`. Supports three
operations: **download** (fetch remote assets into the cache), **prune** (remove
entries older than a configurable age in days), and **list** (enumerate cached
entries with their sizes and ages).

**This executor is mutating.** Always run with `--dry-run` first to inspect
what would be changed before applying real mutations. Passes the
`HYPE_CACHE_DIR` environment variable through to the subprocess so the
cache location is consistent with other training-pack executors.

## Quick-start

```python
# List cached assets (read-only, safe)
import astrid.sdk as sdk
result = sdk.invoke("training.asset_cache", inputs={"list": True})
    kind="executor", project="demo",

# Dry-run a prune of entries older than 30 days
result = sdk.invoke("training.asset_cache", inputs={"prune_older_than": "30"}, dry_run=True)
    kind="executor", project="demo",

# Apply the prune (mutating — review dry-run output first)
result = sdk.invoke("training.asset_cache", inputs={"prune_older_than": "30"})
    kind="executor", project="demo",
```

## Inputs

| Name             | Type   | Description                                    |
|------------------|--------|------------------------------------------------|
| prune_older_than | number | Remove cache entries older than this many days |

## Outputs

No sentinel outputs — this executor uses `cache.mode: none` and always runs
when invoked. Side effects are mutations to the asset cache directory.

## Pipeline position

Auxiliary executor — not in the numbered editorial pipeline. Called on-demand
for cache maintenance and by the `render` executor for asset fetching during
composition.

## Depends on

None.

## Environment

- `HYPE_CACHE_DIR` — passed through to the subprocess; controls the cache root
  directory shared with `pool_build`, `pool_merge`, and `render`.
