# M4: Physical Pack Migration Map

> **Status**: Locked contract for batch execution. Every file move, manifest rewrite, and alias registration must conform to this map.

## Overview

M4 physically relocates capabilities from the legacy `builtin`, `external`, and `upload` packs into domain-specific direct-child packs under `astrid/packs/`. Old canonical ids become pack-level aliases; new canonical ids become the sole active identity.

**Unchanged canonical ids** (stay in place):
- `media.clip_extract` — under `astrid/packs/media/executors/clip_extract/`
- `iteration.prepare` — under `astrid/packs/iteration/executors/prepare/`
- `iteration.assemble` — under `astrid/packs/iteration/executors/assemble/`

**Retired packs** (removed after migration is green):
- `astrid/packs/builtin/`
- `astrid/packs/external/`
- `astrid/packs/upload/`

**New target packs** (13 direct-child packs):
`rendering`, `understanding`, `generation`, `editorial`, `video_editing`, `foley`, `training`, `reigh`, `youtube`, `fal`, `vibecomfy`, `runpod`, `moirae`

---

## Executor Migration Map

### → `rendering` (domain: media, creates/manages render outputs and visual effects)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.render` | `rendering.render` | `astrid/packs/builtin/executors/render/` | `astrid/packs/rendering/executors/render/` | Core render executor; primary rendering capability |
| `builtin.html_canvas_effect` | `rendering.html_canvas_effect` | `astrid/packs/builtin/executors/html_canvas_effect/` | `astrid/packs/rendering/executors/html_canvas_effect/` | **Edge case**: Creates render effect elements and explicitly depends on `rendering.render` |
| `builtin.sprite_sheet` | `rendering.sprite_sheet` | `astrid/packs/builtin/executors/sprite_sheet/` | `astrid/packs/rendering/executors/sprite_sheet/` | Generates sprite sheet assets; rendering-domain output |

### → `understanding` (domain: media, VLM/audio content analysis and captioning)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.scene_describe` | `understanding.scene_describe` | `astrid/packs/builtin/executors/scene_describe/` | `astrid/packs/understanding/executors/scene_describe/` | **Edge case**: VLM captioning boundary is stronger than pipeline-stage ancestry |
| `builtin.understand` | `understanding.understand` | `astrid/packs/builtin/executors/understand/` | `astrid/packs/understanding/executors/understand/` | General content understanding |
| `builtin.video_understand` | `understanding.video_understand` | `astrid/packs/builtin/executors/video_understand/` | `astrid/packs/understanding/executors/video_understand/` | Video content analysis |
| `builtin.visual_understand` | `understanding.visual_understand` | `astrid/packs/builtin/executors/visual_understand/` | `astrid/packs/understanding/executors/visual_understand/` | Visual/frame content analysis |
| `builtin.audio_understand` | `understanding.audio_understand` | `astrid/packs/builtin/executors/audio_understand/` | `astrid/packs/understanding/executors/audio_understand/` | Audio content analysis |

### → `generation` (domain: generation, image/video generative AI)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.generate_image` | `generation.generate_image` | `astrid/packs/builtin/executors/generate_image/` | `astrid/packs/generation/executors/generate_image/` | Primary image generation with model catalog |
| `builtin.generate_image_openai` | `generation.generate_image_openai` | `astrid/packs/builtin/executors/generate_image_openai/` | `astrid/packs/generation/executors/generate_image_openai/` | OpenAI DALL-E image generation |
| `builtin.generate_video` | `generation.generate_video` | `astrid/packs/builtin/executors/generate_video/` | `astrid/packs/generation/executors/generate_video/` | Video generation |

