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
| `iteration.experiment_prepare` | Normalize an experiment's provider manifests into a provider-independent review model with diagnostics. |
| `iteration.experiment_review` | Render a deterministic, provider-independent HTML review page from a normalized review.json. |
| `iteration.experiment_import` | Import an unmanaged/legacy run root (e.g. Discord-command POC) into a provider-independent experiment with an honest import report. Read-only over source; idempotent and byte-stable. |

## Orchestrators

| Orchestrator | What it does |
|---|---|
| `iteration.experiment_review_session` | Interactive, schema-validated rubric review session over a prepared experiment. Reuses `editorial.human_review` as the server and mounts each run's media under a safe per-run route. |

## Provider-independent experiments

Beyond iteration-video assembly, this pack hosts the **provider-independent
experiment** surface — a way to compare runs from any provider (or none) under
one canonical review model without executing anything.

- `iteration.experiment_import` turns an unmanaged run root (e.g. the
  Discord-command POC directory of timestamped submissions) into an
  `experiment.json` + `import.report.json` plus a synthesized `runs/` tree.
  Source evidence is read-only: media is materialized as independent
  copy-on-write clones when supported (never writable hardlinks or eager
  large-media copies), no absolute source path or signed URL is persisted, and
  ambiguous/screenshot-only submissions stay honestly `unknown`.
- `iteration.experiment_prepare` normalizes an experiment's provider manifests
  into `review.json` + `diagnostics.json`.
- `iteration.experiment_review` renders a static, deterministic HTML gallery.
- `iteration.experiment_review_session` runs the interactive rubric review,
  persisting drafts to a durable, versioned `review.state.json` (CAS-safe across
  processes) and validating the final payload against the experiment rubric.

Typical flow:

```
experiment_import  →  experiment_prepare  →  experiment_review_session
                                                       (or experiment_review for a static page)
```

The import executor wires its options through the registry; each option maps
1:1 to an `inputs` entry:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "iteration.experiment_import",
    inputs={
        "root": "./runs/discord-command-poc",
        "title": "Discord POC retrospective",
        "question": "Which submissions produced usable output?",
    },
    out="./import-out",
)
```

## When to use

- Use `iteration.prepare` → `iteration.assemble` in sequence to turn a thread's
  run history into an iteration video.
- The `video_editing.iteration_video` orchestrator sequences these automatically.
- Use the `experiment_*` executors to review/import runs from any provider
  without executing anything.

## When NOT to use

- Do not use for raw video editing or clip trimming — use the `media` pack.
- Do not use for final video rendering — use the `rendering` pack on the emitted
  hype adapter.
- Do not use the experiment executors to execute provider runs — they are
  read-only over evidence and never invoke a provider.

## SDK quick-start

```python
import astrid.sdk as sdk

# Prepare iteration data from a thread run
result = sdk.invoke(
    "iteration.prepare",
    inputs={"run_id": "<run_id>"},
    out="./out",
)

# Assemble into render-ready hype inputs
result = sdk.invoke(
    "iteration.assemble",
    inputs={"prepare_dir": "./out"},
    out="./out",
)

# Import a legacy run root into an experiment
result = sdk.invoke(
    "iteration.experiment_import",
    inputs={"root": "<run_root>"},
    out="./import-out",
)
```
