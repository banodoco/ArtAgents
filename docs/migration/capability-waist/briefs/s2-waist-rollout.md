# S2 — Waist rollout  (mechanical replication of the S1 pattern)

**Read first:** RFC + MIGRATION-PLAN + the S1 result (the proven type-resolution pattern).
**Profile:** solo / full / low. **Why:** behavior-preserving replication behind per-seam parity; finalize still premium-adjudicates decomposition. Depends on S1.

## Outcome
Every remaining name-wired composition seam is type-checked. After this, no consumer enumerates a producer set to validate a reference.

## Scope (IN)
1. **Annotate the rest.** Add `artifact_type` to all remaining executor/orchestrator/model I/O where the semantic type is known (generation: `prompt→image`, video, foley `clip→audio`, transcribe `audio→transcript`, upscale, etc.). Every declared type must resolve in the S1 registry.
2. **Orchestrator child refs.** `child_executors`/`child_orchestrators` ID lists → type-validated references (kernel checks the referenced capability's I/O is type-compatible at the wiring point). Keep imperative `run.py` orchestration — only the *reference validation* changes.
3. **Model `param_map` → adapters.** Move the per-(mode,backend) wire-name translation out of `models.yaml` into the backend adapters (where it belongs); the manifest declares canonical `params` only.
4. **`fal.py` model-name hardcodes → adapter hints.** flux-schnell guidance, ideogram safety (`fal.py:258-265`) become declared adapter hints, not `if entry.id ==` branches.

## Anti-scope (OUT)
No registry collapse (S4), no theme work (S3), no element restructure/purge (S4).

## Done criteria / GATE
Per-seam parity: each rewired validation/translation accepts/rejects/produces the identical result as before across the corpus. All tests green. Suffix-mapping (`_capability_common.py:131`) prefers `artifact_type`.

## Touchpoints
All pack `executor.yaml`/`orchestrator.yaml` with known I/O; `orchestrator/registry.py` (child validation); `model_catalog/models.yaml` + `generation/backends/{fal,vibecomfy,codex}.py`.
