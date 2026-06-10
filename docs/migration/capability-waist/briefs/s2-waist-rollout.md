# S2 — Waist rollout (mechanical replication)

**Context:** RFC + MIGRATION-PLAN + the S1 pattern. **Profile:** solo / full / low. Depends on S1.

## Outcome
Every remaining name-wired composition seam is type-checked. No consumer enumerates a producer set to validate a reference.

## Scope (IN)
1. **Annotate the rest.** `artifact_type` on all remaining executor/orchestrator/model I/O where the semantic type is known (generation `prompt→image`/video, foley `clip→audio`, transcribe `audio→transcript`, upscale, …). Every declared type resolves in the S1 registry.
2. **Orchestrator child refs.** `child_executors`/`child_orchestrators` ID lists → type-validated references (kernel checks I/O type-compat at the wiring point). Imperative `run.py` orchestration stays; only reference validation changes.
3. **Model `param_map` → adapters.** Move per-(mode,backend) wire-name translation out of `models.yaml` into the backend adapters; the manifest declares canonical `params` only.
4. **`fal.py` model-name hardcodes → adapter hints** (flux-schnell guidance, ideogram safety).

## Anti-scope (OUT)
No collapse (S4), no theme work (S3), no element restructure/purge (S4).

## Done / GATE (objective; no human sign-off)
Per-seam parity: each rewired validation/translation gives the identical result as before across the corpus. All tests green; suffix-mapping prefers `artifact_type`. **Reigh protection is the automated round-trip parity gate** (from S0) staying green — no human Reigh sign-off.