### → `editorial` (domain: editorial, clip review/selection/refinement pipeline)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.inspect_cut` | `editorial.inspect_cut` | `astrid/packs/builtin/executors/inspect_cut/` | `astrid/packs/editorial/executors/inspect_cut/` | Cut quality inspection |
| `builtin.refine` | `editorial.refine` | `astrid/packs/builtin/executors/refine/` | `astrid/packs/editorial/executors/refine/` | Clip refinement/improvement |
| `builtin.editor_review` | `editorial.editor_review` | `astrid/packs/builtin/executors/editor_review/` | `astrid/packs/editorial/executors/editor_review/` | Editor-facing review workflow |
| `builtin.human_review` | `editorial.human_review` | `astrid/packs/builtin/executors/human_review/` | `astrid/packs/editorial/executors/human_review/` | Human-in-the-loop review |
| `builtin.human_notes` | `editorial.human_notes` | `astrid/packs/builtin/executors/human_notes/` | `astrid/packs/editorial/executors/human_notes/` | Human annotation/notes |
| `builtin.triage` | `editorial.triage` | `astrid/packs/builtin/executors/triage/` | `astrid/packs/editorial/executors/triage/` | Clip triage categorization |
| `builtin.scenes` | `editorial.scenes` | `astrid/packs/builtin/executors/scenes/` | `astrid/packs/editorial/executors/scenes/` | Scene detection |
| `builtin.shots` | `editorial.shots` | `astrid/packs/builtin/executors/shots/` | `astrid/packs/editorial/executors/shots/` | Shot boundary detection |
| `builtin.quality_zones` | `editorial.quality_zones` | `astrid/packs/builtin/executors/quality_zones/` | `astrid/packs/editorial/executors/quality_zones/` | Quality zone analysis |
| `builtin.boundary_candidates` | `editorial.boundary_candidates` | `astrid/packs/builtin/executors/boundary_candidates/` | `astrid/packs/editorial/executors/boundary_candidates/` | Edit boundary proposals |
| `builtin.quote_scout` | `editorial.quote_scout` | `astrid/packs/builtin/executors/quote_scout/` | `astrid/packs/editorial/executors/quote_scout/` | Quote/highlight detection |
| `builtin.script_pipeline` | `editorial.script_pipeline` | `astrid/packs/builtin/executors/script_pipeline/` | `astrid/packs/editorial/executors/script_pipeline/` | Script-to-edit pipeline |
| `builtin.validate` | `editorial.validate` | `astrid/packs/builtin/executors/validate/` | `astrid/packs/editorial/executors/validate/` | Content validation |
| `builtin.arrange` | `editorial.arrange` | `astrid/packs/builtin/executors/arrange/` | `astrid/packs/editorial/executors/arrange/` | Clip arrangement/ordering |
| `builtin.transcribe` | `editorial.transcribe` | `astrid/packs/builtin/executors/transcribe/` | `astrid/packs/editorial/executors/transcribe/` | Speech transcription (editorial pipeline stage) |

### → `video_editing` (domain: media, timeline editing and video production orchestrators)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.cut` | `video_editing.cut` | `astrid/packs/builtin/executors/cut/` | `astrid/packs/video_editing/executors/cut/` | **Edge case**: Strongest coupling is hype timeline assembly and managed timeline writes |

### → `foley` (domain: media, audio/foley processing)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.foley_review` | `foley.foley_review` | `astrid/packs/builtin/executors/foley_review/` | `astrid/packs/foley/executors/foley_review/` | Foley review workflow |
| `builtin.tile_video` | `foley.tile_video` | `astrid/packs/builtin/executors/tile_video/` | `astrid/packs/foley/executors/tile_video/` | **Edge case**: Strongest runtime caller is `foley_map`, despite generic media mechanics |

### → `training` (domain: development, model training and dataset management)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.pool_build` | `training.pool_build` | `astrid/packs/builtin/executors/pool_build/` | `astrid/packs/training/executors/pool_build/` | Training data pool construction |
| `builtin.pool_merge` | `training.pool_merge` | `astrid/packs/builtin/executors/pool_merge/` | `astrid/packs/training/executors/pool_merge/` | Training data pool merging |
| `builtin.search_loras` | `training.search_loras` | `astrid/packs/builtin/executors/search_loras/` | `astrid/packs/training/executors/search_loras/` | LoRA model search/discovery |
| `builtin.asset_cache` | `training.asset_cache` | `astrid/packs/builtin/executors/asset_cache/` | `astrid/packs/training/executors/asset_cache/` | Training asset caching |

