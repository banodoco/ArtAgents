# Milestone 1: Generic Built-In Training Dataset Builder

## Outcome

Create `builtin.dataset_build`, a generic built-in training dataset orchestrator that replaces the Seinfeld-specific dataset prep prototype for the first supported case: video LoRA dataset preparation with human review and ai-toolkit LTX manifest export.

By the end, a user can run a config-driven dataset build, review candidate clips in the generic list UI, and receive a trainer-ready `final.manifest.json`.

## Scope

In scope:

- Add built-in orchestrator `builtin.dataset_build`.
- Implement the generic dataset config format frozen in M0 for the first supported case: `media_type: video`, video sources, buckets, target counts, duration filter, caption prompt, review reasons, budgets/rate limits, and manifest adapter.
- Implement the M0 source-provider boundary with one concrete provider for YouTube/video sources. Do not hardcode YouTube assumptions into the orchestrator core.
- Implement the M0 caption-provider boundary with one concrete provider wrapping the existing visual/video understanding path.
- Move the list review UI out of `astrid/packs/seinfeld/` into a generic built-in location.
- Follow the M0 placement map for source providers, caption providers, filter stages, manifest adapters, review UI assets, fixtures, and examples; do not create new generic homes opportunistically during implementation.
- Wire `builtin.human_review` into the dataset orchestrator.
- Emit `review_data.json`, `review_state.json`, and `review_server/human_review.final.json`.
- Populate M0 provenance/rights fields on every candidate/review item, even when some rights subfields are unknown.
- Apply human review decisions into `final.manifest.json`.
- Implement one manifest adapter behind the M0 adapter interface: `ai-toolkit-ltx`.
- Ensure the final manifest is compatible with the existing training preflight expectation: flat `clips`, valid `clip_file`, and sibling `<clip_id>.caption.json` sidecars.
- Implement the generic review UI against the M0 local-server contract:
  - paginated or chunked data loading
  - bounded DOM rendering rather than rendering every item at once
  - diff-based saves
  - keyboard navigation and accept/reject shortcuts
  - localhost-only binding and tokenized save/submit endpoints
- Preserve the current Seinfeld dataset behavior as either an example config or a compatibility wrapper.
- Include a tiny local fixture/smoke path that does not require YouTube, OpenAI, Gemini, RunPod, or GPU spend.

Out of scope:

- Full top-up loop after rejects.
- Transcript keyword filtering.
- General image/audio/pair media support beyond schema/interface placeholders.
- Generic training-run orchestration.
- Broad Astrid CLI refactors unrelated to this dataset flow.

## Locked Decisions

- The generic dataset builder id is `builtin.dataset_build`.
- The first concrete manifest adapter is ai-toolkit LTX only.
- The manifest adapter is an interface, not just an implementation. Minimum contract: `format_id`, `validate(items)`, and `export(accepted_items) -> manifest_path`.
- The source-provider and caption-provider interfaces are real boundaries in code, even though this milestone implements only the video/YouTube path.
- The human review primitive remains `builtin.human_review`.
- The review UI is generic and list-first: filters for all/pending/accepted/rejected, per-item yes/no/pending, reject reasons, editable captions, and persistent state.
- Seinfeld and Always Sunny should become configs/examples, not separate pipeline engines.

## Open Questions

- Config file location and schema naming.
- Whether to keep a `seinfeld.dataset_build` compatibility shim for existing users.
- Exact final manifest field names needed by `seinfeld.lora_train` and ai-toolkit staging.

## Constraints

- Do not mutate existing user-generated `runs/` artifacts except when tests explicitly use fixtures.
- Do not hardcode Seinfeld or Always Sunny assumptions in the built-in core.
- Do not let review UI implementation assume unbounded in-memory `/data.json` or one DOM video element per candidate.
- Do not start paid/API-backed stages if the M0 budget and secret validation fails.
- Avoid direct guarded module execution from orchestrator code; use canonical Astrid runners or internal invocation only where current architecture requires it.
- Keep generated source media and review outputs under ignored run directories.
- All tests must pass without network access; external calls must be mockable or fixture-backed.

## Done Criteria

- `python3 -m astrid orchestrators inspect builtin.dataset_build --json` shows the new built-in orchestrator.
- Canonical invocation is documented and works in fixture/smoke mode:
  `python3 -m astrid orchestrators run builtin.dataset_build -- --config <config.yaml> --out <run-dir>`.
- A fixture config can run end-to-end locally through review-data generation and final manifest export.
- The generic review UI can be launched by `builtin.human_review` with mounted video clips.
- The review UI remains usable on a generated large metadata fixture without loading or rendering every item at once.
- Human decisions are applied correctly: only accepted clips appear in `final.manifest.json`; edited captions are reflected in caption sidecars.
- Review save/submit requests use tokenized localhost endpoints and persist only changed decisions.
- The final manifest passes a local compatibility check equivalent to `seinfeld.lora_train` preflight, without provisioning RunPod.
- Focused tests cover config parsing, review decision application, manifest export, and fixture smoke behavior.

## Touchpoints

- `astrid/packs/seinfeld/dataset_build/`
- `astrid/packs/builtin/human_review/`
- `astrid/packs/builtin/youtube_audio/`
- `astrid/packs/builtin/scenes/`
- `astrid/packs/builtin/clip_extract/`
- `astrid/packs/builtin/visual_understand/`
- `astrid/packs/builtin/video_understand/`
- `astrid/packs/seinfeld/lora_train/run.py`
- `tests/`

## Anti-Scope

- Do not implement generic training execution here.
- Do not implement all possible manifest adapters.
- Do not redesign Astrid sessions, project storage, or the whole executor runner.
