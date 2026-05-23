# Milestone 0: Contracts, Names, and Fixtures

## Outcome

Freeze the generic training-dataset/training-run contracts before implementation. This milestone should resolve naming, config schema, extension interfaces, fixture strategy, and compatibility decisions so later milestones build against explicit handoff artifacts.

## Scope

In scope:

- Verify the actual current code surfaces for:
  - `seinfeld.dataset_build`
  - `seinfeld.lora_train`
  - `seinfeld.script_pipeline`
  - `builtin.human_review`
  - `builtin.youtube_audio`
  - `builtin.scenes`
  - `builtin.clip_extract`
  - `builtin.visual_understand`
  - `builtin.video_understand`
  - `builtin.transcribe`
- Lock built-in ids:
  - dataset builder: `builtin.dataset_build`
  - training runner: `builtin.training_run`
  - creative writing/script pipeline: choose and lock one generic built-in id, such as `builtin.script_pipeline` or `builtin.scene_script`.
- Define the dataset config schema as a tagged contract:
  - Required top-level `schema_version`.
  - Required `media_type`, with `video` as the only implemented value in this epic.
  - Explicit handling for unknown versions, missing versions, unknown keys, and default values.
  - Explicit source-provider blocks rather than YouTube-query assumptions embedded in buckets.
- Define canonical `CandidateItem`, `ReviewItem`, and `ReviewDecision` JSON shapes.
  - Candidate/review records must include stable provenance fields: `source_type`, `source_id`, `source_url`, `source_metadata`, `rights`, `content_hash`, `acquired_at` or `downloaded_at`, and derivation metadata when media is generated.
  - Review records must include `media_type`, and optional `pair_id` / `pair_role` placeholders so future paired-media workflows do not require a schema break.
- Define the source-provider interface: `acquire(config) -> Iterator[CandidateItem]`.
  - The first concrete provider wraps the current YouTube/video acquisition flow.
  - Local folders, Reigh assets, stock APIs, generated media, image/audio media, and paired media are contract placeholders only.
- Define the caption-provider interface: `caption(item, config) -> CaptionResult`.
  - The first concrete provider wraps existing visual/video understanding paths.
- Define the `FilterStage` interface: `apply(items, state, config) -> {passed, rejected, stats}` and freeze a minimal `stats` schema.
- Define the manifest adapter interface: `format_id`, `validate(items)`, `export(accepted_items) -> manifest_path`.
- Define the trainer adapter and compute backend boundaries at a contract level:
  - Trainer adapters are discovered through a registry contract: `trainer_id -> adapter`.
  - ai-toolkit LTX is the first trainer adapter.
  - RunPod is the first compute backend.
- Define the module/file ownership map for every generic piece before implementation:
  - dataset orchestrator package
  - source providers
  - caption providers
  - filter stages
  - manifest adapters
  - generic review UI assets
  - training orchestrator package
  - trainer adapters
  - compute backends
  - ai-toolkit support code
  - creative-writing/script pipeline support code and presets
  - example configs and fixtures
  - historical/prototype Seinfeld docs
- Define the secrets contract for this workflow:
  - API keys come only from environment variables or uncommitted env files documented by `.env.example`.
  - No generated config, state, report, or manifest may serialize secret values.
- Define cost and rate-limit config fields:
  - Dataset configs include network/API call budgets and per-provider rate limits where expensive stages are enabled.
  - Trainer configs include `max_gpu_hours` and `max_runpod_spend_usd`.
- Define the local human-review server contract:
  - Bind to `127.0.0.1` by default.
  - Use a per-run token for browser and save/submit endpoints.
  - Freeze endpoint shapes for paginated data, diff-based saves, submit, and state reads.
- Define the canonical run-state schema, including ownership/version fields for stale-save detection.
- Define the committed offline fixture strategy: tiny local media, fixture config, fixture review decisions, and expected manifest.
- Decide the compatibility/removal path for old Seinfeld entrypoints.
  - The target end state is deleting `astrid/packs/seinfeld/` after generic homes and examples exist.
  - Any temporary compatibility shim must live outside the Seinfeld pack or be removed by M4.

Out of scope:

- Implementing the full generic dataset pipeline.
- Implementing training execution.
- Implementing quality filters beyond contract examples.

## Locked Decisions

- Generic built-in ids are `builtin.dataset_build` and `builtin.training_run`.
- `builtin.lora_train` is not a generic built-in id.
- Tests for this epic must pass without network, OpenAI, Gemini, RunPod, or GPU access unless explicitly marked integration.
- Seinfeld and Always Sunny are examples/configs, not built-in pipeline engines.
- `astrid/packs/seinfeld/` is not a long-term compatibility home; the epic should end with the folder removed.
- `schema_version: 1` and `media_type: video` are mandatory in newly generated configs.
- Missing `schema_version` may be treated as v1 only with a deprecation warning; future schema versions must fail with a parseable validation error.
- The M0 contract artifacts should be file-backed schemas/docs, not prose embedded only in this brief.

## Open Questions

- Exact config file path convention for examples.
- Whether compatibility shims should be registered outside the deleted Seinfeld pack or replaced by documented migration commands.
- Exact default values for experimental semantic thresholds; they must be centralized and labeled before M2b ships.

## Constraints

- Do not rely on model guesses about missing packs; verify registry state through `python3 -m astrid executors/orchestrators inspect`.
- Keep contracts small enough for Milestone 1 to implement.
- Prefer file-based schemas and fixture JSON over prose-only contracts.

## Done Criteria

- A written contract doc exists under this epic or project docs and names the schemas/interfaces above.
- The contract doc includes config, state, review, filter-stat, source-provider, caption-provider, manifest-adapter, trainer-adapter, compute-backend, secrets, cost, and local-server contracts.
- The contract doc includes a placement map that says what moves to `builtin/`, what belongs in examples/docs, what is archived as historical prototype material, and confirms that nothing stays in `astrid/packs/seinfeld/` after M4.
- Fixture media/data paths and expected outputs are specified.
- The chain briefs for M1-M4 refer to the locked ids and contracts.
- A reviewer can tell exactly what artifact M1 hands to M2a, M2b, M3, and M4.

## Touchpoints

- `docs/megaplan/epics/builtin-training/`
- Current Seinfeld dataset/training pack files.
- Built-in executor/orchestrator registry.

## Anti-Scope

- Do not start large code moves here.
- Do not add new external service dependencies.