### → `reigh` (domain: integration, Reigh platform integration)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.reigh_data` | `reigh.reigh_data` | `astrid/packs/builtin/executors/reigh_data/` | `astrid/packs/reigh/executors/reigh_data/` | Reigh data operations |
| `builtin.open_in_reigh` | `reigh.open_in_reigh` | `astrid/packs/builtin/executors/open_in_reigh/` | `astrid/packs/reigh/executors/open_in_reigh/` | Open content in Reigh |
| `builtin.spatial_audio_page` | `reigh.spatial_audio_page` | `astrid/packs/builtin/executors/spatial_audio_page/` | `astrid/packs/reigh/executors/spatial_audio_page/` | Spatial audio page rendering |
| `builtin.publish` | `reigh.publish` | `astrid/packs/builtin/executors/publish/` | `astrid/packs/reigh/executors/publish/` | Publish timeline/assets into a Reigh project |

### → `youtube` (domain: integration, YouTube source acquisition and publishing)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.youtube_audio` | `youtube.youtube_audio` | `astrid/packs/builtin/executors/youtube_audio/` | `astrid/packs/youtube/executors/youtube_audio/` | **Edge case**: YouTube network/source acquisition boundary is stronger than generic media |
| `upload.youtube` | `youtube.upload` | `astrid/packs/upload/executors/youtube/` | `astrid/packs/youtube/executors/upload/` | YouTube video upload (moved from upload pack) |

### → `fal` (domain: integration, fal.ai API integration)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `external.fal_foley` | `fal.fal_foley` | `astrid/packs/external/fal_foley/` | `astrid/packs/fal/executors/fal_foley/` | fal.ai foley/audio generation |

### → `vibecomfy` (domain: integration, VibeComfy/ComfyUI workflow execution)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `external.vibecomfy.run` | `vibecomfy.run` | `astrid/packs/external/vibecomfy/executor.yaml` (multi-executor) | `astrid/packs/vibecomfy/executors/run/` | Run VibeComfy workflow |
| `external.vibecomfy.validate` | `vibecomfy.validate` | `astrid/packs/external/vibecomfy/executor.yaml` (multi-executor) | `astrid/packs/vibecomfy/executors/validate/` | Validate VibeComfy workflow |

### → `runpod` (domain: infrastructure, RunPod GPU provisioning and execution)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `external.runpod.provision` | `runpod.provision` | `astrid/packs/external/runpod/executor.yaml` (multi-executor) | `astrid/packs/runpod/executors/provision/` | Provision RunPod GPU pod |
| `external.runpod.exec` | `runpod.exec` | `astrid/packs/external/runpod/executor.yaml` (multi-executor) | `astrid/packs/runpod/executors/exec/` | Execute script on RunPod pod |
| `external.runpod.pull` | `runpod.pull` | `astrid/packs/external/runpod/executor.yaml` (multi-executor) | `astrid/packs/runpod/executors/pull/` | Pull artifacts from RunPod pod |
| `external.runpod.teardown` | `runpod.teardown` | `astrid/packs/external/runpod/executor.yaml` (multi-executor) | `astrid/packs/runpod/executors/teardown/` | Terminate RunPod pod |
| `external.runpod.session` | `runpod.session` | `astrid/packs/external/runpod/executor.yaml` (multi-executor) | `astrid/packs/runpod/executors/session/` | Composite provision→exec→teardown session |

### → `moirae` (domain: integration, Moirae integration)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `external.moirae` | `moirae.moirae` | `astrid/packs/external/moirae/` | `astrid/packs/moirae/executors/moirae/` | Moirae API integration |

