# Built-In Dataset Builder

`training.dataset_build` is the generic reviewed video dataset builder. It replaces the hard-coded Seinfeld dataset path for M1 by moving source acquisition, bucket judging, captioning, review, and manifest export into config.

## Invocation

Run a no-network fixture smoke path:

```bash
python3 -m astrid orchestrators run training.dataset_build -- \
  --config fixtures/builtin-training/dataset-config.json \
  --out runs/builtin-training-fixture \
  --review-decisions fixtures/builtin-training/review-decisions.json
```

Run the Seinfeld example after replacing source URLs and providing the required API key:

```bash
OPENAI_API_KEY=... \
python3 -m astrid orchestrators run training.dataset_build -- \
  --config examples/configs/dataset/seinfeld-dataset.yaml \
  --out runs/seinfeld-dataset
```

For unattended runs, pass `--review-decisions <json>`. Without that flag, the orchestrator starts `editorial.human_review` (legacy alias: `builtin.human_review`) with the generic review UI and waits for submit.

## Migration From The Historical Seinfeld Dataset Builder

Use `examples/configs/dataset/seinfeld-dataset.yaml` as the migration template. Show-specific behavior now belongs in config:

- buckets and target counts live under `buckets`
- YouTube URLs and search queries live under `sources` and bucket `search_queries`
- VLM bucket-gate prompts live under `extensions.bucket_judge`
- caption prompts live under `caption.prompt_template`
- review reject reasons live under `review.reject_reasons`
- training export is selected with `manifest.adapter: ai-toolkit-ltx`

M1 reproduces the prototype's generic VLM bucket-judge and caption flow. It does not implement the M2b top-up loop, and there is intentionally no Seinfeld compatibility shim in built-in code. Continue using explicit config if a show-specific dataset needs different buckets, prompts, rights policy, or budgets.

Historical Seinfeld stage notes now live under `docs/examples/seinfeld/` as
archive-only reference material. Active workflows should use
`training.dataset_build`, `training.training_run`, and `editorial.script_pipeline`
with example configs or presets rather than direct pack-module execution.

## Outputs

The run writes only inside the requested `--out` directory:

- `review_data.json`
- `review_state.json`
- `review_server/human_review.final.json`
- `final.manifest.json`
- `ai-toolkit-ltx.manifest.json`
- confined clip files and sibling `<clip_id>.caption.json` sidecars under `clips/`

The canonical manifest includes only accepted review items. Edited review captions are propagated to sibling caption sidecars before adapter export.
