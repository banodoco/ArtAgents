# Historical Seinfeld Pack Archive

This directory preserves the useful Seinfeld prototype material before the
`astrid/packs/seinfeld/` pack is deleted in Milestone 4. These files are
historical examples and reference material only. They are not registered
executors or orchestrators, and they should not be used as compatibility shims.

## Canonical Built-In Commands

Use the built-in dataset pipeline with the Seinfeld example config:

```bash
python3 -m astrid start builtin.dataset_build --project <project>
python3 -m astrid orchestrators run builtin.dataset_build -- --config examples/configs/dataset/seinfeld-dataset.yaml
```

Use the built-in training pipeline with the Seinfeld training config:

```bash
python3 -m astrid orchestrators run builtin.training_run -- --config examples/configs/training/seinfeld-training.yaml --dry-run
python3 -m astrid orchestrators run builtin.training_run -- --config examples/configs/training/seinfeld-training.yaml --confirm-spend
```

Use the built-in script pipeline with the Seinfeld preset:

```bash
python3 -m astrid executors inspect builtin.script_pipeline --json
python3 -m astrid.packs.builtin.executors.script_pipeline.run --preset seinfeld --fake --produces-dir runs/seinfeld-script/produces
python3 -m astrid.packs.builtin.executors.script_pipeline.run --preset seinfeld --produces-dir runs/seinfeld-script/produces
```

The direct module command above is useful when no Astrid session is bound. In a
bound session, prefer the executor gateway:

```bash
python3 -m astrid executors run builtin.script_pipeline -- --preset seinfeld --produces-dir runs/seinfeld-script/produces
```

## Archived Contents

- `TRAINING_PLAN.md`, `DATASET_QUALITY.md`, `CAPTIONING.md`, and
  `RUNPOD_TRAINING_LAUNCHER_BRIEF.md`: historical prototype planning and
  quality notes.
- `vocabulary.yaml` and `vocab_compile.py`: locked vocabulary reference and
  the old schema compiler.
- `schemas/`: historical structured VLM schemas used by the prototype.
- `dataset_build/`: old dataset-build stage notes, review UI fixture, review
  schema, and sprint brief.
- `aitoolkit_stage/`, `aitoolkit_train/`, `lora_eval_grid/`,
  `lora_register/`, `lora_train/`, `repo_setup/`, and `script_pipeline/`:
  old stage notes and training template references.

## Migration Notes

- `seinfeld.dataset_build` becomes `builtin.dataset_build` plus
  `examples/configs/dataset/seinfeld-dataset.yaml`.
- `seinfeld.lora_train` becomes `builtin.training_run` plus
  `examples/configs/training/seinfeld-training.yaml`.
- `seinfeld.script_pipeline` becomes `builtin.script_pipeline` plus the
  `seinfeld` preset in `astrid/packs/builtin/script_pipeline/presets/`.
- Historical docs may still mention deleted `seinfeld.*` ids because they
  preserve prototype context. Active docs and examples should point at the
  built-in commands above.