---

## Orchestrator Migration Map

### → `video_editing` (domain: media, timeline editing and video production orchestrators)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.hype` | `video_editing.hype` | `astrid/packs/builtin/orchestrators/hype/` | `astrid/packs/video_editing/orchestrators/hype/` | Primary hype video production orchestrator |
| `builtin.event_talks` | `video_editing.event_talks` | `astrid/packs/builtin/orchestrators/event_talks/` | `astrid/packs/video_editing/orchestrators/event_talks/` | Event talks video production |
| `builtin.thumbnail_maker` | `video_editing.thumbnail_maker` | `astrid/packs/builtin/orchestrators/thumbnail_maker/` | `astrid/packs/video_editing/orchestrators/thumbnail_maker/` | Thumbnail generation orchestrator |
| `builtin.iteration_video` | `video_editing.iteration_video` | `astrid/packs/builtin/orchestrators/iteration_video/` | `astrid/packs/video_editing/orchestrators/iteration_video/` | Iterative video refinement |
| `builtin.animate_image` | `video_editing.animate_image` | `astrid/packs/builtin/orchestrators/animate_image/` | `astrid/packs/video_editing/orchestrators/animate_image/` | Image animation production |
| `builtin.logo_ideas` | `video_editing.logo_ideas` | `astrid/packs/builtin/orchestrators/logo_ideas/` | `astrid/packs/video_editing/orchestrators/logo_ideas/` | Logo concept generation |
| `builtin.vary_grid` | `video_editing.vary_grid` | `astrid/packs/builtin/orchestrators/vary_grid/` | `astrid/packs/video_editing/orchestrators/vary_grid/` | Variation grid generation |

### → `foley` (domain: media, audio/foley processing)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.foley_map` | `foley.foley_map` | `astrid/packs/builtin/orchestrators/foley_map/` | `astrid/packs/foley/orchestrators/foley_map/` | Foley sound mapping orchestrator; primary caller of `foley.tile_video` |

### → `training` (domain: development, model training and dataset management)

| Old ID | New Canonical ID | Source Path | Destination Path | Rationale |
|--------|-----------------|-------------|------------------|-----------|
| `builtin.training_run` | `training.training_run` | `astrid/packs/builtin/orchestrators/training_run/` | `astrid/packs/training/orchestrators/training_run/` | Full training run orchestrator |
| `builtin.dataset_build` | `training.dataset_build` | `astrid/packs/builtin/orchestrators/dataset_build/` | `astrid/packs/training/orchestrators/dataset_build/` | Dataset construction orchestrator |

---

## Element Migration Map

All elements move from `builtin/elements/` into `rendering/elements/`, because elements are render-time visual components consumed by the rendering system. Each `element.yaml` gets its `metadata.pack_id` (or equivalent pack identity field) set to `rendering`.

### Animations (→ `rendering/elements/animations/`)

| Old ID | New ID | Source Path | Destination Path |
|--------|--------|-------------|------------------|
| `fade-up` | `fade-up` (unchanged) | `astrid/packs/builtin/elements/animations/fade-up/` | `astrid/packs/rendering/elements/animations/fade-up/` |
| `fade` | `fade` (unchanged) | `astrid/packs/builtin/elements/animations/fade/` | `astrid/packs/rendering/elements/animations/fade/` |
| `scale-in` | `scale-in` (unchanged) | `astrid/packs/builtin/elements/animations/scale-in/` | `astrid/packs/rendering/elements/animations/scale-in/` |
| `slide-left` | `slide-left` (unchanged) | `astrid/packs/builtin/elements/animations/slide-left/` | `astrid/packs/rendering/elements/animations/slide-left/` |
| `slide-up` | `slide-up` (unchanged) | `astrid/packs/builtin/elements/animations/slide-up/` | `astrid/packs/rendering/elements/animations/slide-up/` |
| `type-on` | `type-on` (unchanged) | `astrid/packs/builtin/elements/animations/type-on/` | `astrid/packs/rendering/elements/animations/type-on/` |

