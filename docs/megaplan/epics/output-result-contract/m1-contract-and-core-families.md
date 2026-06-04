# Output/Result contract M1 — the contract, the gate, and the core families

## Outcome
An agent handed any run directory — from ANY executor family — can mechanically determine what was produced, from what inputs, with what integrity, via one universal manifest contract; and the same logical result has the same envelope shape via CLI `--json` and SDK. Reviewer checks: the registry-driven conformance test passes for every executor declaring outputs.

## Context (read first)
`docs/megaplan/epics/formalization-audit-synthesis.md` (Tier B — the audit's strongest convergence: 3 independent agents/frames). Exemplars to GENERALIZE, not change: generation's manifest contract (`astrid/docs/generation/20-manifest-schema.md`, `_build_manifest` in generate_image/generate_video, golden tests), PNG tEXt embedding (`astrid/core/util/png_metadata.py`). The run-ledger contract (`docs/run-ledger-contract.md`) is in force AND m1 already landed the ledger-side plumbing: `run.json.manifest_path` + manifest-output fallback exist (core/project/run.py:327,338; tests/test_project_runs.py:895). DO NOT alter ledger semantics — this plan only produces the manifests those pointers reference. Local ticket: `.megaplan/tickets/*output-result-contract*` if present.

## Scope (IN)
1. **`write_manifest()` choke point** in `astrid/contracts/` (or `astrid/core/contracts-adjacent` location matching house style): validates required fields, computes content hashes, writes atomically. Required fields: `schema_version`, `kind` (documented string vocabulary; core values: image|video|audio|transcript|scenes|shots|quotes|pool|render|analysis), `inputs` (echoed request), `outputs[]` ({path, content_hash, bytes}), `created`, `warnings[]`.
2. **Adopt across the non-conforming families** (current state, audit-verified):
   - understanding: video_understand/visual_understand/audio_understand emit 3 different ad-hoc stdout JSON shapes, zero schema_version (run.py:296/456/491) → each writes manifest.json via the choke point; stdout JSON may remain for compat but must embed the same `schema_version`/`kind`.
   - editorial: scenes (bare list, run.py:104), shots (bare list), transcribe ({"segments"}), quote_scout (bespoke version:1) → sibling manifest.json; do NOT break existing output files consumed downstream — manifest is additive.
   - training pool_build (timeline.POOL_VERSION dialect) → manifest alongside.
   - generation.generate_image_openai: declares `{out}/manifest.json` (executor.yaml:68) but writes a bare list (run.py:322) — bring to v2 conformance (generation is PARTLY conforming, not read-mostly).
   - scene_describe.
   - iteration.assemble (CONTRACT-SHAPING, judged into M1: six declared outputs across JSON/HTML/adapter files including its own domain `iteration.manifest.json` — M1 must settle how the universal manifest coexists with domain manifests BEFORE the schema freezes).
   - reigh.spatial_audio_page (CONTRACT-SHAPING, judged into M1: declared output is a DIRECTORY — forces the directory-output rule: tree-hash/total-bytes or expansion into child artifacts; cannot be deferred to mechanical M2).
   (The remaining long tail — 7 more editorial executors, iteration.prepare, rendering trio, comfy_wrap.run, vibecomfy.run (exemption candidate: external escape hatch, no stable declared output), video_editing.cut, media.clip_extract, moirae, fal_foley, reigh_data, youtube_audio — enter the exemption list here and are retrofitted in M2. Independent review measured the full surface at 30+ executors / ~3-4 weeks; hence the two-milestone split.)
3. **Result envelope parity — CLI adopts the SDK shape, additively**: `InvocationResult`'s top-level fields are Tier-1 LOCKED public API (sdk.py:305, docs/sdk.md:371) — do NOT invent a new shape. CLI `executors run --json` (today: raw `result.payload`, executor/cli.py:635) emits the InvocationResult serialization (with raw payload nested) plus the manifest pointer. GOTCHA (review-verified): "additive" dataclass field is only 80% true — `InvocationResult.to_dict()` (sdk.py:316-326) manually enumerates fields and the construction site (sdk.py:1753-1760) must be updated explicitly. CLI scope is `executors run --json` ONLY — all lifecycle-verb JSON belongs to the agent-CLI plans.
4. **Full-registry conformance gate (CORRECTED mechanism — independent review found Output.path_template enumeration silently misses ~20 executors that declare NO outputs in YAML, including the understanding trio this plan targets)**: enumerate EVERY executor in the registry; each must satisfy manifest-on-invocation OR appear in a committed, reasoned exemption list (heavy/GPU/paid/no-artifact). The exemption list starts large (the long tail) and is burned down by M2 — the gate is green from day one while making non-conformance VISIBLE. Note Output.path_template is at contracts/schema.py:41 (not :35).
5. **Authoring doc**: one page in docs/ stating the manifest requirement for new executors (the "self-describing outputs" principle, currently folklore documented only for generation).

## Locked decisions
- Generation's manifest schema v2 is the base; the universal contract extends it with `kind` — `kind` is a DOCUMENTED STRING VOCABULARY (validated non-empty, core values listed) NOT a closed enum; domain-specific kinds are legal.
- generate_image/generate_video manifests already validate and must not change shape; generate_image_openai is in the adoption list (see Scope 2).
- Additive everywhere: no existing output file changes shape or location; manifests appear alongside.
- register_outputs stays as the audit-trail mechanism; the manifest is the self-description mechanism — do not merge them in this epic.
- EXCLUDED (adjudicated): five-surface AgentUXEnvelope; mandatory effects/rollback/idempotency_key capability fields; reigh cloud-native paths (intentionally out); timeline event payloads.

## Open questions (planner resolves)
- Where the `kind` vocabulary doc lives (contracts/schema.py docstring vs the pack registry docs).
- Whether understanding executors' stdout previews shrink to a pointer at the manifest or stay full (compat with existing consumers decides).

## Constraints
Existing tests + run-ledger conformance test green; offline-capable conformance (no paid API calls in CI); hygiene gate clean (no junk at root — tests write under tmp_path).

## Done criteria
Registry-driven conformance green (with documented exemptions); `executors run <understanding-executor> --json` and the SDK return the shared envelope for the same invocation; authoring doc committed.

## Touchpoints
astrid/contracts/, astrid/packs/understanding/executors/*/run.py, astrid/packs/editorial/executors/*/run.py, astrid/packs/training/executors/pool_build/, astrid/packs/generation (generate_image_openai adoption; others read-only), astrid/core/executor/cli.py, astrid/sdk.py, docs/, tests/.

## Anti-scope
No identity/session work; no CLI lifecycle-verb work (separate epics); no changes to manifest schema v2 semantics for generation; no timeline/threads changes.
