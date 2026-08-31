# Dataset And Training Workflow

This workflow is the canonical path for building a reviewed video dataset and
training an LTX LoRA with Astrid's supported tools. The surviving Seinfeld example
asset is `docs/examples/seinfeld/vocabulary.yaml`, which is used by the
training config vocabulary path.

## 1. Build A Dataset

Start from a strict dataset config. The checked-in examples are lightweight
templates with placeholder licensed sources and ignored `runs/` outputs.

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.dataset_build",
    inputs={"config": "examples/configs/dataset/seinfeld-dataset.yaml"},
    out="runs/seinfeld-dataset",
)
```

For a CI or fixture-style run, pass review decisions explicitly:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.dataset_build",
    inputs={
        "config": "examples/configs/dataset/seinfeld-dataset.yaml",
        "review_decisions": "path/to/your/review-decisions.json",
    },
    out="runs/seinfeld-dataset",
)
```

A smoke path with no-network fixtures:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.dataset_build",
    inputs={
        "config": "path/to/your/dataset-config.json",
        "review_decisions": "path/to/your/review-decisions.json",
    },
    out="runs/training-fixture",
)
```

For unattended runs, pass `--review-decisions <json>`. Without that flag, the
orchestrator starts `editorial.human_review` with the generic review UI and
waits for submit.

The dataset run writes only inside the requested `--out` directory:

- `review_data.json`
- `review_state.json`
- `review_server/human_review.final.json`
- `final.manifest.json`
- `ai-toolkit-ltx.manifest.json`
- confined clip files and sibling `<clip_id>.caption.json` sidecars under
  `clips/`

The canonical manifest includes only accepted review items. Edited review
captions are propagated to sibling caption sidecars before adapter export.

## 2. Review And Finalize

Without `--review-decisions`, `training.dataset_build` starts the generic human
review UI and waits for submit. Review accepts, rejects, or edits captions, and
accepted captions are propagated to sibling caption sidecars before manifest
export. The training workflow should consume the finalized
`ai-toolkit-ltx.manifest.json`, not provisional review data.

Existing local runs such as `runs/seinfeld-dataset` are useful only when they
already contain finalized review artifacts. If a run only has provisional
outputs, rerun the dataset builder or provide review decisions before training.

### Migration From The Historical Seinfeld Dataset Builder

Use `examples/configs/dataset/seinfeld-dataset.yaml` as the migration template.
Show-specific behavior now belongs in config:

- buckets and target counts live under `buckets`
- YouTube URLs and search queries live under `sources` and bucket
  `search_queries`
- VLM bucket-gate prompts live under `extensions.bucket_judge`
- caption prompts live under `caption.prompt_template`
- review reject reasons live under `review.reject_reasons`
- training export is selected with `manifest.adapter: ai-toolkit-ltx`

M1 reproduces the prototype's generic VLM bucket-judge and caption flow. It
does not implement the M2b top-up loop, and there is intentionally no Seinfeld
compatibility shim in built-in code. Continue using explicit config if a
show-specific dataset needs different buckets, prompts, rights policy, or
budgets.

The checked-in Seinfeld example keeps only the wired training vocabulary at
`docs/examples/seinfeld/vocabulary.yaml`. Active workflows should use
`training.dataset_build`, `training.training_run`, and
`editorial.script_pipeline` with example configs or presets rather than direct
pack-module execution.

## 3. Dry-Run Training

Run a dry-run before any live spend. It validates the training config, checks
declared secrets, normalizes the manifest into the training run directory,
builds the ai-toolkit config, writes `planned_cost.json`, and performs no
network, GPU, or RunPod calls.

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.training_run",
    inputs={"config": "examples/configs/training/seinfeld-training.yaml"},
    dry_run=True,
)
```

To use an existing finalized dataset run explicitly:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.training_run",
    inputs={
        "config": "examples/configs/training/seinfeld-training.yaml",
        "manifest": "runs/seinfeld-dataset/ai-toolkit-ltx.manifest.json",
    },
    out="runs/seinfeld-lora",
    dry_run=True,
)
```

## 4. Live Training

Live training fails closed if declared secrets are missing. Review the dry-run
artifacts and spend cap first, then confirm spend for the live run.

```python
import astrid.sdk as sdk

# requires RUNPOD_API_KEY and HF_TOKEN in the environment
result = sdk.invoke(
    "training.training_run",
    inputs={
        "config": "examples/configs/training/seinfeld-training.yaml",
        "confirm_spend": True,
    },
)
```

The run provisions compute, stages the normalized manifest and ai-toolkit
config, starts training, pulls review samples, and pauses at the checkpoint
review gate.

## 5. Review Checkpoints

Open the generated review page from the training run output, compare samples,
and choose a checkpoint label, step, basename, or remote path from
`checkpoints/checkpoint_manifest.json`. The paused state keeps the pod teardown
guard so the operator can resume safely.

## 6. Resume And Register

Resume with the chosen checkpoint. Registration pulls the selected
`.safetensors` file, writes `registered/registered_lora.json`, then tears down
the pod unless `--skip-teardown` is supplied intentionally.

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.training_run",
    inputs={"out": "runs/seinfeld-lora", "pick": "final", "notes": "best checkpoint"},
    argv=("resume",),
)
```

Use `--dry-run` with `resume` to inspect persisted state without mutating
remote resources:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "training.training_run",
    inputs={"out": "runs/seinfeld-lora"},
    argv=("resume",),
    dry_run=True,
)
```

## 7. Script Presets

For script generation, use the built-in script pipeline with a preset. The
Seinfeld and Always Sunny styles are data under
`astrid/packs/editorial/executors/script_pipeline/presets/`.

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "editorial.script_pipeline",
    inputs={
        "preset": "seinfeld",
        "produces_dir": "runs/seinfeld-script/produces",
    },
)
```