### Effects (→ `rendering/elements/effects/`)

| Old ID | New ID | Source Path | Destination Path |
|--------|--------|-------------|------------------|
| `text-card` | `text-card` (unchanged) | `astrid/packs/builtin/elements/effects/text-card/` | `astrid/packs/rendering/elements/effects/text-card/` |

### Transitions (→ `rendering/elements/transitions/`)

| Old ID | New ID | Source Path | Destination Path |
|--------|--------|-------------|------------------|
| `cross-fade` | `cross-fade` (unchanged) | `astrid/packs/builtin/elements/transitions/cross-fade/` | `astrid/packs/rendering/elements/transitions/cross-fade/` |
| `fade` | `fade` (unchanged) | `astrid/packs/builtin/elements/transitions/fade/` | `astrid/packs/rendering/elements/transitions/fade/` |

### Shared (→ `rendering/elements/_shared/`)

| Source Path | Destination Path |
|-------------|------------------|
| `astrid/packs/builtin/elements/_shared/contracts.ts` | `astrid/packs/rendering/elements/_shared/contracts.ts` |

---

## Unchanged Capabilities (Stay Canonical In Place)

These capabilities are already in their correct domain packs. They are NOT moved.

| ID | Kind | Path | Notes |
|----|------|------|-------|
| `media.clip_extract` | executor | `astrid/packs/media/executors/clip_extract/` | Lossless video clip extraction via ffmpeg. Remains the single canonical clip_extract. |
| `iteration.prepare` | executor | `astrid/packs/iteration/executors/prepare/` | Iteration preparation step. |
| `iteration.assemble` | executor | `astrid/packs/iteration/executors/assemble/` | Iteration assembly step. |

---

## Edge Case Placement Rationale

These five capabilities required inspection-backed decisions because their strongest coupling was not to the obvious pack implied by their name or mechanics:

### `builtin.cut` → `video_editing.cut`

**Evidence**: Cut operations are primarily driven by the `hype` orchestrator's timeline assembly pipeline and managed timeline writes. The `video_editing` pack is the home of timeline editing orchestrators (`hype`, `event_talks`, `thumbnail_maker`), making `cut` a natural member of that domain. Placing it in `editorial` would separate it from its primary orchestration context.

### `builtin.tile_video` → `foley.tile_video`

**Evidence**: Despite generic media mechanics (tiling video frames into a grid), the strongest runtime caller is `foley_map` (the foley mapping orchestrator). Placing it in `foley` keeps it co-located with its primary consumer, even though a future refactor might pull generic tiling into a shared media utility.

### `builtin.scene_describe` → `understanding.scene_describe`

**Evidence**: Scene description uses VLM (Vision Language Model) captioning as its core operation. The VLM captioning boundary is stronger than any editorial pipeline-stage ancestry. `understanding` is the domain pack for all VLM/audio analysis capabilities (`video_understand`, `visual_understand`, `audio_understand`), making `scene_describe` a natural member.

### `builtin.youtube_audio` → `youtube.youtube_audio`

**Evidence**: YouTube audio acquisition involves network calls to YouTube's source infrastructure. The YouTube network/source acquisition boundary is stronger than a generic "media download" classification. Placing it in `youtube` alongside `youtube.upload` creates a coherent YouTube integration pack.

### `builtin.html_canvas_effect` → `rendering.html_canvas_effect`

**Evidence**: This executor creates render effect elements and explicitly depends on `rendering.render` for its output pipeline. The coupling to the rendering system is tighter than any editorial use case. Placing it in `rendering` keeps it co-located with `render` and `sprite_sheet`.

---

## Target Pack Taxonomy Defaults

All new packs use these settled defaults per SD3:

