---
name: editorial
description: >
  Editorial pack: the 14-step hype video pipeline from transcribe through
  validate, plus auxiliary tools for human-in-the-loop review, notes
  ingestion, cut inspection, boundary review, and script generation.
  Cross-pack steps include scene_describe (understanding), pool_build and
  pool_merge (training), cut (video_editing), and render (rendering).
---

# Editorial

The editorial pack is the backbone of Astrid's video creation pipeline.
It runs the full 14-step progression from raw source media to a validated
rendered video, with cross-pack handoffs to understanding, training,
video_editing, and rendering.

## Pipeline stage order

The numbered pipeline runs steps 0 through 14. Steps from other packs are
shown with their owning pack in parentheses — they are not part of the
editorial pack but are essential to the pipeline flow.

| Step | Stage | Pack | Sentinel / Output | What it does |
|---|---|---|---|---|
| 0 | transcribe | editorial | `transcript.json` | Transcribe source audio to text via Whisper. |
| 1 | scenes | editorial | `scenes.json`, `scene_items.json` | Detect scene boundaries with ffmpeg-driven analysis. |
| 2 | quality_zones | editorial | `quality_zones.json` | Tag arrangement clips with per-zone quality grades. |
| 3 | shots | editorial | `shots.json` | Slice scenes into shot windows for pool building. |
| 4 | triage | editorial | `scene_triage.json` | Triage scenes by quality — gate before pool building. |
| 5 | scene_describe | understanding | `scene_descriptions.json` | Caption each scene with a vision model (OpenAI). |
| 5.5 | video_understand | understanding | — | Synchronized audio+video window inspection. Optional, interleaved between scene_describe and quote_scout. |
| 6 | quote_scout | editorial | `quote_candidates.json` | Scan transcript for quotable lines suitable for hype clips. |
| 7 | pool_build | training | `pool.json` | Build the candidate clip pool from triaged scenes. |
| 8 | pool_merge | training | `pool.json` (mutated) | Merge multiple pools into a unified pool for arrangement. |
| 9 | arrange | editorial | `arrangement.json` | Compose a brief-specific shot arrangement from the pool via LLM. |
| 10 | cut | video_editing | `hype.timeline.json`, `hype.assets.json`, `hype.metadata.json` | Assemble arrangement into the timeline+assets+metadata JSON triple for Remotion. |
| 11 | refine | editorial | `refine.json` + mutated triple | Apply targeted reviewer-driven refinements to the arrangement. |
| 12 | render | rendering | `hype.mp4` | Render the timeline to video through the Remotion compositor. |
| 13 | editor_review | editorial | `editor_review.json` | Run heuristic editorial reviewers over the rendered video. Human-in-the-loop gate. |
| 14 | validate | editorial | `validation.json` | Validate rendered video against timeline and metadata (Whisper + schema). |

### Pipeline flow diagram

```
transcribe → scenes → quality_zones → shots → triage
                 ↓
           scene_describe (understanding, step 5)
                 ↓ (optional 5.5: video_understand)
           quote_scout
                 ↓
           pool_build → pool_merge (training, steps 7-8)
                 ↓
           arrange → cut (video_editing, step 10) → refine
                 ↓
           render (rendering, step 12)
                 ↓
           editor_review → validate
```

## Auxiliary tools (outside numbered pipeline)

These executors are not part of the numbered 0–14 pipeline. They have no
`pipeline_step_order` in their executor.yaml and operate standalone.

| Executor | What it does |
|---|---|
| `editorial.human_notes` | Convert free-text human editorial notes into structured `editor_review.json` for the pipeline. Optional `--apply` chains a full revise cycle. |
| `editorial.inspect_cut` | Debugging tool: inspect a cut run directory and print a script/structure/clip text report. Supports `--json` and `--clip` flags. Called internally by `editor_review`. |
| `editorial.human_review` | Generic human-gate primitive. Serves an HTML page on localhost, collects human decisions as JSON, blocks until submit. Token-authenticated POSTs. |
| `editorial.boundary_candidates` | Package candidate video frames for visual scene-boundary review. |
| `editorial.script_pipeline` | Preset-driven creative-writing pipeline: generates short scripts through rough attempts, synthesis, style pass, and optional judging. |

## When to use

- Use `editorial.transcribe` through `editorial.validate` in pipeline
  order when running the full hype video workflow. The hype orchestrator
  (`video_editing.hype`) sequences these automatically.
