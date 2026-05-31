# Built-In Dataset And Training Workflow

This workflow is the canonical path for building a reviewed video dataset and
training an LTX LoRA with the built-in tools. The Seinfeld material under
`docs/examples/seinfeld/` is historical archive content; it documents the old
prototype but does not define registered tools.

## 1. Build A Dataset

Start from a strict dataset config. The checked-in examples are lightweight
templates with placeholder licensed sources and ignored `runs/` outputs.

```bash
python3 -m astrid orchestrators run training.dataset_build -- \
  --config examples/configs/dataset/seinfeld-dataset.yaml \
  --out runs/seinfeld-dataset
```

For a CI or fixture-style run, pass review decisions explicitly:

```bash
python3 -m astrid orchestrators run training.dataset_build -- \
  --config examples/configs/dataset/seinfeld-dataset.yaml \
  --out runs/seinfeld-dataset \
  --review-decisions path/to/your/review-decisions.json
```

The dataset run writes `review_data.json`, `review_state.json`,
`final.manifest.json`, and `ai-toolkit-ltx.manifest.json` under the output
directory.

## 2. Review And Finalize

Without `--review-decisions`, `training.dataset_build` starts the generic human
review UI and waits for submit. Review accepts, rejects, or edits captions, and
accepted captions are propagated to sibling caption sidecars before manifest
export. The training workflow should consume the finalized
`ai-toolkit-ltx.manifest.json`, not provisional review data.

Existing local runs such as `runs/seinfeld-dataset` are useful only when they
already contain finalized review artifacts. If a run only has provisional
outputs, rerun the dataset builder or provide review decisions before training.

## 3. Dry-Run Training

Run a dry-run before any live spend. It validates the training config, checks
declared secrets, normalizes the manifest into the training run directory,
builds the ai-toolkit config, writes `planned_cost.json`, and performs no
network, GPU, or RunPod calls.

```bash
python3 -m astrid orchestrators run training.training_run -- \
  --config examples/configs/training/seinfeld-training.yaml \
  --dry-run
```

To use an existing finalized dataset run explicitly:

```bash
python3 -m astrid orchestrators run training.training_run -- \
  --config examples/configs/training/seinfeld-training.yaml \
  --manifest runs/seinfeld-dataset/ai-toolkit-ltx.manifest.json \
  --out runs/seinfeld-lora \
  --dry-run
```

## 4. Live Training

Live training fails closed if declared secrets are missing. Review the dry-run
artifacts and spend cap first, then confirm spend for the live run.

```bash
RUNPOD_API_KEY=... HF_TOKEN=... \
python3 -m astrid orchestrators run training.training_run -- \
  --config examples/configs/training/seinfeld-training.yaml \
  --confirm-spend
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

```bash
python3 -m astrid orchestrators run training.training_run -- \
  resume \
  --out runs/seinfeld-lora \
  --pick final \
  --notes "best checkpoint"
```

Use `--dry-run` with `resume` to inspect persisted state without mutating
remote resources:

```bash
python3 -m astrid orchestrators run training.training_run -- \
  resume \
  --out runs/seinfeld-lora \
  --dry-run \
  --json
```

## 7. Script Presets

For script generation, use the built-in script pipeline with a preset. The
Seinfeld and Always Sunny styles are data under
`astrid/packs/builtin/script_pipeline/presets/`.

```bash
python3 -m astrid executors run editorial.script_pipeline -- \
  --preset seinfeld \
  --produces-dir runs/seinfeld-script/produces
```
