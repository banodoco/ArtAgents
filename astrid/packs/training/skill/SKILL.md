---
name: training
description: >
  Training pack — build video training datasets and run LoRA training
  end to end: clip pools, captioning/review, RunPod-backed trainer
  execution, and checkpoint registration.  Drives the runpod pack
  under the hood.
---

# Training

The training pack assembles video training datasets and runs LoRA training jobs.
It builds clip pools, merges them, searches Hugging Face for LoRAs, manages an
asset cache, and orchestrates end-to-end training runs on RunPod GPUs.

## Executors

| Executor | What it does |
|---|---|
| `training.pool_build` | Build the candidate clip pool from triaged source-video scenes. Pipeline step 7. |
| `training.pool_merge` | Merge multiple candidate clip pools into a unified pool for arrangement. Pipeline step 8. |
| `training.search_loras` | Search Hugging Face Hub for LoRAs associated with a base model. |
| `training.asset_cache` | Manage the repo-local hype asset cache (download, prune, list). |

## Orchestrators

| Orchestrator | What it does |
|---|---|
| `training.dataset_build` | Build a generic reviewed video training dataset from configured sources. |
| `training.training_run` | Run a generic LoRA training job from a prepared dataset manifest — provisions RunPod GPUs, executes the trainer remotely, pulls checkpoints, and registers artifacts. |

## When to use

- Use `training.dataset_build` to assemble a complete video training dataset
  (acquire, split, caption, review).
- Use `training.training_run` to run a LoRA training job end to end.
- Use `training.pool_build` and `training.pool_merge` as part of the editorial
  pipeline (steps 7–8).
- Use `training.search_loras` to discover LoRAs on Hugging Face.

## When NOT to use

- Do not use for raw GPU provisioning or one-off remote script execution — use
  the `runpod` pack for bare pod lifecycle control.

## Credentials

| Env var | Used by |
|---|---|
| `RUNPOD_API_KEY` | training_run orchestrator (GPU provisioning) |
| `HF_TOKEN` | search_loras (Hugging Face Hub API, optional) |

## CLI quick-start

```bash
# Build a clip pool (pipeline step 7)
python3 -m astrid executors run training.pool_build -- --scenes ./out/scenes.json --triage ./out/scene_triage.json --out ./out

# Merge pools (pipeline step 8)
python3 -m astrid executors run training.pool_merge -- --pools ./pool1.json ./pool2.json --out ./out/unified_pool.json

# Search Hugging Face for LoRAs
python3 -m astrid executors run training.search_loras -- --base-model "black-forest-labs/FLUX.1-dev" --out ./loras.json

# Manage asset cache
python3 -m astrid executors run training.asset_cache -- --action list

# Build a training dataset
python3 -m astrid orchestrators run training.dataset_build -- --sources ./sources.json --out ./dataset

# Run a LoRA training job
python3 -m astrid orchestrators run training.training_run -- --dataset ./dataset/manifest.json --out ./training_output
```
