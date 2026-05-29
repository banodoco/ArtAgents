# video_editing.thumbnail_maker

Plan source evidence and generate thumbnail candidates for a video/query pair.
Uses deterministic keyword-based evidence planning and a subcommand-driven
pipeline: resolve-video, plan-evidence, discover-video-evidence,
build-reference-pack, generate-thumbnails.

## When to Use

Use when you need thumbnail candidates derived from a source video, guided by
a query string (e.g., "dramatic speaker portrait"). The planner classifies the
query into person/scene/text/emotion needs and emits evidence stubs.

## Invocation

```bash
python3 -m astrid orchestrators run video_editing.thumbnail_maker \
  -- --video source.mp4 --query "intense reaction moment" --out runs/thumbs
```

Key flags: `--video`, `--query` (default `"auto"`), `--out` (required for full
run), `--count` (default 1), `--size` (default `1536x864`), `--model`
(default `gpt-image-2`), `--dry-run`, `--project`.

## Outputs

```
{out}/
  plan.json                # plan v2
  run.json                 # run provenance
  evidence/
    evidence-plan.json     # keyword-classified evidence needs
    discover-manifest.json # candidate evidence metadata
  references/
    reference-pack.json    # reference-pack manifest
  prompts/                 # (reserved for future use)
  generated/
    thumb-001.png ...      # placeholder generated thumbnails
  review/                  # (reserved for review artifacts)
```
