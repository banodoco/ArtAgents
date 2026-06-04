# Output/Result contract — every executor family emits a self-describing manifest

## Outcome
An agent handed any run directory — from ANY executor family — can mechanically determine what was produced, from what inputs, with what integrity, via one universal manifest contract; and the same logical result has the same envelope shape via CLI `--json` and SDK. Reviewer checks: the per-family conformance test passes for every executor family in the repo.

## Context (read first)
`docs/megaplan/epics/formalization-audit-synthesis.md` (Tier B — the audit's strongest convergence: 3 independent agents/frames). Exemplars to GENERALIZE, not change: generation's manifest contract (`astrid/docs/generation/20-manifest-schema.md`, `_build_manifest` in generate_image/generate_video, golden tests), PNG tEXt embedding (`astrid/core/util/png_metadata.py`). The run-ledger contract (`docs/run-ledger-contract.md`) is in force: run.json is the ledger entry and points at outputs — this epic supplies the universal manifest those pointers reference. Local ticket: `.megaplan/tickets/*output-result-contract*` if present.

## Scope (IN)
1. **`write_manifest()` choke point** in `astrid/contracts/` (or `astrid/core/contracts-adjacent` location matching house style): validates required fields, computes content hashes, writes atomically. Required fields: `schema_version`, `kind` (enum: image|video|audio|transcript|scenes|shots|quotes|pool|render|analysis|...), `inputs` (echoed request), `outputs[]` ({path, content_hash, bytes}), `created`, `warnings[]`.
2. **Adopt across the non-conforming families** (current state, audit-verified):
   - understanding: video_understand/visual_understand/audio_understand emit 3 different ad-hoc stdout JSON shapes, zero schema_version (run.py:296/456/491) → each writes manifest.json via the choke point; stdout JSON may remain for compat but must embed the same `schema_version`/`kind`.
   - editorial: scenes (bare list, run.py:104), shots (bare list), transcribe ({"segments"}), quote_scout (bespoke version:1) → sibling manifest.json; do NOT break existing output files consumed downstream — manifest is additive.
   - training pool_build (timeline.POOL_VERSION dialect) → manifest alongside.
   - scene_describe + foley + any other artifact-writing executor discovered during the sweep.
3. **Result envelope parity**: CLI `executors run --json` currently prints raw `result.payload` (executor/cli.py:632) while SDK returns typed InvocationResult (sdk.py:1715 area). Define ONE result-envelope JSON shape (capability_id, ok, error, outputs/manifest pointer, raw payload nested) emitted by both. Additive: keep raw payload available inside the envelope.
4. **Per-family conformance test**: enumerate every executor that declares outputs, invoke minimally (fake/offline backends — follow generation's golden-test pattern), assert manifest.json exists + validates. New executor families cannot merge without passing.
5. **Authoring doc**: one page in docs/ stating the manifest requirement for new executors (the "self-describing outputs" principle, currently folklore documented only for generation).

## Locked decisions
- Generation's manifest schema v2 is the base; the universal contract extends it with `kind` — generation executors keep `modality` AND gain nothing breaking (their manifests already validate).
- Additive everywhere: no existing output file changes shape or location; manifests appear alongside.
- register_outputs stays as the audit-trail mechanism; the manifest is the self-description mechanism — do not merge them in this epic.
- EXCLUDED (adjudicated): five-surface AgentUXEnvelope; mandatory effects/rollback/idempotency_key capability fields; reigh cloud-native paths (intentionally out); timeline event payloads.

## Open questions (planner resolves)
- Exact `kind` enum vocabulary and whether it lives in contracts/schema.py or the model/pack registry.
- Whether understanding executors' stdout previews shrink to a pointer at the manifest or stay full (compat with existing consumers decides).

## Constraints
Existing tests + run-ledger conformance test green; offline-capable conformance (no paid API calls in CI); hygiene gate clean (no junk at root — tests write under tmp_path).

## Done criteria
Conformance test green across all families; `executors run <understanding-executor> --json` and the SDK return the shared envelope for the same invocation; authoring doc committed.

## Touchpoints
astrid/contracts/, astrid/packs/understanding/executors/*/run.py, astrid/packs/editorial/executors/*/run.py, astrid/packs/training/executors/pool_build/, astrid/packs/generation (read-mostly), astrid/core/executor/cli.py, astrid/sdk.py, docs/, tests/.

## Anti-scope
No identity/session work; no CLI lifecycle-verb work (separate epics); no changes to manifest schema v2 semantics for generation; no timeline/threads changes.
