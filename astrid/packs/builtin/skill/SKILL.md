---
name: builtin
description: >
  Built-in pack — deprecated core namespace retained only for backward-
  compatible aliases (builtin.*).  Ships no live components of its own;
  all capabilities have migrated to domain-specific packs.
---

# Built-in (Deprecated)

The builtin pack is a **deprecated core namespace** retained only for
backward-compatible aliases. It ships no live components of its own.
All capabilities have been split into domain-specific packs.

## Migration map

| Legacy id | Current pack | Current id |
|---|---|---|
| `builtin.pool_build` | training | `training.pool_build` |
| `builtin.pool_merge` | training | `training.pool_merge` |
| `builtin.search_loras` | training | `training.search_loras` |
| `builtin.asset_cache` | training | `training.asset_cache` |
| `builtin.training_run` | training | `training.training_run` |
| `builtin.dataset_build` | training | `training.dataset_build` |
| `builtin.youtube_audio` | youtube | `youtube.youtube_audio` |
| `builtin.render` | rendering | `rendering.render` |

## When to use

- **Never.** Pick the pack that now owns the capability:
  - `editorial` for cut/transcript work
  - `foley` for spatial audio
  - `generation` for image/video synthesis
  - `fal` for fal.ai
  - `training` for dataset/training work
  - `youtube` for YouTube ingest and publish
  - `rendering` for video rendering

Aliases from `builtin.*` to current ids are declared on the owning packs and
resolve transparently, but new work should always use the current canonical ids.
