---
name: vibecomfy
description: >
  VibeComfy pack — inspect, typed-edit, validate, and run ComfyUI / VibeComfy
  workflow JSON. The escape hatch for LoRAs,
  IP-adapter, ControlNet, custom samplers, and graph composition beyond
  the standard generation contracts.
---

# VibeComfy

The vibecomfy pack is the **escape hatch** for ComfyUI generation features
that fall outside the standard `generation` pack contracts. Use it directly
for LoRAs, IP-adapter, ControlNet, custom samplers, or any node-graph surgery
not covered by the opinionated `generation.generate_image` path.

## Executors

| Executor | What it does |
|---|---|
| `vibecomfy.inspect` | Emit a read-only Python-like IR projection plus structured census/topology. |
| `vibecomfy.edit` | Apply one atomic batch of typed edit operations and emit a new UI workflow artifact. |
| `vibecomfy.run` | Execute a ComfyUI / VibeComfy workflow JSON — maps to `python -m vibecomfy.cli run {workflow}`. |
| `vibecomfy.validate` | Validate a ComfyUI / VibeComfy workflow JSON without executing it — maps to `python -m vibecomfy.cli validate {workflow}`. |

## When to use

- Use `vibecomfy.run` when you need LoRAs, IP-adapter, ControlNet, custom
  samplers (DPM++ 3M, UniPC, LCM), exotic conditioning, regional prompting,
  attention injection, CFG scheduling, or any path the standard registry
  does not cover.
- Use `vibecomfy.validate` to check a workflow JSON before execution.
- Use `vibecomfy.inspect` before graph surgery. Its `workflow-ir.py` is a
  readable projection, never mutation input.
- Use `vibecomfy.edit` with a JSON operations artifact. Accepted leaf tools
  are `edit_node`, `add_node`, `remove_node`, `upsert_link`, `remove_link`, and
  `set_node_mode`; the executor wraps them in one atomic `edit_batch`.

## When NOT to use

- Do not use for standard image generation — use `generation.generate_image`
  (the recommended primary entry point).
- Do not use to understand existing media (use `understanding`) or to
  cut/render timelines (use `video_editing`).

## Authority-preserving workflow

These capabilities are admitted through the existing runtime-backed `tasks`
family. Do not add a pack command to the gateway and do not edit the Python-like
projection. Import workflow/operation files as managed objects, reference their
digests in `spec.input_digests`, and authorize the same digests with
`--input-manifest`.

```json
{
  "schema_version": 1,
  "expected_revision": 0,
  "ops": [
    {"op": "edit_node", "target": "ksampler", "field": "steps", "value": 24}
  ]
}
```

Each `ops` entry has one of these exact shapes. `target` and link endpoints are
names from the rendered projection (or stable node UIDs):

| `op` | Required fields | Optional fields |
|---|---|---|
| `edit_node` | `target`, `field`, `value` | — |
| `add_node` | `class_type` | `fields` or `widget_values`, `inputs`, `uid`, `node_id` |
| `remove_node` | `target` | — |
| `upsert_link` | `source`, `target`, `target_input` | `source_output` (defaults to `0`) |
| `remove_link` | `target`, `target_input` | — |
| `set_node_mode` | `target`, `mode` | —; mode is `enabled`, `muted`, or `bypassed` |

The edit outputs are a new `workflow.ui.json`, a fresh read-only projection,
and `edit-report.json` containing hashes, the accepted revision/delta id, and
the canonical typed delta. Feed the new workflow object's digest to
`vibecomfy.validate`, then to `vibecomfy.run`; never mutate a task input in
place.

## SDK quick-start

```python
import astrid.sdk as sdk

# Inspect and typed-edit a workflow
inspection = sdk.invoke(
    "vibecomfy.inspect", kind="executor", project="demo",
    inputs={"workflow": "./my_workflow.json"},
)
edited = sdk.invoke(
    "vibecomfy.edit", kind="executor", project="demo",
    inputs={"workflow": "./my_workflow.json", "operations": "./edits.json"},
)
edited_workflow = edited.outputs["workflow"]

# Validate the edited workflow artifact
validated = sdk.invoke(
    "vibecomfy.validate", kind="executor", project="demo",
    inputs={"workflow": edited_workflow},
)

# Run that same immutable artifact only after validation
run = sdk.invoke(
    "vibecomfy.run", kind="executor", project="demo",
    inputs={"workflow": edited_workflow},
)
```
