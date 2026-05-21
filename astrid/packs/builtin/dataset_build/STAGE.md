# Dataset Build

Use `builtin.dataset_build` for generic built-in video training dataset
workflows that acquire source media, split scenes, filter candidates, caption
clips, collect human review decisions, and export training manifests.

This package is scaffolded for the Milestone 1 generic dataset builder. The
runtime currently exposes only argument parsing and dry-run inspection; the
pipeline stages are implemented in later milestone batches.

## Inspect

```bash
python3 -m astrid orchestrators inspect builtin.dataset_build --json
```

## Dry Run

```bash
python3 -m astrid orchestrators run builtin.dataset_build -- \
  --config examples/configs/dataset/example.yaml \
  --out runs/dataset-build \
  --dry-run
```

## Run

```bash
python3 -m astrid orchestrators run builtin.dataset_build -- \
  --config <config.json-or-yaml> \
  --out runs/<dataset-run>
```

## Package Layout

- `source_providers/` acquires or imports source media and source metadata.
- `caption_providers/` generates or loads candidate captions.
- `filter_stages/` applies deterministic and model-backed candidate filters.
- `manifest_adapters/` exports accepted clips to downstream training formats.
- `review_ui/` contains generic dataset review static assets.
- `schemas/` contains packaged runtime JSON schemas.

## Child Executors

The orchestrator declares only these existing child executors:

- `builtin.youtube_audio`
- `builtin.scenes`
- `builtin.visual_understand`
- `builtin.video_understand`
- `builtin.human_review`

