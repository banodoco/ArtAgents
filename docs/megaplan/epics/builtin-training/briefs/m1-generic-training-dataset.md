# Milestone 1: Generic Built-In Training Dataset Builder

## Outcome

Create `builtin.dataset_build`, a generic built-in training dataset orchestrator that replaces the Seinfeld-specific dataset prep prototype for the first supported case: video LoRA dataset preparation with human review and ai-toolkit LTX manifest export.

By the end, a user can run a config-driven dataset build, review candidate clips in the generic list UI, and receive a trainer-ready `final.manifest.json`.

## M0 Handoff (READ FIRST)

Before starting M1 implementation, read these M0 contract artifacts:
- `CONTRACTS.md` — master contract (all sections, especially §3 config, §4 data shapes, §5 interfaces, §6 manifests, §7 review server, §9 secrets, §10 budgets)
- `contracts/interfaces.py` — Python Protocol signatures for SourceProvider, CaptionProvider, ManifestAdapter (port or import from this; do not create a competing contracts.py location)
- `contracts/schemas/dataset-config.schema.json` — strict v1 config schema (schema_version: 1, media_type: video required)
- `contracts/schemas/candidate-item.schema.json` — provenance/rights fields required on every item
- `contracts/schemas/review-item.schema.json` — review item shape with pair_id/pair_role placeholders
- `contracts/schemas/review-decision.schema.json` — submit decision shape (distinct from /save diff payloads)
- `contracts/schemas/manifest.schema.json` — canonical accepted-item manifest
- `contracts/schemas/ai-toolkit-adapter-manifest.schema.json` — flat clips shape for training preflight
- `contracts/schemas/run-state.schema.json` — canonical run state with state_version for stale-save detection
- `PLACEMENT.md` — where every generic piece lives
- `FIXTURES.md` — fixture paths, expected outputs, no-network validation

## Scope

In scope:

- Add built-in orchestrator `builtin.dataset_build`.
- Implement the generic dataset config format frozen in M0 for the first supported case: `media_type: video`, video sources, buckets, target counts, duration filter, caption prompt, review reasons, budgets/rate limits, and manifest adapter.
- Implement the M0 source-provider boundary with one concrete provider for YouTube/video sources. Do not hardcode YouTube assumptions into the orchestrator core.
- Implement the M0 caption-provider boundary with one concrete provider wrapping the existing visual/video understanding path.
- Move the list review UI out of `astrid/packs/seinfeld/` into a generic built-in location.
- Follow the M0 placement map (PLACEMENT.md) for source providers, caption providers, filter stages, manifest adapters, review UI assets, fixtures, and examples; do not create new generic homes opportunistically during implementation.
- Wire `builtin.human_review` into the dataset orchestrator.
- Emit `review_data.json`, `review_state.json`, and `review_server/human_review.final.json`.
- Populate M0 provenance/rights fields on every candidate/review item, even when some rights subfields are unknown.
- Apply human review decisions into `final.manifest.json`.
- Implement one manifest adapter behind the M0 adapter interface: `ai-toolkit-ltx`.
- Export BOTH the canonical manifest AND the ai-toolkit adapter manifest (flat `clips` shape per ai-toolkit-adapter-manifest.schema.json).
- Ensure the ai-toolkit adapter manifest is compatible with the existing training preflight expectation: flat `clips`, valid `clip_file`/`path`, `clip_id`, and sibling `<clip_id>.caption.json` sidecars.
- Implement the generic review UI against the M0 local-server contract:
  - paginated or chunked data loading (new vs. current full /data.json)
  - bounded DOM rendering rather than rendering every item at once
  - diff-based saves (new vs. current full-state /save overwrite; see CONTRACTS.md §7.2)
  - keyboard navigation and accept/reject shortcuts
  - localhost-only binding and tokenized save/submit endpoints
- Preserve the current Seinfeld dataset behavior as either an example config or a compatibility wrapper.
- Include a tiny local fixture/smoke path that does not require YouTube, OpenAI, Gemini, RunPod, or GPU spend.
- Validate fixtures against their schemas using jsonschema (M1 validation of M0 contract consistency).

Out of scope:

