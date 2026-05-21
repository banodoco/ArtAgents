# Milestone 3: Generic Built-In Training Run

## Outcome

Generalize the existing Seinfeld ai-toolkit LoRA training orchestrator into `builtin.training_run`, a built-in training-run orchestrator that can consume `final.manifest.json` from the generic dataset builder and run ai-toolkit LTX training through RunPod with human checkpoint review.

## Scope

In scope:

- Add built-in orchestrator `builtin.training_run`.
- Define a trainer config format for the first trainer: ai-toolkit LTX.
- Follow the M0 placement map for trainer adapters, compute backends, ai-toolkit support code, checkpoint review assets, and training fixtures.
- Generalize the Seinfeld ai-toolkit-on-RunPod flow behind the trainer/compute backend contracts from M0:
  - repo/setup preflight
  - pod provision
  - dataset/config staging
  - training
  - training log mirroring
  - checkpoint manifest
  - sample/eval grid
  - sample collage or comparable checkpoint-sample review support, absorbing or deleting the current `samples_collage` helper
  - human checkpoint gate
  - chosen checkpoint registration
  - teardown
- Preserve existing Seinfeld behavior through config or compatibility wrapper.
- Add a dry-run/smoke mode that validates config and manifest compatibility without spending GPU money.
- Ensure the new orchestrator consumes Milestone 1/2 `final.manifest.json` directly.
- Enforce the M0 cost/secrets contract before any non-dry-run provisioning:
  - required RunPod credentials are sourced only through the secrets contract
  - `max_gpu_hours` and `max_runpod_spend_usd` are required
  - estimated cost must fit within configured budget
  - headless runs require an explicit spend-confirmation mechanism in config or CLI state
- Configure a conservative RunPod auto-shutdown/timeout guard when the provider supports it, and always record the recovery command in state.

Out of scope:

- New trainer backends beyond ai-toolkit LTX.
- Cloud persistence improvements unrelated to this training flow.
- Model-quality research or hyperparameter tuning beyond existing defaults.

## Locked Decisions

- ai-toolkit LTX is the only implemented trainer adapter in this milestone.
- ai-toolkit LTX is loaded through the M0 trainer registry contract; it must not be hardcoded as the only possible generic path.
- Human checkpoint review remains part of the training-run flow.
- RunPod remains the first compute backend for the implemented trainer.
- `builtin.training_run` orchestrates through explicit trainer and compute backend boundaries; RunPod operations must not be baked into generic training-run logic in a way that prevents later local/Modal/provider backends.
- Dataset preparation remains separate from training execution.

## Open Questions

- How checkpoint registration should be represented generically.
- Whether the existing direct `resume` subcommand should be replaced with a canonical Astrid command path.

## Constraints

- Do not break existing Seinfeld training outputs if compatibility is practical.
- Avoid provisioning in tests; use dry-run/smoke fixtures.
- Non-dry-run provisioning must fail closed when cost budgets, spend confirmation, or secrets are missing.
- Keep pod teardown semantics conservative: do not tear down before the chosen checkpoint is safely local/registered.
- RunPod pod handles must be recorded in a known state file as soon as provisioning succeeds.
- Any failure after pod provisioning must either tear down the pod or leave a clear recovery command with the pod id in the run state and final error output.
- All non-integration tests must pass without network, RunPod, or GPU access.

## Done Criteria

- `python3 -m astrid orchestrators inspect builtin.training_run --json` shows the new built-in orchestrator.
- Canonical invocation is documented and works in dry-run mode:
  `python3 -m astrid orchestrators run builtin.training_run -- --manifest <final.manifest.json> --config <trainer.yaml> --out <run-dir> --dry-run`.
- Dry-run validates a fixture `final.manifest.json` and trainer config.
- Dry-run validates budget and secret requirements without requiring actual secret values.
- Non-dry-run refuses to provision when budgets or explicit spend confirmation are absent.
- Smoke mode can exercise local config generation without RunPod spend.
- The orchestrator writes durable state comparable to `last_run.json`.
- Human checkpoint gate is documented and works through the canonical path.
- Tests cover manifest preflight, trainer config generation, state writing, and resume/registration behavior without GPU.

## Touchpoints

- `astrid/packs/seinfeld/lora_train/`
- `astrid/packs/seinfeld/aitoolkit_stage/`
- `astrid/packs/seinfeld/aitoolkit_train/`
- `astrid/packs/seinfeld/lora_eval_grid/`
- `astrid/packs/seinfeld/lora_register/`
- `astrid/packs/external/runpod/`
- Built-in dataset manifest adapter from Milestone 1.
- `tests/`

## Anti-Scope

- Do not add Kohya, Diffusers, WAN, or image-LoRA trainers in this milestone.
- Do not merge dataset building and training into one monolith.
- Do not redesign RunPod infrastructure beyond what is needed to make this generic.