- Run individual editorial executors standalone when you need to re-run
  a specific stage (e.g., re-transcribe with different settings, re-triage
  with adjusted quality thresholds).
- Use `editorial.human_notes` when you have free-text feedback and want
  it converted to structured pipeline inputs.
- Use `editorial.inspect_cut` for debugging a cut run directory — it
  prints a human-readable report of the timeline, assets, and clips.
- Use `editorial.human_review` as a generic human-in-the-loop gate for
  any review workflow (dataset review, eval-grid pick, arrangement
  approval).
- Use `editorial.boundary_candidates` when you want to visually review
  scene boundaries before committing to cuts.
- Use `editorial.script_pipeline` when you need AI-generated creative
  scripts from a preset or prompt.

## Credentials

| Env var | Used by |
|---|---|
| `OPENAI_API_KEY` | transcribe (Whisper API), arrange (LLM), refine (LLM), editor_review (Claude vision), script_pipeline (DeepSeek) |
| `ANTHROPIC_API_KEY` | editor_review (Claude vision model for frame sampling) |

## SDK quick-start

```python
# Transcribe (step 0)
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.transcribe",
    inputs={"audio": "./source.mp3"},
    out="./out",
)

# Detect scenes (step 1)
result = sdk.invoke(
    "editorial.scenes",
    inputs={"video": "./source.mp4"},
    out="./out",
)

# Quality zones (step 2)
result = sdk.invoke(
    "editorial.quality_zones",
    inputs={"video": "./source.mp4"},
    out="./out",
)

# Shots (step 3)
result = sdk.invoke(
    "editorial.shots",
    inputs={"video": "./source.mp4", "scenes": "./out/scenes.json"},
    out="./out",
)

# Triage (step 4) — quality gate before pool building
result = sdk.invoke(
    "editorial.triage",
    inputs={"scenes": "./out/scenes.json", "shots": "./out/shots.json"},
    out="./out",
)

# Quote scout (step 6) — find quotable lines
result = sdk.invoke(
    "editorial.quote_scout",
    inputs={"transcript": "./out/transcript.json"},
    out="./out",
)

# Arrange (step 9) — compose shot arrangement
result = sdk.invoke(
    "editorial.arrange",
    inputs={
        "pool": "./out/unified_pool.json",
        "brief": "./briefs/my-hype.md",
        "theme": "./themes/default.json",
    },
    out="./out",
)

# Refine (step 11) — last editorial pass before cut
result = sdk.invoke(
    "editorial.refine",
    inputs={
        "arrangement": "./out/arrangement.json",
        "pool": "./out/unified_pool.json",
        "timeline": "./out/hype.timeline.json",
        "assets": "./out/hype.assets.json",
    },
    out="./out",
)

# Editor review (step 13) — human-in-loop gate
result = sdk.invoke(
    "editorial.editor_review",
    inputs={"brief_dir": "./out", "run_dir": "./runs/my-run"},
    out="./out",
)

# Validate (step 14) — schema + Whisper validation
result = sdk.invoke(
    "editorial.validate",
    inputs={
        "video": "./out/hype.mp4",
        "timeline": "./out/hype.timeline.json",
        "metadata": "./out/hype.metadata.json",
    },
    out="./out",
)

# Human notes (auxiliary) — convert feedback to structured inputs
result = sdk.invoke(
    "editorial.human_notes",
    inputs={"notes": "./my-notes.md"},
    out="./out",
)

# Inspect cut (auxiliary) — debug a cut run directory
result = sdk.invoke(
    "editorial.inspect_cut",
    inputs={"run_dir": "./runs/my-run", "json": True},
)

# Human review (auxiliary) — serve review page
result = sdk.invoke(
    "editorial.human_review",
    inputs={"html": "./review-page.html", "data": "./data.json"},
    out="./out",
)

# Boundary candidates (auxiliary) — package frames for review
result = sdk.invoke(
    "editorial.boundary_candidates",
    inputs={
        "video": "./source.mp4",
        "manifest": "./boundary_manifest.json",
    },
    out="./out",
)

# Script pipeline (auxiliary) — generate creative scripts
result = sdk.invoke(
    "editorial.script_pipeline",
    inputs={
        "preset": "hype-intro",
        "prompt": "A dramatic opening scene",
    },
    out="./out",
)
```
