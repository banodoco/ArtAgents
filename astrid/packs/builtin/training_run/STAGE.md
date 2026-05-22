# builtin.training_run

Generic built-in LoRA training orchestration. The orchestrator consumes a
training-run config and a prepared dataset manifest, then coordinates compute,
remote trainer execution, artifact pulls, checkpoint review, registration, and
teardown through registry-declared backends and executors.

This stage intentionally keeps provider-specific work behind backends and
executor dependencies. Generic code must not call RunPod helper functions
directly.

## Inspect

```bash
python3 -m astrid orchestrators inspect builtin.training_run --json
```

## Dry Run

Use dry-run before any live operation. It validates the config, reports missing
declared secrets, writes the normalized manifest, builds the ai-toolkit config,
writes `planned_cost.json`, and persists local planning state. It performs no
RunPod, network, or GPU calls.

```bash
python3 -m astrid orchestrators run builtin.training_run -- \
  --config configs/training-run.json \
  --dry-run
```

## Smoke

Smoke mode performs the same local-only artifact generation as dry-run, with a
state mode that distinguishes CI/smoke validation from an operator dry-run.

```bash
python3 -m astrid orchestrators run builtin.training_run -- \
  --config configs/training-run.json \
  --smoke
```

Direct module form:

```bash
python3 -m astrid.packs.builtin.training_run.run \
  --config configs/training-run.json \
  --dry-run
```

## Seinfeld Example

`examples/configs/training/seinfeld-training.yaml` carries the current Seinfeld
LoRA defaults as config for `builtin.training_run`. The existing
`seinfeld.lora_train` path is intentionally preserved for M3; removing or
migrating that pack-specific path is deferred to a later milestone.

## Live Run

Live mode fails closed before provisioning if any environment variable declared
in `secrets.required_env` is missing. Use `--confirm-spend` only after reviewing
dry-run output and spend limits in the config. `--yes` is retained as a
compatibility alias. After successful training and local sample download, live
mode pauses at the checkpoint review gate and keeps the pod teardown guard in
state for resume or explicit follow-up.

```bash
RUNPOD_API_KEY=... HF_TOKEN=... \
python3 -m astrid orchestrators run builtin.training_run -- \
  --config configs/training-run.json \
  --confirm-spend
```

## Resume

Resume uses the training run directory's persisted state and continues from a
paused checkpoint-review gate. It validates `--pick` against
`checkpoint_manifest.json`, registers the selected checkpoint locally before
teardown, and records the final registration metadata. Use `--skip-teardown`
only when you intentionally want to keep the pod alive after registration.

```bash
python3 -m astrid orchestrators run builtin.training_run -- \
  resume \
  --out runs/training/my-run \
  --pick final \
  --notes "best checkpoint"
```

Direct module form:

```bash
python3 -m astrid.packs.builtin.training_run.run resume \
  --out runs/training/my-run \
  --pick final
```

## Outputs

- `last_run.json`: run state and resumability metadata.
- `manifests/ai-toolkit-ltx/manifest.json`: normalized training-owned manifest.
- `trainer/ai-toolkit-ltx/config.yaml`: generated ai-toolkit trainer config.
- `planned_cost.json`: local estimated-cost and capability planning output.
- `review/index.html`: local review index for downloaded sample assets.
- `registered/registered_lora.json`: metadata for the selected registered checkpoint.
