# experiment_review

**Executor:** `iteration.experiment_review`
**Version:** 1.0
**Network:** false
**M1:** output_result_manifest: true

## Purpose

Render a deterministic, provider-independent HTML review page from a
normalized `review.json` produced by `experiment_prepare`.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `--review` | yes | Path to normalized `review.json`. |
| `--out` | yes | Output directory. |
| `--runs-dir` | no | Owning runs directory used to re-verify and link local media for offline playback. |
| `--conclusions` | no | Validated observations, inferences, and decisions for this experiment. |
| `--review-final` | no | Validated persisted rubric decisions for this experiment. |

## Outputs

| File | Description |
|------|-------------|
| `review.html` | Deterministic self-contained HTML review page. |
| `review.summary.csv` | Deterministic portable case/status/provider summary. |
| `manifest.json` | Universal result manifest (M1). |

## Behavior

1. Reads and validates `review.json` against the review contract.
2. Renders a static HTML page with:
   - Experiment header with status badges.
   - Case cards with inputs, prompt/parameters, and outputs in a 3-column grid.
   - Status badges color-coded by lifecycle.
   - Capture gap warnings, error messages, timing, and cost.
   - All untrusted text is HTML-escaped (prompts, provider names, model names,
     paths, error messages).
3. With `--runs-dir`, re-hashes each artifact and enables inline playback only
   for bytes that still match the recorded SHA-256.
4. Renders integrity diagnostics, exact captured non-secret requests, source
   manifest/run-record provenance, and evidence-bearing conclusions.
5. Output is deterministic given the same validated inputs and local bytes.

## Provider independence

The HTML renderer contains no provider-specific execution branches.
All cases are rendered through the same card template regardless of
whether they come from Fal, OpenAI, ComfyUI, Discord, or local generators.

## Security

- All untrusted text is HTML-escaped using `html.escape(text, quote=True)`.
- No provider execution logic exists in the renderer.
- No live URLs or secrets are emitted — those are stripped during normalization.
- Artifact paths accept no URI schemes or traversal. Verified local paths are
  URL-quoted and linked relative to the page; unresolved paths remain text.

## Invocation

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "iteration.experiment_review",
        kind="executor", project="demo",
    inputs={
        "review": "path/to/review.json",
        "runs_dir": "projects/my-project/runs",
    },
)
```