| Pack | origin | install_tier | pack_type | domain | stability | support |
|------|--------|-------------|-----------|--------|-----------|---------|
| `rendering` | builtin | core | capability | media | stable | core |
| `understanding` | builtin | core | capability | media | stable | core |
| `generation` | builtin | core | capability | generation | stable | core |
| `editorial` | builtin | core | capability | editorial | stable | core |
| `video_editing` | builtin | core | capability | media | stable | core |
| `foley` | builtin | core | capability | media | stable | core |
| `training` | builtin | core | capability | development | stable | core |
| `reigh` | builtin | core | capability | integration | stable | core |
| `youtube` | builtin | core | capability | integration | stable | core |
| `fal` | external | core | capability | integration | stable | core |
| `vibecomfy` | external | core | capability | integration | stable | core |
| `runpod` | external | core | capability | infrastructure | stable | core |
| `moirae` | external | core | capability | integration | stable | core |

---

## Alias Contract

Every old canonical id becomes a pack-level alias in the destination pack's `pack.yaml`. The alias resolver in `astrid/core/executor/registry.py` and `astrid/core/orchestrator/registry.py` already resolves aliases before lookup, so `registry.get('builtin.render')` will route to `rendering.render` after the alias is registered.

**Key aliases** (representative; full set mirrors the tables above):

| Legacy ID | Alias Target | Registered In |
|-----------|-------------|---------------|
| `builtin.render` | `rendering.render` | `rendering/pack.yaml` |
| `builtin.hype` | `video_editing.hype` | `video_editing/pack.yaml` |
| `builtin.cut` | `video_editing.cut` | `video_editing/pack.yaml` |
| `builtin.scene_describe` | `understanding.scene_describe` | `understanding/pack.yaml` |
| `builtin.tile_video` | `foley.tile_video` | `foley/pack.yaml` |
| `builtin.youtube_audio` | `youtube.youtube_audio` | `youtube/pack.yaml` |
| `builtin.html_canvas_effect` | `rendering.html_canvas_effect` | `rendering/pack.yaml` |
| `external.vibecomfy.run` | `vibecomfy.run` | `vibecomfy/pack.yaml` |
| `external.vibecomfy.validate` | `vibecomfy.validate` | `vibecomfy/pack.yaml` |
| `external.runpod.provision` | `runpod.provision` | `runpod/pack.yaml` |
| `external.runpod.exec` | `runpod.exec` | `runpod/pack.yaml` |
| `external.runpod.pull` | `runpod.pull` | `runpod/pack.yaml` |
| `external.runpod.teardown` | `runpod.teardown` | `runpod/pack.yaml` |
| `external.runpod.session` | `runpod.session` | `runpod/pack.yaml` |
| `external.fal_foley` | `fal.fal_foley` | `fal/pack.yaml` |
| `external.moirae` | `moirae.moirae` | `moirae/pack.yaml` |
| `upload.youtube` | `youtube.upload` | `youtube/pack.yaml` |

For all `builtin.*` executors/orchestrators not listed above, the alias follows the pattern `builtin.<name>` → `<target_pack>.<name>` as per the tables above.

---

## Verification Checklist

After physical relocation, verify:

1. `python3 -m astrid executors inspect rendering.render --json` returns the canonical executor
2. `python3 -m astrid executors inspect builtin.render --json` resolves through alias
3. `python3 -m astrid orchestrators inspect video_editing.hype --json` returns the canonical orchestrator
4. `python3 -m astrid orchestrators inspect builtin.hype --json` resolves through alias
5. `python3 -m astrid executors inspect media.clip_extract --json` still works (unchanged)
6. `python3 -m astrid executors inspect iteration.prepare --json` still works (unchanged)
7. `python3 -m astrid executors inspect iteration.assemble --json` still works (unchanged)
8. No active `astrid.packs.builtin`, `astrid.packs.external`, or `astrid.packs.upload` imports remain in framework code
9. All moved manifests have correct `id`, `metadata.runtime_module`, and `command.argv` strings
10. Pack validation passes for every new/changed pack
