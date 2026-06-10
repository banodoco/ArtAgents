# S1 — Waist + timeline proof (the go/no-go)

**Context:** RFC + MIGRATION-PLAN. Runs on the POST-RESTRUCTURE tree (contracts is a true leaf; foundation/_shared exist). **Profile:** directed / full / depth medium.

## Outcome
The rendering path composes by **artifact type**, not by name. One vertical slice proves M×N→M+N end to end. Green oracle here validates the type-waist thesis.

## Scope (IN)
1. **Carrier.** Add `artifact_type: str | None = None` to `Port`/`Output` in the contracts leaf (post-RESTRUCTURE location of `contracts/schema.py`). Parse it in the two parsers (executor + orchestrator schema). Optional → every existing manifest loads unchanged.
2. **Registry.** `ArtifactTypeRegistry`, pack-extensible via `pack.extensions["artifact_types"]` (mirror the existing `ElementKindRegistry`). Seed the ~13 types from MIGRATION-PLAN §2 (canonicalize `video/clip`↔`clip/visual`). Declared-but-unregistered = validation error; unknown *runtime* values stay opaque.
3. **Annotate the timeline path only.** `consumes`/`produces` artifact types on the 12 element manifests (per MIGRATION-PLAN §3); give `ElementDefinition` real `inputs`/`outputs`; annotate the `render` executor I/O.
4. **Rewire the timeline validator.** Replace enumerate-and-membership (`timeline/validators/timeline.py` `_effect_ids` path) with resolve id → capability → kernel type-check `clip/visual` → validate params. **Preserve open-string opaque fallback (Reigh).**

## Anti-scope (OUT)
No registry collapse (S4), no theme/scoped-config (S3), no element restructure/purge (S4), no non-timeline annotation (S2).

## Done / GATE (parity oracle)
New type-resolution path accepts/rejects the **identical** set of timelines as the old `_effect_ids` path across the corpus. All tests green. New tests: registry resolution + pack extension; element I/O present; open-string fallback preserved.