- Full top-up loop after rejects.
- Transcript keyword filtering.
- General image/audio/pair media support beyond schema/interface placeholders.
- Generic training-run orchestration.
- Broad Astrid CLI refactors unrelated to this dataset flow.
- Stale-save detection on /save (M2a work; M1 implements the diff-save endpoint shape).

## Locked Decisions

- The generic dataset builder id is `builtin.dataset_build`.
- Generic training runner id: `builtin.training_run`. Creative writing id: `builtin.script_pipeline`. (from M0)
- `builtin.lora_train` is NOT a generic built-in id. (from M0)
- The first concrete manifest adapter is ai-toolkit LTX only.
- The manifest adapter is an interface, not just an implementation. Minimum contract: `format_id`, `validate(items)`, and `export(accepted_items) -> manifest_path`.
- The source-provider and caption-provider interfaces are real boundaries in code, even though this milestone implements only the video/YouTube path.
- Port or import interface signatures from `contracts/interfaces.py` — do not create a competing `contracts.py` location under `builtin/dataset_build`.
- The human review primitive remains `builtin.human_review`.
- The review UI is generic and list-first: filters for all/pending/accepted/rejected, per-item yes/no/pending, reject reasons, editable captions, and persistent state.
- Seinfeld and Always Sunny should become configs/examples, not separate pipeline engines.
- `schema_version: 1` and `media_type: video` are mandatory in newly generated configs. Missing schema_version treated as deprecated v1 per parser policy (contracts/schema-version-parser-policy.md).
- API keys come only from environment variables or .env files; no secrets in configs/state/manifests. (from M0 CONTRACTS.md §9)
- No compatibility shim lives in astrid/packs/seinfeld/; any temporary shim must live outside and be removed by M4. (from M0 CONTRACTS.md §13)

## Open Questions (Resolved by M0)

- ~~Config file location and schema naming.~~ → See PLACEMENT.md: example configs under `examples/configs/dataset/`.
- ~~Whether to keep a `seinfeld.dataset_build` compatibility shim.~~ → No shim in Seinfeld pack. Document migration commands instead. See CONTRACTS.md §13.
- ~~Exact final manifest field names.~~ → See ai-toolkit-adapter-manifest.schema.json: flat `clips[]` with `clip_file`/`path`, `clip_id`, `caption_file`.

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
- Both the canonical manifest AND the ai-toolkit adapter manifest are emitted and parse correctly.
- The ai-toolkit adapter manifest passes a local compatibility check equivalent to `seinfeld.lora_train` preflight, without provisioning RunPod.
- Focused tests cover config parsing, review decision application, manifest export, and fixture smoke behavior.
- Fixture JSON files are validated against their corresponding JSON schemas (jsonschema conformance check).

## Touchpoints

- `astrid/packs/seinfeld/dataset_build/` (prototype to generalize)
- `astrid/packs/builtin/human_review/` (review server — existing, generic)
- `astrid/packs/builtin/youtube_audio/` (source download — existing)
- `astrid/packs/builtin/scenes/` (scene detection — existing)
- `astrid/packs/builtin/visual_understand/` (caption/judge — existing)
- `astrid/packs/builtin/video_understand/` (caption/judge — existing)
- `astrid/packs/seinfeld/lora_train/run.py` (preflight shape reference)
- `docs/megaplan/epics/builtin-training/CONTRACTS.md` (M0 master contract)
- `docs/megaplan/epics/builtin-training/contracts/interfaces.py` (M0 interface signatures)
- `docs/megaplan/epics/builtin-training/contracts/schemas/` (M0 JSON schemas)
- `docs/megaplan/epics/builtin-training/contracts/fixtures/` (M0 fixture JSON)
- `docs/megaplan/epics/builtin-training/PLACEMENT.md` (M0 placement map)
- `docs/megaplan/epics/builtin-training/FIXTURES.md` (M0 fixture strategy)
- `tests/`

> **NOTE:** `builtin.clip_extract` does NOT exist in this checkout. M0 verified it is missing. Extraction logic is currently inlined in `seinfeld.dataset_build/run.py` or will be internal to `builtin.dataset_build`.

## Anti-Scope

- Do not implement generic training execution here.
- Do not implement all possible manifest adapters.
- Do not redesign Astrid sessions, project storage, or the whole executor runner.
