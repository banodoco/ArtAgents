---
name: iteration
description: >
  Iteration pack — builds iteration videos from thread provenance by
  gathering candidate runs, scoring quality, and assembling a canonical
  iteration timeline plus render-ready hype inputs.
---

# Iteration

The iteration pack turns a thread's run history into an iteration video artifact.
It collects thread provenance, scores quality across candidate runs, and assembles
the canonical iteration timeline with render-compatible hype inputs.

## Executors

| Executor | What it does |
|---|---|
| `iteration.prepare` | Collect thread provenance, quality scores, and candidate runs into iteration prepare artifacts. |
| `iteration.assemble` | Adapt prepared iteration data into canonical iteration artifacts and render-ready hype inputs (timeline + assets). |

## When to use

- Use `iteration.prepare` → `iteration.assemble` in sequence to turn a thread's
  run history into an iteration video.
- The `video_editing.iteration_video` orchestrator sequences these automatically.

## When NOT to use

- Do not use for raw video editing or clip trimming — use the `media` pack.
- Do not use for final video rendering — use the `rendering` pack on the emitted
  hype adapter.

## CLI quick-start

```bash
# Prepare iteration data from a thread run
python3 -m astrid executors run iteration.prepare -- --run-id <run_id> --out ./out

# Assemble into render-ready hype inputs
python3 -m astrid executors run iteration.assemble -- --prepare-dir ./out --out ./out
```
