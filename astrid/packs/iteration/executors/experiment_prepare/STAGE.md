# experiment_prepare

**Executor:** `iteration.experiment_prepare`
**Version:** 1.0
**Network:** false
**M1:** output_result_manifest: true

## Purpose

Normalize an experiment's provider manifests into a provider-independent
review model. Produces `review.json` and `diagnostics.json`.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `--experiment` | yes | Path to `experiment.json` definition file. |
| `--runs-dir` | yes | Directory containing project runs (for resolving run/manifest paths). |
| `--out` | yes | Output directory. |

## Outputs

| File | Description |
|------|-------------|
| `review.json` | Provider-independent normalized review with one entry per case. |
| `diagnostics.json` | Status counts, duplicate output groups, input-echo cases, capture gaps. |
| `manifest.json` | Universal result manifest (M1). |

## Behavior

1. Reads and validates `experiment.json` against the experiment contract.
2. For each case, resolves the run directory and reads `manifest.json`.
   - Validates a same-run `run.json` when present.
   - Verifies an optional source-manifest SHA-256 pin from `experiment.json`
     against the exact bytes being parsed.
3. Normalizes each manifest into a provider-independent review case.
   - Supports generation v2 manifests (Fal, OpenAI, local).
   - Supports universal v1 manifests (ComfyUI, Discord, etc.).
4. Produces `diagnostics.json` with aggregation.
5. Writes a universal result manifest.

## Provider independence

This executor does not contain any provider-specific execution logic.
It only reads `manifest.json` files and maps them to the common review
model using schema-aware normalization.

## Failure handling

- Missing run directories: first-class failed case with a recovery detail.
- Missing manifests: first-class failed case with a capture gap.
- Invalid experiment: error with schema validation message.
- Corrupted manifests: case is recorded with `missing_manifest` capture gap.
- Source-manifest digest mismatch: the affected case fails closed and the
  mismatch appears in both review diagnostics and the rendered page.

## Invocation

```bash
python3 -m astrid executors run iteration.experiment_prepare \
  --experiment path/to/experiment.json \
  --runs-dir projects/my-project/runs \
  --out ./out
```
