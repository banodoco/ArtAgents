# M4: Physical Pack Migration

## Outcome

Physically migrate `builtin`, `external`, and `upload` capabilities into
purpose-named packs while preserving compatibility through the M2 alias layer.

## Scope

In:

- Create purpose-named packs as needed:
  `media`, `rendering`, `understanding`, `generation`, `editorial`,
  `video_editing`, `foley`, `training`, `reigh`, `youtube`, `fal`,
  `vibecomfy`, `runpod`, `moirae`.
- Move executor/orchestrator/element files into their target packs.
- Update manifests and runtime entrypoints.
- Update imports and subprocess/module paths.
- Remove or retire `builtin`, `external`, and `upload` only after aliases and
  tests prove compatibility.
- Remove `validate.py` special handling that only exists for the old builtin
  layout, if safe.
- Fix `_paths.executor_argv()` and any other hardcoded
  `astrid.packs.builtin...` assumptions.
- Update docs and generated capability index.
- Run focused tests plus the repo's standard CI command.

Out:

- Do not change executor/orchestrator behavior beyond path/id migration.
- Do not rename user-facing recipes unless aliases preserve old names.
- Do not introduce nested pack discovery; packs remain direct children of
  `astrid/packs`.
- Do not solve unrelated rendering/theme architecture beyond placing current
  base element contracts.

## Locked Target Placement

Default target map:

- `media`: `clip_extract`, `transcribe`, `scenes`, `shots`, `tile_video`
- `rendering`: `render`, `asset_cache`, `validate`, `inspect_cut`, base element
  contracts
- `understanding`: `understand`, `audio_understand`, `visual_understand`,
  `video_understand`, `scene_describe`
- `generation`: image/video generation executors plus `sprite_sheet`,
  `search_loras`, `animate_image`, `vary_grid`, `logo_ideas`
- `editorial`: quote/triage/arrange/refine/pool/review/human-notes workflow
  primitives
- `video_editing`: `hype`, `event_talks`, and workflow-specific glue
- `foley`: `foley_map`, `foley_review`, `spatial_audio_page`
- `iteration`: `iteration_video`, `prepare`, `assemble`
- `training`: `dataset_build`, `training_run`
- `reigh`: `publish`, `open_in_reigh`, `reigh_data`
- `youtube`: `youtube_audio`, `upload`
- `fal`: `fal_foley`
- `vibecomfy`: `run`, `validate`
- `runpod`: `provision`, `exec`, `pull`, `teardown`, `session`
- `moirae`: Moirae wrapper

If code inspection reveals a stronger boundary, update the migration note and
tests; do not silently improvise.

## Compatibility Requirements

- Existing `builtin.*`, `external.*`, and `upload.*` ids used in plans, docs, or
  command examples continue to resolve through aliases.
- Existing pack discovery remains direct-child based.
- Existing local pack override semantics continue to work.
- Existing skill installation and capability index generation continue to work.

## Touchpoints

- `astrid/packs/builtin`
- `astrid/packs/external`
- `astrid/packs/upload`
- `astrid/packs/iteration`
- `astrid/core/pack.py`
- `astrid/core/executor/registry.py`
- `astrid/core/orchestrator/registry.py`
- `astrid/packs/validate.py`
- `astrid/_paths.py`
- `astrid/pipeline.py`
- docs, examples, generated capability index
- tests importing old module paths or ids

## Done Criteria

- Old ids resolve to new capabilities.
- New canonical ids are discoverable and inspectable.
- No stale `builtin`/`external` hardcoded runtime assumption remains unless
  explicitly documented as a compatibility shim.
- Focused tests pass.
- Full standard CI passes.
