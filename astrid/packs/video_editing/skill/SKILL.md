---
name: video_editing
description: >
  Video editing pack: orchestrators for the full hype pipeline, event
  talk videos, thumbnail generation, iteration video renders, logo
  concept grids, image-to-video animation, and grid-based variation
  editing.  Also includes the cut executor for timeline assembly.
---

# Video Editing

The video_editing pack covers seven orchestrators and one executor that
together form the video creation and editing surface of Astrid.

## Orchestrator decision tree

| Use case | Orchestrator | What it does |
|---|---|---|
| Full hype video pipeline (transcribe → render) | `video_editing.hype` | End-to-end pipeline: transcribe source, detect scenes, build clip pool, arrange shots, cut timeline, render video. The default entry point for hype videos. |
| Event talk videos (templated talks + render) | `video_editing.event_talks` | Build event talk videos from a template, search transcripts, find holding screens, and render via local ffmpeg/Remotion. |
| Thumbnail generation from video + query | `video_editing.thumbnail_maker` | Generate a set of thumbnail candidates from a source video and a text query. Plans evidence needs, discovers source frames, and renders a grid of candidates. |
| Iteration video compilation | `video_editing.iteration_video` | Prepare an iteration graph, assemble render adapter files, render through rendering.render, and finalize iteration video outputs. |
| Logo concept grid generation | `video_editing.logo_ideas` | Generate a grid of distinct logo concepts: Kimi K2 drafts prompts, then GPT Image 2 renders a composite grid (or per-image renders with `--provider z-image`). |
| Image-to-video animation | `video_editing.animate_image` | Two-stage pipeline: generate a still image via fal GPT Image 2 edit, then animate it with fal WAN 2.2 animate/move driven by a reference video. |
| Grid-based variation editing | `video_editing.vary_grid` | Iterative grid editor: take an existing grid image, pick reference cells, generate a new grid of variations via fal GPT Image 2 edit. |

## Executors

| Executor | What it does |
|---|---|
| `video_editing.cut` | Assembles an arrangement into a timeline+assets+metadata JSON triple for Remotion. Pipeline step 10 — bridges editorial arrangement to rendering. |

The `cut` executor is the timeline-assembly stage that sits between
editorial arrangement (step 9) and rendering (step 12). It consumes
`arrangement.json`, the unified clip pool, the creative brief, and an
optional theme, then produces `hype.timeline.json`, `hype.assets.json`,
and `hype.metadata.json` — the three-file input to rendering.render.

## When to use

- Use `video_editing.hype` for the full end-to-end hype video pipeline.
  This is the canonical orchestrator for turning source media into a
  finished video.
- Use `video_editing.event_talks` when you have event talk content and
  want templated video output with transcript search and holding screens.
- Use `video_editing.thumbnail_maker` when you need thumbnail candidates
  for a video — provides a query-driven planning and generation flow.
- Use `video_editing.iteration_video` for compiling iteration/experiment
  runs into a video summary.
- Use `video_editing.logo_ideas` for quick logo concept exploration via
  LLM prompt drafting and image generation.
- Use `video_editing.animate_image` to turn a still image into an
  animated video driven by motion from a reference clip.
- Use `video_editing.vary_grid` for iterative grid-based image variation
  and editing.
- Use `video_editing.cut` standalone when you have an arrangement and
  pool ready and only need the timeline assembly step.

## Credentials

| Env var | Used by |
|---|---|
| `OPENAI_API_KEY` | hype (LLM arrangement/refine), logo_ideas (Kimi K2 via Fireworks) |
| `FAL_KEY` | logo_ideas, animate_image, vary_grid |
| `FIREWORKS_API_KEY` | logo_ideas, vary_grid |

## Quick-start

```python
# Full hype pipeline (orchestrator)
import astrid.sdk as sdk
result = sdk.invoke(
    "video_editing.hype",
    inputs={"video": "./source.mp4", "brief": "./briefs/my-hype.md", "theme": "./themes/default.json"},
    out="./runs/my-run",
)

# Thumbnail candidates
result = sdk.invoke(
    "video_editing.thumbnail_maker",
    inputs={"video": "./source.mp4", "query": "epic moment"},
    out="./thumbs",
)

# Logo concept grid
result = sdk.invoke(
    "video_editing.logo_ideas",
    inputs={"prompt": "a bold tech startup logo"},
    out="./logos",
)

# Animate an image with a reference video
result = sdk.invoke(
    "video_editing.animate_image",
    inputs={"image": "./still.png", "reference_video": "./motion.mp4"},
    out="./animated",
)

# Grid variation editing
result = sdk.invoke(
    "video_editing.vary_grid",
    inputs={"grid": "./grid.png", "cells": "0,3"},
    out="./variations",
)

# Cut (executor) — assemble timeline from arrangement
result = sdk.invoke(
    "video_editing.cut",
    inputs={
        "arrangement": "./out/arrangement.json",
        "pool": "./out/unified_pool.json",
        "brief": "./briefs/my-hype.md",
    },
    out="./out",
)
```

Event talk videos run their step subcommands through the orchestrator module:

```bash
python3 -m astrid.packs.video_editing.orchestrators.event_talks.run \
  ados-sunday-template --out ./talk-output
```
