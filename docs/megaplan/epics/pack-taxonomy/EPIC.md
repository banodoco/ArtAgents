# Pack Taxonomy Epic

## Goal

Replace Astrid's origin-shaped pack layout (`builtin`, `external`) with
purpose-shaped packs whose default/bundled/integration status is metadata, not
part of the pack id.

The target model is:

- **Pack**: installable/discoverable capability surface.
- **Capability**: executor, orchestrator, or element inside a pack.
- **Bundle/category**: visual grouping in CLI/docs, not a filesystem folder.
- **Origin/defaultness**: metadata such as `origin`, `install_tier`,
  `pack_type`, `stability`, not a name like `builtin_media`.

## Locked Direction

Purpose-named packs are the conceptual surface:

```text
media
rendering
understanding
generation
editorial
video_editing
foley
iteration
training
reigh
youtube
fal
vibecomfy
runpod
moirae
examples
local
```

`builtin` and `external` are compatibility origins, not future product
abstractions. They should dissolve over the chain, with old ids kept working
through aliases.

## Flexibility

This structure deliberately makes later reclassification cheap. Moving a pack
from default to optional, or from "bundled standard" to "integration", should be
a manifest/config/docs change, not a rename. The physical pack id should express
purpose (`media`, `fal`, `foley`); metadata should express install status and
source.

## Source Evidence

This epic is informed by the DeepSeek fan-out in:

- `.tmp/pack-taxonomy-results/01-current-capability-inventory.txt`
- `.tmp/pack-taxonomy-results/02-runtime-discovery-constraints.txt`
- `.tmp/pack-taxonomy-results/03-workflow-boundary-analysis.txt`
- `.tmp/pack-taxonomy-results/04-integration-boundary-analysis.txt`
- `.tmp/pack-taxonomy-results/05-elements-theme-boundary-analysis.txt`
- `.tmp/pack-taxonomy-results/06-demo-lab-pack-audit.txt`
- `.tmp/pack-taxonomy-results/07-compatibility-alias-plan.txt`
- `.tmp/pack-taxonomy-results/08-cli-docs-user-shape.txt`

The reports live in ignored `.tmp/`; this directory captures the durable
decisions needed for the chain.

## Target Ownership

Initial target placement:

```text
media:
  clip_extract, transcribe, scenes, shots, tile_video

rendering:
  render, asset_cache, validate, inspect_cut, base element contracts

understanding:
  understand, audio_understand, visual_understand, video_understand,
  scene_describe

generation:
  generate_image, generate_image_openai, generate_video, sprite_sheet,
  search_loras, animate_image, vary_grid, logo_ideas

editorial:
  quote_scout, triage, boundary_candidates, quality_zones, arrange, refine,
  pool_build, pool_merge, editor_review, human_review, human_notes

video_editing:
  hype orchestrator, event_talks, and workflow-specific glue if not general

foley:
  foley_map, foley_review, spatial_audio_page

iteration:
  iteration_video, prepare, assemble

training:
  dataset_build, training_run

reigh:
  publish, open_in_reigh, reigh_data

youtube:
  youtube_audio, upload

fal:
  fal_foley

vibecomfy:
  run, validate

runpod:
  provision, exec, pull, teardown, session

moirae:
  render wrapper
```

Known ambiguous placements may be adjusted by the migration sprint if the code
shows a stronger boundary:

- `cut`: video-editing workflow glue vs generic editorial/timeline assembly.
- `tile_video`: media primitive vs foley-only helper; default to `media`.
- `scene_describe`: understanding primitive vs hype-coupled editorial output;
  default to `understanding` only if its schema is made generic.
- `youtube_audio`: YouTube integration vs media ingest; default to `youtube`
  because provider-specific behavior matters.
- `html_canvas_effect`: dev/local scaffolding vs rendering; default to dev/local
  if moving it out does not degrade discoverability.

## Milestones

1. **Foundation**: add taxonomy metadata, grouped CLI output, docs, and fix the
   immediate `text_review` visibility leak.
2. **Aliases**: add manifest-declared aliases and make old ids resolve through
   registries before any broad file moves.
3. **Examples Cleanup**: delete/move hidden scaffold/demo packs and remove
   accidental duplicate `clip_extract` product exposure.
4. **Physical Migration**: split `builtin`, `external`, and `upload` into
   purpose-named packs while preserving aliases and tests.

## Stop Lines

- Do not physically move `builtin` capabilities before alias loading is tested.
- Do not keep shim pack directories unless the alias layer is proven
  insufficient.
- Do not name packs `builtin_*`; use metadata for bundled/default status.
- Do not turn individual elements into packs. Base element contracts belong to
  rendering; concrete visual implementations belong to themes if/when theme
  packs exist.
- Do not claim `hype` is the domain. `hype` is a recipe/orchestrator; the pack
  should be `video_editing` or a comparably purpose-shaped name.
