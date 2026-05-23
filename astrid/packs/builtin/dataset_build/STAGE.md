# Dataset Build

`builtin.dataset_build` builds a reviewed video training dataset from configured
sources. It is file-backed by design: every expensive or human-facing boundary
writes a checkpoint in the run directory so interrupted runs can resume without
discarding completed work.

## Run

```bash
python3 -m astrid orchestrators run builtin.dataset_build -- \
  --config <config.json-or-yaml> \
  --out runs/<dataset-run>
```

Optional inputs:

- `--review-decisions <path>` applies non-interactive review decisions and then
  finalizes manifests.
- `--dry-run` validates config, budgets, and required secrets, prints the
  planned filters/budgets/fixture mode, and exits without creating the run
  directory or any artifacts.
- `--skip-review` runs acquisition, deterministic/model-backed filters,
  captioning, and review-data checkpointing, then leaves state at `reviewing`.
  It does not launch `builtin.human_review`, does not write final manifests,
  and does not auto-accept pending items.
- `--review-only` requires matching `review_state.json` and existing
  `review_data.json`, then runs only review/finalization from those checkpoints.
  It does not reacquire sources, rerun filters, or caption.

Config-level `review.enabled: false` is separate compatibility behavior. It
bypasses the browser and accepts all captioned active items non-interactively.
It is not the same as `--skip-review`.

## Runtime Phases

The runtime phases are ordered as follows:

1. Parse and normalize config, including legacy filter blocks and ordered
   `filters.stages`.
2. Load existing `review_state.json` if present, or create a new one.
3. Acquire candidates and write `candidates.json`.
4. Convert candidates into review items.
5. Run deterministic filters and write `work_preview.json` before model-backed
   filters or captioning.
6. Run model-backed filters, currently `bucket_judge_filter`, and write
   `filtered_items.json`.
7. Caption active items and write caption sidecars under the run directory.
8. Write `review_data.json` with active and rejected items. If
   `review.sampling` is configured, every item is retained and marked with
   `review_sampled`; unsampled items remain pending unless explicitly decided.
9. Run human review, apply `--review-decisions`, honor `--skip-review`, or
   accept-all for `review.enabled: false`.
10. Apply review decisions and write `final.manifest.json` plus the configured
    adapter manifest, currently `ai-toolkit-ltx.manifest.json`.

`work_preview.json` is intentionally written after acquisition plus cheap
deterministic filters and before bucket judge, captioning, or other expensive
work. It records active/rejected counts, deterministic filter rejects/warnings,
planned caption calls, enabled model-backed stages, budget limits, fixture mode,
and whether expensive spend is disabled.

## Checkpoints

Run artifacts are stored under `--out`:

- `review_state.json`: authoritative run state, state version, config hash,
  processed source IDs, filter stats, review decisions, and status.
- `candidates.json`: acquired candidates after media is copied into the run.
- `work_preview.json`: cheap-filter preview before model-backed/caption work.
- `filtered_items.json`: active and rejected item groups after filters.
- `review_data.json`: data served to the review UI.
- `review_server/human_review.final.json`: final submit payload from
  `builtin.human_review`, when the browser review server is used or
  compatibility accept-all writes an equivalent payload.
- `final.manifest.json`: canonical accepted-item manifest.
- `<adapter>.manifest.json`: adapter-specific export.

Writes use the shared atomic JSON helpers where run state or checkpoint
authority matters.

## Resume Semantics

Existing `review_state.json` is authoritative. On resume, the runtime validates
it and compares its `config_hash` with the normalized current config. A mismatch
raises `ResumeConfigMismatchError` before mutating state.

Supported resume statuses:

- `initializing`, `acquiring`, `failed`, `filtering`: load usable checkpoints if
  present, otherwise reacquire and continue.
- `preview_ready`: load `filtered_items.json` from the deterministic-filter
  boundary and continue with model-backed filters/captioning.
- `captioning`: load `filtered_items.json` and continue caption/review work.
- `reviewing`: load `review_data.json` and continue review/finalization.
- `finalized`: return a summary of existing manifests without rewriting them.

Resume does not delete prior completed artifacts unless the current phase
intentionally rewrites the next checkpoint.

## Source Identity

Canonical source identity is shared by source-cap filtering and resume
processed-source tracking:

1. Use `derived_from.source_id` when present.
2. Otherwise use `source_id`.

This handles YouTube-derived clips whose per-clip `source_id` differs from the
original video ID. The YouTube source provider also derives a stable URL/query
source key before download and skips provider-expensive work when that key is in
`processed_source_ids`.

## Filters

Legacy filter blocks normalize to ordered internal stages:

1. `duration_filter`
2. `resolution_filter`
3. `rights_filter`
4. `black_frame_filter`
5. `content_hash_filter`
6. `source_cap_filter`

Explicit `filters.stages` preserves list order. `bucket_judge_filter` is
model-backed and expensive, whether declared directly in `filters.stages` or
adapted from `extensions.bucket_judge`.

Cheap filter defaults are conservative:

- `black_frame_filter` is metadata-only by default with threshold `0.98`.
  Missing metadata warns and passes. Media probing happens only with
  `probe_media: true`.
- `content_hash_filter` rejects later duplicates and keeps the first item in
  order.
- `source_cap_filter` uses canonical source identity and preserves input order.
- `rights_filter` rejects restricted rights statuses, warns/passes unknown
  rights, and can reject configured restricted licenses.

## Fixture And No-Network Expectations

`extensions.fixture_mode: true` keeps fixture tests local and deterministic.
Fixture mode bypasses API secret and budget preflight, loads caption and judge
sidecars when configured, and must not require network access or API keys.

No-spend configs should set budgets to zero and use fixture sidecars:

```json
{
  "budgets": {
    "max_api_calls": 0,
    "max_estimated_cost_usd": 0,
    "providers": {
      "caption.visual_understand": {"max_calls": 0},
      "bucket_judge.visual_understand": {"max_calls": 0}
    }
  },
  "extensions": {
    "fixture_mode": true,
    "fixture_caption_dir": "captions",
    "fixture_judge_dir": "judges"
  }
}
```

Use `--dry-run` for preflight-only checks. Use fixture configs plus
`--review-decisions`, `--skip-review`, or `--review-only` for offline runtime
tests.

## Inspect

```bash
python3 -m astrid orchestrators inspect builtin.dataset_build --json
```

## Package Layout

- `source_providers/`: source acquisition and provider-level resume skips.
- `caption_providers/`: fixture or model-backed caption generation.
- `filter_stages/`: deterministic and model-backed candidate filters.
- `manifest_adapters/`: downstream manifest exports.
- `review_ui/`: generic dataset review static assets.
- `schemas/`: packaged runtime JSON schemas.

## Child Executors

The orchestrator declares these child executors:

- `builtin.youtube_audio`
- `builtin.scenes`
- `builtin.visual_understand`
- `builtin.video_understand`
- `builtin.human_review`
