# Inspect Cut

**Executor**: `editorial.inspect_cut`  
**Status**: implemented  
**Role**: Auxiliary (outside the numbered pipeline)

Inspects a generated cut run directory and reports timeline, asset, and
arrangement health. This is an auxiliary debugging tool — it does not
appear in the numbered pipeline step order. Use it to inspect the outputs
of `video_editing.cut` before rendering, or to diagnose issues in an
existing brief output directory.

The executor loads the enriched arrangement (timeline + metadata +
transcript segments), builds a visual text report with three sections:

- **Script** — per-clip dialogue text with any auto-fix findings and
  warnings from the refine report (audio boundary issues, rejected
  nudges, flagged clips)
- **Structure** — ASCII track visualization (A=audio, V=visual,
  O=overlay, S=stinger) with dead-zone overlap markers, clip inventory,
  and duration/scale
- **Clip detail** — per-clip deep dive (when `--clip <order>` is
  passed) showing trim range, current/before/after transcript,
  zone overlaps, and available fix options

Supports `--json` for machine-readable output (useful in scripts),
`--no-color` for plain-text, and `--clip` to zoom into a single clip.

## SDK quick-start

Inspect a run directory:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.inspect_cut",
    inputs={"run_dir": "./runs/my-run"},
)
```

Inspect a specific clip (by arrangement order):

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.inspect_cut",
    inputs={"run_dir": "./runs/my-run", "clip": "3"},
)
```

Machine-readable JSON output:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.inspect_cut",
    inputs={"run_dir": "./runs/my-run", "json": True},
)
```

Inspect a brief output directory (post-cut):

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.inspect_cut",
    inputs={"run_dir": "./out", "no_color": True},
)
```

## Inputs

| Name    | Type      | Required | Description                               |
|---------|-----------|----------|-------------------------------------------|
| run_dir | directory | yes      | Cut run directory to inspect (positional arg) |

## Outputs

Inspect cut writes a text report to stdout (or JSON when `--json` is set).
It does not produce output files — it is a read-only inspection tool.

## Auxiliary tool

`editorial.inspect_cut` is an auxiliary executor — it is **not** part of
the numbered editorial pipeline (steps 0–14). It is a debugging and
inspection utility for examining cut run directories. Call it ad-hoc
whenever you need to understand the state of timeline/assets/metadata
before or after rendering.

It is called internally by `editorial.editor_review` (step 13) to enrich
the evidence presented to the Claude reviewer, but it is not itself a
pipeline step. There is no `pipeline_step_order` in executor.yaml and
no `depends_on` graph — it operates standalone on a single directory.
